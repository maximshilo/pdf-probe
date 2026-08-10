# Contributing

Thanks for looking at `pdf-probe`. This project is a small, solo-maintained CLI, so the workflow below is intentionally lightweight — but the checks it describes are the ones every change is expected to pass.

For how the codebase itself is organized, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup

Install the package with its dev dependencies, ideally inside a virtualenv:

```bash
pip install -e ".[dev]"
```

This pulls in `pytest`, `pytest-cov`, `black`, `ruff`, and `nox` on top of the runtime dependency (`pypdf`).

Optionally, enable the repo's pre-commit hook to auto-format staged Python files with `black` before every commit:

```bash
git config core.hooksPath .githooks
```

## Running checks

Run the full check suite (tests with coverage, then formatting and lint) with a single command:

```bash
nox
```

This runs `pytest`, then `black --check`, then `ruff check`, each in its own isolated `nox` environment. A pull request should pass all three.

To auto-fix formatting and lint issues instead of just checking them:

```bash
nox -s format
```

## Running a subset of tests

To run just one category of tests (unit, integration, or end-to-end) through the shared test orchestrator:

```bash
python -m tests.framework.runner --category unit
```

Or run pytest directly, as usual:

```bash
pytest tests/test_integration.py -v
```

## Code style

- Formatting: `black`, line length 100 (`pyproject.toml`'s `[tool.black]`).
- Linting: `ruff`, rules `E`, `F`, `W`, `I` (`pyproject.toml`'s `[tool.ruff]`).
- No inline comments unless they capture a non-obvious *why* (a constraint, an invariant, a workaround) — see the existing modules for the expected level of documentation in docstrings vs. comments.
- New behavior should come with test coverage in the matching category (unit for a single class/function, integration for a stage or a few stages against a real `PdfReader`, end-to-end for full CLI runs against on-disk PDFs) — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#testing) for how the test suite is organized.

## Changelog

User-facing changes (bug fixes, new flags, behavior changes) should get an entry under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md), following [Keep a Changelog](https://keepachangelog.com/) conventions.

## Submitting a change

1. Make sure `nox` passes.
2. Update `README.md` if user-facing behavior changed, or `docs/ARCHITECTURE.md` if internal structure changed.
3. Add a `CHANGELOG.md` entry for anything user-visible.
4. Open a pull request describing the change and why it's needed.
