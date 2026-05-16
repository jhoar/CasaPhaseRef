from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from casa_phase_ref.config import (
    ObservatoryProfile,
    PhaseRefConfig,
    StopAfter,
    dump_resolved_config,
    load_config,
)


def test_load_example_config(example_config_path):
    cfg = load_config(example_config_path)
    assert cfg.vis == "my_observation.ms"
    assert cfg.fluxcal == "3C286"
    assert cfg.bandcal == "3C286"
    assert cfg.phasecal == "J1234+5678"
    assert cfg.target == "TARGET"
    assert cfg.refant == "ea10"
    assert cfg.observatory.profile == ObservatoryProfile.GENERIC
    assert cfg.imaging.imsize == [2048, 2048]


def test_config_defaults_are_applied():
    cfg = PhaseRefConfig.model_validate(
        {
            "vis": "obs.ms",
            "fluxcal": "3C286",
            "bandcal": "3C286",
            "phasecal": "J1234+5678",
            "target": "TARGET",
            "refant": "ea10",
        }
    )
    assert cfg.spw == ""
    assert cfg.flagging.rflag is True
    assert cfg.execution.resume is True
    assert cfg.execution.stop_after is None
    assert cfg.calibration.phase_gain.solint == "int"
    assert cfg.vlbi.eop.enabled is False
    assert cfg.vlbi.eop.source == "casa_auto"


def test_stop_after_enum_parses():
    cfg = PhaseRefConfig.model_validate(
        {
            "vis": "obs.ms",
            "fluxcal": "3C286",
            "bandcal": "3C286",
            "phasecal": "J1234+5678",
            "target": "TARGET",
            "refant": "ea10",
            "execution": {"stop_after": "bandpass"},
        }
    )
    assert cfg.execution.stop_after == StopAfter.BANDPASS


def test_missing_required_field_fails():
    with pytest.raises(ValidationError):
        PhaseRefConfig.model_validate(
            {
                "vis": "obs.ms",
                "fluxcal": "3C286",
                "bandcal": "3C286",
                "target": "TARGET",
                "refant": "ea10",
            }
        )


def test_invalid_imsize_type_fails():
    with pytest.raises(ValidationError):
        PhaseRefConfig.model_validate(
            {
                "vis": "obs.ms",
                "fluxcal": "3C286",
                "bandcal": "3C286",
                "phasecal": "J1234+5678",
                "target": "TARGET",
                "refant": "ea10",
                "imaging": {"imsize": [0, 2048]},
            }
        )


def test_unknown_profile_fails():
    with pytest.raises(ValidationError):
        PhaseRefConfig.model_validate(
            {
                "vis": "obs.ms",
                "fluxcal": "3C286",
                "bandcal": "3C286",
                "phasecal": "J1234+5678",
                "target": "TARGET",
                "refant": "ea10",
                "observatory": {"profile": "not-a-profile"},
            }
        )


def test_dump_resolved_config_uses_global_alias(tmp_path):
    cfg = PhaseRefConfig.model_validate(
        {
            "vis": "obs.ms",
            "fluxcal": "3C286",
            "bandcal": "3C286",
            "phasecal": "J1234+5678",
            "target": "TARGET",
            "refant": "ea10",
            "fringe_fitting": {
                "enabled": True,
                "global": {
                    "field": "FRINGE",
                    "caltable": "cal.fringe.global",
                    "solint": "inf",
                    "refant": "ea10",
                },
            },
        }
    )
    out = tmp_path / "resolved.yaml"
    dump_resolved_config(cfg, out)
    data = yaml.safe_load(Path(out).read_text())
    assert "global" in data["fringe_fitting"]
    assert "global_fit" not in data["fringe_fitting"]


def test_vlbi_eop_file_source_parses():
    cfg = PhaseRefConfig.model_validate(
        {
            "vis": "obs.ms",
            "fluxcal": "3C286",
            "bandcal": "3C286",
            "phasecal": "J1234+5678",
            "target": "TARGET",
            "refant": "ea10",
            "observatory": {"profile": "vlbi"},
            "vlbi": {"eop": {"enabled": True, "source": "file", "file": "iers.eop"}},
        }
    )
    assert cfg.vlbi.eop.enabled is True
    assert cfg.vlbi.eop.source == "file"
    assert cfg.vlbi.eop.file == "iers.eop"


def test_ionosphere_config_parses():
    cfg = PhaseRefConfig.model_validate(
        {
            "vis": "obs.ms",
            "fluxcal": "3C286",
            "bandcal": "3C286",
            "phasecal": "J1234+5678",
            "target": "TARGET",
            "refant": "ea10",
            "calibration": {
                "ionosphere": {
                    "enabled": True,
                    "tec_source": "ionex_file",
                    "ionex_file": "codg0010.24i",
                    "interp": "nearest",
                }
            },
        }
    )
    assert cfg.calibration.ionosphere.enabled is True
    assert cfg.calibration.ionosphere.tec_source == "ionex_file"
    assert cfg.calibration.ionosphere.ionex_file == "codg0010.24i"
    assert cfg.calibration.ionosphere.interp == "nearest"
