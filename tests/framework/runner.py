"""A lightweight orchestrator that runs each test category through pytest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import pytest

from pdf_probe.logging_ import Logger, LogLevel


@dataclass
class TestSuiteResult:
    category: str
    exit_code: int

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


class TestManager:
    """Runs pdf-probe's test categories (unit/integration/e2e) via pytest.

    This is the higher-level orchestrator the three test types share, without
    reimplementing pytest's own collection/execution engine: each category
    still runs as a normal `pytest.main()` invocation, so fixtures, coverage,
    and CI integration are unaffected. What it adds is a single place to run
    one or all categories and get a consistently logged summary through the
    shared `Logger`.
    """

    CATEGORIES: Dict[str, List[str]] = {
        "unit": [
            "tests/test_markdown_report.py",
            "tests/test_value_formatter.py",
            "tests/test_infrastructure.py",
        ],
        "integration": ["tests/test_integration.py"],
        "e2e": ["tests/test_e2e.py"],
    }

    def __init__(self, logger: Optional[Logger] = None) -> None:
        self._logger = logger or Logger.get("TestManager")

    def run(self, categories: Optional[Iterable[str]] = None) -> List[TestSuiteResult]:
        selected = list(categories) if categories else list(self.CATEGORIES)
        results = []
        for name in selected:
            paths = self.CATEGORIES[name]
            self._logger.info(f"Running {name} tests: {' '.join(paths)}")
            exit_code = int(pytest.main([*paths, "-v"]))
            result = TestSuiteResult(category=name, exit_code=exit_code)
            log = self._logger.info if result.passed else self._logger.error
            log(f"{name} tests {'passed' if result.passed else 'FAILED'} (exit code {exit_code})")
            results.append(result)
        return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run pdf-probe's test suites through pytest.")
    parser.add_argument(
        "--category",
        choices=sorted(TestManager.CATEGORIES),
        action="append",
        dest="categories",
        help="Run only this category (may be repeated). Default: run all.",
    )
    args = parser.parse_args(argv)

    Logger.configure(LogLevel.INFO)
    results = TestManager().run(args.categories)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
