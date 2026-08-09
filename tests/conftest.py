"""Shared fixtures: real, on-disk PDFs built with pypdf for end-to-end tests."""

from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

PAGE_TEXTS = ["Page one content.", "Page two content."]
BOOKMARK_TITLE = "Chapter 1"
ATTACHMENT_NAME = "notes.txt"
ATTACHMENT_DATA = b"Sample attachment content for e2e tests."
ENCRYPTED_PASSWORD = "secret123"


def _add_text_page(writer: PdfWriter, font_ref, text: str) -> None:
    page = writer.add_blank_page(width=200, height=100)

    font_dict = DictionaryObject()
    font_dict[NameObject("/F1")] = font_ref
    resources = DictionaryObject()
    resources[NameObject("/Font")] = font_dict
    page[NameObject("/Resources")] = resources

    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 14 Tf 10 50 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def _build_writer() -> PdfWriter:
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

    for text in PAGE_TEXTS:
        _add_text_page(writer, font_ref, text)

    writer.add_metadata(
        {
            "/Title": "E2E Sample PDF",
            "/Author": "pdf-probe test suite",
            "/Subject": "End-to-end fixture",
            "/Keywords": "test, pdf-probe, e2e",
        }
    )
    writer.add_outline_item(BOOKMARK_TITLE, 0)
    writer.add_attachment(ATTACHMENT_NAME, ATTACHMENT_DATA)
    return writer


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    _build_writer().write(path)
    return path


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    writer = _build_writer()
    writer.encrypt(ENCRYPTED_PASSWORD)
    path = tmp_path / "encrypted.pdf"
    writer.write(path)
    return path
