# Architecture

This document describes how `pdf_probe` is put together internally. It's aimed at contributors; for installation and usage, see the [README](../README.md).

## Overview

`pdf_probe` is built as an object-oriented, stage-based pipeline rather than one large script. A single run:

1. Parses CLI arguments into an immutable `Config` (`pdf_probe/cli.py`, `pdf_probe/config.py`).
2. Builds an `ExecutionContext` bundling the config, logger, error handler, and artifact manager (`pdf_probe/context.py`).
3. Runs a fixed, ordered `Pipeline` of `Stage` objects against a shared `PipelineData` object (`pdf_probe/pipeline/`).
4. Writes the resulting Markdown report to disk via the `ArtifactManager` (`pdf_probe/artifacts.py`).

`Application` (`pdf_probe/application.py`) drives steps 2–4 and enforces the CLI's I/O contract: on success, print only the output path to stdout and return `0`; on failure, print a diagnostic to stderr and return `1`. `build_report()` in the same module is a stable entry point for callers that want the rendered Markdown directly, without writing it to disk or going through the CLI.

## Directory map

```
pdf_probe/
├── cli.py                       # argparse: CLI args -> Config
├── application.py               # Application: validate input, run pipeline, write output
├── config.py                    # Config: immutable per-run configuration
├── context.py                   # ExecutionContext: config + logger + error handler + artifacts
├── errors.py                    # PdfProbeError hierarchy + ErrorHandler
├── logging_.py                  # Logger: thin wrapper around `logging`
├── progress.py                  # ProgressReporter implementations (bar / logging)
├── artifacts.py                 # ArtifactManager: the one place output is written to disk
├── tools.py                     # ExternalTool: invokes pdfinfo/pdftotext/qpdf
├── values.py                    # PdfValueFormatter: normalizes/humanizes extracted values
├── markdown.py                  # MarkdownReport: builds the output document section by section
├── __main__.py                  # `python -m pdf_probe` entry point
└── pipeline/
    ├── pipeline.py              # Pipeline: stage order, execution, error routing
    ├── stage.py                 # Stage: the abstract base every stage implements
    ├── data.py                  # PipelineData: mutable state threaded through the pipeline
    └── stages/
        ├── load_document.py     # Opens the PDF, decrypts it if needed
        ├── file_inspection.py   # Filesystem facts: size, SHA-256, mtime
        ├── text_extraction.py   # Per-page text via pypdf, falling back to pdftotext
        ├── metadata.py          # Document info dict, XMP, catalog/trailer
        ├── outline.py           # Bookmarks and named destinations
        ├── embedded_content.py  # Attachments and form fields
        ├── page_inspection.py   # Per-page boxes, images, annotations
        ├── external_tools.py    # Runs pdfinfo / qpdf to enrich the full report
        ├── slim_report.py       # Terminal stage: builds the default report
        └── full_report.py       # Terminal stage: builds the --full report

tests/
├── conftest.py               # SamplePdfFactory: real, on-disk PDF fixtures
├── test_infrastructure.py    # Unit tests: Logger, ErrorHandler, ExternalTool, Pipeline, progress
├── test_integration.py       # Integration tests: stages against a real PdfReader
├── test_e2e.py               # End-to-end tests: full CLI runs against on-disk PDFs
├── test_markdown_report.py   # Unit tests for MarkdownReport
├── test_value_formatter.py   # Unit tests for PdfValueFormatter
└── framework/
    ├── base.py               # PdfProbeTestCase: shared Logger/ErrorHandler wiring
    ├── unit.py               # UnitTestCase
    ├── integration.py        # IntegrationTestCase: builds ExecutionContext + PipelineData
    ├── e2e.py                # EndToEndTestCase
    └── runner.py             # TestManager: runs each category through pytest
```

## Pipeline & stages

`Pipeline.build()` (`pdf_probe/pipeline/pipeline.py`) assembles the stages in a fixed execution order, chosen for correctness (e.g. the document must be loaded before anything else can run):

```
LoadDocumentStage → FileInspectionStage → TextExtractionStage → MetadataStage
  → OutlineStage → EmbeddedContentStage → PageInspectionStage → ExternalToolsStage
  → SlimReportStage (default) | FullReportStage (--full)
```

This execution order is independent of the *rendered report's* section order, which the terminal report stage (`SlimReportStage` or `FullReportStage`) decides for itself once every extraction stage has finished.

Each stage reads and writes fields on the shared `PipelineData` object and describes itself for progress reporting via two methods:

