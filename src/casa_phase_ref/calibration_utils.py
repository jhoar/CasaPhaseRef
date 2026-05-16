from __future__ import annotations

import logging
from pathlib import Path

from .casa_runtime import load_casa_tasks
from .config import PhaseRefConfig


class EopConfigurationError(ValueError):
    """Raised when VLBI EOP correction settings are invalid."""


class TecConfigurationError(ValueError):
    """Raised when ionospheric TEC correction settings are invalid."""


def _validate_eop_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise EopConfigurationError(f"EOP file not found: {path}")
    if path.suffix.lower() not in {".txt", ".dat", ".eop"}:
        raise EopConfigurationError(
            f"Unsupported EOP file format for {path}. Expected one of: .txt, .dat, .eop"
        )
    if path.stat().st_size == 0:
        raise EopConfigurationError(f"EOP file is empty: {path}")


def _validate_ionex_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise TecConfigurationError(f"IONEX file not found: {path}")
    if path.suffix.lower() not in {".ionex", ".inx", ".gz"} and not path.name.lower().endswith("i"):
        raise TecConfigurationError(
            f"Unsupported IONEX file format for {path}. Expected IONEX-style extension (e.g. *.YYi, .ionex, .inx, .gz)"
        )
    if path.stat().st_size == 0:
        raise TecConfigurationError(f"IONEX file is empty: {path}")


def apply_eop_correction(
    ms_path: str,
    config: PhaseRefConfig,
    casa_tasks: dict[str, object] | None = None,
    logger: logging.Logger | None = None,
    caltable_path: str | None = None,
) -> str:
    """Generate and apply an EOP calibration table for VLBI datasets."""
    casa = casa_tasks if casa_tasks is not None else load_casa_tasks()
    log = logger or logging.getLogger(__name__)

    eop_cfg = config.vlbi.eop
    eop_table = caltable_path or str(Path(ms_path).with_suffix(".eop.cal"))

    gencal_kwargs: dict[str, object] = {
        "vis": ms_path,
        "caltable": eop_table,
        "caltype": "eop",
    }
    if eop_cfg.source == "file":
        if not eop_cfg.file:
            raise EopConfigurationError("vlbi.eop.file is required when vlbi.eop.source=file")
        eop_file = Path(eop_cfg.file)
        _validate_eop_file(eop_file)
        gencal_kwargs["infile"] = str(eop_file)

    log.info("Starting VLBI EOP correction (source=%s)", eop_cfg.source)
    casa["gencal"](**gencal_kwargs)
    casa["applycal"](
        vis=ms_path,
        field="",
        gaintable=[eop_table],
        interp=["nearest"],
        calwt=False,
    )
    log.info("Completed VLBI EOP correction")
    return eop_table


def apply_tec_correction(
    ms_path: str,
    config: PhaseRefConfig,
    casa_tasks: dict[str, object] | None = None,
    logger: logging.Logger | None = None,
    caltable_path: str | None = None,
) -> str:
    """Generate and apply an ionospheric TEC calibration table."""
    casa = casa_tasks if casa_tasks is not None else load_casa_tasks()
    log = logger or logging.getLogger(__name__)

    tec_cfg = config.calibration.ionosphere
    tec_table = caltable_path or str(Path(ms_path).with_suffix(".tec.G"))
    gencal_kwargs: dict[str, object] = {
        "vis": ms_path,
        "caltable": tec_table,
        "caltype": "tecim",
    }

    if tec_cfg.tec_source == "ionex_file":
        if not tec_cfg.ionex_file:
            raise TecConfigurationError(
                "calibration.ionosphere.ionex_file is required when tec_source=ionex_file"
            )
        ionex_path = Path(tec_cfg.ionex_file)
        _validate_ionex_file(ionex_path)
        gencal_kwargs["infile"] = str(ionex_path)

    log.info("Starting ionospheric TEC correction (source=%s)", tec_cfg.tec_source)
    casa["gencal"](**gencal_kwargs)
    casa["applycal"](
        vis=ms_path,
        field="",
        gaintable=[tec_table],
        interp=[tec_cfg.interp],
        calwt=False,
    )
    log.info("Completed ionospheric TEC correction")
    return tec_table
