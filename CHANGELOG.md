# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-08-10

### Added

- A 30-second timeout on every external tool invocation (`pdfinfo`, `pdftotext`, `qpdf`), so a hung process against a malformed or adversarial PDF can no longer block a run indefinitely.

### Fixed

- `--password` is now forwarded to `pdfinfo`, `pdftotext`, and `qpdf`, so encrypted PDFs work correctly with `--full` and with the `pdftotext` text-extraction fallback (previously only `pypdf` itself received the password).
- `--verbose` output no longer leaks the PDF password — external tool commands are redacted before being logged.

## [0.1.0]

Initial release.
