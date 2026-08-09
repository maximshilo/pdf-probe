"""Orchestrating the pdf-probe pipeline: stage order, execution, error routing."""

from __future__ import annotations

from typing import List, Optional

from pdf_probe.context import ExecutionContext
from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.stage import Stage
from pdf_probe.pipeline.stages.embedded_content import EmbeddedContentStage
from pdf_probe.pipeline.stages.external_tools import ExternalToolsStage
from pdf_probe.pipeline.stages.file_inspection import FileInspectionStage
from pdf_probe.pipeline.stages.full_report import FullReportStage
from pdf_probe.pipeline.stages.load_document import LoadDocumentStage
from pdf_probe.pipeline.stages.metadata import MetadataStage
from pdf_probe.pipeline.stages.outline import OutlineStage
from pdf_probe.pipeline.stages.page_inspection import PageInspectionStage
from pdf_probe.pipeline.stages.slim_report import SlimReportStage
from pdf_probe.pipeline.stages.text_extraction import TextExtractionStage
from pdf_probe.progress import LoggingProgressReporter, ProgressBarReporter, ProgressReporter


class Pipeline:
    """A fixed, ordered sequence of stages run against one `PipelineData`.

    Stage *execution* order (this list) is chosen for correctness (e.g. the
    document must be loaded before anything else can run) and is independent
    of the *rendered report's* section order, which the terminal report stage
    decides for itself once every extraction stage has finished.

    Reports progress via a `ProgressReporter`: a live progress bar by default
    (visible at INFO level, no `-v` needed), or one DEBUG-level line per
    stage under `--verbose`, where the bar would otherwise collide with
    detailed log output. A final summary is always logged at INFO regardless
    of which reporter is in use.
    """

    def __init__(
        self,
        stages: List[Stage],
        context: ExecutionContext,
        progress: Optional[ProgressReporter] = None,
    ) -> None:
        self._stages = stages
        self._context = context
        self._progress = progress or self._default_progress_reporter(context)

    @staticmethod
    def _default_progress_reporter(context: ExecutionContext) -> ProgressReporter:
        if context.config.verbose:
            return LoggingProgressReporter(context.logger)
        return ProgressBarReporter()

    @classmethod
    def build(cls, context: ExecutionContext) -> "Pipeline":
        stages: List[Stage] = [
            LoadDocumentStage(context),
            FileInspectionStage(context),
            TextExtractionStage(context),
            MetadataStage(context),
            OutlineStage(context),
            EmbeddedContentStage(context),
            PageInspectionStage(context),
            ExternalToolsStage(context),
        ]
        stages.append(FullReportStage(context) if context.config.full else SlimReportStage(context))
        return cls(stages, context)

    def execute(self, data: PipelineData) -> None:
        total = len(self._stages)
        self._progress.start(total)
        for position, stage in enumerate(self._stages, start=1):
            stage_name = stage.get_stage_name()
            action = stage.get_action_string()
            self._progress.stage_started(position, total, stage_name, action)
            with self._context.error_handler.handling(stage.name):
                stage.run(data)
            self._progress.stage_finished(position, total, stage_name, action)
        self._progress.finish(total)
        self._context.logger.info(f"Pipeline complete: {total}/{total} stages succeeded")
