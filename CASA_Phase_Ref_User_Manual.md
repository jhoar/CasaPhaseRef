# CASA Phase Referencing Pipeline User Manual

Version: `casa-phase-ref` 0.2.0  
Applies to: the repository/package generated in this project

---

## 1. Purpose and scope

`casa-phase-ref` is a configuration-driven Python package for running a CASA phase-referencing calibration and imaging workflow for radio interferometric data stored as a CASA Measurement Set.

The package is intended to make a common phase-referenced continuum calibration sequence reproducible and scriptable. Instead of editing a large CASA script for every observation, you describe the observation and calibration choices in a YAML configuration file, then run the pipeline through a command-line interface.

The current implementation is best understood as a robust generic connected-interferometer pipeline skeleton. It supports VLA-like, ALMA-like, generic, and VLBI profile workflows at the configuration level. The VLBI path now includes optional fringe fitting (`fringe_fitting`) for global and/or phase-reference solves, with optional transfer to the target. It is still not a full observatory-certified VLBI pipeline: EOP correction, ionospheric TEC correction, pulse-cal handling, and additional observatory-specific amplitude/delay-rate practices remain user responsibilities.

---

## 2. What the pipeline does

The main `run` command executes these steps:

1. Creates a structured run directory.
2. Writes a resolved configuration file containing all defaults.
3. Runs `listobs` inspection.
4. Saves an initial flag backup, if enabled.
5. Performs initial flagging:
   - autocorrelation flagging
   - shadow flagging
   - zero clipping
   - optional `rflag`
   - optional manual flag rules
6. Sets the flux calibrator model with `setjy`.
7. Solves instrumental delay with `gaincal(..., gaintype="K")`, if enabled.
8. Solves a short pre-bandpass phase solution.
9. Solves bandpass calibration, if enabled.
10. Solves phase gains for flux and phase calibrators.
11. Solves amplitude gains for flux and phase calibrators.
12. Transfers the absolute flux scale to the phase calibrator with `fluxscale`.
13. Applies calibration to:
    - the flux calibrator using flux calibrator gain solutions
    - the phase calibrator using phase calibrator gain solutions
    - the target using phase calibrator gain solutions
14. Splits the corrected target data into a calibrated target Measurement Set.
15. Images the target with `tclean`.
16. Writes a machine-readable run summary.

The essential phase-referencing operation happens during target `applycal`: the target receives delay/bandpass solutions from the delay/bandpass calibrator and time-interpolated gain solutions from the phase calibrator.

---

## 3. Installation

### 3.1 Development installation

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3.2 Installing the built wheel

If you already have the built wheel:

```bash
python -m pip install dist/casa_phase_ref-0.2.0-py3-none-any.whl
```

### 3.3 CASA availability

The package deliberately does not require CASA at install time. This allows normal Python tests and configuration validation to run without a CASA installation.

Commands that execute CASA tasks require a CASA-capable Python environment where `casatasks` is importable. If CASA tasks are not available, `inspect` and `run` will fail or skip in integration tests.

Typical execution patterns are:

```bash
casa-phase-ref validate configs/example-phase-ref.yaml
```

for normal Python-only validation, and:

```bash
casa-phase-ref run configs/example-phase-ref.yaml
```

inside a CASA-capable environment.

If using the full CASA application launcher, the repository also includes:

```bash
casa --nogui -c scripts/run-in-casa.py run configs/example-phase-ref.yaml
```

Depending on your CASA installation, you may need to ensure the package is installed into the Python environment used by CASA.

---

## 4. Command-line interface

The command-line tool is named:

```bash
casa-phase-ref
```

It has four subcommands:

```bash
casa-phase-ref validate CONFIG.yaml
casa-phase-ref inspect CONFIG.yaml
casa-phase-ref run CONFIG.yaml
casa-phase-ref clean-products CONFIG.yaml [--yes]
```

### 4.1 `validate`

Validates the YAML configuration using the package schema. It does not run CASA tasks.

```bash
casa-phase-ref validate configs/example-phase-ref.yaml
```

This command:

- parses the YAML file
- applies default values
- checks required fields
- prints the resolved configuration as JSON
- emits static warnings

Example warnings include:

- the Measurement Set path does not exist at validation time
- `vlbi` profile is selected; fringe fitting is available, but full observatory-specific VLBI calibration still requires additional steps outside this generic pipeline
- `selfcal.enabled=true` but no self-calibration rounds are configured

Use this command before running CASA.

### 4.2 `inspect`

Runs CASA `listobs` and writes an observation report into the configured run directory.

```bash
casa-phase-ref inspect configs/example-phase-ref.yaml
```

This command requires CASA tasks to be available.

It writes:

```text
<execution.output_dir>/reports/listobs.txt
```

The current implementation centralizes runtime Measurement Set inspection here, but it does not yet fully parse the `listobs` report to confirm that all configured fields, antennas, and SPWs are present. That is a natural extension point.

### 4.3 `run`

Runs the full calibration and imaging workflow.

```bash
casa-phase-ref run configs/example-phase-ref.yaml
```

This command requires CASA tasks to be available.

It writes products into the directory specified by:

```yaml
execution:
  output_dir: "runs/example_TARGET"
```

### 4.4 `clean-products`

Removes the configured run directory.

Dry-run mode:

```bash
casa-phase-ref clean-products configs/example-phase-ref.yaml
```

Actual deletion:

```bash
casa-phase-ref clean-products configs/example-phase-ref.yaml --yes
```

This command removes the entire directory named by `execution.output_dir`. Use with care.



### 4.5 `run` with VLBI fringe fitting (complete example)

A complete fringe-fitting configuration is provided at:

```text
configs/example-vlbi-fringe-fit.yaml
```

Validate first:

```bash
casa-phase-ref validate configs/example-vlbi-fringe-fit.yaml
```

Then run inside a CASA-capable environment:

```bash
casa-phase-ref run configs/example-vlbi-fringe-fit.yaml
```

If you are using the CASA launcher:

