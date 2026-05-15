from __future__ import annotations


class CasaPhaseRefError(RuntimeError):
    """Base package error."""


class CasaUnavailableError(CasaPhaseRefError):
    """Raised when CASA tasks cannot be imported."""


class PipelineStepError(CasaPhaseRefError):
    """Raised when a named pipeline step fails."""

    def __init__(self, step: str, message: str | None = None) -> None:
        self.step = step
        super().__init__(message or f"Pipeline step failed: {step}")


class ProductExistsError(CasaPhaseRefError):
    """Raised when a product exists and overwrite is disabled."""


class ValidationReportError(CasaPhaseRefError):
    """Raised when runtime validation fails."""
