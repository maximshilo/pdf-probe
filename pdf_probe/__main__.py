#!/usr/bin/env python3
"""CLI entry point for pdf-probe."""

import sys

from pdf_probe.probe import main

if __name__ == "__main__":
    raise SystemExit(main())
