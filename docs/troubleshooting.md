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

## Symptoms of misordered calibration chain

If gain tables are applied in the wrong order, common signatures include:

- Residual dispersive phase ramps even after TEC correction (often seen when TEC is applied after delay/bandpass).
- Large phase jumps scan-to-scan on VLBI data when EOP/fringe terms are not ahead of downstream gains.
- `applycal` warnings about poor interpolation or many failed solutions when delay/bandpass tables are applied after phase/amplitude gains.
- Apparent amplitude decorrelation on the target while calibrators look reasonable (often due to misplaced fringe-fit or gain tables).

Recommended chain order is:

1. EOP/metadata corrections (VLBI)
2. TEC/pulse-cal a-priori terms
3. Delay and bandpass
4. Fringe-fit phase/delay-rate
5. Gain/amplitude solutions
