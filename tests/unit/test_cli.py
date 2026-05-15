from __future__ import annotations

from casa_phase_ref.cli import main
from casa_phase_ref.errors import CasaUnavailableError


def test_cli_validate_returns_zero(example_config_path, capsys):
    result = main(["validate", str(example_config_path)])
    captured = capsys.readouterr()
    assert result == 0
    assert "Configuration is valid." in captured.out
    assert "my_observation.ms" in captured.out


def test_cli_requires_subcommand(capsys):
    result = None
    try:
        main([])
    except SystemExit as exc:
        result = exc.code
    assert result != 0


def test_clean_products_dry_run(example_config_path, capsys):
    result = main(["clean-products", str(example_config_path)])
    captured = capsys.readouterr()
    assert result == 0
    assert "Nothing to clean" in captured.out or "Would remove" in captured.out


def test_cli_validate_catches_pydantic_validation_error(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("vis: obs.ms\n")  # missing required fields
    result = main(["validate", str(bad)])
    assert result == 2
    assert "ERROR" in capsys.readouterr().err


def test_cli_inspect_catches_casa_unavailable(example_config_path, monkeypatch, capsys):
    def _raise() -> None:
        raise CasaUnavailableError("CASA not available in test")

    monkeypatch.setattr("casa_phase_ref.cli.load_casa_tasks", _raise)
    result = main(["inspect", str(example_config_path)])
    assert result == 2
    assert "ERROR" in capsys.readouterr().err


def test_cli_run_catches_casa_unavailable(example_config_path, monkeypatch, capsys):
    def _raise() -> None:
        raise CasaUnavailableError("CASA not available in test")

    monkeypatch.setattr("casa_phase_ref.pipeline.load_casa_tasks", _raise)
    result = main(["run", str(example_config_path)])
    assert result == 2
    assert "ERROR" in capsys.readouterr().err
