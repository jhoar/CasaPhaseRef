from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ObservatoryProfile, PhaseRefConfig


def validate_static_config(cfg: PhaseRefConfig) -> list[str]:
    warnings: list[str] = []
    if cfg.observatory.profile == ObservatoryProfile.VLBI:
        warnings.append(
            "VLBI profile selected. This generic pipeline does not yet implement full VLBI "
            "fringe-fitting/EOP/ionosphere-specific calibration. Use this profile for validation "
            "only unless you extend the pipeline path."
        )
    if cfg.selfcal.enabled and not cfg.selfcal.rounds:
        warnings.append("selfcal.enabled=true but no selfcal rounds are configured.")
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
