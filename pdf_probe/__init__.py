"""pdf-probe: Extract PDF metadata and text with Markdown reports."""

__version__ = "0.2.1"
__author__ = "Maxim Shilo"
__email__ = "maximshilo.dev@gmail.com"

from pdf_probe.application import Application, build_report, main
from pdf_probe.config import Config

__all__ = ["Application", "Config", "build_report", "main", "__version__"]
