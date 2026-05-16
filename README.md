# CASA Phase Referencing Pipeline

Config-driven CASA phase-referencing calibration and imaging pipeline.

This is a package skeleton intended for conventional phase-referenced continuum interferometry. It keeps CASA imports runtime-only so normal unit tests, linting, and packaging can run without a CASA installation.

## Commands

```bash
casa-phase-ref validate configs/example-phase-ref.yaml
casa-phase-ref inspect configs/example-phase-ref.yaml
casa-phase-ref run configs/example-phase-ref.yaml
casa-phase-ref clean-products configs/example-phase-ref.yaml --yes
```

## Install for development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run unit tests

```bash
pytest -m "not integration"
```

## Run CASA integration tests

```bash
pytest -m "integration and casa"
```

## Run inside CASA

```bash
casa --nogui -c scripts/run-in-casa.py run configs/example-phase-ref.yaml
```

## Build

```bash
python -m build
```

## Output structure

Each run writes to `execution.output_dir`:

```text
runs/example_TARGET/
├── config.resolved.yaml
├── logs/pipeline.log
├── calibration/
├── products/
└── reports/
    ├── listobs.txt
    └── run-summary.json
```

## VLBI fringe fitting mode

The `vlbi` observatory profile now supports an explicit CASA `fringefit` stage through the
`fringe_fitting` config block. This keeps connected-array phase referencing and VLBI-style
fringe solving as separate, explicit workflows.

Minimal example:

```yaml
observatory:
  profile: "vlbi"

fringe_fitting:
  enabled: true
  global:
    field: "FRINGE_FINDER"
    caltable: "cal.fringe.global"
    solint: "inf"
    refant: "BR"
    minsnr: 5.0
  phase_reference:
    field: "PHASE_CAL"
    caltable: "cal.fringe.phasecal"
    solint: "scan"
    refant: "BR"
    minsnr: 4.0
  apply_to_target: true
```
