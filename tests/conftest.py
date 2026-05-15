from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def example_config_path(fixture_dir: Path) -> Path:
    return fixture_dir / "example-phase-ref.yaml"