- `get_stage_name()` — a noun phrase (e.g. `"File Inspection"`) used in `--verbose`'s `"Running stage: ..."` log lines.
- `get_action_string()` — a present-tense phrase (e.g. `"Inspecting file"`) shown in the progress bar.

## Shared infrastructure

### Execution context

`ExecutionContext` (`pdf_probe/context.py`) bundles the `Config`, `Logger`, `ErrorHandler`, and `ArtifactManager` that stages depend on. It's built once per run via `ExecutionContext.create()`, and every stage receives it at construction time instead of a long, unrelated argument list.

### Logging

`Logger` (`pdf_probe/logging_.py`) is a thin, injectable wrapper around the standard library's `logging` module, configured once from `--verbose` (`DEBUG` if set, `INFO` otherwise). Each stage gets its own `Logger.get(type(self).__name__)`, so log lines are automatically attributed to the stage that emitted them (e.g. `pdf_probe.ExternalToolsStage: ...`). Verbose output never touches stdout — pdf-probe's CLI contract reserves stdout for the final report path on success.

### Error handling

`ErrorHandler` (`pdf_probe/errors.py`) reports and formats `PdfProbeError`s uniformly, tagging each with the stage (or test) that raised it. `PdfProbeError` carries a `component`, whether it's `recoverable`, and an optional wrapped `cause`. `ErrorHandler.handling()` is the one place exception-to-log translation happens: a `PdfProbeError` is logged and re-raised unless marked recoverable; any other exception is wrapped in a `StageExecutionError` first. The pipeline runs every stage under `error_handler.handling(stage.name)`.

### Progress reporting

By default, a live progress bar (`ProgressBarReporter`, `pdf_probe/progress.py`) redraws in place on stderr as each stage runs, with an animated `.`/`..`/`...` suffix on the current action, and disappears cleanly once the run finishes. Under `--verbose`, the bar is replaced by `LoggingProgressReporter`, which emits one `DEBUG`-level log line per stage instead (a redrawing bar would just collide with detailed log output). Both fall back to plain, non-animated lines when stderr isn't a terminal. A final summary (`"Pipeline complete: N/N stages succeeded"`) is always logged at `INFO` regardless of which reporter is in use.

### External tools

`ExternalTool` (`pdf_probe/tools.py`) resolves and invokes `pdfinfo`, `pdftotext`, and `qpdf` via `PATH`. A few things worth knowing if you touch this file:

- **Password forwarding**: `password_args()` builds each tool's own password flag (`-upw <password>` for the poppler tools, `--password=<password>` for `qpdf`). Every call site that shells out for an encrypted PDF must include this, or that tool silently fails to decrypt it even though `pypdf` itself has the right password.
- **Timeout**: every invocation runs under a 30-second timeout (`_TIMEOUT_SECONDS`), so a hung or adversarial PDF can't block a run indefinitely. A timeout is logged at `WARNING` (visible without `--verbose`, since it's an anomalous event, unlike a tool simply not being on `PATH`) and reported back as a failed `ToolResult` rather than raised — a stage doesn't fail just because an optional enrichment tool did.
- **Log redaction**: `_redact()` masks password values before any command is logged, so `--verbose` never leaks a PDF password to stderr. Any new log line that includes a full command must go through it.

### Reporting & artifacts

`MarkdownReport` (`pdf_probe/markdown.py`) builds the output document section by section. `PdfValueFormatter` (`pdf_probe/values.py`) normalizes and humanizes raw extracted values (dates, booleans, dictionaries) for display. `ArtifactManager` (`pdf_probe/artifacts.py`) is the one place output is written to disk — today that's exactly one artifact per run (the Markdown report), but funneling every write through it gives future artifact types one consistent place to land.

## Testing

The test suite mirrors the architecture above:

- `tests/framework/` provides `UnitTestCase`, `IntegrationTestCase`, and `EndToEndTestCase` base classes, all wired to the same `Logger`/`ErrorHandler` the application uses, so a test failure is reported through the identical formatting/logging path as a production failure.
- **Unit tests** (`test_infrastructure.py`, `test_markdown_report.py`, `test_value_formatter.py`) exercise a single class or function in isolation.
- **Integration tests** (`test_integration.py`) run one or more stages directly against a real `PdfReader`, skipping the CLI/`Application` layer.
- **End-to-end tests** (`test_e2e.py`) run the full CLI against real, on-disk PDFs built by `SamplePdfFactory` (`tests/conftest.py`).
- `TestManager` (`tests/framework/runner.py`) runs each category through pytest and logs the result — runnable directly as `python -m tests.framework.runner --category <unit|integration|e2e>`.
