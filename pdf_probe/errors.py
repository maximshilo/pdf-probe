"""Unified error handling shared by the application and the test framework."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from pdf_probe.logging_ import Logger


class PdfProbeError(Exception):
    """Base class for errors raised anywhere in pdf-probe's own code.

    Carries enough diagnostic context for :class:`ErrorHandler` to format and
    log it uniformly: which component raised it, whether the run can continue
    despite it, and (if it wraps another exception) the original cause.
    """

    def __init__(
        self,
        message: str,
        *,
        component: str = "",
        recoverable: bool = False,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.component = component
        self.recoverable = recoverable
        self.cause = cause


class DecryptionError(PdfProbeError):
    """Raised when an encrypted PDF cannot be decrypted with the supplied password."""


class StageExecutionError(PdfProbeError):
    """Wraps an unexpected exception raised while a pipeline stage (or test) ran."""


class ErrorHandler:
    """Reports and formats :class:`PdfProbeError`\\ s through a shared :class:`Logger`.

    Used identically by the pipeline (each stage runs under
    ``error_handler.handling(stage.name)``) and by the test framework's base
    test cases, so a failure looks the same everywhere it's logged.
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def report(self, error: PdfProbeError) -> None:
        """Log `error`, tagged with its component, at the appropriate level."""
        log = self._logger.warning if error.recoverable else self._logger.error
        detail = f"[{error.component}] {error}" if error.component else str(error)
        log(detail)
        if error.cause is not None:
            self._logger.debug(f"Caused by: {error.cause!r}")

    @contextmanager
    def handling(self, component: str, *, recoverable: bool = False) -> Iterator[None]:
        """Run a block of code, reporting any failure as owned by `component`.

        A :class:`PdfProbeError` raised inside the block is reported and then
        re-raised unless it is marked recoverable. Any other exception is
        wrapped in a :class:`StageExecutionError` first. This is the one place
        exception-to-log translation happens, instead of every stage and test
        duplicating its own try/except formatting.
        """
        try:
            yield
        except PdfProbeError as exc:
            if not exc.component:
                exc.component = component
            self.report(exc)
            if not exc.recoverable:
                raise
        except Exception as exc:
            wrapped = StageExecutionError(
                str(exc), component=component, recoverable=recoverable, cause=exc
            )
            self.report(wrapped)
            if not recoverable:
                raise wrapped from exc
