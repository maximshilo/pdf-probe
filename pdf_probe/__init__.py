"""pdf-probe: Extract PDF metadata and text with Markdown reports."""

__version__ = "0.1.0"
__author__ = "Maxim Shilo"
__email__ = "maximshilo.dev@gmail.com"

from pdf_probe.probe import build_report, main

__all__ = ["build_report", "main", "__version__"]
