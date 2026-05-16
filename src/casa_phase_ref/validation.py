from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ObservatoryProfile, PhaseRefConfig
from .errors import ValidationReportError


def validate_static_config(cfg: PhaseRefConfig) -> list[str]:
    warnings: list[str] = []
    if cfg.observatory.profile == ObservatoryProfile.VLBI:
        if cfg.calibration.ionosphere.enabled:
            warnings.append(
                "VLBI profile selected. Ionospheric TEC correction is enabled via calibration.ionosphere and will run before fringe/delay solves."
            )
        else:
            warnings.append(
                "VLBI profile selected, but calibration.ionosphere.enabled=false. Consider enabling TEC correction for long-baseline low-frequency observations."
            )
        if cfg.vlbi.eop.enabled:
            warnings.append(
                "VLBI profile selected. EOP correction is enabled via vlbi.eop and will run before delay/fringe solves."
            )
        else:
            warnings.append(
                "VLBI profile selected, but vlbi.eop.enabled=false. Enable EOP correction unless your observatory workflow already applied EOP externally."
            )
    if (
        cfg.observatory.profile == ObservatoryProfile.VLBI
        and cfg.fringe_fitting.enabled
        and cfg.fringe_fitting.global_fit is None
        and cfg.fringe_fitting.phase_reference is None
    ):
        raise ValidationReportError(
            "fringe_fitting.enabled=true requires at least one solve: fringe_fitting.global or fringe_fitting.phase_reference."
        )
    if cfg.selfcal.enabled:
        raise ValidationReportError(
            "selfcal is not yet implemented. Set selfcal.enabled=false."
        )
    expected_tables = (
        2
        + int(cfg.calibration.ionosphere.enabled)
        + int(cfg.calibration.delay.enabled)
        + int(cfg.calibration.bandpass.enabled)
    )
    if (
        cfg.observatory.profile == ObservatoryProfile.VLBI
        and cfg.fringe_fitting.enabled
        and cfg.fringe_fitting.apply_to_target
    ):
        expected_tables += int(cfg.fringe_fitting.global_fit is not None)
        expected_tables += int(cfg.fringe_fitting.phase_reference is not None)
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
    if cfg.calibration.ionosphere.enabled and cfg.calibration.ionosphere.tec_source == "ionex_file":
        ionex_file = cfg.calibration.ionosphere.ionex_file
        if not ionex_file:
            raise ValidationReportError(
                "calibration.ionosphere.ionex_file must be set when ionosphere.enabled=true and tec_source=ionex_file."
            )
        if not Path(ionex_file).exists():
            raise ValidationReportError(
                f"IONEX file not found: {ionex_file}. Provide a valid path or switch tec_source to auto."
            )
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
