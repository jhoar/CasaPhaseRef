from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ObservatoryProfile, PhaseRefConfig
from .errors import ValidationReportError


def validate_static_config(cfg: PhaseRefConfig) -> list[str]:
    warnings: list[str] = []
    if cfg.observatory.profile == ObservatoryProfile.VLBI:
        warnings.append(
            "VLBI profile selected. Fringe fitting is available when fringe_fitting.enabled=true; add EOP/ionosphere/a-priori telescope calibration as needed for your observatory workflow."
        )
    if cfg.selfcal.enabled:
        raise ValidationReportError(
            "selfcal is not yet implemented. Set selfcal.enabled=false."
        )
    expected_tables = (
        2 + int(cfg.calibration.delay.enabled) + int(cfg.calibration.bandpass.enabled)
    )
    if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled:
        expected_tables += int(cfg.fringe_fitting.global_fit is not None)
        expected_tables += int(
            cfg.fringe_fitting.phase_reference is not None and cfg.fringe_fitting.apply_to_target
        )
    actual = len(cfg.calibration.apply.target_interp)
    if actual != expected_tables:
        raise ValidationReportError(
            f"calibration.apply.target_interp has {actual} entries but {expected_tables} "
            f"gaintables are configured "
            f"(delay={cfg.calibration.delay.enabled}, bandpass={cfg.calibration.bandpass.enabled}). "
            f"Update target_interp to have exactly {expected_tables} entries."
        )
    if not Path(cfg.vis).exists():
        warnings.append(f"Measurement Set path does not exist at validation time: {cfg.vis}")
    return warnings


def inspect_measurement_set(
    cfg: PhaseRefConfig,
    casa: dict[str, Any],
    report_path: Path,
) -> dict[str, Any]:
    """Run listobs as the practical runtime inspection hook.

    CASA listobs produces a text report. Parsing every telescope-specific detail is deliberately
    left for future work; this function centralizes where stronger MS validation can be added.
    """
    casa["listobs"](vis=cfg.vis, listfile=str(report_path), overwrite=True)
    return {
        "listobs_report": str(report_path),
        "checked_fields": [cfg.fluxcal, cfg.bandcal, cfg.phasecal, cfg.target],
        "checked_refant": cfg.refant,
        "checked_spw": cfg.spw,
    }
