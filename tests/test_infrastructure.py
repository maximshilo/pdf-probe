"""Unit tests for the shared infrastructure: Logger, ErrorHandler, ArtifactManager,
ExternalTool, and Pipeline orchestration (against stub stages)."""

from __future__ import annotations

import logging
import sys
import time
from io import StringIO

import pytest

from pdf_probe.artifacts import ArtifactManager
from pdf_probe.config import Config
from pdf_probe.context import ExecutionContext
from pdf_probe.errors import ErrorHandler, PdfProbeError, StageExecutionError
from pdf_probe.logging_ import Logger, LogLevel
from pdf_probe.pipeline.data import PipelineData
from pdf_probe.pipeline.pipeline import Pipeline
from pdf_probe.pipeline.stage import Stage
from pdf_probe.progress import LoggingProgressReporter, ProgressBarReporter, ProgressReporter
from pdf_probe.tools import ExternalTool
from tests.framework import UnitTestCase


class TestLogger(UnitTestCase):
    def test_get_nests_under_shared_root(self):
        logger = Logger.get("Widget")
        self.assertEqual(logger._logger.name, "pdf_probe.Widget")

    def test_configure_sets_root_level(self):
        Logger.configure(LogLevel.DEBUG)
        self.assertEqual(logging.getLogger("pdf_probe").level, logging.DEBUG)
        Logger.configure(LogLevel.INFO)
        self.assertEqual(logging.getLogger("pdf_probe").level, logging.INFO)


class TestErrorHandler(UnitTestCase):
    def test_handling_reraises_fatal_pdf_probe_error(self):
        handler = ErrorHandler(Logger.get("test"))
        with self.assertRaises(PdfProbeError):
            with handler.handling("Component"):
                raise PdfProbeError("boom")

    def test_handling_wraps_unexpected_exceptions(self):
        handler = ErrorHandler(Logger.get("test"))
        with self.assertRaises(StageExecutionError) as ctx:
            with handler.handling("Component"):
                raise ValueError("kaboom")
        self.assertEqual(ctx.exception.component, "Component")
        self.assertIsInstance(ctx.exception.cause, ValueError)

    def test_recoverable_error_is_suppressed(self):
        handler = ErrorHandler(Logger.get("test"))
        with handler.handling("Component", recoverable=True):
            raise ValueError("shrug")

    def test_component_defaults_to_handling_context(self):
        handler = ErrorHandler(Logger.get("test"))
        error = PdfProbeError("boom")
        with self.assertRaises(PdfProbeError):
            with handler.handling("MyComponent"):
                raise error
        self.assertEqual(error.component, "MyComponent")


class TestArtifactManager(UnitTestCase):
    @pytest.fixture(autouse=True)
    def _inject_tmp_path(self, tmp_path):
        self.tmp_path = tmp_path

    def test_save_writes_content_and_returns_path(self):
        manager = ArtifactManager(Logger.get("test"))
        path = self.tmp_path / "out.md"
        result = manager.save(path, "hello")
        self.assertEqual(result, path)
        self.assertEqual(path.read_text(), "hello")

    def test_save_report_delegates_to_save(self):
        manager = ArtifactManager(Logger.get("test"))
        path = self.tmp_path / "report.md"
        manager.save_report("content", path)
        self.assertEqual(path.read_text(), "content")


