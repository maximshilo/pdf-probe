"""Unit tests for pdf_probe module."""

import pytest
from pathlib import Path
from pdf_probe import probe


class TestMarkdownUtilities:
    """Test markdown utility functions."""

    def test_markdown_escape(self):
        """Test markdown character escaping."""
        assert probe.markdown_escape("hello") == "hello"
        assert probe.markdown_escape("test`backtick") == "test\\`backtick"
        assert probe.markdown_escape("test\\backslash") == "test\\\\backslash"

    def test_markdown_code_block_simple(self):
        """Test markdown code block generation."""
        result = probe.markdown_code_block("print('hello')")
        assert result.startswith("```")
        assert result.endswith("```")
        assert "print('hello')" in result

    def test_markdown_code_block_with_language(self):
        """Test markdown code block with language specification."""
        result = probe.markdown_code_block("print('hello')", "python")
        assert "```python" in result
        assert "print('hello')" in result

    def test_markdown_code_block_none_content(self):
        """Test markdown code block with None content."""
        result = probe.markdown_code_block(None, "text")
        assert "```text" in result


class TestHumanizeScalar:
    """Test scalar value humanization."""

    def test_humanize_none(self):
        """Test humanization of None."""
        assert probe.humanize_scalar(None) is None

    def test_humanize_bool(self):
        """Test humanization of boolean values."""
        assert probe.humanize_scalar(True) == "Yes"
        assert probe.humanize_scalar(False) == "No"

    def test_humanize_number(self):
        """Test humanization of numeric values."""
        assert probe.humanize_scalar(42) == "42"
        assert probe.humanize_scalar(3.14) == "3.14"

    def test_humanize_string(self):
        """Test humanization of strings."""
        assert probe.humanize_scalar("hello") == "hello"
        assert probe.humanize_scalar("  hello  world  ") == "hello world"

    def test_humanize_list(self):
        """Test humanization of lists."""
        result = probe.humanize_scalar([1, 2, 3])
        assert result == "1, 2, 3"

    def test_humanize_dict_xdefault(self):
        """Test humanization of dict with x-default."""
        result = probe.humanize_scalar({"x-default": "value"})
        assert result == "value"


class TestPickFirstValue:
    """Test pick_first_value function."""

    def test_pick_first_non_null_value(self):
        """Test picking the first non-null value."""
        assert probe.pick_first_value(None, "value", "other") == "value"
        assert probe.pick_first_value(None, None, "value") == "value"

    def test_pick_first_all_none(self):
        """Test when all values are None."""
        assert probe.pick_first_value(None, None, None) is None


class TestFormatPageNumbers:
    """Test page number formatting."""

    def test_format_page_numbers_empty(self):
        """Test formatting empty page list."""
        assert probe.format_page_numbers([]) == "None"

    def test_format_page_numbers_single(self):
        """Test formatting single page."""
        assert probe.format_page_numbers([1]) == "1"

    def test_format_page_numbers_multiple(self):
        """Test formatting multiple pages."""
        assert probe.format_page_numbers([1, 2, 3]) == "1, 2, 3"


class TestCountEntries:
    """Test entry counting."""

    def test_count_entries_none(self):
        """Test counting None."""
        assert probe.count_entries(None) == 0

    def test_count_entries_list(self):
        """Test counting list items."""
        assert probe.count_entries([1, 2, 3]) == 3

    def test_count_entries_string(self):
        """Test counting string (non-list iterable)."""
        assert probe.count_entries("hello") == 5



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
