"""Renders the --full report: raw structured dumps of everything extracted."""

from __future__ import annotations

import json

from pdf_probe.markdown import MarkdownReport
from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class FullReportStage(Stage):
    """Builds the exhaustive report: everything extractable, as raw JSON dumps.

    Runs last, after every extraction stage. Reads the PDF catalog/trailer
    directly from `data.reader` and normalizes them on demand, rather than
    having `LoadDocumentStage` precompute dumps that only this report needs.
    """

    def get_stage_name(self) -> str:
        return "Full Report Generation"

    def get_action_string(self) -> str:
        return "Generating full report"

    def run(self, data: PipelineData) -> None:
        config = self._context.config
        report = data.report
        reader = data.reader

        report.title(f"PDF Full Extraction Report: {MarkdownReport.escape(config.pdf_path.name)}")
        report.paragraph(
            "This report contains everything this environment could extract "
            "directly from the PDF, including structured metadata, low-level "
            "PDF structure dumps, and text content."
        )

        report.bullets(
            "Source File",
            [
                ("Report mode", "`full`"),
                ("Absolute path", f"`{config.pdf_path}`"),
                ("Output Markdown", f"`{config.output_path}`"),
                ("Generated at (UTC)", f"`{data.generated_at}`"),
                ("File size (bytes)", f"`{data.file_info.size}`"),
                ("Last modified (UTC)", f"`{data.file_info.last_modified}`"),
                ("SHA256", f"`{data.file_info.sha256}`"),
            ],
            "No source file details were available.",
        )

        report.bullets(
            "PDF Summary",
            [
                ("PDF header", f"`{data.pdf_header}`"),
                ("Encrypted", f"`{data.is_encrypted}`"),
                ("Number of pages", f"`{data.page_count}`"),
                ("Text extraction source", f"`{data.text_source}`"),
                ("Password supplied", f"`{data.password_used}`"),
                ("User access permissions", f"`{data.user_access_permissions}`"),
            ],
            "No PDF summary data was available.",
        )

        report.heading("Document Information Dictionary")
        report.code_block(self._json(data.metadata), "json")

        report.heading("XMP Metadata")
        if data.xmp_metadata is not None:
            report.code_block(self._json(data.xmp_metadata), "json")
        else:
            report.raw("No XMP metadata packet was found.")

        report.heading("PDF Catalog")
        catalog = PdfValueFormatter.normalize(reader.trailer.get("/Root"))
        report.code_block(self._json(catalog), "json")

        report.heading("PDF Trailer")
        trailer = PdfValueFormatter.normalize(reader.trailer)
        report.code_block(self._json(trailer), "json")

        report.heading("Bookmarks / Outline")
        if data.outline:
            report.code_block(self._json(data.outline), "json")
        else:
            report.raw("No outline entries were found.")

        report.heading("Named Destinations")
        if data.named_destinations:
            report.code_block(self._json(data.named_destinations), "json")
        else:
            report.raw("No named destinations were found.")

        report.heading("Embedded Attachments")
        if data.attachments:
            report.code_block(self._json(data.attachments), "json")
        else:
            report.raw("No embedded attachments were found.")

        report.heading("Form Fields")
        if data.form_fields is not None:
            report.code_block(self._json(data.form_fields), "json")
        else:
            report.raw("No AcroForm fields were found.")

        report.heading("Per-Page Metadata")
        report.code_block(self._json(data.page_metadata), "json")

        report.heading("Text Content")
        report.raw(data.text_content)

        report.heading("Text Content Snapshot")
        report.code_block(self._json(data.text_pages), "json")

        report.heading("External Tool: pdfinfo")
        report.code_block(data.pdfinfo.stdout or data.pdfinfo.stderr or "Tool unavailable.", "text")

        report.heading("External Tool: pdfinfo -meta")
        report.code_block(
            data.pdfinfo_meta.stdout or data.pdfinfo_meta.stderr or "Tool unavailable.", "xml"
        )

        report.heading("External Tool: qpdf --json")
        report.code_block(
            data.qpdf_json.stdout or data.qpdf_json.stderr or "Tool unavailable.", "json"
        )

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)
