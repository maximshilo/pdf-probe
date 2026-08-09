"""End-to-end tests: run the real pipeline against real, on-disk PDFs."""

import hashlib
import sys
from pathlib import Path

import pytest

from pdf_probe import build_report, probe
from tests.conftest import ATTACHMENT_NAME, BOOKMARK_TITLE, ENCRYPTED_PASSWORD, PAGE_TEXTS


def sha256sum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestBuildReportSlim:
    def test_contains_expected_content(self, sample_pdf, tmp_path):
        output_path = tmp_path / "sample.md"
        report = build_report(sample_pdf, output_path, password="", full=False)

        assert "E2E Sample PDF" in report
        assert "pdf-probe test suite" in report
        for text in PAGE_TEXTS:
            assert text in report
        assert "Number of pages" in report and "`2`" in report
        assert sha256sum(sample_pdf) in report
        assert BOOKMARK_TITLE in report
        assert ATTACHMENT_NAME in report


class TestBuildReportFull:
    def test_contains_raw_dumps(self, sample_pdf, tmp_path):
        output_path = tmp_path / "sample.full.md"
        report = build_report(sample_pdf, output_path, password="", full=True)

        assert "## Document Information Dictionary" in report
        assert "## PDF Catalog" in report
        assert "## Embedded Attachments" in report
        assert ATTACHMENT_NAME in report
        assert "## Per-Page Metadata" in report
        assert "mediabox" in report.lower()


class TestMainCli:
    def test_writes_default_output_path_slim(self, sample_pdf, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["pdf-probe", str(sample_pdf)])

        exit_code = probe.main()

        expected_output = sample_pdf.with_suffix(".md")
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == str(expected_output)
        assert expected_output.exists()
        assert "E2E Sample PDF" in expected_output.read_text()

    def test_writes_default_output_path_full(self, sample_pdf, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["pdf-probe", str(sample_pdf), "--full"])

        exit_code = probe.main()

        expected_output = sample_pdf.with_suffix(".full.md")
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == str(expected_output)
        assert expected_output.exists()
        assert "## Document Information Dictionary" in expected_output.read_text()


class TestMainCliEncrypted:
    def test_wrong_password_fails(self, encrypted_pdf, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["pdf-probe", str(encrypted_pdf)])

        exit_code = probe.main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert captured.err.strip() != ""
        assert not encrypted_pdf.with_suffix(".md").exists()

    def test_correct_password_succeeds(self, encrypted_pdf, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv", ["pdf-probe", str(encrypted_pdf), "--password", ENCRYPTED_PASSWORD]
        )

        exit_code = probe.main()

        expected_output = encrypted_pdf.with_suffix(".md")
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == str(expected_output)
        content = expected_output.read_text()
        assert "Password supplied: Yes" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
