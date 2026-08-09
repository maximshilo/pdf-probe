"""Base class for end-to-end tests: the real CLI pipeline against real PDFs."""

from __future__ import annotations

import sys
from typing import List, Tuple

from pdf_probe import application
from tests.framework.base import PdfProbeTestCase


class EndToEndTestCase(PdfProbeTestCase):
    """Tests that run the real pipeline end to end, through `Application`/`main()`.

    Subclasses that use `run_cli` must inject pytest's `monkeypatch`/`capsys`
    fixtures onto `self` via an autouse fixture (`unittest.TestCase` methods
    can't receive fixtures as parameters directly) — see `test_e2e.py`.
    """

    def run_cli(self, argv: List[str]) -> Tuple[int, str, str]:
        self.monkeypatch.setattr(sys, "argv", ["pdf-probe", *argv])
        exit_code = application.main()
        captured = self.capsys.readouterr()
        return exit_code, captured.out, captured.err
