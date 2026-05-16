# Configuration

The main configuration sections are:

- `observatory`: profile-level behavior.
- `execution`: output directory, overwrite/resume, and stop-after behavior.
- `safety`: guardrails around flag backups and in-place modification.
- `flagging`: automatic and manual flagging rules.
- `calibration`: delay, bandpass, gain, and application strategy.
- `fringe_fitting`: VLBI-only fringe-fit solves (`fringefit`) and target application.
- `imaging`: `tclean` parameters.
- `selfcal`: reserved structure for future explicit self-calibration rounds.

Use `execution.stop_after` to run a partial pipeline, for example:

```yaml
execution:
  stop_after: "bandpass"
```

For VLBI profile runs, configure fringe fitting explicitly:

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

When `fringe_fitting.enabled=true`, update `calibration.apply.target_interp` so it has one
entry per active gaintable (base gain tables + enabled fringe tables).
