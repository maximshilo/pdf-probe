"""Integration tests: exercise the pipeline's stages directly against real PDFs,
without going through the CLI or report rendering."""

from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from pdf_probe.errors import PdfProbeError
from pdf_probe.pipeline.pipeline import Pipeline
from pdf_probe.pipeline.stages.external_tools import ExternalToolsStage
from pdf_probe.pipeline.stages.metadata import MetadataStage
from pdf_probe.pipeline.stages.outline import OutlineStage
from pdf_probe.pipeline.stages.page_inspection import PageInspectionStage
from pdf_probe.pipeline.stages.text_extraction import TextExtractionStage
from pdf_probe.tools import ExternalTool, ToolResult
from tests.conftest import SamplePdfFactory
from tests.framework import IntegrationTestCase


class TestPipelineSlim(IntegrationTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf):
        self.sample_pdf = sample_pdf

    def _run(self, *, password: str = "", full: bool = False):
        context = self.make_context(self.sample_pdf, password=password, full=full)
        data = self.make_data()
        Pipeline.build(context).execute(data)
        return data

    def test_core_fields(self):
        data = self._run()

        self.assertEqual(data.page_count, 2)
        self.assertFalse(data.is_encrypted)
        self.assertEqual(data.text_source, "pypdf")
        self.assertEqual(
            data.file_info.sha256, hashlib.sha256(self.sample_pdf.read_bytes()).hexdigest()
        )
        self.assertEqual(data.metadata["/Title"], "E2E Sample PDF")
        self.assertEqual(data.metadata["/Author"], "pdf-probe test suite")
        self.assertIsNone(data.xmp_metadata)

    def test_outline_and_attachments(self):
        data = self._run()

        self.assertEqual(len(data.outline), 1)
        self.assertEqual(data.outline[0]["title"], SamplePdfFactory.BOOKMARK_TITLE)

        self.assertEqual(
            data.attachment_summary,
            [
                {
                    "name": SamplePdfFactory.ATTACHMENT_NAME,
                    "file_count": 1,
                    "total_bytes": len(SamplePdfFactory.ATTACHMENT_DATA),
                    "sizes": [len(SamplePdfFactory.ATTACHMENT_DATA)],
                }
            ],
        )
        self.assertEqual(data.form_field_names, [])

    def test_full_only_fields_stay_empty(self):
        data = self._run(full=False)

        self.assertIsNone(data.attachments)
        self.assertIsNone(data.form_fields)
        self.assertIsNone(data.named_destinations)
        self.assertIsNone(data.page_metadata)


class TestPipelineFull(IntegrationTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf):
        self.sample_pdf = sample_pdf

    def test_full_only_fields_populated(self):
        context = self.make_context(self.sample_pdf, full=True)
        data = self.make_data()
        Pipeline.build(context).execute(data)

        self.assertEqual(
            data.attachments[SamplePdfFactory.ATTACHMENT_NAME][0]["text"],
            SamplePdfFactory.ATTACHMENT_DATA.decode(),
        )
        self.assertIsNone(data.form_fields)
        self.assertEqual(len(data.page_metadata), 2)
        self.assertEqual(data.page_metadata[0]["mediabox"], [0.0, 0.0, 200, 100])


class TestPipelineEncrypted(IntegrationTestCase):
    @pytest.fixture(autouse=True)
    def _inject(self, encrypted_pdf):
        self.encrypted_pdf = encrypted_pdf

    def test_wrong_password_raises(self):
        context = self.make_context(self.encrypted_pdf, password="wrong")
        with self.assertRaises(PdfProbeError):
            Pipeline.build(context).execute(self.make_data())

    def test_correct_password_decrypts(self):
        context = self.make_context(
            self.encrypted_pdf, password=SamplePdfFactory.ENCRYPTED_PASSWORD
        )
        data = self.make_data()
        Pipeline.build(context).execute(data)

        self.assertTrue(data.is_encrypted)
        self.assertTrue(data.password_used)
        self.assertEqual(data.page_count, 2)


class TestIndividualStages(IntegrationTestCase):
    """Lower-level stages, run directly against a real `PdfReader`."""

    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf):
        self.sample_pdf = sample_pdf

    def _loaded_data(self):
        data = self.make_data()
        data.reader = self.load_reader(self.sample_pdf)
        return data

    def test_page_inspection_overview(self):
        context = self.make_context(self.sample_pdf)
        data = self._loaded_data()

        PageInspectionStage(context).run(data)

        self.assertEqual([page["page_number"] for page in data.page_overview], [1, 2])
        self.assertTrue(all(page["image_count"] == 0 for page in data.page_overview))
        self.assertTrue(all(page["annotation_count"] == 0 for page in data.page_overview))

    def test_metadata_catalog_language_absent(self):
        context = self.make_context(self.sample_pdf)
        data = self._loaded_data()

        MetadataStage(context).run(data)

        self.assertIsNone(data.catalog_language)

    def test_text_extraction_uses_pypdf_source(self):
        context = self.make_context(self.sample_pdf)
        data = self._loaded_data()

        TextExtractionStage(context).run(data)

        self.assertEqual(data.text_source, "pypdf")
        self.assertEqual(
            [item["text"].strip() for item in data.text_pages], SamplePdfFactory.PAGE_TEXTS
        )

    def test_flatten_outline_titles(self):
        context = self.make_context(self.sample_pdf)
        data = self._loaded_data()

        OutlineStage(context).run(data)

        self.assertEqual(data.outline[0]["title"], SamplePdfFactory.BOOKMARK_TITLE)
        self.assertEqual(data.outline[0]["depth"], 0)


class TestExternalToolPasswordForwarding(IntegrationTestCase):
    """Pins that a configured `--password` reaches every external-tool call.

    Mocks `ExternalTool.run` rather than requiring real pdfinfo/pdftotext/qpdf
    binaries, so these stay meaningful in environments (e.g. CI) where those
    tools aren't installed - only the command-line args each stage builds
    matter here, not what a real tool does with them.
    """

    @pytest.fixture(autouse=True)
    def _inject(self, sample_pdf):
        self.sample_pdf = sample_pdf

    @staticmethod
    def _unavailable(*args, **kwargs) -> ToolResult:
        return ToolResult(available=False, command=[])

    def test_external_tools_stage_forwards_password(self):
        context = self.make_context(self.sample_pdf, password="secret123", full=True)
        data = self.make_data()

        with patch.object(ExternalTool, "run", side_effect=self._unavailable) as mock_run:
            ExternalToolsStage(context).run(data)

        calls = [call.args for call in mock_run.call_args_list]
        self.assertEqual(len(calls), 3)  # pdfinfo, pdfinfo -meta, qpdf --json
        for pdfinfo_call in calls[:2]:
            self.assertIn("-upw", pdfinfo_call)
            self.assertEqual(pdfinfo_call[pdfinfo_call.index("-upw") + 1], "secret123")
        self.assertIn("--password=secret123", calls[2])

    def test_text_extraction_fallback_forwards_password_to_pdftotext(self):
        context = self.make_context(self.sample_pdf, password="secret123")
        data = self.make_data()
        data.reader = self.load_reader(self.sample_pdf)
        for page in data.reader.pages:
            page.extract_text = lambda *args, **kwargs: ""

        with patch.object(ExternalTool, "run", side_effect=self._unavailable) as mock_run:
            TextExtractionStage(context).run(data)

        args = mock_run.call_args.args
        self.assertIn("-upw", args)
        self.assertEqual(args[args.index("-upw") + 1], "secret123")
