from __future__ import annotations

import pytest
from pydantic import ValidationError

from casa_phase_ref.config import PhaseRefConfig
from casa_phase_ref.errors import ValidationReportError
from casa_phase_ref.validation import validate_static_config

_BASE = {
    "vis": "obs.ms",
    "fluxcal": "3C286",
    "bandcal": "3C286",
    "phasecal": "J1234+5678",
    "target": "TARGET",
    "refant": "ea10",
}


def _cfg(**overrides: object) -> PhaseRefConfig:
    return PhaseRefConfig.model_validate({**_BASE, **overrides})


def test_validate_warns_for_missing_vis(tmp_path):
    cfg = _cfg(vis="nonexistent_file.ms")
    warnings = validate_static_config(cfg)
    assert any("does not exist" in w for w in warnings)


def test_validate_no_warnings_for_existing_vis(tmp_path):
    ms = tmp_path / "real.ms"
    ms.mkdir()
    cfg = _cfg(vis=str(ms))
    warnings = validate_static_config(cfg)
    assert not any("does not exist" in w for w in warnings)


def test_validate_warns_for_vlbi_profile():
    cfg = _cfg(observatory={"profile": "vlbi"})
    warnings = validate_static_config(cfg)
    assert any("VLBI" in w for w in warnings)


def test_validate_raises_when_selfcal_enabled():
    cfg = _cfg(selfcal={"enabled": True, "rounds": []})
    with pytest.raises(ValidationReportError, match="selfcal is not yet implemented"):
        validate_static_config(cfg)


def test_validate_raises_when_target_interp_too_short():
    # delay=True, bandpass=True → 4 tables; provide only 3
    cfg = _cfg(calibration={"apply": {"target_interp": ["nearest", "nearest", "linear"]}})
    with pytest.raises(ValidationReportError, match="target_interp"):
        validate_static_config(cfg)


def test_validate_raises_when_target_interp_too_long():
    # delay=True, bandpass=True → 4 tables; provide 5
    cfg = _cfg(
        calibration={
            "apply": {"target_interp": ["nearest", "nearest", "linear", "linear", "linear"]}
        }
    )
    with pytest.raises(ValidationReportError, match="target_interp"):
        validate_static_config(cfg)


def test_validate_target_interp_adjusts_for_disabled_delay():
    # delay=False, bandpass=True → 3 tables; provide 3
    cfg = _cfg(
        calibration={
            "delay": {"enabled": False},
            "apply": {"target_interp": ["nearest", "linear", "linear"]},
        }
    )
    # Should not raise
    warnings = validate_static_config(cfg)
    assert isinstance(warnings, list)


def test_validate_target_interp_adjusts_for_both_disabled():
    # delay=False, bandpass=False → 2 tables; provide 2
    cfg = _cfg(
        calibration={
            "delay": {"enabled": False},
            "bandpass": {"enabled": False},
            "apply": {"target_interp": ["linear", "linear"]},
        }
    )
    warnings = validate_static_config(cfg)
    assert isinstance(warnings, list)