class TestExternalTool(UnitTestCase):
    def test_unavailable_tool_reports_unavailable(self):
        tool = ExternalTool("definitely-not-a-real-binary-xyz", Logger.get("test"))
        result = tool.run("--version")
        self.assertFalse(result.available)
        self.assertFalse(result.succeeded())

    def test_available_tool_runs(self):
        tool = ExternalTool("python3", Logger.get("test"))
        result = tool.run("--version")
        self.assertTrue(result.available)
        self.assertTrue(result.succeeded())
        self.assertIn("Python", result.stdout + result.stderr)

    def test_password_args_uses_upw_flag_for_poppler_tools(self):
        self.assertEqual(
            ExternalTool("pdfinfo", Logger.get("test")).password_args("secret"),
            ["-upw", "secret"],
        )
        self.assertEqual(
            ExternalTool("pdftotext", Logger.get("test")).password_args("secret"),
            ["-upw", "secret"],
        )

    def test_password_args_uses_password_flag_for_qpdf(self):
        self.assertEqual(
            ExternalTool("qpdf", Logger.get("test")).password_args("secret"),
            ["--password=secret"],
        )

    def test_password_args_empty_when_no_password(self):
        self.assertEqual(ExternalTool("qpdf", Logger.get("test")).password_args(""), [])

    def test_run_times_out_and_reports_failure_instead_of_hanging(self):
        tool = ExternalTool(sys.executable, Logger.get("test"))
        tool._TIMEOUT_SECONDS = 0.5

        start = time.monotonic()
        result = tool.run("-c", "import time; time.sleep(5)")
        elapsed = time.monotonic() - start

        self.assertTrue(result.available)
        self.assertFalse(result.succeeded())
        self.assertIn("Timed out", result.stderr)
        self.assertLess(elapsed, 4.0)

    def test_redact_masks_upw_password(self):
        command = ["pdfinfo", "-upw", "hunter2", "file.pdf"]
        self.assertEqual(ExternalTool._redact(command), ["pdfinfo", "-upw", "***", "file.pdf"])

    def test_redact_masks_qpdf_password_flag(self):
        command = ["qpdf", "--password=hunter2", "--json", "file.pdf"]
        self.assertEqual(
            ExternalTool._redact(command), ["qpdf", "--password=***", "--json", "file.pdf"]
        )

    def test_redact_leaves_command_without_password_untouched(self):
        command = ["pdfinfo", "file.pdf"]
        self.assertEqual(ExternalTool._redact(command), command)

    def _capture_logs(self) -> "_CapturingHandler":
        Logger.configure(LogLevel.DEBUG)
        self.addCleanup(Logger.configure, LogLevel.INFO)
        handler = _CapturingHandler()
        logger = logging.getLogger("pdf_probe")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        return handler

    def test_timeout_logs_a_warning_without_leaking_the_command(self):
        handler = self._capture_logs()
        tool = ExternalTool(sys.executable, Logger.get("test"))
        tool._TIMEOUT_SECONDS = 0.5

        tool.run("-c", "import time; time.sleep(5)", "-upw", "hunter2")

        warnings = [r for r in handler.records if r.levelno == logging.WARNING]
        self.assertEqual(len(warnings), 1)
        message = warnings[0].getMessage()
        self.assertIn("timed out", message.lower())
        self.assertNotIn("hunter2", message)

    def test_running_line_is_logged_with_password_redacted(self):
        handler = self._capture_logs()
        tool = ExternalTool(sys.executable, Logger.get("test"))

        tool.run("-upw", "hunter2", "--version")

        running_lines = [
            r.getMessage() for r in handler.records if r.getMessage().startswith("Running:")
        ]
        self.assertEqual(len(running_lines), 1)
        self.assertNotIn("hunter2", running_lines[0])
        self.assertIn("-upw ***", running_lines[0])


class _RecordingStage(Stage):
    """A minimal stub stage used only to test `Pipeline` orchestration."""

    def __init__(self, context, stage_name, on_run=None):
        super().__init__(context)
        self._stage_name = stage_name
        self._on_run = on_run

    @property
    def name(self):
        return self._stage_name

    def get_stage_name(self) -> str:
        return self._stage_name

    def get_action_string(self) -> str:
        return self._stage_name

    def run(self, data: PipelineData) -> None:
        data.text_pages.append({"stage": self._stage_name})
        if self._on_run:
            self._on_run(data)


