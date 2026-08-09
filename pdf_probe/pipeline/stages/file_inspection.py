"""Computes filesystem facts about the source PDF (size, hash, mtime)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from pdf_probe.pipeline.data import FileInfo, PipelineData
from pdf_probe.pipeline.stage import Stage

UTC = timezone.utc


class FileInspectionStage(Stage):
    """Hashes and stats the source PDF, independent of its PDF contents."""

    _CHUNK_SIZE = 1024 * 1024

    def get_stage_name(self) -> str:
        return "File Inspection"

    def get_action_string(self) -> str:
        return "Inspecting file"

    def run(self, data: PipelineData) -> None:
        pdf_path = self._context.config.pdf_path
        stat = pdf_path.stat()
        data.file_info = FileInfo(
            size=stat.st_size,
            last_modified=self._isoformat_timestamp(stat.st_mtime),
            sha256=self._sha256sum(pdf_path),
        )

    @classmethod
    def _sha256sum(cls, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(cls._CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _isoformat_timestamp(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
