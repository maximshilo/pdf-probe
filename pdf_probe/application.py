"""Wires configuration, execution context, and the pipeline together."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Sequence

from pdf_probe.cli import parse_args
from pdf_probe.config import Config
from pdf_probe.context import ExecutionContext
from pdf_probe.errors import PdfProbeError
from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.pipeline import Pipeline


class Application:
    """Drives one pdf-probe run: validate input, run the pipeline, write output."""

    def __init__(self, config: Config, context: Optional[ExecutionContext] = None) -> None:
        self._config = config
        self._context = context or ExecutionContext.create(config)

    def render_report(self) -> str:
        """Run the pipeline and return the rendered report, without writing it."""
        data = PipelineData()
        Pipeline.build(self._context).execute(data)
        return data.report.render()

    def run(self) -> int:
        """Validate the input, render the report, and write it to disk.

        Mirrors the CLI's contract exactly: on success, prints only the
        output path to stdout and returns 0; on failure, prints a diagnostic
        to stderr and returns 1.
        """
        pdf_path = self._config.pdf_path
        if not pdf_path.exists():
            print(f"PDF not found: {pdf_path}", file=sys.stderr)
            return 1
        if not pdf_path.is_file():
            print(f"Not a file: {pdf_path}", file=sys.stderr)
            return 1

        try:
            report_text = self.render_report()
        except PdfProbeError as exc:
            print(f"Failed to extract PDF data: {exc}", file=sys.stderr)
            return 1

        self._context.artifacts.save_report(report_text, self._config.output_path)
        print(self._config.output_path)
        return 0


def build_report(pdf_path: Path, output_path: Path, password: str, full: bool) -> str:
    """Render a report for `pdf_path` without writing it to disk.

    A stable entry point for callers that want the rendered Markdown
    directly, without going through the CLI.
    """
    config = Config(pdf_path=pdf_path, output_path=output_path, password=password, full=full)
    return Application(config).render_report()


def main(argv: Optional[Sequence[str]] = None) -> int:
    config = parse_args(argv)
    return Application(config).run()
