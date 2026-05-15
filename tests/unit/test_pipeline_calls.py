from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from casa_phase_ref.config import StopAfter, load_config
from casa_phase_ref.pipeline import run_pipeline


@pytest.fixture
def fake_casa_tasks():
    task_names = [
        "applycal",
        "bandpass",
        "flagdata",
        "flagmanager",
        "fluxscale",
        "gaincal",
        "imhead",
        "imstat",
        "listobs",
        "plotms",
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
