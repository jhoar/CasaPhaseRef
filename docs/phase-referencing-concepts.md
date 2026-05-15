# Phase-referencing concepts

Phase referencing transfers time-dependent phase and amplitude gain solutions from a nearby calibrator to the target. In this package the essential transfer occurs in the target `applycal` call, where the target field receives the gain solutions derived from the configured `phasecal`.

This package assumes a conventional connected-element style workflow unless extended with a telescope-specific profile.
