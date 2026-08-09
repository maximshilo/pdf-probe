"""Run configuration for a single pdf-probe invocation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Immutable configuration for one pdf-probe run.

    Built by :mod:`pdf_probe.cli` from command-line arguments, or directly by
    callers of :func:`pdf_probe.build_report` who don't go through the CLI.
    """

    pdf_path: Path
    output_path: Path
    password: str = ""
    full: bool = False
    verbose: bool = False
