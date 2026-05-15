from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

from .casa_runtime import load_casa_tasks
from .config import load_config
from .errors import CasaPhaseRefError
from .pipeline import run_pipeline
from .run_context import create_run_paths
from .validation import inspect_measurement_set, validate_static_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="casa-phase-ref",
        description="Run a CASA phase-referencing calibration and imaging pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate configuration without CASA tasks.")
    validate.add_argument("config")

    inspect = subparsers.add_parser("inspect", help="Run CASA listobs inspection.")
    inspect.add_argument("config")

    run = subparsers.add_parser("run", help="Execute the calibration and imaging pipeline.")
    run.add_argument("config")

    clean = subparsers.add_parser("clean-products", help="Remove generated run directory products.")
    clean.add_argument("config")
    clean.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete; otherwise print target only.",
    )

    return parser


def cmd_validate(config_path: str) -> int:
    cfg = load_config(config_path)
    warnings = validate_static_config(cfg)
    print("Configuration is valid.")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    print(cfg.model_dump_json(indent=2))
    return 0


def cmd_inspect(config_path: str) -> int:
    cfg = load_config(config_path)
    casa = load_casa_tasks()
    paths = create_run_paths(cfg)
    result = inspect_measurement_set(cfg, casa, paths.reports / "listobs.txt")
    print("Inspection complete.")
    print(f"listobs report: {result['listobs_report']}")
    return 0


def cmd_run(config_path: str) -> int:
    cfg = load_config(config_path)
    summary = run_pipeline(cfg)
    print("Pipeline complete.")
    print(f"Run directory: {cfg.execution.output_dir}")
    print(f"Steps: {len(summary['steps'])}")
    return 0


def cmd_clean(config_path: str, yes: bool) -> int:
    cfg = load_config(config_path)
    root = Path(cfg.execution.output_dir)
    if not root.exists():
        print(f"Nothing to clean: {root}")
        return 0
    if not yes:
        print(f"Would remove: {root}")
        print("Re-run with --yes to delete.")
        return 0
    shutil.rmtree(root)
    print(f"Removed: {root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return cmd_validate(args.config)
        elif args.command == "inspect":
            return cmd_inspect(args.config)
        elif args.command == "run":
            return cmd_run(args.config)
        else:  # clean-products — argparse enforces no other value
            return cmd_clean(args.config, args.yes)
    except CasaPhaseRefError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print(f"ERROR: Invalid configuration:\n{exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
