"""Unit tests for MarkdownReport and the slim report's page-number formatting."""

from pdf_probe.markdown import MarkdownReport
from pdf_probe.pipeline.stages.slim_report import SlimReportStage
from tests.framework import UnitTestCase


class TestMarkdownEscape(UnitTestCase):
    def test_plain_text_is_unchanged(self):
        self.assertEqual(MarkdownReport.escape("hello"), "hello")

    def test_backtick_is_escaped(self):
        self.assertEqual(MarkdownReport.escape("test`backtick"), "test\\`backtick")

    def test_backslash_is_escaped(self):
        self.assertEqual(MarkdownReport.escape("test\\backslash"), "test\\\\backslash")


class TestMarkdownCodeBlock(UnitTestCase):
    def test_simple_block(self):
        result = MarkdownReport.format_code_block("print('hello')")
        self.assertTrue(result.startswith("```"))
        self.assertTrue(result.endswith("```"))
        self.assertIn("print('hello')", result)

    def test_block_with_language(self):
        result = MarkdownReport.format_code_block("print('hello')", "python")
        self.assertIn("```python", result)
        self.assertIn("print('hello')", result)

    def test_none_content(self):
        result = MarkdownReport.format_code_block(None, "text")
        self.assertIn("```text", result)

    def test_fence_lengthens_to_avoid_collision_with_content(self):
        result = MarkdownReport.format_code_block("has ``` inside")
        self.assertTrue(result.startswith("````"))


class TestMarkdownReportAssembly(UnitTestCase):
    def test_bullets_renders_only_truthy_values(self):
        report = MarkdownReport()
        report.bullets("Title", [("A", "1"), ("B", None), ("C", "3")], "empty")
        rendered = report.render()
        self.assertIn("## Title", rendered)
        self.assertIn("- A: 1", rendered)
        self.assertIn("- C: 3", rendered)
        self.assertNotIn("- B:", rendered)

    def test_bullets_falls_back_to_empty_message(self):
        report = MarkdownReport()
        report.bullets("Title", [("A", None)], "Nothing here.")
        self.assertIn("Nothing here.", report.render())

    def test_list_section_renders_items(self):
        report = MarkdownReport()
        report.list_section("Items", ["one", "two"], "empty")
        rendered = report.render()
        self.assertIn("- one", rendered)
        self.assertIn("- two", rendered)

    def test_render_ends_with_single_trailing_newline(self):
        report = MarkdownReport()
        report.title("T")
        rendered = report.render()
        self.assertTrue(rendered.endswith("\n"))
        self.assertFalse(rendered.endswith("\n\n"))


class TestSlimReportPageNumberFormatting(UnitTestCase):
    """`_format_page_numbers` is presentation-only, so it lives on the stage
    that renders it rather than on `PdfValueFormatter`."""

    def test_empty_list_reads_none(self):
        self.assertEqual(SlimReportStage._format_page_numbers([]), "None")

    def test_single_page(self):
        self.assertEqual(SlimReportStage._format_page_numbers([1]), "1")

    def test_multiple_pages(self):
        self.assertEqual(SlimReportStage._format_page_numbers([1, 2, 3]), "1, 2, 3")
