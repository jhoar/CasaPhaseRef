from __future__ import annotations

import os
from pathlib import Path

import pytest

from casa_phase_ref.casa_runtime import load_casa_tasks
from casa_phase_ref.config import PhaseRefConfig
from casa_phase_ref.errors import CasaUnavailableError
from casa_phase_ref.pipeline import run_pipeline


@pytest.mark.integration
@pytest.mark.casa
def test_real_measurement_set_smoke(tmp_path):
    ms_path = os.environ.get("CASA_TEST_MS")
    if not ms_path:
        pytest.skip("Set CASA_TEST_MS to run real Measurement Set smoke test.")
    if not Path(ms_path).exists():
        pytest.skip(f"CASA_TEST_MS does not exist: {ms_path}")
    try:
        load_casa_tasks()
    except CasaUnavailableError as exc:
        pytest.skip(str(exc))

    cfg = PhaseRefConfig.model_validate(
        {
            "vis": ms_path,
            "fluxcal": os.environ.get("CASA_TEST_FLUXCAL", "3C286"),
            "bandcal": os.environ.get("CASA_TEST_BANDCAL", "3C286"),
            "phasecal": os.environ.get("CASA_TEST_PHASECAL", "J1234+5678"),
            "target": os.environ.get("CASA_TEST_TARGET", "TARGET"),
            "refant": os.environ.get("CASA_TEST_REFANT", "ea10"),
            "execution": {"output_dir": str(tmp_path / "run"), "resume": True},
            "flagging": {"rflag": False},
            "imaging": {
                "imagename": "smoke_image",
                "imsize": [256, 256],
                "cell": "1arcsec",
                "niter": 10,
                "threshold": "1mJy",
                "interactive": False,
            },
        }
    )
    summary = run_pipeline(cfg)
    assert summary["errors"] == []
