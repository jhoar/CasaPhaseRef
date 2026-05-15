from __future__ import annotations

import pytest

from casa_phase_ref.casa_runtime import load_casa_tasks
from casa_phase_ref.errors import CasaUnavailableError


@pytest.mark.integration
@pytest.mark.casa
def test_casa_runtime_can_load_tasks():
    try:
        tasks = load_casa_tasks()
    except CasaUnavailableError as exc:
        pytest.skip(str(exc))
    expected_tasks = {
        "applycal",
        "bandpass",
        "flagdata",
        "flagmanager",
        "fluxscale",
        "gaincal",
        "listobs",
        "setjy",
        "split",
        "tclean",
    }
    assert expected_tasks.issubset(tasks.keys())
