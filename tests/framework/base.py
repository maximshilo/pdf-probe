"""Base test case wiring the shared Logger/ErrorHandler into every test."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from typing import Iterator

from pdf_probe.errors import ErrorHandler
from pdf_probe.logging_ import Logger


class PdfProbeTestCase(unittest.TestCase):
    """Common base for every pdf-probe test, of any category.

    A `unittest.TestCase` subclass so pytest collects and runs it natively
    (fixtures, parametrization, and coverage all keep working unchanged).
    Wires in the same `Logger`/`ErrorHandler` classes the application uses,
    so a failure during test setup is reported through the identical
    formatting/logging path as a production failure.
    """

    def setUp(self) -> None:
        super().setUp()
        self.logger = Logger.get(type(self).__name__)
        self.error_handler = ErrorHandler(self.logger)

    @contextmanager
    def guarded(self, component: str = "") -> Iterator[None]:
        """Run a block of test code through the shared `ErrorHandler`.

        Failures are logged the same way a pipeline stage failure would be,
        then re-raised so pytest still reports the test as failed normally.
        """
        with self.error_handler.handling(component or type(self).__name__):
            yield