```bash
casa --nogui -c scripts/run-in-casa.py run configs/example-vlbi-fringe-fit.yaml
```

This example enables both fringe-fit solve blocks:

- `fringe_fitting.global` for a global/fringe-finder solve table
- `fringe_fitting.phase_reference` for a phase calibrator solve table
- `fringe_fitting.apply_to_target: true` so those fringe tables are included during target `applycal`

Important: `calibration.apply.target_interp` must have one entry per active gaintable. In this example there are six tables (delay, bandpass, phase gain, amplitude gain, global fringe, phase-reference fringe), so `target_interp` has six entries.

---

## 5. Run directory structure

For a configuration with:

```yaml
execution:
  output_dir: "runs/example_TARGET"
```

the pipeline creates:

```text
runs/example_TARGET/
├── config.resolved.yaml
├── logs/
│   └── pipeline.log
├── calibration/
│   ├── cal.K
│   ├── cal.BPpre.G
│   ├── cal.B
│   ├── cal.Gp
│   ├── cal.Gap
│   └── cal.fluxscale
├── products/
│   ├── TARGET_calibrated.ms
│   └── target_phase_ref.*
└── reports/
    ├── listobs.txt
    ├── run-summary.json
    └── plots/
```

The `plots/` directory is created for future diagnostic plot generation. The current implementation does not yet generate plots.

### 5.1 `config.resolved.yaml`

This file contains the fully resolved configuration after defaults have been applied. It is useful for provenance and reproducibility.

### 5.2 `logs/pipeline.log`

This file contains the Python pipeline log: run start, step names, run directory, and completion/failure messages.

### 5.3 `reports/run-summary.json`

This file records:

- package version
- CASA version, if detectable
- Python version
- platform
- UTC timestamp
- input field mapping
- observatory configuration
- execution configuration
- step statuses
- warnings
- errors
- inspection metadata

---

## 6. Configuration file overview

A configuration file is a YAML document. At minimum, it must define:

```yaml
vis: "my_observation.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"
```

A complete configuration contains these top-level sections:

```yaml
vis: "my_observation.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"
spw: ""
flux_standard: "Perley-Butler 2017"
calwt: false

observatory: {}
execution: {}
safety: {}
flagging: {}
calibration: {}
imaging: {}
selfcal: {}
```

All sections except the six required string fields have defaults.

---

## 7. Complete reference configuration

This is equivalent to the bundled `configs/example-phase-ref.yaml`.

```yaml
vis: "my_observation.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"
spw: ""
flux_standard: "Perley-Butler 2017"
calwt: false

observatory:
  profile: "generic"
  apply_antpos: false
  apply_switched_power: false

execution:
  output_dir: "runs/example_TARGET"
  overwrite: false
  resume: true
  stop_after: null

safety:
  require_flag_backup: true
  write_corrected_data: true
  allow_in_place_ms_modification: true

flagging:
  autocorr: true
  shadow: true
  clip_zeros: true
  rflag: true
  manual: []

calibration:
  delay:
    enabled: true
    field: null
    solint: "inf"
    combine: "scan"
  bandpass:
    enabled: true
    field: null
    solint: "inf"
    combine: "scan"
  phase_gain:
    solint: "int"
    calmode: "p"
  amplitude_gain:
    solint: "inf"
    calmode: "ap"
  apply:
    target_interp: ["nearest", "nearest", "linear", "linear"]

imaging:
  imagename: "target_phase_ref"
  cell: "0.2arcsec"
  imsize: [2048, 2048]
  weighting: "briggs"
  robust: 0.5
  niter: 10000
  threshold: "30uJy"
  specmode: "mfs"
  deconvolver: "mtmfs"
  nterms: 2
  interactive: false

selfcal:
  enabled: false
  rounds: []
```

---

## 8. Top-level configuration options

### 8.1 `vis`

Required string.

Path to the input CASA Measurement Set.

Example:

```yaml
vis: "/data/project/uid___A002_X123.ms"
```

At `validate` time, the package warns if the path does not exist, but validation can still succeed. This is useful when validating on a different machine from the CASA execution environment.

### 8.2 `fluxcal`

Required string.

Name or field identifier for the primary flux calibrator.

Example:

```yaml
fluxcal: "3C286"
```

Used by:

- `setjy`
- gain calibration field selection
- `fluxscale` reference source
- flux calibrator `applycal`

### 8.3 `bandcal`

Required string.

Name or field identifier for the bandpass calibrator.

Example:

```yaml
bandcal: "3C286"
```

Often the same source as `fluxcal`, but it can be different.

Used by default for:

- delay calibration
- pre-bandpass phase solve
- bandpass calibration
- delay/bandpass gainfield applied to the target

Can be overridden in:

```yaml
calibration:
  delay:
    field: "..."
  bandpass:
    field: "..."
```

### 8.4 `phasecal`

Required string.

Name or field identifier for the phase-reference calibrator.

Example:

```yaml
phasecal: "J1234+5678"
```

Used for:

- phase and amplitude gain solutions
- target `applycal` gain transfer
- `fluxscale` transfer source

The target receives phase and amplitude gain solutions from this field.

### 8.5 `target`

Required string.

Name or field identifier for the science target.

Example:

```yaml
target: "NGC_1234"
```

Used for:

- target `applycal`
- target `split`
- output Measurement Set naming

The split output will be:

```text
<execution.output_dir>/products/<target>_calibrated.ms
```

### 8.6 `refant`

Required string.

Reference antenna used by CASA calibration tasks.

Example:

```yaml
refant: "ea10"
```

Choose a stable, central antenna with good data coverage.

### 8.7 `spw`

Optional string. Default: empty string, meaning all spectral windows.

Example:

```yaml
spw: "0,1,2,3"
```

Passed to calibration tasks such as `gaincal` and `bandpass`. The split and imaging stages currently use all SPWs from the corrected target Measurement Set.

### 8.8 `flux_standard`

Optional string. Default:

```yaml
flux_standard: "Perley-Butler 2017"
```

