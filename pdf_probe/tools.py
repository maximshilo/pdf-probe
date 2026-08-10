"""Invoking optional external command-line tools (pdfinfo, pdftotext, qpdf)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List

from pdf_probe.logging_ import Logger


@dataclass
class ToolResult:
    """The outcome of trying to run an external tool."""

    available: bool
    command: List[str]
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""

    def succeeded(self) -> bool:
        return self.available and self.exit_code == 0


@dataclass
class ExternalTool:
    """A named external tool, resolved and invoked via ``PATH``."""

    _TIMEOUT_SECONDS = 30
    _REDACTED = "***"

    name: str
    logger: Logger = field(compare=False)

    def is_available(self) -> bool:
        return shutil.which(self.name) is not None

    def password_args(self, password: str) -> List[str]:
        """CLI args that supply `password` to this tool, in its own syntax."""
        if not password:
            return []
        if self.name == "qpdf":
            return [f"--password={password}"]
        return ["-upw", password]

    def run(self, *args: str) -> ToolResult:
        command = [self.name, *args]
        if not self.is_available():
            self.logger.debug(f"Tool not available on PATH: {self.name}")
            return ToolResult(available=False, command=command)

        self.logger.debug(f"Running: {' '.join(self._redact(command))}")
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=self._TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            self.logger.warning(
                f"Tool timed out after {self._TIMEOUT_SECONDS}s and was killed: {self.name}"
            )
            return ToolResult(
                available=True,
                command=command,
                stderr=f"Timed out after {self._TIMEOUT_SECONDS}s",
            )
        return ToolResult(
            available=True,
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @classmethod
    def _redact(cls, command: List[str]) -> List[str]:
        """`command` with any password value masked, safe to put in a log line.

        Only the logged representation is masked - `command` itself (used to
        actually invoke the tool, and stored on `ToolResult`) is untouched.
        """
        redacted: List[str] = []
        mask_next = False
        for arg in command:
            if mask_next:
                redacted.append(cls._REDACTED)
                mask_next = False
            elif arg == "-upw":
                redacted.append(arg)
                mask_next = True
            elif arg.startswith("--password="):
                redacted.append(f"--password={cls._REDACTED}")
            else:
                redacted.append(arg)
        return redacted
