"""The mutable state threaded through the pipeline, stage by stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from pdf_probe.markdown import MarkdownReport
from pdf_probe.tools import ToolResult

UTC = timezone.utc


@dataclass
class FileInfo:
    """Filesystem facts about the source PDF, independent of its contents."""

    size: int
    last_modified: Optional[str]
    sha256: str


@dataclass
class PipelineData:
    """Everything extracted from a single PDF over the life of one pipeline run.

    A typed, explicit replacement for the old free-form `report_data` dict:
    every extraction stage populates the handful of fields it owns, and the
    terminal report stage reads whichever fields its report format needs.
    Fields stay `Optional`/empty by default and are only populated when a
    stage that produces them actually runs (e.g. `*_meta` fields stay `None`
    outside `--full` mode).
    """

    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    report: MarkdownReport = field(default_factory=MarkdownReport)

    # LoadDocumentStage
    reader: Optional[PdfReader] = None
    is_encrypted: Optional[bool] = None
    password_used: Optional[bool] = None
    page_count: Optional[int] = None
    pdf_header: Optional[str] = None
    user_access_permissions: Any = None

    # FileInspectionStage
    file_info: Optional[FileInfo] = None

    # TextExtractionStage
    text_source: Optional[str] = None
    text_pages: List[Dict[str, Any]] = field(default_factory=list)
    text_content: Optional[str] = None

    # MetadataStage
    metadata: Any = None
    xmp_metadata: Optional[Dict[str, Any]] = None
    catalog_language: Any = None

    # OutlineStage
    outline: List[Dict[str, Any]] = field(default_factory=list)
    named_destinations_count: int = 0
    named_destinations: Optional[Dict[str, Any]] = None

    # EmbeddedContentStage
    attachment_summary: List[Dict[str, Any]] = field(default_factory=list)
    attachments: Optional[Dict[str, Any]] = None
    form_field_names: List[str] = field(default_factory=list)
    form_fields: Optional[Dict[str, Any]] = None

    # PageInspectionStage
    page_overview: List[Dict[str, Any]] = field(default_factory=list)
    page_metadata: Optional[List[Dict[str, Any]]] = None

    # ExternalToolsStage
    pdfinfo: Optional[ToolResult] = None
    pdfinfo_fields: Dict[str, str] = field(default_factory=dict)
    pdfinfo_meta: Optional[ToolResult] = None
    qpdf_json: Optional[ToolResult] = None
