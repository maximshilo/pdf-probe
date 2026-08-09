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

    name: str
    logger: Logger = field(compare=False)

    def is_available(self) -> bool:
        return shutil.which(self.name) is not None

    def run(self, *args: str) -> ToolResult:
        command = [self.name, *args]
        if not self.is_available():
            self.logger.debug(f"Tool not available on PATH: {self.name}")
            return ToolResult(available=False, command=command)

        self.logger.debug(f"Running: {' '.join(command)}")
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return ToolResult(
            available=True,
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
