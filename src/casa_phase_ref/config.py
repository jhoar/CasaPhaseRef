from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class ObservatoryProfile(str, Enum):
    GENERIC = "generic"
    VLA = "vla"
    ALMA = "alma"
    VLBI = "vlbi"


class StopAfter(str, Enum):
    LISTOBS = "listobs"
    FLAGGING = "flagging"
    SETJY = "setjy"
    DELAY = "delay"
    BANDPASS = "bandpass"
    GAINS = "gains"
    FLUXSCALE = "fluxscale"
    APPLYCAL = "applycal"
    SPLIT = "split"
    IMAGE = "image"


class ObservatoryConfig(BaseModel):
    profile: ObservatoryProfile = ObservatoryProfile.GENERIC
    apply_antpos: bool = False
    apply_switched_power: bool = False


class ExecutionConfig(BaseModel):
    output_dir: str = "runs/default"
    overwrite: bool = False
    resume: bool = True
    stop_after: StopAfter | None = None


class SafetyConfig(BaseModel):
    require_flag_backup: bool = True
    write_corrected_data: bool = True
    allow_in_place_ms_modification: bool = True


class ManualFlagRule(BaseModel):
    field: str | None = None
    antenna: str | None = None
    spw: str | None = None
    timerange: str | None = None
    reason: str | None = None


class FlaggingConfig(BaseModel):
    autocorr: bool = True
    shadow: bool = True
    clip_zeros: bool = True
    rflag: bool = True
    manual: list[ManualFlagRule] = Field(default_factory=list)


class CalibrationDelayConfig(BaseModel):
    enabled: bool = True
    field: str | None = None
    solint: str = "inf"
    combine: str = "scan"


class CalibrationBandpassConfig(BaseModel):
    enabled: bool = True
    field: str | None = None
    solint: str = "inf"
    combine: str = "scan"


class CalibrationGainConfig(BaseModel):
    solint: str
    calmode: Literal["p", "a", "ap"]


class CalibrationApplyConfig(BaseModel):
    target_interp: list[str] = Field(
        default_factory=lambda: ["nearest", "nearest", "linear", "linear"]
    )


class CalibrationConfig(BaseModel):
    delay: CalibrationDelayConfig = Field(default_factory=CalibrationDelayConfig)
    bandpass: CalibrationBandpassConfig = Field(default_factory=CalibrationBandpassConfig)
    phase_gain: CalibrationGainConfig = Field(
        default_factory=lambda: CalibrationGainConfig(solint="int", calmode="p")
    )
    amplitude_gain: CalibrationGainConfig = Field(
        default_factory=lambda: CalibrationGainConfig(solint="inf", calmode="ap")
    )
    apply: CalibrationApplyConfig = Field(default_factory=CalibrationApplyConfig)


class ImagingConfig(BaseModel):
    imagename: str = "target_phase_ref"
    cell: str = "0.2arcsec"
    imsize: list[int] = Field(default_factory=lambda: [2048, 2048])
    weighting: str = "briggs"
    robust: float = 0.5
    niter: int = 10000
    threshold: str = "30uJy"
    specmode: str = "mfs"
    deconvolver: str = "mtmfs"
    nterms: int = 2
    interactive: bool = False

    @field_validator("imsize")
    @classmethod
    def validate_imsize(cls, value: list[int]) -> list[int]:
        if len(value) != 2 or any(v <= 0 for v in value):
            raise ValueError("imsize must contain two positive integers")
        return value


class SelfCalRound(BaseModel):
    name: str
    calmode: Literal["p", "a", "ap"] = "p"
    solint: str = "inf"
    minsnr: float = 3.0
    niter: int = 5000
    threshold: str = "50uJy"


class SelfCalConfig(BaseModel):
    enabled: bool = False
    rounds: list[SelfCalRound] = Field(default_factory=list)


class PhaseRefConfig(BaseModel):
    vis: str
    fluxcal: str
    bandcal: str
    phasecal: str
    target: str
    refant: str
    spw: str = ""
    flux_standard: str = "Perley-Butler 2017"
    calwt: bool = False

    observatory: ObservatoryConfig = Field(default_factory=ObservatoryConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    flagging: FlaggingConfig = Field(default_factory=FlaggingConfig)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)
    imaging: ImagingConfig = Field(default_factory=ImagingConfig)
    selfcal: SelfCalConfig = Field(default_factory=SelfCalConfig)

    @field_validator("vis", "fluxcal", "bandcal", "phasecal", "target", "refant")
    @classmethod
    def required_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be empty")
        return value


def load_config(path: str | Path) -> PhaseRefConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return PhaseRefConfig.model_validate(data)


def dump_resolved_config(cfg: PhaseRefConfig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg.model_dump(mode="json"), handle, sort_keys=False)
