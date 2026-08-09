"""Shared fixtures: real, on-disk PDFs built with pypdf for integration/e2e tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


class SamplePdfFactory:
    """Builds the real, on-disk PDF fixtures used across the test suites.

    Kept as one class (rather than free functions) so the fixture PDF's shape
    - its pages, bookmark, and attachment - is defined in exactly one place
    with a clear interface, instead of being reconstructed ad hoc per test.
    """

    PAGE_TEXTS = ["Page one content.", "Page two content."]
    BOOKMARK_TITLE = "Chapter 1"
    ATTACHMENT_NAME = "notes.txt"
    ATTACHMENT_DATA = b"Sample attachment content for e2e tests."
    ENCRYPTED_PASSWORD = "secret123"

    def build(self) -> PdfWriter:
        writer = PdfWriter()

        font = DictionaryObject()
        font.update(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)

        for text in self.PAGE_TEXTS:
            self._add_text_page(writer, font_ref, text)

        writer.add_metadata(
            {
                "/Title": "E2E Sample PDF",
                "/Author": "pdf-probe test suite",
                "/Subject": "End-to-end fixture",
                "/Keywords": "test, pdf-probe, e2e",
            }
        )
        writer.add_outline_item(self.BOOKMARK_TITLE, 0)
        writer.add_attachment(self.ATTACHMENT_NAME, self.ATTACHMENT_DATA)
        return writer

    def write(self, path: Path) -> Path:
        self.build().write(path)
        return path

    def write_encrypted(self, path: Path, password: str = ENCRYPTED_PASSWORD) -> Path:
        writer = self.build()
        writer.encrypt(password)
        writer.write(path)
        return path

    @staticmethod
    def _add_text_page(writer: PdfWriter, font_ref: object, text: str) -> None:
        page = writer.add_blank_page(width=200, height=100)

        font_dict = DictionaryObject()
        font_dict[NameObject("/F1")] = font_ref
        resources = DictionaryObject()
        resources[NameObject("/Font")] = font_dict
        page[NameObject("/Resources")] = resources

        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 14 Tf 10 50 Td ({text}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)


@pytest.fixture
def pdf_factory() -> SamplePdfFactory:
    return SamplePdfFactory()


@pytest.fixture
def sample_pdf(tmp_path: Path, pdf_factory: SamplePdfFactory) -> Path:
    return pdf_factory.write(tmp_path / "sample.pdf")


@pytest.fixture
def encrypted_pdf(tmp_path: Path, pdf_factory: SamplePdfFactory) -> Path:
    return pdf_factory.write_encrypted(tmp_path / "encrypted.pdf")