class _CapturingHandler(logging.Handler):
    """Collects emitted records for direct inspection.

    Not `caplog`: `Logger.configure()` sets `propagate = False` on the
    `pdf_probe` logger (so pdf-probe doesn't double-log through a host
    application's root logger), which also means pytest's root-attached
    `caplog` handler never sees these records. Attaching our own handler
    directly to the `pdf_probe` logger sidesteps that entirely.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestPipeline(UnitTestCase):
    @pytest.fixture(autouse=True)
    def _inject_tmp_path(self, tmp_path):
        self.tmp_path = tmp_path

    def _make_context(self, *, verbose: bool = False) -> ExecutionContext:
        config = Config(
            pdf_path=self.tmp_path / "x.pdf", output_path=self.tmp_path / "x.md", verbose=verbose
        )
        return ExecutionContext.create(config)

    def _capture_logs(self) -> _CapturingHandler:
        handler = _CapturingHandler()
        logger = logging.getLogger("pdf_probe")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        return handler

    def test_stages_run_in_order(self):
        context = self._make_context()
        data = PipelineData()
        stages = [_RecordingStage(context, "A"), _RecordingStage(context, "B")]
        Pipeline(stages, context).execute(data)
        self.assertEqual([entry["stage"] for entry in data.text_pages], ["A", "B"])

    def test_stage_error_propagates_as_pdf_probe_error(self):
        context = self._make_context()

        def boom(data):
            raise ValueError("nope")

        stages = [_RecordingStage(context, "Boom", on_run=boom)]
        with self.assertRaises(PdfProbeError):
            Pipeline(stages, context).execute(PipelineData())

    def test_verbose_mode_logs_stage_lines_at_debug_only(self):
        context = self._make_context(verbose=True)
        handler = self._capture_logs()
        stages = [_RecordingStage(context, "A"), _RecordingStage(context, "B")]
        Pipeline(stages, context).execute(PipelineData())

        info_messages = [r.getMessage() for r in handler.records if r.levelno == logging.INFO]
        debug_messages = [r.getMessage() for r in handler.records if r.levelno == logging.DEBUG]

        # Per-stage detail is DEBUG-only; INFO carries just the final summary.
        self.assertTrue(any("Pipeline complete: 2/2" in m for m in info_messages))
        self.assertFalse(any("Running stage" in m or "Stage succeeded" in m for m in info_messages))
        self.assertTrue(
            any("[1/2]" in m and "A" in m and "Running stage" in m for m in debug_messages)
        )
        self.assertTrue(
            any("[1/2]" in m and "A" in m and "Stage succeeded" in m for m in debug_messages)
        )
        self.assertTrue(
            any("[2/2]" in m and "B" in m and "Running stage" in m for m in debug_messages)
        )
        self.assertTrue(
            any("[2/2]" in m and "B" in m and "Stage succeeded" in m for m in debug_messages)
        )

    def test_default_mode_uses_progress_bar_not_the_logger(self):
        context = self._make_context(verbose=False)
        handler = self._capture_logs()
        stages = [_RecordingStage(context, "A")]
        Pipeline(stages, context).execute(PipelineData())

        messages = [r.getMessage() for r in handler.records]
        self.assertFalse(any("Running stage" in m or "Stage succeeded" in m for m in messages))
        self.assertTrue(any("Pipeline complete: 1/1" in m for m in messages))

    def test_default_reporter_is_progress_bar(self):
        context = self._make_context(verbose=False)
        self.assertIsInstance(Pipeline._default_progress_reporter(context), ProgressBarReporter)

    def test_verbose_reporter_is_logging_reporter(self):
        context = self._make_context(verbose=True)
        self.assertIsInstance(Pipeline._default_progress_reporter(context), LoggingProgressReporter)

    def test_drives_progress_reporter_hooks_in_order(self):
        context = self._make_context()
        fake = _FakeProgressReporter()
        stages = [_RecordingStage(context, "A"), _RecordingStage(context, "B")]
        Pipeline(stages, context, progress=fake).execute(PipelineData())

        self.assertEqual(
            fake.calls,
            [
                ("start", 2),
                ("stage_started", 1, 2, "A", "A"),
                ("stage_finished", 1, 2, "A", "A"),
                ("stage_started", 2, 2, "B", "B"),
                ("stage_finished", 2, 2, "B", "B"),
                ("finish", 2),
            ],
        )


class _FakeProgressReporter(ProgressReporter):
    """Records every hook call, in order, for testing `Pipeline` orchestration."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def start(self, total: int) -> None:
        self.calls.append(("start", total))

    def stage_started(self, position: int, total: int, stage_name: str, action: str) -> None:
        self.calls.append(("stage_started", position, total, stage_name, action))

    def stage_finished(self, position: int, total: int, stage_name: str, action: str) -> None:
        self.calls.append(("stage_finished", position, total, stage_name, action))

    def finish(self, total: int) -> None:
        self.calls.append(("finish", total))


