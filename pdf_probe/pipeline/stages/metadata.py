"""Extracts document metadata: the info dictionary, XMP data, catalog language."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pypdf import PdfReader

from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class MetadataStage(Stage):
    """Normalizes the document info dictionary, XMP metadata, and /Lang."""

    def get_stage_name(self) -> str:
        return "Metadata Extraction"

    def get_action_string(self) -> str:
        return "Reading metadata"

    def run(self, data: PipelineData) -> None:
        reader = data.reader
        data.metadata = PdfValueFormatter.normalize(reader.metadata)
        data.xmp_metadata = self._extract_xmp_metadata(reader)
        data.catalog_language = self._extract_catalog_language(reader)

    @staticmethod
    def _extract_xmp_metadata(reader: PdfReader) -> Optional[Dict[str, Any]]:
        xmp = reader.xmp_metadata
        if xmp is None:
            return None

        data: Dict[str, Any] = {}
        for name in dir(xmp):
            if name.startswith("_"):
                continue
            try:
                value = getattr(xmp, name)
            except Exception as exc:  # pragma: no cover - defensive path
                data[name] = {"error": str(exc)}
                continue
            if callable(value):
                continue
            data[name] = PdfValueFormatter.normalize(value)
        return data

    @staticmethod
    def _extract_catalog_language(reader: PdfReader) -> Any:
        root = reader.trailer.get("/Root")
        if root is None:
            return None
        if hasattr(root, "get_object"):
            try:
                root = root.get_object()
            except Exception:
                return None
        if hasattr(root, "get"):
            return PdfValueFormatter.normalize(root.get("/Lang"))
        return None
