"""Base class for integration tests: individual stages against a real PdfReader."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from pdf_probe.config import Config
from pdf_probe.context import ExecutionContext
from pdf_probe.pipeline.data import PipelineData
from tests.framework.base import PdfProbeTestCase


class IntegrationTestCase(PdfProbeTestCase):
    """Tests that exercise one or more `Stage`s directly against a real `PdfReader`.

    Skips the CLI/`Application` layer entirely: builds an `ExecutionContext`
    and `PipelineData` directly so a single stage (or a short, explicit chain
    of stages) can be run and inspected in isolation, the same way the old
    free-function extractors used to be called directly.
    """

    def make_context(
        self, pdf_path: Path, *, password: str = "", full: bool = False
    ) -> ExecutionContext:
        config = Config(
            pdf_path=pdf_path,
            output_path=pdf_path.with_suffix(".md"),
            password=password,
            full=full,
        )
        return ExecutionContext.create(config)

    def load_reader(self, pdf_path: Path, *, password: str = "") -> PdfReader:
        reader = PdfReader(str(pdf_path), strict=False)
        if reader.is_encrypted:
            reader.decrypt(password)
        return reader

    def make_data(self) -> PipelineData:
        return PipelineData()
