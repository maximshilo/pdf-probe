"""Artifact persistence: the one place pdf-probe writes files to disk."""

from __future__ import annotations

from pathlib import Path

from pdf_probe.logging_ import Logger


class ArtifactManager:
    """Saves generated output to disk, logging each write.

    Today pdf-probe produces exactly one artifact per run (the Markdown
    report), but funneling every write through here rather than ad hoc
    ``Path.write_text`` calls gives future artifact types (diagnostic dumps,
    intermediate files) one consistent place to land.
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def save(self, path: Path, content: str, *, encoding: str = "utf-8") -> Path:
        path.write_text(content, encoding=encoding)
        self._logger.debug(f"Saved artifact: {path}")
        return path

    def save_report(self, content: str, path: Path) -> Path:
        return self.save(path, content)
