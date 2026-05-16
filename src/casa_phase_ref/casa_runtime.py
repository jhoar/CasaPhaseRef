from __future__ import annotations

from typing import Any

from .errors import CasaUnavailableError


def load_casa_tasks() -> dict[str, Any]:
    try:
        from casatasks import (
            applycal,
            bandpass,
            flagdata,
            flagmanager,
            fluxscale,
            fringefit,
            gaincal,
            gencal,
            listobs,
            setjy,
            split,
            tclean,
        )
    except ImportError as exc:
        raise CasaUnavailableError(
            "CASA tasks are not available. Run inside CASA 6, or install supported "
            "casatasks/casatools wheels for your platform."
        ) from exc

    return {
        "applycal": applycal,
        "bandpass": bandpass,
        "flagdata": flagdata,
        "flagmanager": flagmanager,
        "fluxscale": fluxscale,
        "fringefit": fringefit,
        "gaincal": gaincal,
        "gencal": gencal,
        "listobs": listobs,
        "setjy": setjy,
        "split": split,
        "tclean": tclean,
    }


def casa_version() -> str:
    try:
        import casatasks

        return getattr(casatasks, "version_string", "unknown")
    except Exception:
        return "unavailable"
