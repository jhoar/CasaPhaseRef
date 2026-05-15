from __future__ import annotations

import json
import logging
import platform
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .casa_runtime import casa_version
from .config import PhaseRefConfig, dump_resolved_config
from .errors import ProductExistsError


@dataclass(frozen=True)
class RunPaths:
    root: Path
    logs: Path
    calibration: Path
    products: Path
    reports: Path
    plots: Path


def create_run_paths(cfg: PhaseRefConfig) -> RunPaths:
    root = Path(cfg.execution.output_dir)
    paths = RunPaths(
        root=root,
        logs=root / "logs",
        calibration=root / "calibration",
        products=root / "products",
        reports=root / "reports",
        plots=root / "reports" / "plots",
    )
    if root.exists() and not cfg.execution.overwrite and not cfg.execution.resume:
        raise ProductExistsError(f"Run directory already exists: {root}")
    for path in paths.__dict__.values():
        path.mkdir(parents=True, exist_ok=True)
    resolved_config_path = root / "config.resolved.yaml"
    if not cfg.execution.resume or not resolved_config_path.exists():
        dump_resolved_config(cfg, resolved_config_path)
    return paths


def setup_logging(paths: RunPaths) -> logging.Logger:
    logger = logging.getLogger("casa_phase_ref")
    logger.setLevel(logging.INFO)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        h.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(paths.logs / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def ensure_absent_or_overwritable(path: Path, overwrite: bool, resume: bool) -> None:
    if not path.exists():
        return
    if resume:
        return
    if not overwrite:
        raise ProductExistsError(f"Product already exists and overwrite=false: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def base_summary(cfg: PhaseRefConfig) -> dict[str, Any]:
    return {
        "package_version": __version__,
        "casa_version": casa_version(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "vis": cfg.vis,
            "fluxcal": cfg.fluxcal,
            "bandcal": cfg.bandcal,
            "phasecal": cfg.phasecal,
            "target": cfg.target,
            "refant": cfg.refant,
            "spw": cfg.spw,
        },
        "observatory": cfg.observatory.model_dump(mode="json"),
        "execution": cfg.execution.model_dump(mode="json"),
        "steps": [],
        "warnings": [],
        "errors": [],
        "inspection": None,
    }
