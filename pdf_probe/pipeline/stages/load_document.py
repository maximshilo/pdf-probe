"""Opens the source PDF and decrypts it if necessary."""

from __future__ import annotations

from pypdf import PdfReader

from pdf_probe.errors import DecryptionError
from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.values import PdfValueFormatter


class LoadDocumentStage(Stage):
    """Opens the PDF with pypdf and decrypts it if it's encrypted."""

    def get_stage_name(self) -> str:
        return "Document Loading"

    def get_action_string(self) -> str:
        return "Loading document"

    def run(self, data: PipelineData) -> None:
        config = self._context.config
        reader = PdfReader(str(config.pdf_path), strict=False)

        if reader.is_encrypted:
            if reader.decrypt(config.password) == 0:
                raise DecryptionError(
                    "The PDF is encrypted and could not be decrypted with the "
                    "provided password.",
                    component=self.name,
                )

        data.reader = reader
        data.is_encrypted = reader.is_encrypted
        data.password_used = bool(config.password)
        data.page_count = len(reader.pages)
        data.pdf_header = reader.pdf_header
        data.user_access_permissions = PdfValueFormatter.normalize(reader.user_access_permissions)
        self._logger.debug(f"Loaded document: {data.page_count} page(s)")
