"""Extracts embedded attachments and AcroForm field data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class EmbeddedContentStage(Stage):
    """Extracts embedded file attachments and form fields."""

    def get_stage_name(self) -> str:
        return "Attachments and Form Fields"

    def get_action_string(self) -> str:
        return "Reading attachments and form fields"

    def run(self, data: PipelineData) -> None:
        reader = data.reader
        data.attachment_summary = self._summarize_attachments(reader)
        data.form_field_names = self._form_field_names(reader)
        if self._context.config.full:
            data.attachments = self._extract_attachments(reader)
            data.form_fields = self._extract_form_fields(reader)

    @staticmethod
    def _summarize_attachments(reader: PdfReader) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for name, blobs in reader.attachments.items():
            sizes = [len(blob) for blob in blobs]
            summary.append(
                {
                    "name": name,
                    "file_count": len(blobs),
                    "total_bytes": sum(sizes),
                    "sizes": sizes,
                }
            )
        return summary

    @staticmethod
    def _extract_attachments(reader: PdfReader) -> Dict[str, Any]:
        attachments: Dict[str, Any] = {}
        for name, blobs in reader.attachments.items():
            attachments[name] = [PdfValueFormatter.decode_bytes(blob) for blob in blobs]
        return attachments

    @staticmethod
    def _form_field_names(reader: PdfReader) -> List[str]:
        fields = reader.get_fields() or {}
        return sorted(str(name) for name in fields.keys())

    @staticmethod
    def _extract_form_fields(reader: PdfReader) -> Optional[Dict[str, Any]]:
        fields = reader.get_fields()
        if not fields:
            return None
        return PdfValueFormatter.normalize(fields)
