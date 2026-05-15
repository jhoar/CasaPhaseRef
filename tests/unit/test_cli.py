from __future__ import annotations

from casa_phase_ref.cli import main


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
