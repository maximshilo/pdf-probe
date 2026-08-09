"""Invokes optional external tools (pdfinfo, qpdf) to enrich the report."""

from __future__ import annotations

from typing import Dict

from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.tools import ExternalTool


class ExternalToolsStage(Stage):
    """Runs `pdfinfo` (always) and, in --full mode, `pdfinfo -meta`/`qpdf --json`.

    `pdfinfo`'s parsed fields feed the slim report's Technical Summary and
    Core Metadata sections, so it always runs; the two extra full-mode
    invocations only produce raw dumps that the slim report never shows.
    """

    def get_stage_name(self) -> str:
        return "External Tools"

    def get_action_string(self) -> str:
        return "Running external tools"

    def run(self, data: PipelineData) -> None:
        pdf_path = self._context.config.pdf_path
        pdfinfo = ExternalTool("pdfinfo", self._logger)

        data.pdfinfo = pdfinfo.run(str(pdf_path))
        data.pdfinfo_fields = (
            self._parse_pdfinfo_output(data.pdfinfo.stdout) if data.pdfinfo.succeeded() else {}
        )

        if self._context.config.full:
            data.pdfinfo_meta = pdfinfo.run("-meta", str(pdf_path))
            qpdf = ExternalTool("qpdf", self._logger)
            data.qpdf_json = qpdf.run("--json", str(pdf_path))

    @staticmethod
    def _parse_pdfinfo_output(output: str) -> Dict[str, str]:
        fields: Dict[str, str] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
        return fields
