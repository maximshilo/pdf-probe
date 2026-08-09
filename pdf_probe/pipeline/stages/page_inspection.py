"""Extracts per-page structural details: images, rotation, boxes, annotations."""

from __future__ import annotations

from typing import Any, Dict, List

from pypdf import PdfReader

from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class PageInspectionStage(Stage):
    """Builds a per-page overview, and (in --full mode) full per-page metadata."""

    def get_stage_name(self) -> str:
        return "Page Inspection"

    def get_action_string(self) -> str:
        return "Inspecting pages"

    def run(self, data: PipelineData) -> None:
        reader = data.reader
        data.page_overview = self._build_overview(reader)
        if self._context.config.full:
            data.page_metadata = self._build_full_metadata(reader)

    @staticmethod
    def _build_overview(reader: PdfReader) -> List[Dict[str, Any]]:
        pages: List[Dict[str, Any]] = []
        page_labels = list(getattr(reader, "page_labels", []))
        for index, page in enumerate(reader.pages, start=1):
            image_names: List[str] = []
            image_error = None
            try:
                for image in page.images:
                    image_names.append(
                        getattr(image, "name", None) or f"image-{len(image_names) + 1}"
                    )
            except Exception as exc:  # pragma: no cover - defensive path
                image_error = str(exc)

            page_info = {
                "page_number": index,
                "label": page_labels[index - 1] if len(page_labels) >= index else None,
                "rotation": getattr(page, "rotation", None),
                "image_count": len(image_names),
                "image_names": image_names,
                "annotation_count": PdfValueFormatter.count_entries(
                    getattr(page, "annotations", None)
                ),
            }
            if image_error is not None:
                page_info["image_error"] = image_error
            pages.append(page_info)
        return pages

    @staticmethod
    def _build_full_metadata(reader: PdfReader) -> List[Dict[str, Any]]:
        pages: List[Dict[str, Any]] = []
        for index, page in enumerate(reader.pages, start=1):
            images: List[Dict[str, Any]]
            try:
                images = [
                    {
                        "name": getattr(image, "name", None),
                        "data": PdfValueFormatter.decode_bytes(image.data),
                    }
                    for image in page.images
                ]
            except Exception as exc:  # pragma: no cover - defensive path
                images = [{"error": str(exc)}]

            pages.append(
                {
                    "page_number": index,
                    "label": (
                        reader.page_labels[index - 1] if len(reader.page_labels) >= index else None
                    ),
                    "rotation": PdfValueFormatter.normalize(getattr(page, "rotation", None)),
                    "mediabox": PdfValueFormatter.normalize(getattr(page, "mediabox", None)),
                    "cropbox": PdfValueFormatter.normalize(getattr(page, "cropbox", None)),
                    "trimbox": PdfValueFormatter.normalize(getattr(page, "trimbox", None)),
                    "bleedbox": PdfValueFormatter.normalize(getattr(page, "bleedbox", None)),
                    "artbox": PdfValueFormatter.normalize(getattr(page, "artbox", None)),
                    "annotations": PdfValueFormatter.normalize(getattr(page, "annotations", None)),
                    "images": images,
                }
            )
        return pages
