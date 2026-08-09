"""Integration tests: exercise individual pdf_probe extraction functions
directly against real PDFs, without going through report rendering."""

import hashlib

import pytest
from pypdf import PdfReader

from pdf_probe import probe
from tests.conftest import ATTACHMENT_DATA, ATTACHMENT_NAME, BOOKMARK_TITLE, PAGE_TEXTS


class TestExtractReportDataSlim:
    def test_core_fields(self, sample_pdf, tmp_path):
        data = probe.extract_report_data(
            sample_pdf, tmp_path / "sample.md", password="", include_full=False
        )

        assert data["page_count"] == 2
        assert data["is_encrypted"] is False
        assert data["text_source"] == "pypdf"
        assert data["sha256"] == hashlib.sha256(sample_pdf.read_bytes()).hexdigest()
        assert data["metadata"]["/Title"] == "E2E Sample PDF"
        assert data["metadata"]["/Author"] == "pdf-probe test suite"
        assert data["xmp_metadata"] is None

    def test_outline_and_attachments(self, sample_pdf, tmp_path):
        data = probe.extract_report_data(
            sample_pdf, tmp_path / "sample.md", password="", include_full=False
        )

        assert len(data["outline"]) == 1
        assert data["outline"][0]["title"] == BOOKMARK_TITLE

        assert data["attachment_summary"] == [
            {
                "name": ATTACHMENT_NAME,
                "file_count": 1,
                "total_bytes": len(ATTACHMENT_DATA),
                "sizes": [len(ATTACHMENT_DATA)],
            }
        ]
        assert data["form_field_names"] == []

    def test_full_only_keys_absent(self, sample_pdf, tmp_path):
        data = probe.extract_report_data(
            sample_pdf, tmp_path / "sample.md", password="", include_full=False
        )

        for key in ("trailer", "catalog", "attachments", "form_fields", "page_metadata"):
            assert key not in data


class TestExtractReportDataFull:
    def test_full_only_keys_present(self, sample_pdf, tmp_path):
        data = probe.extract_report_data(
            sample_pdf, tmp_path / "sample.full.md", password="", include_full=True
        )

        assert data["attachments"][ATTACHMENT_NAME][0]["text"] == ATTACHMENT_DATA.decode()
        assert data["form_fields"] is None
        assert data["catalog"]["value"]["/Type"] == "/Catalog"
        assert len(data["page_metadata"]) == 2
        assert data["page_metadata"][0]["mediabox"] == [0.0, 0.0, 200, 100]


class TestExtractReportDataEncrypted:
    def test_wrong_password_raises(self, encrypted_pdf, tmp_path):
        with pytest.raises(ValueError):
            probe.extract_report_data(
                encrypted_pdf, tmp_path / "out.md", password="wrong", include_full=False
            )

    def test_correct_password_decrypts(self, encrypted_pdf, tmp_path):
        data = probe.extract_report_data(
            encrypted_pdf, tmp_path / "out.md", password="secret123", include_full=False
        )

        assert data["is_encrypted"] is True
        assert data["password_used"] is True
        assert data["page_count"] == 2


class TestIndividualExtractors:
    """Lower-level extractors, called directly against a real PdfReader."""

    def test_extract_page_overview(self, sample_pdf):
        reader = PdfReader(str(sample_pdf))
        overview = probe.extract_page_overview(reader)

        assert [page["page_number"] for page in overview] == [1, 2]
        assert all(page["image_count"] == 0 for page in overview)
        assert all(page["annotation_count"] == 0 for page in overview)

    def test_extract_catalog_language_absent(self, sample_pdf):
        reader = PdfReader(str(sample_pdf))
        assert probe.extract_catalog_language(reader) is None

    def test_extract_text_by_page_uses_pypdf_source(self, sample_pdf):
        reader = PdfReader(str(sample_pdf))
        source, _, page_texts = probe.extract_text_by_page(reader, sample_pdf)

        assert source == "pypdf"
        assert [item["text"].strip() for item in page_texts] == PAGE_TEXTS

    def test_flatten_outline_titles(self, sample_pdf):
        reader = PdfReader(str(sample_pdf))
        entries = probe.flatten_outline(reader.outline)

        assert entries[0]["title"] == BOOKMARK_TITLE
        assert entries[0]["depth"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
