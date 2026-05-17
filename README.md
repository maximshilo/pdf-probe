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

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for the full license text.
