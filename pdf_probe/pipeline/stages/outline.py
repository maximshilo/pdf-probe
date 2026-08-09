"""Extracts bookmarks/outline and named destinations."""

from __future__ import annotations

from typing import Any, Dict, List

from pypdf import PdfReader

from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class OutlineStage(Stage):
    """Extracts the bookmark tree and named destinations."""

    def get_stage_name(self) -> str:
        return "Outline and Destinations"

    def get_action_string(self) -> str:
        return "Reading outline and destinations"

    def run(self, data: PipelineData) -> None:
        reader = data.reader
        data.outline = self._flatten_outline(reader.outline)
        data.named_destinations_count = len(reader.named_destinations)
        if self._context.config.full:
            data.named_destinations = self._extract_named_destinations(reader)

    @classmethod
    def _flatten_outline(cls, items: List[Any], depth: int = 0) -> List[Dict[str, Any]]:
        flattened: List[Dict[str, Any]] = []
        for item in items:
            if isinstance(item, list):
                flattened.extend(cls._flatten_outline(item, depth + 1))
                continue
            entry: Dict[str, Any] = {"depth": depth}
            for attribute in ("title", "page", "color", "bold", "italic"):
                if hasattr(item, attribute):
                    entry[attribute] = PdfValueFormatter.normalize(getattr(item, attribute))
            if not entry.keys() - {"depth"}:
                entry["value"] = repr(item)
            flattened.append(entry)
        return flattened

    @staticmethod
    def _extract_named_destinations(reader: PdfReader) -> Dict[str, Any]:
        destinations: Dict[str, Any] = {}
        for name, destination in reader.named_destinations.items():
            entry: Dict[str, Any] = {}
            for attribute in ("title", "page", "typ", "left", "right", "top", "bottom", "zoom"):
                if hasattr(destination, attribute):
                    entry[attribute] = PdfValueFormatter.normalize(getattr(destination, attribute))
            if not entry:
                entry = {"value": repr(destination)}
            destinations[name] = entry
        return destinations
