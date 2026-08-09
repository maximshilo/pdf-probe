"""Unified logging used by the application, the pipeline, and the tests.

``Logger`` is a thin, injectable wrapper around the standard library's
``logging`` module rather than a from-scratch implementation: components
depend on an explicit ``Logger`` instance (constructor-injected), while the
actual formatting/level/stream handling is centrally configured once via
``Logger.configure()``.
"""

from __future__ import annotations

import logging
import sys
from enum import Enum
from typing import Optional, TextIO

_ROOT_NAME = "pdf_probe"


class LogLevel(Enum):
    """Verbosity levels supported by :class:`Logger`."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


class Logger:
    """A named logger bound to the shared ``pdf_probe`` logging configuration."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    @classmethod
    def configure(cls, level: LogLevel = LogLevel.INFO, stream: Optional[TextIO] = None) -> None:
        """Configure the shared handler/formatter/level once for the whole run.

        Verbose output must never touch stdout: pdf-probe's CLI contract is
        that stdout carries only the final report path on success. `stream`
        resolves `sys.stderr` at call time rather than as a default-argument
        value, so it still targets the current stream when that's been
        swapped out (e.g. by pytest's `capsys`).
        """
        root = logging.getLogger(_ROOT_NAME)
        root.handlers.clear()
        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(handler)
        root.setLevel(level.value)
        root.propagate = False

    @classmethod
    def get(cls, name: str) -> "Logger":
        """Return a `Logger` for `name`, nested under the shared root."""
        return cls(f"{_ROOT_NAME}.{name}")

    def debug(self, message: str, *args: object) -> None:
        self._logger.debug(message, *args)

    def info(self, message: str, *args: object) -> None:
        self._logger.info(message, *args)

    def warning(self, message: str, *args: object) -> None:
        self._logger.warning(message, *args)

    def error(self, message: str, *args: object) -> None:
        self._logger.error(message, *args)