class _FakeTtyStream(StringIO):
    def isatty(self) -> bool:
        return True


class TestLoggingProgressReporter(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        Logger.configure(LogLevel.DEBUG)
        self.addCleanup(Logger.configure, LogLevel.INFO)

    def _capture_logs(self):
        handler = _CapturingHandler()
        logger = logging.getLogger("pdf_probe")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        return handler

    def test_logs_use_stage_name_not_action_string(self):
        handler = self._capture_logs()
        reporter = LoggingProgressReporter(Logger.get("test"))

        reporter.stage_started(1, 3, "File Inspection", "Inspecting file")
        reporter.stage_finished(1, 3, "File Inspection", "Inspecting file")

        messages = [r.getMessage() for r in handler.records]
        self.assertIn("[1/3] Running stage: File Inspection", messages)
        self.assertIn("[1/3] Stage succeeded: File Inspection", messages)
        self.assertFalse(any("Inspecting file" in m for m in messages))
        self.assertTrue(all(r.levelno == logging.DEBUG for r in handler.records))


class TestProgressBarReporter(UnitTestCase):
    def test_uses_action_string_not_stage_name(self):
        stream = StringIO()
        reporter = ProgressBarReporter(stream=stream)

        reporter.start(1)
        reporter.stage_finished(1, 1, "File Inspection", "Inspecting file")

        output = stream.getvalue()
        self.assertIn("Inspecting file", output)
        self.assertNotIn("File Inspection", output)

    def test_dots_animate_over_time_on_a_tty(self):
        stream = _FakeTtyStream()
        reporter = ProgressBarReporter(stream=stream, tick_seconds=0.02)

        reporter.start(1)
        reporter.stage_started(1, 1, "Working Stage", "Working")
        deadline = time.monotonic() + 2.0
        while "Working..." not in stream.getvalue() and time.monotonic() < deadline:
            time.sleep(0.01)
        reporter.finish(1)

        output = stream.getvalue()
        self.assertIn("Working.", output)
        self.assertIn("Working..", output)
        self.assertIn("Working...", output)

    def test_animation_thread_stops_after_finish(self):
        stream = _FakeTtyStream()
        reporter = ProgressBarReporter(stream=stream, tick_seconds=0.02)

        reporter.start(1)
        thread = reporter._thread
        self.assertIsNotNone(thread)
        self.assertTrue(thread.is_alive())

        reporter.finish(1)

        self.assertFalse(thread.is_alive())

    def test_non_tty_falls_back_to_plain_lines(self):
        stream = StringIO()
        reporter = ProgressBarReporter(stream=stream)

        reporter.start(2)
        reporter.stage_finished(1, 2, "Stage A", "A")
        reporter.stage_finished(2, 2, "Stage B", "B")
        reporter.finish(2)

        output = stream.getvalue()
        self.assertNotIn("\r", output)
        self.assertIn("0/2 Starting", output)
        self.assertIn("1/2 A", output)
        self.assertIn("2/2 B", output)

    def test_tty_redraws_in_place(self):
        stream = _FakeTtyStream()
        reporter = ProgressBarReporter(stream=stream)

        reporter.start(1)
        reporter.stage_finished(1, 1, "Stage A", "A")

        output = stream.getvalue()
        self.assertIn("\r\x1b[K", output)
        self.assertIn("1/1 A", output)

    def test_finish_clears_the_line_instead_of_leaving_the_bar_visible(self):
        stream = _FakeTtyStream()
        reporter = ProgressBarReporter(stream=stream)

        reporter.start(1)
        reporter.stage_finished(1, 1, "Stage A", "A")
        before_finish = stream.getvalue()
        reporter.finish(1)
        after_finish = stream.getvalue()

        # finish() appends exactly one more clear sequence and nothing else -
        # no bar characters, no trailing newline pushing past the cleared line.
        self.assertEqual(after_finish, before_finish + "\r\x1b[K")

    def test_bar_fill_reflects_progress(self):
        stream = StringIO()
        reporter = ProgressBarReporter(stream=stream, width=10)

        reporter.start(10)
        reporter.stage_finished(5, 10, "Halfway Stage", "Halfway")

        line = stream.getvalue().strip().splitlines()[-1]
        self.assertIn("[#####-----] 5/10 Halfway", line)
