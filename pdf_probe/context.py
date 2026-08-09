"""Shared execution context: the explicit set of dependencies a run needs."""

from __future__ import annotations

from dataclasses import dataclass

from pdf_probe.artifacts import ArtifactManager
from pdf_probe.config import Config
from pdf_probe.errors import ErrorHandler
from pdf_probe.logging_ import Logger, LogLevel


@dataclass
class ExecutionContext:
    """Cross-cutting services threaded through the pipeline and its stages.

    Components declare what they need in their constructor (usually just
    `context`) instead of receiving a long, unrelated argument list, while
    still only touching the specific services they use.
    """

    config: Config
    logger: Logger
    error_handler: ErrorHandler
    artifacts: ArtifactManager

    @classmethod
    def create(cls, config: Config) -> "ExecutionContext":
        Logger.configure(LogLevel.DEBUG if config.verbose else LogLevel.INFO)
        logger = Logger("pdf_probe")
        return cls(
            config=config,
            logger=logger,
            error_handler=ErrorHandler(logger),
            artifacts=ArtifactManager(logger),
        )