Passed to CASA `setjy` as the flux density standard.

### 8.9 `calwt`

Optional boolean. Default: `false`.

Passed to `applycal`.

Example:

```yaml
calwt: false
```

For many continuum imaging workflows, keeping `calwt: false` is a conservative default. Change only if you understand the desired calibration weight behavior for your dataset.

---

## 9. `observatory` section

The `observatory` section describes the intended observatory profile.

```yaml
observatory:
  profile: "generic"
  apply_antpos: false
  apply_switched_power: false
```

### 9.1 `observatory.profile`

Optional string. Default: `generic`.

Allowed values:

```text
generic
vla
alma
vlbi
```

Current behavior:

- `generic`, `vla`, and `alma` all use the same generic pipeline path.
- `vlbi` emits a warning to indicate you are using a generic framework: fringe fitting is supported, but full VLBI a priori and observatory-certified processing are still your responsibility.

Example:

```yaml
observatory:
  profile: "vla"
```

### 9.2 `observatory.apply_antpos`

Optional boolean. Default: `false`.

Reserved for future support of antenna position corrections. The current pipeline does not yet act on this flag.

### 9.3 `observatory.apply_switched_power`

Optional boolean. Default: `false`.

Reserved for future observatory-specific switched-power or gain-curve handling. The current pipeline does not yet act on this flag.

---

## 10. `execution` section

The `execution` section controls output location and run behavior.

```yaml
execution:
  output_dir: "runs/example_TARGET"
  overwrite: false
  resume: true
  stop_after: null
```

### 10.1 `execution.output_dir`

Optional string. Default:

```yaml
output_dir: "runs/default"
```

Directory where all logs, calibration products, split products, images, and reports are written.

Example:

```yaml
execution:
  output_dir: "runs/2026-05-15_NGC1234_Cband"
```

### 10.2 `execution.overwrite`

Optional boolean. Default: `false`.

Controls whether existing products may be removed and regenerated.

The current product handling works together with `resume`:

- if a product does not exist, the pipeline proceeds
- if a product exists and `resume: true`, the pipeline allows it to remain
- if a product exists, `resume: false`, and `overwrite: false`, the pipeline fails
- if a product exists, `resume: false`, and `overwrite: true`, the product is removed before running

Example for a clean rerun:

```yaml
execution:
  overwrite: true
  resume: false
```

### 10.3 `execution.resume`

Optional boolean. Default: `true`.

Allows an existing run directory and existing products to remain. This is useful during iterative CASA reductions where you may stop after one stage, inspect outputs, and continue.

Important limitation: the current implementation allows existing products when `resume: true`, but it does not yet skip already completed steps by reading prior state. It still calls the CASA tasks. Treat `resume` primarily as an overwrite-safety policy rather than a full workflow checkpoint system.

### 10.4 `execution.stop_after`

Optional string or `null`. Default: `null`.

Stops the pipeline after the named step and writes `run-summary.json`.

Allowed values:

```text
listobs
flagging
setjy
delay
bandpass
gains
fluxscale
applycal
split
image
```

Example:

```yaml
execution:
  stop_after: "bandpass"
```

Useful for staged reduction:

1. run to `listobs`
2. inspect fields and antennas
3. run to `bandpass`
4. inspect bandpass tables
5. run to `applycal`
6. inspect calibrated data
7. run to `image`

---

## 11. `safety` section

The `safety` section contains flags intended to make potentially destructive operations explicit.

```yaml
safety:
  require_flag_backup: true
  write_corrected_data: true
  allow_in_place_ms_modification: true
```

### 11.1 `safety.require_flag_backup`

Optional boolean. Default: `true`.

If enabled, the pipeline saves a flag backup named `original` before initial flagging:

```python
flagmanager(vis=vis, mode="save", versionname="original")
```

It also saves `after_initial_flagging` and `after_applycal` flag versions during the run.

### 11.2 `safety.write_corrected_data`

Optional boolean. Default: `true`.

Reserved for future enforcement of whether the pipeline may write calibrated data to `CORRECTED_DATA`. The current pipeline always applies calibration with CASA `applycal`, which writes corrected data.

### 11.3 `safety.allow_in_place_ms_modification`

Optional boolean. Default: `true`.

Reserved for future enforcement of whether the input Measurement Set may be modified in place. The current pipeline performs in-place flagging and `applycal` on the configured `vis`.

Practical recommendation: work on a copy of the raw Measurement Set unless you are confident the original can be modified.

---

## 12. `flagging` section

The `flagging` section controls initial automatic and manual flagging.

```yaml
flagging:
  autocorr: true
  shadow: true
  clip_zeros: true
  rflag: true
  manual: []
```

### 12.1 `flagging.autocorr`

Optional boolean. Default: `true`.

If enabled:

```python
flagdata(vis=vis, mode="manual", autocorr=True)
```

### 12.2 `flagging.shadow`

Optional boolean. Default: `true`.

If enabled:

```python
flagdata(vis=vis, mode="shadow")
```

### 12.3 `flagging.clip_zeros`

Optional boolean. Default: `true`.

If enabled:

```python
flagdata(vis=vis, mode="clip", clipzeros=True)
```

### 12.4 `flagging.rflag`

Optional boolean. Default: `true`.

If enabled, runs CASA `rflag` with the current hardcoded thresholds:

```python
flagdata(
  vis=vis,
  mode="rflag",
  field="",
  datacolumn="data",
  timedevscale=4.0,
  freqdevscale=4.0,
  action="apply",
)
```

For delicate data, set this to `false` and perform more controlled flagging:

```yaml
flagging:
  rflag: false
```

### 12.5 `flagging.manual`

Optional list. Default: empty list.

Each manual rule may contain:

```yaml
field: optional string
antenna: optional string
spw: optional string
timerange: optional string
reason: optional string
```

The `reason` field is kept in the configuration for documentation, but it is not passed to CASA.

Example:

