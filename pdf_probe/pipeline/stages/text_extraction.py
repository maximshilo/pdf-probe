"""Extracts page text via pypdf, falling back to `pdftotext -layout`."""

from __future__ import annotations

from typing import Any, Dict, List

from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.tools import ExternalTool


class TextExtractionStage(Stage):
    """Extracts text per page, preferring pypdf and falling back to pdftotext."""

    def get_stage_name(self) -> str:
        return "Text Extraction"

    def get_action_string(self) -> str:
        return "Extracting text"

    def run(self, data: PipelineData) -> None:
        reader = data.reader
        pdf_path = self._context.config.pdf_path

        page_texts: List[Dict[str, Any]] = []
        extracted_chunks: List[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text(extraction_mode="layout") or ""
            page_texts.append({"page_number": index, "source": "pypdf", "text": text})
            extracted_chunks.append(text.strip())

        if any(extracted_chunks):
            data.text_source = "pypdf"
            data.text_pages = page_texts
            data.text_content = self._render(page_texts)
            return

        pdftotext = ExternalTool("pdftotext", self._logger)
        password = self._context.config.password
        result = pdftotext.run("-layout", *pdftotext.password_args(password), str(pdf_path), "-")
        if result.succeeded():
            pages = self._split_pdftotext_output(result.stdout)
            data.text_source = "pdftotext"
            data.text_pages = [
                {"page_number": index, "source": "pdftotext", "text": text}
                for index, text in enumerate(pages, start=1)
            ]
            data.text_content = self._render(data.text_pages)
            return

        data.text_source = "pypdf"
        data.text_pages = page_texts
        data.text_content = "_No text extracted from the PDF._"

    @staticmethod
    def _split_pdftotext_output(text: str) -> List[str]:
        pages = text.split("\f")
        while pages and not pages[-1].strip():
            pages.pop()
        return pages or [text]

    @staticmethod
    def _render(page_texts: List[Dict[str, Any]]) -> str:
        if not page_texts:
            return "_No text extracted from the PDF._"
        if all(item.get("page_number") is not None for item in page_texts):
            rendered_pages = []
            for item in page_texts:
                page_text = (item.get("text") or "").strip()
                rendered_pages.append(
                    f"### Page {item['page_number']}\n\n"
                    f"{page_text or '_No text extracted on this page._'}"
                )
            return "\n\n".join(rendered_pages)
        text = "\n\n".join((item.get("text") or "").strip() for item in page_texts).strip()
        return text or "_No text extracted from the PDF._"
