"""Building a Markdown report document, one section at a time.

Every pipeline stage that contributes to the final report writes through this
class instead of assembling and joining raw string lists by hand.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple


class MarkdownReport:
    """An in-progress Markdown document, built up section by section."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    @staticmethod
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("`", "\\`")

    @staticmethod
    def format_code_block(content: Optional[str], language: str = "") -> str:
        if content is None:
            content = ""
        fence = "```"
        while fence in content:
            fence += "`"
        if language:
            return f"{fence}{language}\n{content.rstrip()}\n{fence}"
        return f"{fence}\n{content.rstrip()}\n{fence}"

    def title(self, text: str) -> "MarkdownReport":
        self._lines.append(f"# {text}")
        self._lines.append("")
        return self

    def heading(self, text: str, level: int = 2) -> "MarkdownReport":
        self._lines.append(f"{'#' * level} {text}")
        self._lines.append("")
        return self

    def paragraph(self, text: str) -> "MarkdownReport":
        self._lines.append(text)
        self._lines.append("")
        return self

    def raw(self, text: str) -> "MarkdownReport":
        self._lines.append(text)
        self._lines.append("")
        return self

    def code_block(self, content: Optional[str], language: str = "") -> "MarkdownReport":
        self._lines.append(self.format_code_block(content, language))
        self._lines.append("")
        return self

    def bullets(
        self,
        title: str,
        items: Sequence[Tuple[str, Optional[str]]],
        empty_message: str,
        *,
        level: int = 2,
    ) -> "MarkdownReport":
        self.heading(title, level=level)
        rendered = [f"- {label}: {value}" for label, value in items if value]
        if rendered:
            self._lines.extend(rendered)
        else:
            self._lines.append(empty_message)
        self._lines.append("")
        return self

    def list_section(
        self, title: str, items: Iterable[str], empty_message: str, *, level: int = 2
    ) -> "MarkdownReport":
        self.heading(title, level=level)
        items = list(items)
        if items:
            self._lines.extend(f"- {item}" for item in items)
        else:
            self._lines.append(empty_message)
        self._lines.append("")
        return self

    def render(self) -> str:
        return "\n".join(self._lines).rstrip() + "\n"