```yaml
flagging:
  manual:
    - field: "3C286"
      antenna: "ea05"
      timerange: "2026/05/15/10:00:00~2026/05/15/10:10:00"
      reason: "bad antenna during flux calibrator scan"
    - spw: "2:120~140"
      reason: "narrow-band RFI"
```

The pipeline converts each rule into a CASA call similar to:

```python
flagdata(vis=vis, mode="manual", field="3C286", antenna="ea05", timerange="...")
```

---

## 13. `calibration` section

The `calibration` section controls the CASA calibration sequence.

```yaml
calibration:
  delay:
    enabled: true
    field: null
    solint: "inf"
    combine: "scan"
  bandpass:
    enabled: true
    field: null
    solint: "inf"
    combine: "scan"
  phase_gain:
    solint: "int"
    calmode: "p"
  amplitude_gain:
    solint: "inf"
    calmode: "ap"
  apply:
    target_interp: ["nearest", "nearest", "linear", "linear"]
```

### 13.1 `calibration.delay.enabled`

Optional boolean. Default: `true`.

If enabled, solves a delay calibration table:

```text
<output_dir>/calibration/cal.K
```

using:

```python
gaincal(..., gaintype="K")
```

If disabled, the delay table is omitted from later gain table lists.

Example:

```yaml
calibration:
  delay:
    enabled: false
```

### 13.2 `calibration.delay.field`

Optional string or `null`. Default: `null`.

If `null`, the pipeline uses `bandcal`.

Example:

```yaml
calibration:
  delay:
    field: "J0319+4130"
```

### 13.3 `calibration.delay.solint`

Optional string. Default: `inf`.

Passed to delay `gaincal` as `solint`.

Example:

```yaml
calibration:
  delay:
    solint: "inf"
```

### 13.4 `calibration.delay.combine`

Optional string. Default: `scan`.

Passed to delay `gaincal` as `combine`.

Example:

```yaml
calibration:
  delay:
    combine: "scan"
```

### 13.5 `calibration.bandpass.enabled`

Optional boolean. Default: `true`.

If enabled, solves a bandpass calibration table:

```text
<output_dir>/calibration/cal.B
```

If disabled, the bandpass table is omitted from later gain table lists. The current implementation still solves the pre-bandpass phase table `cal.BPpre.G` before the conditional bandpass solve.

### 13.6 `calibration.bandpass.field`

Optional string or `null`. Default: `null`.

If `null`, the pipeline uses `bandcal`.

Example:

```yaml
calibration:
  bandpass:
    field: "3C84"
```

### 13.7 `calibration.bandpass.solint`

Optional string. Default: `inf`.

Passed to `bandpass` as `solint`.

### 13.8 `calibration.bandpass.combine`

Optional string. Default: `scan`.

Passed to `bandpass` as `combine`.

### 13.9 `calibration.phase_gain.solint`

Optional string. Default: `int`.

Passed to phase `gaincal`.

The phase gain solve uses:

```python
field=",".join([fluxcal, phasecal])
calmode="p"
```

unless `calmode` is changed.

Common values:

```yaml
phase_gain:
  solint: "int"
```

or:

```yaml
phase_gain:
  solint: "30s"
```

### 13.10 `calibration.phase_gain.calmode`

Optional string. Default: `p`.

Allowed values:

```text
p
a
ap
```

For normal phase referencing, keep this as:

```yaml
calmode: "p"
```

### 13.11 `calibration.amplitude_gain.solint`

Optional string. Default: `inf`.

Passed to amplitude gain `gaincal`.

### 13.12 `calibration.amplitude_gain.calmode`

Optional string. Default: `ap`.

Allowed values:

```text
p
a
ap
```

For normal amplitude and phase gain calibration, keep:

```yaml
calmode: "ap"
```

### 13.13 `calibration.apply.target_interp`

Optional list of strings. Default:

```yaml
target_interp: ["nearest", "nearest", "linear", "linear"]
```

This list is passed to the target `applycal` call as `interp`.

Its length must match the number of gain tables used by the target `applycal` call.

With both delay and bandpass enabled, gain tables are:

```text
cal.K
cal.B
cal.Gp
cal.fluxscale
```

so four interpolation entries are expected.

If delay is disabled but bandpass is enabled, gain tables are:

```text
cal.B
cal.Gp
cal.fluxscale
```

so you should use three entries, for example:

```yaml
calibration:
  delay:
    enabled: false
  apply:
    target_interp: ["nearest", "linear", "linear"]
```

If both delay and bandpass are disabled, gain tables are:

```text
cal.Gp
cal.fluxscale
```

so use two entries:

```yaml
calibration:
  delay:
    enabled: false
  bandpass:
    enabled: false
  apply:
    target_interp: ["linear", "linear"]
```

The current schema does not validate this length automatically, so mismatches may fail at CASA runtime.

---

## 14. `imaging` section

The `imaging` section controls the final `tclean` call.

```yaml
imaging:
  imagename: "target_phase_ref"
  cell: "0.2arcsec"
  imsize: [2048, 2048]
  weighting: "briggs"
  robust: 0.5
  niter: 10000
  threshold: "30uJy"
  specmode: "mfs"
  deconvolver: "mtmfs"
  nterms: 2
  interactive: false
```

### 14.1 `imaging.imagename`

Optional string. Default: `target_phase_ref`.

Base name for the CASA image products. The pipeline prefixes this with the run products directory.

Example:

```yaml
imaging:
  imagename: "NGC1234_Cband_phase_ref"
```

Output products are written under:

```text
<execution.output_dir>/products/
```

### 14.2 `imaging.cell`

Optional string. Default: `0.2arcsec`.

Cell size passed to `tclean`.

Example:

```yaml
cell: "0.05arcsec"
```

### 14.3 `imaging.imsize`

Optional list of two positive integers. Default: `[2048, 2048]`.

Image dimensions in pixels.

Example:

```yaml
imsize: [4096, 4096]
```

The schema validates that this contains exactly two positive integers.

### 14.4 `imaging.weighting`

Optional string. Default: `briggs`.

