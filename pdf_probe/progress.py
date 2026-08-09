"""Reporting pipeline progress to the terminal."""

from __future__ import annotations

import sys
import threading
from typing import Optional, TextIO

from pdf_probe.logging_ import Logger


class ProgressReporter:
    """Reports per-stage pipeline progress as the pipeline runs.

    Base class is a no-op interface; subclasses override only the hooks they
    care about. Two implementations trade detail for legibility:
    `ProgressBarReporter` draws a single, continuously-updating bar (the
    default INFO-level experience); `LoggingProgressReporter` instead emits
    one DEBUG-level line per stage (the `--verbose` experience), since
    interleaving a redrawing bar with detailed log output would just look
    broken.
    """

    def start(self, total: int) -> None:
        """Called once, before the first stage runs."""

    def stage_started(self, position: int, total: int, stage_name: str, action: str) -> None:
        """Called just before a stage runs.

        `stage_name` is the stage's `get_stage_name()` (a noun phrase, e.g.
        "File Inspection"); `action` is its `get_action_string()` (a
        present-tense phrase, e.g. "Inspecting file").
        """

    def stage_finished(self, position: int, total: int, stage_name: str, action: str) -> None:
        """Called once a stage has finished successfully."""

    def finish(self, total: int) -> None:
        """Called once, after every stage has finished successfully."""


class LoggingProgressReporter(ProgressReporter):
    """Verbose mode: one DEBUG-level line per stage, started and finished.

    Uses each stage's `stage_name` (a noun phrase) rather than its `action`
    string, since "Running stage: <name>" reads naturally with a name, not
    a present-tense phrase — "Running stage: File Inspection", not
    "Running stage: Inspecting file".
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def stage_started(self, position: int, total: int, stage_name: str, action: str) -> None:
        self._logger.debug(f"[{position}/{total}] Running stage: {stage_name}")

    def stage_finished(self, position: int, total: int, stage_name: str, action: str) -> None:
        self._logger.debug(f"[{position}/{total}] Stage succeeded: {stage_name}")


class ProgressBarReporter(ProgressReporter):
    """Default mode: a single, in-place terminal progress bar.

    While a stage is running, its action string grows an animated
    "." -> ".." -> "..." suffix that ticks once per second (then wraps back
    to "."), so a slow stage still visibly shows activity between position
    updates. Once the pipeline finishes, the bar is erased entirely rather
    than left on screen, so the terminal's final state is clean.

    Falls back to one plain status line per event when `stream` isn't a
    terminal (e.g. output redirected to a file, or captured by a test) —
    no animation, since redrawing with carriage returns would otherwise
    corrupt non-interactive output.
    """

    def __init__(
        self, stream: Optional[TextIO] = None, *, width: int = 24, tick_seconds: float = 1.0
    ) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._width = width
        self._tick_seconds = tick_seconds
        self._is_tty = hasattr(self._stream, "isatty") and self._stream.isatty()

        self._lock = threading.Lock()
        self._position = 0
        self._total = 0
        self._action = ""
        self._dots = 0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, total: int) -> None:
        with self._lock:
            self._total = total
            self._position = 0
            self._action = "Starting"
            self._dots = 0
        self._draw()
        if self._is_tty:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()

    def stage_started(self, position: int, total: int, stage_name: str, action: str) -> None:
        with self._lock:
            self._total = total
            self._position = position - 1
            self._action = action
            self._dots = 0
        self._draw()

    def stage_finished(self, position: int, total: int, stage_name: str, action: str) -> None:
        with self._lock:
            self._total = total
            self._position = position
            self._action = action
            self._dots = 0
        self._draw()

    def finish(self, total: int) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._is_tty:
            self._stream.write("\r\x1b[K")
            self._stream.flush()

    def _animate(self) -> None:
        while not self._stop_event.wait(self._tick_seconds):
            with self._lock:
                self._dots = self._dots % 3 + 1
            self._draw()

    def _draw(self) -> None:
        with self._lock:
            position, total, action, dots = self._position, self._total, self._action, self._dots

        suffix = "." * dots if self._is_tty else ""
        filled = self._width if total == 0 else round(self._width * position / total)
        bar = "#" * filled + "-" * (self._width - filled)
        line = f"[{bar}] {position}/{total} {action}{suffix}"

        if self._is_tty:
            self._stream.write("\r\x1b[K" + line)
        else:
            self._stream.write(line + "\n")
        self._stream.flush()
