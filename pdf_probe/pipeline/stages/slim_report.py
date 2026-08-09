"""Renders the default, human-readable slim report."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pdf_probe.markdown import MarkdownReport
from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class SlimReportStage(Stage):
    """Builds the default report: a curated summary plus full extracted text.

    Runs last, after every extraction stage. Most of its sections (e.g.
    "Technical Summary") synthesize data from several extraction stages at
    once, so it reads the fully-populated `PipelineData` rather than owning
    any single stage's extracted data.
    """

    _MAX_BOOKMARK_ENTRIES = 15

    def get_stage_name(self) -> str:
        return "Slim Report Generation"

    def get_action_string(self) -> str:
        return "Generating slim report"

    def run(self, data: PipelineData) -> None:
        config = self._context.config
        report = data.report
        file_info = data.file_info
        text_stats = self._collect_text_stats(data.text_pages, data.page_count)

        pages_with_images = [
            p["page_number"] for p in data.page_overview if p.get("image_count", 0) > 0
        ]
        pages_with_annotations = [
            p["page_number"] for p in data.page_overview if p.get("annotation_count", 0) > 0
        ]
        attachment_files = sum(item["file_count"] for item in data.attachment_summary)
        bookmark_highlights = self._summarize_outline_titles(data.outline)

        report.title(f"PDF Report: {MarkdownReport.escape(config.pdf_path.name)}")
        report.paragraph(
            "This is the default slim report: a human-readable summary of the "
            "document and its metadata, followed by the full extracted text."
        )

        report.bullets(
            "Source File",
            [
                ("Report mode", "slim"),
                ("Absolute path", f"`{config.pdf_path}`"),
                ("Output Markdown", f"`{config.output_path}`"),
                ("Generated at (UTC)", f"`{data.generated_at}`"),
                ("File size (bytes)", f"`{file_info.size}`"),
                ("Last modified (UTC)", f"`{file_info.last_modified}`"),
                ("SHA256", f"`{file_info.sha256}`"),
            ],
            "No source file details were available.",
        )

        report.bullets(
            "Core Metadata",
            self._collect_core_metadata(data),
            "No human-meaningful descriptive metadata was found.",
        )

        additional_metadata = self._collect_additional_metadata(data.metadata)
        if additional_metadata:
            report.bullets(
                "Additional Metadata",
                additional_metadata,
                "No additional metadata fields were found.",
            )

        report.bullets(
            "Technical Summary",
            [
                ("PDF header", f"`{data.pdf_header}`"),
                ("Number of pages", f"`{data.page_count}`"),
                ("Encrypted", PdfValueFormatter.humanize(data.is_encrypted)),
                (
                    "User access permissions",
                    PdfValueFormatter.pick_first(data.user_access_permissions, "Unavailable"),
                ),
                ("Tagged PDF", PdfValueFormatter.pick_first(data.pdfinfo_fields.get("Tagged"))),
                ("Optimized", PdfValueFormatter.pick_first(data.pdfinfo_fields.get("Optimized"))),
                ("Page size", PdfValueFormatter.pick_first(data.pdfinfo_fields.get("Page size"))),
                (
                    "XMP metadata packet present",
                    PdfValueFormatter.humanize(data.xmp_metadata is not None),
                ),
            ],
            "No technical summary data was available.",
        )

        report.bullets(
            "Extraction Notes",
            [
                ("Text extraction source", f"`{data.text_source}`"),
                (
                    "Fallback extractor used",
                    PdfValueFormatter.humanize(data.text_source != "pypdf"),
                ),
                ("Password supplied", PdfValueFormatter.humanize(data.password_used)),
                (
                    "Pages with extracted text",
                    (
                        f"`{len(text_stats['pages_with_text'])}/{data.page_count}`"
                        if text_stats["coverage_known"]
                        else "Unknown"
                    ),
                ),
                (
                    "Pages without extracted text",
                    (
                        self._format_page_numbers(text_stats["pages_without_text"])
                        if text_stats["coverage_known"]
                        else "Unknown"
                    ),
                ),
                ("Total extracted characters", f"`{text_stats['total_characters']}`"),
            ],
            "No extraction notes were available.",
        )

        report.bullets(
            "Structure Summary",
            [
                ("Bookmarks", f"`{len(data.outline)}`"),
                ("Named destinations", f"`{data.named_destinations_count}`"),
                ("Embedded attachments", f"`{attachment_files}`"),
                ("Form fields", f"`{len(data.form_field_names)}`"),
                (
                    "Pages with images",
                    f"`{len(pages_with_images)}/{data.page_count}` "
                    f"({self._format_page_numbers(pages_with_images)})",
                ),
                (
                    "Pages with annotations",
                    f"`{len(pages_with_annotations)}/{data.page_count}` "
                    f"({self._format_page_numbers(pages_with_annotations)})",
                ),
            ],
            "No structure summary data was available.",
        )

        if bookmark_highlights:
            report.list_section(
                "Bookmark Highlights",
                bookmark_highlights,
                "No bookmark titles were available.",
            )

        attachment_lines = self._summarize_attachments(data.attachment_summary)
        if attachment_lines:
            report.list_section(
                "Embedded Attachment Names",
                attachment_lines,
                "No embedded attachments were found.",
            )

        if data.form_field_names:
            report.list_section(
                "Form Field Names", data.form_field_names, "No form fields were found."
            )

        report.heading("Text Content")
        report.raw(data.text_content)

    @staticmethod
    def _collect_text_stats(
        page_texts: List[Dict[str, Any]], page_count: Optional[int]
    ) -> Dict[str, Any]:
        pages_with_text: List[int] = []
        pages_without_text: List[int] = []
        total_characters = 0

        for item in page_texts:
            text = (item.get("text") or "").strip()
            page_number = item.get("page_number")
            total_characters += len(text)
            if page_number is None:
                continue
            if text:
                pages_with_text.append(page_number)
            else:
                pages_without_text.append(page_number)

        coverage_known = len(pages_with_text) + len(pages_without_text) == page_count
        return {
            "pages_with_text": pages_with_text,
            "pages_without_text": pages_without_text,
            "coverage_known": coverage_known,
            "total_characters": total_characters,
        }

    @staticmethod
    def _format_page_numbers(page_numbers: List[int]) -> str:
        if not page_numbers:
            return "None"
        return ", ".join(str(number) for number in page_numbers)

    @classmethod
    def _summarize_outline_titles(cls, outline: List[Dict[str, Any]]) -> List[str]:
        entries: List[str] = []
        for item in outline:
            title = (
                PdfValueFormatter.humanize(item.get("title")) if isinstance(item, dict) else None
            )
            if not title:
                continue
            depth = item.get("depth", 0) if isinstance(item, dict) else 0
            entries.append(f"Level {depth}: {title}" if depth else title)
        if len(entries) > cls._MAX_BOOKMARK_ENTRIES:
            omitted = len(entries) - cls._MAX_BOOKMARK_ENTRIES
            entries = entries[: cls._MAX_BOOKMARK_ENTRIES] + [
                f"... {omitted} more bookmark entries omitted"
            ]
        return entries

    @staticmethod
    def _summarize_attachments(attachments: List[Dict[str, Any]]) -> List[str]:
        summaries = []
        for item in attachments:
            plural = "s" if item["file_count"] != 1 else ""
            summaries.append(
                f"{item['name']} ({item['file_count']} file{plural}, "
                f"{item['total_bytes']} bytes)"
            )
        return summaries

    @staticmethod
    def _collect_core_metadata(data: PipelineData) -> List[Tuple[str, str]]:
        items: List[Tuple[str, str]] = []
        metadata = data.metadata
        xmp_metadata = data.xmp_metadata
        pdfinfo_fields = data.pdfinfo_fields

        def add(label: str, *candidates: Any, is_date: bool = False) -> None:
            values = (
                [PdfValueFormatter.format_date(candidate) for candidate in candidates]
                if is_date
                else list(candidates)
            )
            value = PdfValueFormatter.pick_first(*values)
            if value:
                items.append((label, value))

        add(
            "Title",
            PdfValueFormatter.get_mapping_value(metadata, "/Title"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "dc_title"),
            pdfinfo_fields.get("Title"),
        )
        add(
            "Author",
            PdfValueFormatter.get_mapping_value(metadata, "/Author"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "dc_creator"),
            pdfinfo_fields.get("Author"),
        )
        add(
            "Subject",
            PdfValueFormatter.get_mapping_value(metadata, "/Subject"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "dc_description"),
            pdfinfo_fields.get("Subject"),
        )
        add(
            "Keywords",
            PdfValueFormatter.get_mapping_value(metadata, "/Keywords"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "pdf_keywords", "dc_subject"),
            pdfinfo_fields.get("Keywords"),
        )
        add(
            "Language",
            data.catalog_language,
            PdfValueFormatter.get_mapping_value(metadata, "/Lang"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "dc_language"),
            pdfinfo_fields.get("Language"),
        )
        add("Publisher", PdfValueFormatter.get_mapping_value(xmp_metadata, "dc_publisher"))
        add(
            "Identifier",
            PdfValueFormatter.get_mapping_value(xmp_metadata, "xmp_identifier", "dc_identifier"),
        )
        add(
            "Rights",
            PdfValueFormatter.get_mapping_value(
                xmp_metadata, "dc_rights", "xmp_rights_web_statement"
            ),
        )
        add(
            "Creator",
            PdfValueFormatter.get_mapping_value(metadata, "/Creator"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "xmp_creator_tool"),
            pdfinfo_fields.get("Creator"),
        )
        add(
            "Producer",
            PdfValueFormatter.get_mapping_value(metadata, "/Producer"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "pdf_producer"),
            pdfinfo_fields.get("Producer"),
        )
        add(
            "Creation Date",
            PdfValueFormatter.get_mapping_value(metadata, "/CreationDate"),
            PdfValueFormatter.get_mapping_value(xmp_metadata, "xmp_create_date"),
            pdfinfo_fields.get("CreationDate"),
            is_date=True,
        )
        add(
            "Modification Date",
            PdfValueFormatter.get_mapping_value(metadata, "/ModDate"),
            PdfValueFormatter.get_mapping_value(
                xmp_metadata, "xmp_modify_date", "xmp_metadata_date"
            ),
            pdfinfo_fields.get("ModDate"),
            is_date=True,
        )
        return items

    @staticmethod
    def _collect_additional_metadata(metadata: Any) -> List[Tuple[str, str]]:
        if not isinstance(metadata, dict):
            return []
        standard_keys = {
            "/Title",
            "/Author",
            "/Subject",
            "/Keywords",
            "/Lang",
            "/Creator",
            "/Producer",
            "/CreationDate",
            "/ModDate",
        }
        items: List[Tuple[str, str]] = []
        for key in sorted(metadata):
            if key in standard_keys:
                continue
            value = PdfValueFormatter.humanize(metadata[key])
            if value:
                items.append((key.lstrip("/"), value))
        return items
