"""The common interface every pipeline stage implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pdf_probe.context import ExecutionContext
from pdf_probe.logging_ import Logger
from pdf_probe.pipeline.data import PipelineData


class Stage(ABC):
    """One clearly-scoped unit of work in the pdf-probe pipeline.

    Every stage receives the shared :class:`ExecutionContext` at construction
    time (config, logger, error handler, artifacts) and the run's
    :class:`PipelineData` when it executes. A stage reads whatever fields it
    depends on from `data`, writes the fields it owns, and may append to
    `data.report`. Failures propagate as normal exceptions; the pipeline is
    responsible for routing them through the shared `ErrorHandler`.
    """

    def __init__(self, context: ExecutionContext) -> None:
        self._context = context
        self._logger: Logger = Logger.get(type(self).__name__)

    @property
    def name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def get_stage_name(self) -> str:
        """A short, human-readable noun phrase naming this stage.

        Used wherever the stage itself (not what it's currently doing) is
        being referred to — e.g. `--verbose`'s "Running stage: <name>" log
        lines — a phrase like "File Inspection", not the class name.
        """

    @abstractmethod
    def get_action_string(self) -> str:
        """A short, human-readable description of what this stage is doing.

        Shown in the progress bar as the stage runs — a present-tense phrase
        like "Extracting text", distinct from `get_stage_name()`.
        """

    @abstractmethod
    def run(self, data: PipelineData) -> None:
        """Perform this stage's work, mutating `data` in place."""