Passed to `tclean` as `weighting`.

Examples:

```yaml
weighting: "natural"
```

```yaml
weighting: "briggs"
```

### 14.5 `imaging.robust`

Optional float. Default: `0.5`.

Passed to `tclean` as `robust`. Relevant for Briggs weighting.

Example:

```yaml
robust: 0.0
```

### 14.6 `imaging.niter`

Optional integer. Default: `10000`.

Maximum number of clean iterations.

Example:

```yaml
niter: 5000
```

### 14.7 `imaging.threshold`

Optional string. Default: `30uJy`.

Cleaning threshold passed to `tclean`.

Example:

```yaml
threshold: "0.1mJy"
```

### 14.8 `imaging.specmode`

Optional string. Default: `mfs`.

Passed to `tclean` as `specmode`.

The current pipeline is designed primarily for continuum MFS imaging.

### 14.9 `imaging.deconvolver`

Optional string. Default: `mtmfs`.

Passed to `tclean` as `deconvolver`.

Examples:

```yaml
deconvolver: "hogbom"
```

```yaml
deconvolver: "mtmfs"
```

### 14.10 `imaging.nterms`

Optional integer. Default: `2`.

Passed to `tclean` as `nterms`.

Relevant for `mtmfs` imaging.

### 14.11 `imaging.interactive`

Optional boolean. Default: `false`.

Passed to `tclean` as `interactive`.

For batch processing:

```yaml
interactive: false
```

For manual clean mask interaction:

```yaml
interactive: true
```

---

## 15. `selfcal` section

The `selfcal` section is currently configuration-only. The current pipeline defines the schema but does not execute self-calibration rounds.

```yaml
selfcal:
  enabled: false
  rounds: []
```

If you set:

```yaml
selfcal:
  enabled: true
  rounds: []
```

validation emits a warning:

```text
selfcal.enabled=true but no selfcal rounds are configured.
```

A future self-calibration configuration could look like:

```yaml
selfcal:
  enabled: true
  rounds:
    - name: "p_inf"
      calmode: "p"
      solint: "inf"
      minsnr: 3.0
      niter: 5000
      threshold: "50uJy"
    - name: "p_60s"
      calmode: "p"
      solint: "60s"
      minsnr: 3.0
      niter: 10000
      threshold: "30uJy"
```

Allowed fields for each round:

| Field | Type | Default | Meaning |
|---|---:|---:|---|
| `name` | string | required | Round name |
| `calmode` | `p`, `a`, or `ap` | `p` | Gaincal mode |
| `solint` | string | `inf` | Solution interval |
| `minsnr` | float | `3.0` | Minimum solution S/N |
| `niter` | integer | `5000` | Imaging iterations for that round |
| `threshold` | string | `50uJy` | Imaging threshold for that round |

---

## 16. Typical use case walkthroughs

### Walkthrough 1: Validate a new observation config

Create `my-target.yaml`:

```yaml
vis: "/data/observations/my_target.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "MY_TARGET"
refant: "ea10"

execution:
  output_dir: "runs/my_target_first_pass"

imaging:
  imagename: "my_target_first_pass"
  cell: "0.2arcsec"
  imsize: [2048, 2048]
  threshold: "50uJy"
```

Run:

```bash
casa-phase-ref validate my-target.yaml
```

Review the resolved configuration and warnings. A missing Measurement Set warning is acceptable if you are validating on a different machine.

---

### Walkthrough 2: Inspect the Measurement Set

After moving to a CASA-capable environment:

```bash
casa-phase-ref inspect my-target.yaml
```

Open:

```text
runs/my_target_first_pass/reports/listobs.txt
```

Check:

- field names or field IDs
- antenna names
- scan sequence
- spectral window IDs
- observation times

If field names differ from the YAML file, update the configuration before running calibration.

---

### Walkthrough 3: Run only through bandpass calibration

This is useful when you want to inspect calibration tables before applying to the target.

```yaml
execution:
  output_dir: "runs/my_target_bandpass_check"
  stop_after: "bandpass"
```

Run:

```bash
casa-phase-ref run my-target.yaml
```

The pipeline stops after creating calibration products such as:

```text
runs/my_target_bandpass_check/calibration/cal.K
runs/my_target_bandpass_check/calibration/cal.BPpre.G
runs/my_target_bandpass_check/calibration/cal.B
```

You can then inspect them manually with CASA plotting tools.

---

### Walkthrough 4: Run full phase-referenced imaging

Use:

```yaml
execution:
  output_dir: "runs/my_target_full"
  stop_after: null
```

Run:

```bash
casa-phase-ref run my-target.yaml
```

Expected key products:

```text
runs/my_target_full/products/MY_TARGET_calibrated.ms
runs/my_target_full/products/my_target_first_pass.image.tt0
runs/my_target_full/reports/run-summary.json
runs/my_target_full/logs/pipeline.log
```

For `mtmfs` imaging, CASA image suffixes may include `.image.tt0`, `.image.tt1`, `.model.tt0`, `.residual.tt0`, and related products.

---

### Walkthrough 5: Use a separate bandpass calibrator

If the flux calibrator and bandpass calibrator are different:

```yaml
fluxcal: "3C286"
bandcal: "J0319+4130"
phasecal: "J1234+5678"
target: "MY_TARGET"
```

By default, delay and bandpass calibration both use `bandcal`.

To explicitly use a different field for delay:

```yaml
calibration:
  delay:
    field: "J0319+4130"
  bandpass:
    field: "J0319+4130"
```

---

### Walkthrough 6: Conservative flagging without `rflag`

For datasets where automatic RFI flagging may be too aggressive:

```yaml
flagging:
  autocorr: true
  shadow: true
  clip_zeros: true
  rflag: false
  manual:
    - antenna: "ea05"
      timerange: "2026/05/15/10:00:00~2026/05/15/10:05:00"
      reason: "known bad antenna interval"
```

Run to `flagging` first:

```yaml
execution:
  stop_after: "flagging"
```

