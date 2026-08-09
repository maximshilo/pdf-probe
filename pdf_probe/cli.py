"""Command-line argument parsing for pdf-probe."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from pdf_probe.config import Config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract PDF metadata and text and write either a slim human-readable "
            "report or an exhaustive full report in Markdown."
        )
    )
    parser.add_argument("pdf", help="Path to the source PDF file")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output Markdown file (defaults to <pdf>.md)",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Password for encrypted PDFs, if needed",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Write the exhaustive full report instead of the default slim report",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug-level logging on stderr",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> Config:
    args = build_parser().parse_args(argv)

    pdf_path = Path(args.pdf).expanduser().resolve()
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    elif args.full:
        output_path = pdf_path.with_suffix(".full.md")
    else:
        output_path = pdf_path.with_suffix(".md")

    return Config(
        pdf_path=pdf_path,
        output_path=output_path,
        password=args.password,
        full=args.full,
        verbose=args.verbose,
    )
