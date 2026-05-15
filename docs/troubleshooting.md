# Troubleshooting

## CASA task import fails

Run inside CASA 6 or install compatible `casatasks`/`casatools` wheels for your platform.

## Product already exists

Set either:

```yaml
execution:
  resume: true
```

or:

```yaml
execution:
  overwrite: true
```

## No solutions found

Check field names, reference antenna, SPW selection, calibrator flux, and flagging aggressiveness.

## Target image is empty

Check that the target was correctly split from `CORRECTED_DATA`, that phase calibrator solutions exist near the target scans, and that the imaging cell size/imsize cover the expected field.
