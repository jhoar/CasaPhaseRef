from __future__ import annotations

import pytest
from pydantic import ValidationError

from casa_phase_ref.config import ObservatoryProfile, PhaseRefConfig, StopAfter, load_config


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
