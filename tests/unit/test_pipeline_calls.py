from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from casa_phase_ref.config import (
    FringeFitSolveConfig,
    ManualFlagRule,
    StopAfter,
    load_config,
)
from casa_phase_ref.errors import ValidationReportError
from casa_phase_ref.pipeline import compose_gaintable_chain, run_pipeline


@pytest.fixture
def fake_casa_tasks():
    task_names = [
        "applycal",
        "bandpass",
        "flagdata",
        "flagmanager",
        "fluxscale",
        "fringefit",
        "gaincal",
        "gencal",
        "listobs",
        "setjy",
        "split",
        "tclean",
    ]
    return {name: MagicMock(name=name) for name in task_names}


def _cfg(example_config_path, tmp_path):
    cfg = load_config(example_config_path)
    cfg.execution.output_dir = str(tmp_path / "run")
    cfg.execution.resume = True
    return cfg


def test_pipeline_runs_expected_core_tasks(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    for name in [
        "listobs",
        "flagmanager",
        "flagdata",
        "setjy",
        "gaincal",
        "bandpass",
        "fluxscale",
        "applycal",
        "split",
        "tclean",
    ]:
        assert fake_casa_tasks[name].called, name


def test_pipeline_creates_run_summary(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert Path(cfg.execution.output_dir, "reports", "run-summary.json").exists()
    assert Path(cfg.execution.output_dir, "config.resolved.yaml").exists()


def test_pipeline_sets_flux_calibrator(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    fake_casa_tasks["setjy"].assert_called_once_with(
        vis="my_observation.ms",
        field="3C286",
        standard="Perley-Butler 2017",
        usescratch=True,
    )


def test_pipeline_solves_delay_on_bandpass_calibrator(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    delay_call = fake_casa_tasks["gaincal"].call_args_list[0]
    assert delay_call.kwargs["caltable"].endswith("calibration/cal.K")
    assert delay_call.kwargs["field"] == "3C286"
    assert delay_call.kwargs["gaintype"] == "K"
    assert delay_call.kwargs["solint"] == "inf"
    assert delay_call.kwargs["refant"] == "ea10"


def test_pipeline_applies_phasecal_to_target(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    target_apply_call = next(
        call
        for call in fake_casa_tasks["applycal"].call_args_list
        if call.kwargs.get("field") == "TARGET"
    )
    assert target_apply_call.kwargs["field"] == "TARGET"
    assert target_apply_call.kwargs["gainfield"][-2:] == ["J1234+5678", "J1234+5678"]
    assert target_apply_call.kwargs["interp"] == ["nearest", "nearest", "linear", "linear"]


def test_pipeline_splits_corrected_target_data(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    kwargs = fake_casa_tasks["split"].call_args.kwargs
    assert kwargs["field"] == "TARGET"
    assert kwargs["datacolumn"] == "corrected"
    assert kwargs["outputvis"].endswith("products/TARGET_calibrated.ms")


def test_pipeline_runs_tclean_with_configured_imaging(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    kwargs = fake_casa_tasks["tclean"].call_args.kwargs
    assert kwargs["imagename"].endswith("products/target_phase_ref")
    assert kwargs["deconvolver"] == "mtmfs"
    assert kwargs["nterms"] == 2
    assert kwargs["imsize"] == [2048, 2048]
    assert kwargs["interactive"] is False


def test_pipeline_stops_after_bandpass(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.execution.stop_after = StopAfter.BANDPASS
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert summary["steps"][-1]["name"] == "bandpass"
    assert not fake_casa_tasks["fluxscale"].called
    assert not fake_casa_tasks["tclean"].called


def test_pipeline_rflag_can_be_disabled(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.flagging.rflag = False
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    modes = [call.kwargs.get("mode") for call in fake_casa_tasks["flagdata"].call_args_list]
    assert "rflag" not in modes


def test_pipeline_stops_after_bandpass_skips_later_steps(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.execution.stop_after = StopAfter.BANDPASS
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert summary["steps"][-1]["name"] == "bandpass"
    assert not fake_casa_tasks["fluxscale"].called
    assert not fake_casa_tasks["applycal"].called
    assert not fake_casa_tasks["tclean"].called


def test_pipeline_flag_backup_disabled_skips_all_saves(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.safety.require_flag_backup = False
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    save_calls = [
        c for c in fake_casa_tasks["flagmanager"].call_args_list if c.kwargs.get("mode") == "save"
    ]
    assert len(save_calls) == 0


def test_pipeline_manual_flag_passes_empty_spw(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.flagging.manual = [ManualFlagRule(spw="", antenna="ea01")]
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    manual_calls = [
        c
        for c in fake_casa_tasks["flagdata"].call_args_list
        if c.kwargs.get("mode") == "manual" and "antenna" in c.kwargs
    ]
    assert len(manual_calls) == 1
    assert manual_calls[0].kwargs["spw"] == ""


def test_pipeline_raises_on_selfcal_enabled(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.selfcal.enabled = True
    with pytest.raises(ValidationReportError, match="selfcal is not yet implemented"):
        run_pipeline(cfg, casa_tasks=fake_casa_tasks)


def test_pipeline_raises_on_target_interp_mismatch(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.calibration.apply.target_interp = ["nearest"]  # wrong length for 4 gaintables
    with pytest.raises(ValidationReportError, match="target_interp"):
        run_pipeline(cfg, casa_tasks=fake_casa_tasks)


def test_pipeline_inspection_key_present_on_success(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert "inspection" in summary
    assert summary["inspection"] is not None


def test_pipeline_warnings_emitted_for_missing_vis(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    # example config points to my_observation.ms which does not exist
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert any("does not exist" in w for w in summary["warnings"])


def test_pipeline_vlbi_runs_fringefit_and_applies_phase_reference(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    from casa_phase_ref.config import ObservatoryProfile

    cfg.observatory.profile = ObservatoryProfile.VLBI
    cfg.fringe_fitting.enabled = True
    cfg.fringe_fitting.global_fit = FringeFitSolveConfig(
        field="3C286",
        caltable="cal.fringe.global",
        solint="inf",
        refant="ea10",
        minsnr=5.0,
    )
    cfg.fringe_fitting.phase_reference = FringeFitSolveConfig(
        field="J1234+5678",
        caltable="cal.fringe.phasecal",
        solint="scan",
        refant="ea10",
        minsnr=4.0,
    )
    cfg.calibration.apply.target_interp = [
        "nearest", "nearest", "linear", "linear", "nearest", "linear"
    ]
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert fake_casa_tasks["fringefit"].call_count == 2
    target_apply_call = next(
        call
        for call in fake_casa_tasks["applycal"].call_args_list
        if call.kwargs.get("field") == "TARGET"
    )
    assert target_apply_call.kwargs["gainfield"][-4:] == ["3C286", "J1234+5678", "J1234+5678", "J1234+5678"]


def test_pipeline_non_vlbi_has_no_fringe_step(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert all(step["name"] != "fringe_fit" for step in summary["steps"])


def test_pipeline_vlbi_apply_to_target_false_skips_fringe_tables_on_target(
    example_config_path, fake_casa_tasks, tmp_path
):
    from casa_phase_ref.config import ObservatoryProfile

    cfg = _cfg(example_config_path, tmp_path)
    cfg.observatory.profile = ObservatoryProfile.VLBI
    cfg.fringe_fitting.enabled = True
    cfg.fringe_fitting.apply_to_target = False
    cfg.fringe_fitting.global_fit = FringeFitSolveConfig(
        field="3C286",
        caltable="cal.fringe.global",
        solint="inf",
        refant="ea10",
        minsnr=5.0,
    )
    cfg.fringe_fitting.phase_reference = FringeFitSolveConfig(
        field="J1234+5678",
        caltable="cal.fringe.phasecal",
        solint="scan",
        refant="ea10",
        minsnr=4.0,
    )
    cfg.calibration.apply.target_interp = ["nearest", "nearest", "linear", "linear"]
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    target_apply_call = next(
        call
        for call in fake_casa_tasks["applycal"].call_args_list
        if call.kwargs.get("field") == "TARGET"
    )
    gaintables = target_apply_call.kwargs["gaintable"]
    assert all("cal.fringe.global" not in table for table in gaintables)
    assert all("cal.fringe.phasecal" not in table for table in gaintables)


def test_pipeline_can_stop_after_fringe_fit(example_config_path, fake_casa_tasks, tmp_path):
    from casa_phase_ref.config import ObservatoryProfile

    cfg = _cfg(example_config_path, tmp_path)
    cfg.observatory.profile = ObservatoryProfile.VLBI
    cfg.execution.stop_after = StopAfter.FRINGE_FIT
    cfg.fringe_fitting.enabled = True
    cfg.fringe_fitting.global_fit = FringeFitSolveConfig(
        field="3C286",
        caltable="cal.fringe.global",
        solint="inf",
        refant="ea10",
    )
    cfg.calibration.apply.target_interp = ["nearest", "nearest", "linear", "linear", "linear"]
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert summary["steps"][-1]["name"] == "fringe_fit"
    assert not fake_casa_tasks["fluxscale"].called


def test_pipeline_vlbi_eop_disabled_emits_warning_and_skips_gencal(
    example_config_path, fake_casa_tasks, tmp_path
):
    from casa_phase_ref.config import ObservatoryProfile

    cfg = _cfg(example_config_path, tmp_path)
    cfg.observatory.profile = ObservatoryProfile.VLBI
    cfg.vlbi.eop.enabled = False
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert fake_casa_tasks["gencal"].call_count == 0


def test_pipeline_vlbi_eop_enabled_runs_before_delay(
    example_config_path, fake_casa_tasks, tmp_path
):
    from casa_phase_ref.config import ObservatoryProfile

    cfg = _cfg(example_config_path, tmp_path)
    cfg.observatory.profile = ObservatoryProfile.VLBI
    cfg.vlbi.eop.enabled = True
    cfg.vlbi.eop.source = "casa_auto"
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert fake_casa_tasks["gencal"].called
    first_delay_index = next(i for i, c in enumerate(fake_casa_tasks["gaincal"].call_args_list) if c.kwargs.get("gaintype") == "K")
    assert first_delay_index == 0


def test_pipeline_tec_enabled_creates_deterministic_table_name(
    example_config_path, fake_casa_tasks, tmp_path
):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.calibration.ionosphere.enabled = True
    cfg.calibration.apply.target_interp = ["nearest", "nearest", "nearest", "linear", "linear"]
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    tec_call = next(
        c for c in fake_casa_tasks["gencal"].call_args_list if c.kwargs.get("caltype") == "tecim"
    )
    assert tec_call.kwargs["caltable"].endswith("calibration/my_observation.tec.G")


def test_pipeline_tec_uses_ionex_file_when_configured(
    example_config_path, fake_casa_tasks, tmp_path
):
    ionex_file = tmp_path / "codg0010.24i"
    ionex_file.write_text("IONEX")
    cfg = _cfg(example_config_path, tmp_path)
    cfg.calibration.ionosphere.enabled = True
    cfg.calibration.ionosphere.tec_source = "ionex_file"
    cfg.calibration.ionosphere.ionex_file = str(ionex_file)
    cfg.calibration.apply.target_interp = ["nearest", "nearest", "nearest", "linear", "linear"]
    run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    tec_call = next(
        c for c in fake_casa_tasks["gencal"].call_args_list if c.kwargs.get("caltype") == "tecim"
    )
    assert tec_call.kwargs["infile"] == str(ionex_file)


def test_pipeline_pulsecal_auto_added_to_applycal_and_qa(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.calibration.pulsecal.enabled = True
    cfg.calibration.pulsecal.apply_to = "both"
    cfg.calibration.apply.target_interp = ["nearest", "nearest", "nearest", "linear", "linear"]
    summary = run_pipeline(cfg, casa_tasks=fake_casa_tasks)
    assert fake_casa_tasks["gencal"].called
    target_apply_call = next(call for call in fake_casa_tasks["applycal"].call_args_list if call.kwargs.get("field") == "TARGET")
    assert any("cal.pulsecal.G" in table for table in target_apply_call.kwargs["gaintable"])
    assert "pulsecal" in summary["qa"]


def test_pipeline_pulsecal_manual_table_requires_existing_path(example_config_path, fake_casa_tasks, tmp_path):
    cfg = _cfg(example_config_path, tmp_path)
    cfg.calibration.pulsecal.enabled = True
    cfg.calibration.pulsecal.mode = "manual_table"
    cfg.calibration.pulsecal.table = str(tmp_path / "missing.tbl")
    cfg.calibration.apply.target_interp = ["nearest", "nearest", "nearest", "linear", "linear"]
    with pytest.raises(Exception, match="Pipeline step failed: pulsecal"):

        run_pipeline(cfg, casa_tasks=fake_casa_tasks)


def test_compose_gaintable_chain_deterministic_order(example_config_path):
    cfg = load_config(example_config_path)
    cfg.calibration.ionosphere.enabled = True
    cfg.calibration.pulsecal.enabled = True
    chain = compose_gaintable_chain(
        cfg,
        tec_table="tec.G",
        eop_table="EOP",
        pulsecal_table="pulse.G",
        delay_table="K",
        bandpass_table="B",
        fringe_global_table="fringe.global",
        fringe_phase_table="fringe.phase",
        phase_gain_table="Gp",
        amplitude_gain_table="Gflux",
        include_pulsecal_for_calibrators=True,
        include_fringe_for_target=True,
    )
    assert chain == ["tec.G", "pulse.G", "K", "B", "Gp", "Gflux"]


def test_compose_gaintable_chain_vlbi_with_eop_and_fringe(example_config_path):
    from casa_phase_ref.config import ObservatoryProfile

    cfg = load_config(example_config_path)
    cfg.observatory.profile = ObservatoryProfile.VLBI
    cfg.vlbi.eop.enabled = True
    cfg.calibration.ionosphere.enabled = True
    cfg.fringe_fitting.enabled = True
    cfg.fringe_fitting.global_fit = FringeFitSolveConfig(field="3C286", caltable="fg", solint="inf", refant="ea10")
    cfg.fringe_fitting.phase_reference = FringeFitSolveConfig(field="J1234+5678", caltable="fp", solint="scan", refant="ea10")
    chain = compose_gaintable_chain(
        cfg,
        tec_table="tec.G",
        eop_table="EOP",
        delay_table="K",
        bandpass_table="B",
        fringe_global_table="fringe.global",
        fringe_phase_table="fringe.phase",
        phase_gain_table="Gp",
        include_fringe_for_target=True,
    )
    assert chain == ["EOP", "tec.G", "K", "B", "fringe.global", "fringe.phase", "Gp"]


def test_compose_gaintable_chain_pulsecal_target_toggle(example_config_path):
    cfg = load_config(example_config_path)
    cfg.calibration.pulsecal.enabled = True
    chain = compose_gaintable_chain(
        cfg,
        delay_table="K",
        bandpass_table="B",
        pulsecal_table="pulse.G",
        phase_gain_table="Gp",
        include_pulsecal_for_target=True,
        include_pulsecal_for_calibrators=False,
    )
    assert chain == ["K", "B", "pulse.G", "Gp"]