Then inspect flagging manually before continuing.

---

### Walkthrough 7: Image quickly for a first-look check

For a fast first image, reduce image size and clean depth:

```yaml
execution:
  output_dir: "runs/my_target_quicklook"

imaging:
  imagename: "my_target_quicklook"
  imsize: [512, 512]
  cell: "0.5arcsec"
  niter: 1000
  threshold: "1mJy"
  interactive: false
```

Run:

```bash
casa-phase-ref run my-target-quicklook.yaml
```

This is not intended as a final science image, but it can reveal gross calibration or field-selection errors quickly.

---

### Walkthrough 8: Cleanly rerun from scratch

If a previous run produced products and you want to remove/recreate them automatically:

```yaml
execution:
  output_dir: "runs/my_target_full"
  overwrite: true
  resume: false
```

Run:

```bash
casa-phase-ref run my-target.yaml
```

This allows the pipeline to remove existing known products before regenerating them.

Alternatively, delete the entire run directory first:

```bash
casa-phase-ref clean-products my-target.yaml --yes
casa-phase-ref run my-target.yaml
```

---

### Walkthrough 9: Disable delay calibration

For a simple dataset where delay calibration is unnecessary:

```yaml
calibration:
  delay:
    enabled: false
  apply:
    target_interp: ["nearest", "linear", "linear"]
```

Because the delay table is removed from the target `applycal` gain table list, `target_interp` must also be shortened.

---

### Walkthrough 10: VLBI profile warning

You may write:

```yaml
observatory:
  profile: "vlbi"
```

Validation will succeed but emit a warning. The pipeline supports configurable fringe fitting in VLBI mode, but it is still not a full observatory-certified VLBI phase-referencing pipeline. Add observatory-required a priori and post-calibration steps before scientific use.

---

## 17. Example configurations

### 17.1 Minimal generic config

```yaml
vis: "obs.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"
```

### 17.2 Full generic continuum config

```yaml
vis: "/data/obs.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"
spw: "0,1,2,3"
flux_standard: "Perley-Butler 2017"
calwt: false

observatory:
  profile: "generic"

execution:
  output_dir: "runs/TARGET_full"
  overwrite: false
  resume: true
  stop_after: null

flagging:
  autocorr: true
  shadow: true
  clip_zeros: true
  rflag: true
  manual: []

calibration:
  delay:
    enabled: true
    solint: "inf"
    combine: "scan"
  bandpass:
    enabled: true
    solint: "inf"
    combine: "scan"
  phase_gain:
    solint: "int"
    calmode: "p"
  amplitude_gain:
    solint: "inf"
    calmode: "ap"
  apply:
    target_interp: ["nearest", "nearest", "linear", "linear"]

imaging:
  imagename: "TARGET_Cband"
  cell: "0.2arcsec"
  imsize: [2048, 2048]
  weighting: "briggs"
  robust: 0.5
  niter: 10000
  threshold: "30uJy"
  specmode: "mfs"
  deconvolver: "mtmfs"
  nterms: 2
  interactive: false
```

### 17.3 First-look config

```yaml
vis: "/data/obs.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"

execution:
  output_dir: "runs/TARGET_quicklook"

flagging:
  rflag: false

imaging:
  imagename: "TARGET_quicklook"
  imsize: [512, 512]
  cell: "0.5arcsec"
  niter: 1000
  threshold: "1mJy"
```

### 17.4 Staged calibration config

```yaml
vis: "/data/obs.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"

execution:
  output_dir: "runs/TARGET_stage_bandpass"
  stop_after: "bandpass"
```

### 17.5 Manual flagging config

```yaml
vis: "/data/obs.ms"
fluxcal: "3C286"
bandcal: "3C286"
phasecal: "J1234+5678"
target: "TARGET"
refant: "ea10"

flagging:
  autocorr: true
  shadow: true
  clip_zeros: true
  rflag: false
  manual:
    - antenna: "ea05"
      timerange: "2026/05/15/10:00:00~2026/05/15/10:10:00"
      reason: "bad antenna interval"
    - field: "TARGET"
      spw: "2:120~140"
      reason: "narrow-band RFI"
```

---

## 18. Step-by-step pipeline details

This section maps pipeline steps to CASA tasks and generated products.

### 18.1 `listobs`

CASA call:

```python
listobs(vis=cfg.vis, listfile="<run>/reports/listobs.txt", overwrite=True)
```

Summary step name:

```text
listobs
```

Stop point:

```yaml
execution:
  stop_after: "listobs"
```

### 18.2 `flagging`

Possible CASA calls:

```python
flagmanager(vis=vis, mode="save", versionname="original")
flagdata(vis=vis, mode="manual", autocorr=True)
flagdata(vis=vis, mode="shadow")
flagdata(vis=vis, mode="clip", clipzeros=True)
flagdata(vis=vis, mode="rflag", ...)
flagdata(vis=vis, mode="manual", ...manual rule...)
flagmanager(vis=vis, mode="save", versionname="after_initial_flagging")
```

Stop point:

```yaml
execution:
  stop_after: "flagging"
```

### 18.3 `setjy`

CASA call:

```python
setjy(vis=vis, field=fluxcal, standard=flux_standard, usescratch=True)
```

Stop point:

```yaml
execution:
  stop_after: "setjy"
```

### 18.4 `delay`

Generated product:

```text
<run>/calibration/cal.K
```

CASA call:

```python
gaincal(
  vis=vis,
  caltable="<run>/calibration/cal.K",
  field=delay_field,
  spw=spw,
  gaintype="K",
  solint=calibration.delay.solint,
  refant=refant,
  combine=calibration.delay.combine,
)
```

Stop point:

```yaml
execution:
  stop_after: "delay"
```

### 18.5 `bandpass`

Generated products:

```text
<run>/calibration/cal.BPpre.G
<run>/calibration/cal.B
```

CASA calls:

```python
gaincal(... caltable="cal.BPpre.G", calmode="p", solint="int" ...)
bandpass(... caltable="cal.B" ...)
```

