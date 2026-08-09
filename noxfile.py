import nox

nox.options.sessions = ["tests", "lint"]


@nox.session
def tests(session):
    session.install("-e", ".[dev]")
    session.run("pytest", "tests/", "--cov=pdf_probe", "--cov-report=term-missing")


@nox.session
def lint(session):
    session.install("-e", ".[dev]")
    session.run("black", "--check", "pdf_probe", "tests")
    session.run("ruff", "check", "pdf_probe", "tests")


@nox.session
def format(session):
    session.install("-e", ".[dev]")
    session.run("black", "pdf_probe", "tests")
    session.run("ruff", "check", "--fix", "pdf_probe", "tests")
