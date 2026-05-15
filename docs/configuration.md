# Configuration

The main configuration sections are:

- `observatory`: profile-level behavior.
- `execution`: output directory, overwrite/resume, and stop-after behavior.
- `safety`: guardrails around flag backups and in-place modification.
- `flagging`: automatic and manual flagging rules.
- `calibration`: delay, bandpass, gain, and application strategy.
- `imaging`: `tclean` parameters.
- `selfcal`: reserved structure for future explicit self-calibration rounds.

Use `execution.stop_after` to run a partial pipeline, for example:

```yaml
execution:
  stop_after: "bandpass"
```
