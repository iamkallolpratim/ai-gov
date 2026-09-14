"""Entrypoint scripts must be runnable the way the container and the README run them.

`python scripts/seed.py` puts `scripts/` on `sys.path`, not the repository root, so
without an explicit bootstrap `import app` fails with `ModuleNotFoundError` — which is
exactly what broke `docker compose up` after migrations had already succeeded.

Each script is executed in a subprocess pointed at a dead database (port 1, refused
immediately), so it gets far enough to prove its imports resolve without ever touching a
real database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted(p.name for p in (REPO_ROOT / "scripts").glob("*.py"))

#: Refused instantly, so nothing can reach a developer's real database.
DEAD_DB = {
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "1",
    "DATABASE_URL": "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing",
    "REDIS_URL": "redis://127.0.0.1:1/0",
    "OPA_URL": "http://127.0.0.1:1",
    "ENVIRONMENT": "local",
}


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(DEAD_DB)
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def assert_imports_resolved(result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    assert "No module named 'app'" not in output, (
        "The script cannot import the application package:\n" + output[-2000:]
    )
    assert "ModuleNotFoundError" not in output, output[-2000:]


def test_scripts_directory_is_not_empty():
    assert SCRIPTS, "no scripts found; this test would silently pass"


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_runs_as_a_file(script: str):
    """How docker/entrypoint.sh and the README invoke them."""
    assert_imports_resolved(run([f"scripts/{script}"]))


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_runs_as_a_module(script: str):
    """`python -m scripts.x`, which resolves sys.path differently."""
    assert_imports_resolved(run(["-m", f"scripts.{script.removesuffix('.py')}"]))


def test_entrypoint_commands_are_covered():
    """Every `python ...` line in the container entrypoint must be tested above."""
    entrypoint = (REPO_ROOT / "docker" / "entrypoint.sh").read_text()
    invoked = {
        line.split("python ")[1].split()[0]
        for line in entrypoint.splitlines()
        if " python " in f" {line.strip()} " and "python " in line
    }
    referenced = {f"scripts/{name}" for name in SCRIPTS}
    unknown = {cmd for cmd in invoked if cmd.startswith("scripts/")} - referenced
    assert not unknown, f"entrypoint runs untested scripts: {unknown}"
