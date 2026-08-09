"""Base class for unit tests of small, isolated pdf-probe components."""

from __future__ import annotations

from tests.framework.base import PdfProbeTestCase


class UnitTestCase(PdfProbeTestCase):
    """Tests that exercise a single class or function in isolation, no I/O."""
