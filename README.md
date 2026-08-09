# pdf-probe

`pdf-probe` is a command-line tool that inspects a PDF and writes a Markdown report containing extracted text plus document metadata.

By default, it produces a slim, human-readable report with the key document details and full extracted text. With `--full`, it generates an exhaustive report that includes low-level PDF structure, normalized metadata dumps, per-page details, and output from optional external tools when available.

## Features

- Extracts text from each PDF page and writes it into a Markdown report.
- Generates a slim summary report by default.
- Supports a full forensic-style report with raw structured metadata.
- Reads document info, XMP metadata, outline/bookmarks, named destinations, attachments, form fields, and page-level details.
- Computes file details including SHA-256, file size, and modification timestamp.
- Supports encrypted PDFs through the `--password` option.
- Falls back to `pdftotext` if `pypdf` does not extract any text.
- Uses `pdfinfo` and `qpdf` when installed to enrich the full report.

## Requirements

Python dependency:

- `pypdf>=6.11.0`

Optional system tools:

- `pdfinfo`
- `pdftotext`
- `qpdf`

## Installation

Install the Python dependency with pip:

```bash
pip install 'pypdf>=6.11.0'
```

If you want richer extraction in environments that support it, also install the optional command-line tools listed above.

## Usage

Basic usage:

```bash
python3 -m pdf_probe input.pdf
```

Write a full report:

```bash
python3 -m pdf_probe input.pdf --full
```

Choose a custom output path:

```bash
python3 -m pdf_probe input.pdf -o report.md
```

Process an encrypted PDF:

```bash
python3 -m pdf_probe protected.pdf --password secret
```

Command-line options:

- `pdf`: path to the source PDF file.
- `-o, --output`: output Markdown path. Defaults to the input filename with an `.md` extension.
- `--password`: password for encrypted PDFs.
- `--full`: write the exhaustive report instead of the default slim report.
- `-v, --verbose`: enable debug-level logging on stderr (stdout still only ever prints the output path on success).

## Output

### Slim report

The default report includes:

- Source file details and output path.
- Core metadata such as title, author, subject, keywords, creator, producer, and dates.
- Technical summary including page count, encryption status, PDF header, permissions, and XMP presence.
- Extraction notes such as text source, fallback usage, password usage, and text coverage.
- Structure summary covering bookmarks, attachments, form fields, images, and annotations.
- Extracted text content organized by page when available.

### Full report

The `--full` report adds:

- Normalized document information dictionary.
- XMP metadata dump.
- PDF catalog and trailer dumps.
- Full bookmark and named-destination data.
- Embedded attachment details.
- Form field data.
- Per-page metadata including boxes, annotations, and image data.
- Raw text extraction snapshot.
- External tool output from `pdfinfo`, `pdfinfo -meta`, and `qpdf --json` when available.

## Notes

- If the PDF file does not exist or is not a regular file, the script exits with an error.
- If an encrypted PDF cannot be decrypted with the supplied password, the script exits with an error.
- The script prints the generated Markdown file path to standard output on success.

## Architecture

`pdf_probe` is built as an object-oriented pipeline rather than one large script:

- **Pipeline & stages** (`pdf_probe/pipeline/`): a `Pipeline` runs an ordered list of `Stage` objects — `LoadDocumentStage`, `FileInspectionStage`, `TextExtractionStage`, `MetadataStage`, `OutlineStage`, `EmbeddedContentStage`, `PageInspectionStage`, `ExternalToolsStage`, and a terminal `SlimReportStage`/`FullReportStage` chosen by `--full`. Each stage reads and writes fields on a shared `PipelineData` object, and describes itself for progress reporting via two methods: `get_stage_name()`, a noun phrase (e.g. "File Inspection") used in `--verbose`'s "Running stage: ..." log lines, and `get_action_string()`, a present-tense phrase (e.g. "Inspecting file") shown in the progress bar.
- **Progress reporting** (`pdf_probe/progress.py`): by default, a live progress bar redraws in place on stderr as each stage runs, with an animated `.`/`..`/`...` suffix on the current action, and disappears cleanly once the run finishes. Under `--verbose`, the bar is replaced by one DEBUG-level log line per stage instead (a redrawing bar would just collide with detailed log output). Both fall back to plain, non-animated lines when stderr isn't a terminal.
- **Logging** (`pdf_probe/logging_.py`): a single `Logger` class (thin wrapper around `logging`), configured once from `--verbose`, used by every stage.
- **Error handling** (`pdf_probe/errors.py`): a single `ErrorHandler` reports and formats failures uniformly, tagging each with the stage (or test) that raised it.
- **Reporting & artifacts** (`pdf_probe/markdown.py`, `pdf_probe/artifacts.py`): `MarkdownReport` builds the output document section by section; `ArtifactManager` is the one place output is written to disk.
- **Shared context** (`pdf_probe/context.py`): an `ExecutionContext` bundles the config, logger, error handler, and artifact manager that stages depend on, built once per run via `ExecutionContext.create()`.

The test suite mirrors this: `tests/framework/` provides `UnitTestCase`, `IntegrationTestCase`, and `EndToEndTestCase` base classes (all wired to the same `Logger`/`ErrorHandler`), plus a `TestManager` that runs each category through pytest and logs the result — runnable directly as `python -m tests.framework.runner`.

## Development

Install the dev dependencies (ideally inside a virtualenv):

```bash
pip install -e ".[dev]"
```

Run the full check suite (tests + lint) with a single command:

```bash
nox
```

This runs pytest with coverage, then `black --check` and `ruff check`, each in its own isolated environment. To auto-fix formatting and lint issues instead:

```bash
nox -s format
```

To run just one category of tests (unit, integration, or end-to-end) through the shared test orchestrator:

```bash
python -m tests.framework.runner --category unit
```

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for the full license text.