Stop point:

```yaml
execution:
  stop_after: "bandpass"
```

### 18.6 `gains`

Generated products:

```text
<run>/calibration/cal.Gp
<run>/calibration/cal.Gap
```

CASA calls:

```python
gaincal(... caltable="cal.Gp", calmode="p" ...)
gaincal(... caltable="cal.Gap", calmode="ap" ...)
```

Stop point:

```yaml
execution:
  stop_after: "gains"
```

### 18.7 `fluxscale`

Generated product:

```text
<run>/calibration/cal.fluxscale
```

CASA call:

```python
fluxscale(
  vis=vis,
  caltable="cal.Gap",
  fluxtable="cal.fluxscale",
  reference=fluxcal,
  transfer=phasecal,
)
```

Stop point:

```yaml
execution:
  stop_after: "fluxscale"
```

### 18.8 `applycal`

CASA calls:

```python
applycal(... field=fluxcal ... gainfield=[..., fluxcal, fluxcal])
applycal(... field=phasecal ... gainfield=[..., phasecal, phasecal])
applycal(... field=target ... gainfield=[..., phasecal, phasecal])
```

The target call is the core phase-referencing transfer.

Stop point:

```yaml
execution:
  stop_after: "applycal"
```

### 18.9 `split`

Generated product:

```text
<run>/products/<target>_calibrated.ms
```

CASA call:

```python
split(
  vis=vis,
  outputvis="<run>/products/<target>_calibrated.ms",
  field=target,
  datacolumn="corrected",
  keepflags=False,
)
```

Stop point:

```yaml
execution:
  stop_after: "split"
```

### 18.10 `image`

Generated products:

```text
<run>/products/<imagename>.*
```

CASA call:

```python
tclean(
  vis="<run>/products/<target>_calibrated.ms",
  imagename="<run>/products/<imaging.imagename>",
  specmode=imaging.specmode,
  deconvolver=imaging.deconvolver,
  nterms=imaging.nterms,
  imsize=imaging.imsize,
  cell=imaging.cell,
  weighting=imaging.weighting,
  robust=imaging.robust,
  niter=imaging.niter,
  threshold=imaging.threshold,
  interactive=imaging.interactive,
  savemodel="modelcolumn",
)
```

Stop point:

```yaml
execution:
  stop_after: "image"
```

Since `image` is the final step, this is equivalent to a full run.

---

## 19. Testing and verification

### 19.1 Run normal tests

```bash
pytest -m "not integration"
```

These tests do not require CASA.

### 19.2 Run CASA import integration tests

```bash
pytest -m "integration and casa"
```

CASA-dependent tests skip automatically if CASA is unavailable.

### 19.3 Run a real Measurement Set smoke test

Set environment variables:

```bash
export CASA_TEST_MS=/path/to/test.ms
export CASA_TEST_FLUXCAL=3C286
export CASA_TEST_BANDCAL=3C286
export CASA_TEST_PHASECAL=J1234+5678
export CASA_TEST_TARGET=TARGET
export CASA_TEST_REFANT=ea10
pytest tests/integration/test_real_ms_smoke.py -m "integration and casa"
```

This requires a real small Measurement Set with matching fields and antenna names.

---

## 20. Troubleshooting

### 20.1 `ERROR: CASA tasks are not available`

The command is running in a Python environment where `casatasks` cannot be imported.

Use a CASA-capable Python environment, or install the package into the Python environment used by CASA.

### 20.2 `Measurement Set path does not exist at validation time`

The `validate` command warns when `vis` does not exist.

This is not fatal. It may be expected if you validate on one machine and run CASA on another. Before `inspect` or `run`, the path must be valid in the execution environment.

### 20.3 `Product already exists and overwrite=false`

A calibration table or output product already exists, and the configuration prevents overwriting.

Options:

```yaml
execution:
  resume: true
```

or:

```yaml
execution:
  overwrite: true
  resume: false
```

or clean the run directory:

```bash
casa-phase-ref clean-products config.yaml --yes
```

### 20.4 `applycal` fails because `interp` length is wrong

If you disable delay or bandpass calibration, update:

```yaml
calibration:
  apply:
    target_interp: [...]
```

The number of interpolation entries must match the number of gain tables used.

### 20.5 Target image is empty

Common causes:

- wrong target field name
- wrong phase calibrator field name
- failed or poor gain solutions
- target not detected
- image cell or imsize inappropriate
- excessive flagging
- wrong SPW selection

Recommended staged check:

```yaml
execution:
  stop_after: "applycal"
```

Then inspect corrected calibrator and target data in CASA before imaging.

### 20.6 No gain solutions found

Common causes:

- wrong field names
- poor reference antenna
- too short solution interval for available S/N
- excessive flagging
- bad SPW selection

Try:

```yaml
calibration:
  phase_gain:
    solint: "inf"
```

or choose a better `refant`.

### 20.7 `vlbi` profile gives a warning

This is expected. The current pipeline does not implement full VLBI calibration.

For VLBI, extend this generic workflow with EOP/ionosphere corrections, observatory-specific amplitude calibration, and any additional station-specific phase-reference transfer requirements. Fringe fitting is already configurable via `fringe_fitting`.

---

## 21. Current limitations

The current package is intentionally structured for extension, but the following features are not yet fully implemented:

- full VLBI phase-referencing path
- observatory-specific VLA/ALMA calibration recipes
- antenna position correction execution
- switched-power or gain-curve calibration
- parsing `listobs` to enforce field, antenna, and SPW existence
- diagnostic plot generation
- automatic image statistics and RMS estimation
- self-calibration execution
- full checkpointed resume semantics
- automatic calibration table inspection
- automatic flagging summaries before and after flag steps

These limitations do not prevent use as a reproducible generic CASA phase-referencing skeleton, but they should be considered before scientific production use.

---

## 22. Recommended operating practice

For a new dataset:

