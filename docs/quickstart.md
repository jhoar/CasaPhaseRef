# Quickstart

1. Copy `configs/example-phase-ref.yaml`.
2. Edit the Measurement Set path, calibrator names, target name, reference antenna, and imaging parameters.
3. Validate the config:

```bash
casa-phase-ref validate my-config.yaml
```

4. In a CASA-capable environment, inspect the observation:

```bash
casa-phase-ref inspect my-config.yaml
```

5. Run the pipeline:

```bash
casa-phase-ref run my-config.yaml
```
