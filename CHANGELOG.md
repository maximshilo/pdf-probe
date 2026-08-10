# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.1] - 2026-08-10

### Fixed

- `--full` no longer hangs on multi-page PDFs whose objects are shared across pages (e.g. fonts, resource dictionaries). `PdfValueFormatter.normalize` tracked visited objects per traversal path, so an object reached again via a sibling path (rather than back through its own ancestors) was re-expanded instead of short-circuited, causing traversal to blow up combinatorially once the prior depth-accounting fix let it reach that shared structure.

## [0.2.0] - 2026-08-10

### Added

- A 30-second timeout on every external tool invocation (`pdfinfo`, `pdftotext`, `qpdf`), so a hung process against a malformed or adversarial PDF can no longer block a run indefinitely.

### Fixed

- `--password` is now forwarded to `pdfinfo`, `pdftotext`, and `qpdf`, so encrypted PDFs work correctly with `--full` and with the `pdftotext` text-extraction fallback (previously only `pypdf` itself received the password).
- `--verbose` output no longer leaks the PDF password — external tool commands are redacted before being logged.

## [0.1.0]

Initial release.