1. Copy the raw Measurement Set or work in a controlled data directory.
2. Create a minimal YAML configuration.
3. Run `validate`.
4. Run `inspect` and review `listobs.txt`.
5. Run with `stop_after: "bandpass"`.
6. Inspect delay and bandpass calibration tables manually.
7. Run with `stop_after: "applycal"`.
8. Inspect corrected calibrator data manually.
9. Run through `split`.
10. Make a quick-look image.
11. Adjust imaging parameters.
12. Run the final imaging pass.
13. Archive `config.resolved.yaml`, `pipeline.log`, `run-summary.json`, and final products.

A conservative staged configuration is often safer than a one-shot full run.

---

## 23. Configuration option summary

| Option | Type | Default | Required | Notes |
|---|---:|---:|---:|---|
| `vis` | string | none | yes | Input Measurement Set |
| `fluxcal` | string | none | yes | Flux calibrator field |
| `bandcal` | string | none | yes | Bandpass calibrator field |
| `phasecal` | string | none | yes | Phase-reference calibrator field |
| `target` | string | none | yes | Science target field |
| `refant` | string | none | yes | Reference antenna |
| `spw` | string | `""` | no | Spectral window selection |
| `flux_standard` | string | `Perley-Butler 2017` | no | CASA `setjy` standard |
| `calwt` | boolean | `false` | no | CASA `applycal` weight calibration flag |
| `observatory.profile` | enum | `generic` | no | `generic`, `vla`, `alma`, `vlbi` |
| `observatory.apply_antpos` | boolean | `false` | no | Reserved, not yet executed |
| `observatory.apply_switched_power` | boolean | `false` | no | Reserved, not yet executed |
| `execution.output_dir` | string | `runs/default` | no | Run output directory |
| `execution.overwrite` | boolean | `false` | no | Remove existing products when not resuming |
| `execution.resume` | boolean | `true` | no | Allow existing products |
| `execution.stop_after` | enum/null | `null` | no | Stop after named step |
| `safety.require_flag_backup` | boolean | `true` | no | Save flag backup before flagging |
| `safety.write_corrected_data` | boolean | `true` | no | Reserved; current pipeline writes corrected data |
| `safety.allow_in_place_ms_modification` | boolean | `true` | no | Reserved; current pipeline modifies input MS |
| `flagging.autocorr` | boolean | `true` | no | Flag autocorrelations |
| `flagging.shadow` | boolean | `true` | no | Shadow flagging |
| `flagging.clip_zeros` | boolean | `true` | no | Clip zero data |
| `flagging.rflag` | boolean | `true` | no | Run CASA `rflag` |
| `flagging.manual` | list | `[]` | no | Manual flag rules |
| `calibration.delay.enabled` | boolean | `true` | no | Solve delay table |
| `calibration.delay.field` | string/null | `null` | no | Defaults to `bandcal` |
| `calibration.delay.solint` | string | `inf` | no | Delay solution interval |
| `calibration.delay.combine` | string | `scan` | no | Delay combine mode |
| `calibration.bandpass.enabled` | boolean | `true` | no | Solve bandpass table |
| `calibration.bandpass.field` | string/null | `null` | no | Defaults to `bandcal` |
| `calibration.bandpass.solint` | string | `inf` | no | Bandpass solution interval |
| `calibration.bandpass.combine` | string | `scan` | no | Bandpass combine mode |
| `calibration.phase_gain.solint` | string | `int` | no | Phase gain solution interval |
| `calibration.phase_gain.calmode` | enum | `p` | no | `p`, `a`, `ap` |
| `calibration.amplitude_gain.solint` | string | `inf` | no | Amplitude gain solution interval |
| `calibration.amplitude_gain.calmode` | enum | `ap` | no | `p`, `a`, `ap` |
| `calibration.apply.target_interp` | list | `nearest, nearest, linear, linear` | no | Must match gain table count |
| `imaging.imagename` | string | `target_phase_ref` | no | Output image basename |
| `imaging.cell` | string | `0.2arcsec` | no | Image cell size |
| `imaging.imsize` | list[int] | `[2048, 2048]` | no | Two positive integers |
| `imaging.weighting` | string | `briggs` | no | `tclean` weighting |
| `imaging.robust` | float | `0.5` | no | Briggs robust value |
| `imaging.niter` | integer | `10000` | no | Clean iteration limit |
| `imaging.threshold` | string | `30uJy` | no | Clean threshold |
| `imaging.specmode` | string | `mfs` | no | Imaging spectral mode |
| `imaging.deconvolver` | string | `mtmfs` | no | Deconvolver |
| `imaging.nterms` | integer | `2` | no | MT-MFS Taylor terms |
| `imaging.interactive` | boolean | `false` | no | Interactive clean |
| `selfcal.enabled` | boolean | `false` | no | Schema only; not yet executed |
| `selfcal.rounds` | list | `[]` | no | Schema only; not yet executed |

---

## 24. Quick command reference

```bash
# Validate config without CASA task execution
casa-phase-ref validate config.yaml

# Run listobs inspection; requires CASA
casa-phase-ref inspect config.yaml

# Run pipeline; requires CASA
casa-phase-ref run config.yaml

# Show which run directory would be deleted
casa-phase-ref clean-products config.yaml

# Delete the run directory
casa-phase-ref clean-products config.yaml --yes

# Run normal tests without CASA
pytest -m "not integration"

# Run CASA integration tests
pytest -m "integration and casa"
```

---

## 25. Practical checklist before a full run

Before running the full pipeline, confirm:

- `vis` points to the correct Measurement Set.
- `fluxcal`, `bandcal`, `phasecal`, and `target` match field names or IDs in `listobs`.
- `refant` exists and is suitable.
- `spw` is correct or intentionally blank.
- `execution.output_dir` is unique for the run.
- `overwrite` and `resume` are set intentionally.
- automatic `rflag` is appropriate for the dataset.
- imaging `cell` and `imsize` are appropriate for the array configuration and science target.
- `target_interp` length matches the number of enabled calibration tables.
- for VLBI, the generic pipeline has been extended before scientific use.

