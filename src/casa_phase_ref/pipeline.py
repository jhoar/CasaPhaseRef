from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .casa_runtime import load_casa_tasks
from .config import ObservatoryProfile, PhaseRefConfig, StopAfter
from .errors import PipelineStepError, ValidationReportError
from .run_context import (
    base_summary,
    create_run_paths,
    ensure_absent_or_overwritable,
    setup_logging,
    write_json,
)
from .validation import inspect_measurement_set, validate_static_config

CasaTasks = dict[str, Any]


def _call_step(step: str, func: Callable[[], None], summary: dict[str, Any]) -> None:
    try:
        func()
        summary["steps"].append({"name": step, "status": "ok"})
    except Exception as exc:
        summary["steps"].append({"name": step, "status": "failed", "error": str(exc)})
        summary["errors"].append({"step": step, "error": str(exc)})
        raise PipelineStepError(step) from exc


def _should_stop(cfg: PhaseRefConfig, step: StopAfter) -> bool:
    return cfg.execution.stop_after == step


def run_pipeline(cfg: PhaseRefConfig, casa_tasks: CasaTasks | None = None) -> dict[str, Any]:
    casa = casa_tasks if casa_tasks is not None else load_casa_tasks()
    paths = create_run_paths(cfg)
    logger = setup_logging(paths)
    summary = base_summary(cfg)

    try:
        warnings = validate_static_config(cfg)
    except ValidationReportError as exc:
        summary["errors"].append({"step": "validation", "error": str(exc)})
        write_json(paths.reports / "run-summary.json", summary)
        raise

    summary["warnings"].extend(warnings)
    for w in warnings:
        logger.warning(w)

    logger.info("Starting CASA phase-referencing pipeline")
    logger.info("Run directory: %s", paths.root)

    vis = cfg.vis
    fluxcal = cfg.fluxcal
    bandcal = cfg.bandcal
    phasecal = cfg.phasecal
    target = cfg.target
    refant = cfg.refant
    spw = cfg.spw

    delay_cal = paths.calibration / "cal.K"
    bp_prephase_cal = paths.calibration / "cal.BPpre.G"
    bp_cal = paths.calibration / "cal.B"
    phase_cal = paths.calibration / "cal.Gp"
    amp_cal = paths.calibration / "cal.Gap"
    flux_cal = paths.calibration / "cal.fluxscale"
    target_ms = paths.products / f"{target}_calibrated.ms"
    imagename = str(paths.products / cfg.imaging.imagename)

    fringe_global_cal: Path | None = None
    fringe_phase_cal: Path | None = None
    if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled:
        if cfg.fringe_fitting.global_fit is not None:
            fringe_global_cal = paths.calibration / cfg.fringe_fitting.global_fit.caltable
        if cfg.fringe_fitting.phase_reference is not None:
            fringe_phase_cal = paths.calibration / cfg.fringe_fitting.phase_reference.caltable

    products_to_check: list[Path] = [
        delay_cal,
        bp_prephase_cal,
        bp_cal,
        phase_cal,
        amp_cal,
        flux_cal,
        target_ms,
    ]
    if fringe_global_cal is not None:
        products_to_check.append(fringe_global_cal)
    if fringe_phase_cal is not None:
        products_to_check.append(fringe_phase_cal)

    for product in products_to_check:
        ensure_absent_or_overwritable(product, cfg.execution.overwrite, cfg.execution.resume)

    def listobs_step() -> None:
        inspection = inspect_measurement_set(cfg, casa, paths.reports / "listobs.txt")
        summary["inspection"] = inspection

    logger.info("Running listobs/inspection")
    _call_step("listobs", listobs_step, summary)
    if _should_stop(cfg, StopAfter.LISTOBS):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    def flagging_step() -> None:
        if cfg.safety.require_flag_backup:
            casa["flagmanager"](vis=vis, mode="save", versionname="original")
        if cfg.flagging.autocorr:
            casa["flagdata"](vis=vis, mode="manual", autocorr=True)
        if cfg.flagging.shadow:
            casa["flagdata"](vis=vis, mode="shadow")
        if cfg.flagging.clip_zeros:
            casa["flagdata"](vis=vis, mode="clip", clipzeros=True)
        if cfg.flagging.rflag:
            casa["flagdata"](
                vis=vis,
                mode="rflag",
                field="",
                datacolumn="data",
                timedevscale=4.0,
                freqdevscale=4.0,
                action="apply",
            )
        for rule in cfg.flagging.manual:
            kwargs = {k: v for k, v in rule.model_dump().items() if v is not None and k != "reason"}
            if kwargs:
                casa["flagdata"](vis=vis, mode="manual", **kwargs)
        if cfg.safety.require_flag_backup:
            casa["flagmanager"](vis=vis, mode="save", versionname="after_initial_flagging")

    logger.info("Running flagging")
    _call_step("flagging", flagging_step, summary)
    if _should_stop(cfg, StopAfter.FLAGGING):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    def setjy_step() -> None:
        casa["setjy"](vis=vis, field=fluxcal, standard=cfg.flux_standard, usescratch=True)

    logger.info("Setting flux model")
    _call_step("setjy", setjy_step, summary)
    if _should_stop(cfg, StopAfter.SETJY):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    delay_field = cfg.calibration.delay.field or bandcal

    def delay_step() -> None:
        if cfg.calibration.delay.enabled:
            casa["gaincal"](
                vis=vis,
                caltable=str(delay_cal),
                field=delay_field,
                spw=spw,
                gaintype="K",
                solint=cfg.calibration.delay.solint,
                refant=refant,
                combine=cfg.calibration.delay.combine,
            )

    logger.info("Solving delay calibration")
    _call_step("delay", delay_step, summary)
    if _should_stop(cfg, StopAfter.DELAY):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    bandpass_field = cfg.calibration.bandpass.field or bandcal

    def bandpass_step() -> None:
        casa["gaincal"](
            vis=vis,
            caltable=str(bp_prephase_cal),
            field=bandpass_field,
            spw=spw,
            solint="int",
            calmode="p",
            refant=refant,
            gaintable=[str(delay_cal)] if cfg.calibration.delay.enabled else [],
        )
        if cfg.calibration.bandpass.enabled:
            casa["bandpass"](
                vis=vis,
                caltable=str(bp_cal),
                field=bandpass_field,
                spw=spw,
                solint=cfg.calibration.bandpass.solint,
                combine=cfg.calibration.bandpass.combine,
                refant=refant,
                gaintable=[str(delay_cal), str(bp_prephase_cal)]
                if cfg.calibration.delay.enabled
                else [str(bp_prephase_cal)],
            )

    logger.info("Solving bandpass calibration")
    _call_step("bandpass", bandpass_step, summary)
    if _should_stop(cfg, StopAfter.BANDPASS):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    base_gaintables: list[str] = []
    if cfg.calibration.delay.enabled:
        base_gaintables.append(str(delay_cal))
    if cfg.calibration.bandpass.enabled:
        base_gaintables.append(str(bp_cal))

    def gains_step() -> None:
        casa["gaincal"](
            vis=vis,
            caltable=str(phase_cal),
            field=",".join([fluxcal, phasecal]),
            spw=spw,
            solint=cfg.calibration.phase_gain.solint,
            calmode=cfg.calibration.phase_gain.calmode,
            refant=refant,
            gaintable=base_gaintables,
        )
        casa["gaincal"](
            vis=vis,
            caltable=str(amp_cal),
            field=",".join([fluxcal, phasecal]),
            spw=spw,
            solint=cfg.calibration.amplitude_gain.solint,
            calmode=cfg.calibration.amplitude_gain.calmode,
            refant=refant,
            gaintable=base_gaintables + [str(phase_cal)],
        )

    def fringe_fit_step() -> None:
        if cfg.observatory.profile != ObservatoryProfile.VLBI or not cfg.fringe_fitting.enabled:
            return
        if cfg.fringe_fitting.global_fit is not None and fringe_global_cal is not None:
            global_fit = cfg.fringe_fitting.global_fit
            casa["fringefit"](
                vis=vis,
                caltable=str(fringe_global_cal),
                field=global_fit.field,
                solint=global_fit.solint,
                refant=global_fit.refant,
                minsnr=global_fit.minsnr,
            )
        if cfg.fringe_fitting.phase_reference is not None and fringe_phase_cal is not None:
            phase_fit = cfg.fringe_fitting.phase_reference
            gaintables = list(base_gaintables)
            if fringe_global_cal is not None:
                gaintables.append(str(fringe_global_cal))
            casa["fringefit"](
                vis=vis,
                caltable=str(fringe_phase_cal),
                field=phase_fit.field,
                solint=phase_fit.solint,
                refant=phase_fit.refant,
                minsnr=phase_fit.minsnr,
                gaintable=gaintables,
            )

    logger.info("Solving fringe fitting (VLBI profile)")
    _call_step("fringe_fit", fringe_fit_step, summary)

    logger.info("Solving gain calibration")
    _call_step("gains", gains_step, summary)
    if _should_stop(cfg, StopAfter.GAINS):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    def fluxscale_step() -> None:
        casa["fluxscale"](
            vis=vis,
            caltable=str(amp_cal),
            fluxtable=str(flux_cal),
            reference=fluxcal,
            transfer=phasecal,
        )

    logger.info("Bootstrapping flux scale")
    _call_step("fluxscale", fluxscale_step, summary)
    if _should_stop(cfg, StopAfter.FLUXSCALE):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    gaintables = base_gaintables + [str(phase_cal), str(flux_cal)]
    if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled:
        if fringe_global_cal is not None:
            gaintables.append(str(fringe_global_cal))
        if fringe_phase_cal is not None and cfg.fringe_fitting.apply_to_target:
            gaintables.append(str(fringe_phase_cal))
    band_gainfields: list[str] = []
    if cfg.calibration.delay.enabled:
        band_gainfields.append(delay_field)
    if cfg.calibration.bandpass.enabled:
        band_gainfields.append(bandpass_field)

    def applycal_step() -> None:
        casa["applycal"](
            vis=vis,
            field=fluxcal,
            gaintable=gaintables,
            gainfield=band_gainfields + [fluxcal, fluxcal] + ([cfg.fringe_fitting.global_fit.field] if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled and fringe_global_cal is not None else []) + ([cfg.fringe_fitting.phase_reference.field] if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled and fringe_phase_cal is not None and cfg.fringe_fitting.apply_to_target else []),
            interp=["nearest"] * len(gaintables),
            calwt=cfg.calwt,
        )
        casa["applycal"](
            vis=vis,
            field=phasecal,
            gaintable=gaintables,
            gainfield=band_gainfields + [phasecal, phasecal] + ([cfg.fringe_fitting.global_fit.field] if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled and fringe_global_cal is not None else []) + ([cfg.fringe_fitting.phase_reference.field] if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled and fringe_phase_cal is not None and cfg.fringe_fitting.apply_to_target else []),
            interp=["nearest"] * len(gaintables),
            calwt=cfg.calwt,
        )
        casa["applycal"](
            vis=vis,
            field=target,
            gaintable=gaintables,
            gainfield=band_gainfields + [phasecal, phasecal] + ([cfg.fringe_fitting.global_fit.field] if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled and fringe_global_cal is not None else []) + ([cfg.fringe_fitting.phase_reference.field] if cfg.observatory.profile == ObservatoryProfile.VLBI and cfg.fringe_fitting.enabled and fringe_phase_cal is not None and cfg.fringe_fitting.apply_to_target else []),
            interp=cfg.calibration.apply.target_interp,
            calwt=cfg.calwt,
        )
        if cfg.safety.require_flag_backup:
            casa["flagmanager"](vis=vis, mode="save", versionname="after_applycal")

    logger.info("Applying calibration")
    _call_step("applycal", applycal_step, summary)
    if _should_stop(cfg, StopAfter.APPLYCAL):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    def split_step() -> None:
        casa["split"](
            vis=vis,
            outputvis=str(target_ms),
            field=target,
            datacolumn="corrected",
            keepflags=False,
        )

    logger.info("Splitting corrected target data")
    _call_step("split", split_step, summary)
    if _should_stop(cfg, StopAfter.SPLIT):
        write_json(paths.reports / "run-summary.json", summary)
        return summary

    img = cfg.imaging

    def image_step() -> None:
        casa["tclean"](
            vis=str(target_ms),
            imagename=imagename,
            field="",
            spw="",
            specmode=img.specmode,
            deconvolver=img.deconvolver,
            nterms=img.nterms,
            imsize=img.imsize,
            cell=img.cell,
            weighting=img.weighting,
            robust=img.robust,
            niter=img.niter,
            threshold=img.threshold,
            interactive=img.interactive,
            savemodel="modelcolumn",
        )

    logger.info("Imaging target")
    _call_step("image", image_step, summary)

    write_json(paths.reports / "run-summary.json", summary)
    logger.info("Pipeline complete")
    return summary
