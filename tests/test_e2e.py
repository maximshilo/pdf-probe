"""End-to-end tests: run the real pipeline against real, on-disk PDFs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pdf_probe import build_report
from tests.conftest import SamplePdfFactory
from tests.framework import EndToEndTestCase


def sha256sum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestBuildReportSlim(EndToEndTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf, tmp_path):
        self.sample_pdf = sample_pdf
        self.tmp_path = tmp_path

    def test_contains_expected_content(self):
        output_path = self.tmp_path / "sample.md"
        report = build_report(self.sample_pdf, output_path, password="", full=False)

        self.assertIn("E2E Sample PDF", report)
        self.assertIn("pdf-probe test suite", report)
        for text in SamplePdfFactory.PAGE_TEXTS:
            self.assertIn(text, report)
        self.assertIn("Number of pages", report)
        self.assertIn("`2`", report)
        self.assertIn(sha256sum(self.sample_pdf), report)
        self.assertIn(SamplePdfFactory.BOOKMARK_TITLE, report)
        self.assertIn(SamplePdfFactory.ATTACHMENT_NAME, report)


class TestBuildReportFull(EndToEndTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf, tmp_path):
        self.sample_pdf = sample_pdf
        self.tmp_path = tmp_path

    def test_contains_raw_dumps(self):
        output_path = self.tmp_path / "sample.full.md"
        report = build_report(self.sample_pdf, output_path, password="", full=True)

        self.assertIn("## Document Information Dictionary", report)
        self.assertIn("## PDF Catalog", report)
        self.assertIn("## Embedded Attachments", report)
        self.assertIn(SamplePdfFactory.ATTACHMENT_NAME, report)
        self.assertIn("## Per-Page Metadata", report)
        self.assertIn("mediabox", report.lower())


class TestMainCli(EndToEndTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf, monkeypatch, capsys):
        self.sample_pdf = sample_pdf
        self.monkeypatch = monkeypatch
        self.capsys = capsys

    def test_writes_default_output_path_slim(self):
        exit_code, out, _err = self.run_cli([str(self.sample_pdf)])

        expected_output = self.sample_pdf.with_suffix(".md")
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip(), str(expected_output))
        self.assertTrue(expected_output.exists())
        self.assertIn("E2E Sample PDF", expected_output.read_text())

    def test_writes_default_output_path_full(self):
        exit_code, out, _err = self.run_cli([str(self.sample_pdf), "--full"])

        expected_output = self.sample_pdf.with_suffix(".full.md")
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip(), str(expected_output))
        self.assertTrue(expected_output.exists())
        self.assertIn("## Document Information Dictionary", expected_output.read_text())

    def test_verbose_logs_to_stderr_only(self):
        exit_code, out, err = self.run_cli([str(self.sample_pdf), "-v"])

        expected_output = self.sample_pdf.with_suffix(".md")
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip(), str(expected_output))
        self.assertIn("Pipeline complete", err)
        self.assertIn("Stage succeeded", err)

    def test_verbose_logs_use_stage_names_not_action_strings(self):
        exit_code, out, err = self.run_cli([str(self.sample_pdf), "-v"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Running stage: File Inspection", err)
        self.assertIn("Stage succeeded: File Inspection", err)
        self.assertNotIn("Running stage: Inspecting file", err)

    def test_default_verbosity_shows_progress_bar_not_debug_detail(self):
        exit_code, out, err = self.run_cli([str(self.sample_pdf)])

        expected_output = self.sample_pdf.with_suffix(".md")
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip(), str(expected_output))
        # capsys isn't a terminal, so the bar falls back to one plain line per
        # event, using each stage's readable action string, rather than
        # redrawing with carriage returns.
        self.assertIn("0/9 Starting", err)
        self.assertIn("1/9 Loading document", err)
        self.assertIn("9/9 Generating slim report", err)
        self.assertNotIn("Running stage", err)
        self.assertNotIn("Stage succeeded", err)
        self.assertIn("Pipeline complete: 9/9 stages succeeded", err)


class TestMainCliEncrypted(EndToEndTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, encrypted_pdf, monkeypatch, capsys):
        self.encrypted_pdf = encrypted_pdf
        self.monkeypatch = monkeypatch
        self.capsys = capsys

    def test_wrong_password_fails(self):
        exit_code, _out, err = self.run_cli([str(self.encrypted_pdf)])

        self.assertEqual(exit_code, 1)
        self.assertNotEqual(err.strip(), "")
        self.assertFalse(self.encrypted_pdf.with_suffix(".md").exists())

    def test_correct_password_succeeds(self):
        exit_code, out, _err = self.run_cli(
            [str(self.encrypted_pdf), "--password", SamplePdfFactory.ENCRYPTED_PASSWORD]
        )

        expected_output = self.encrypted_pdf.with_suffix(".md")
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip(), str(expected_output))
        content = expected_output.read_text()
        self.assertIn("Password supplied: Yes", content)
