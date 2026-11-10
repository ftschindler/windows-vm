#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Run one marked layer of the test suite, on any operating system.

Usage:
  run-tests.py <marker> [extra pytest args...]

The command this builds used to live in the Makefile as

    uvx --with pytest $(uv run .scripts/extract-deps.py skills) pytest -m <marker>

which is three shell features in one line: command substitution, word splitting,
and a `$(...)` that `make` hands to `/bin/sh`. None of those exist on a Windows
shell, and the same line was duplicated in a pre-commit hook behind `bash -c`.
Doing the composition in Python instead gives make, the hook and CI one code path
that behaves the same everywhere, and leaves `make` an optional convenience
rather than a requirement.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACT_DEPS = REPO_ROOT / ".scripts" / "extract-deps.py"

# Both trees are scanned, because the tests import from both: a test of a skill's
# script needs that skill's dependencies, and a test of a guard under .scripts/
# needs the guard's. Nothing here has a lockfile, so a PEP 723 header is the only
# place either of them says what it needs.
SCANNED = (REPO_ROOT / "skills", REPO_ROOT / ".scripts")


def script_dependencies() -> list[str]:
    """The union of every script's PEP 723 dependencies, as `--with` flags.

    Imported from `extract-deps.py` rather than shelled out to, because a
    subprocess here would be the command substitution this script exists to
    remove. The file name is not an identifier, so it is loaded by path.
    """
    spec = importlib.util.spec_from_file_location("extract_deps", EXTRACT_DEPS)
    if spec is None or spec.loader is None:  # pragma: no cover - a broken checkout
        sys.exit(f"run-tests: cannot load {EXTRACT_DEPS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    deps: set[str] = set()
    for tree in SCANNED:
        for script in tree.glob("**/*"):
            if script.is_file():
                try:
                    deps.update(module.extract_deps(script))
                except (UnicodeDecodeError, PermissionError):
                    pass
    flags: list[str] = []
    for name in sorted(deps):
        flags += ["--with", name]
    return flags


def main() -> int:
    if not sys.argv[1:]:
        sys.exit("usage: run-tests.py <marker> [pytest args...]")
    marker, *extra = sys.argv[1:]
    command = [
        "uvx",
        "--with",
        "pytest",
        *script_dependencies(),
        "pytest",
        "-m",
        marker,
        # A marker this file does not declare in pytest.toml is a typo that would
        # otherwise select nothing and look like a clean run. With this, pytest
        # refuses it by name. Collecting no tests is caught separately: pytest
        # exits 5 for an empty selection, which is returned as the failure it is.
        "--strict-markers",
        *(extra or ["-v"]),
    ]
    print(" ".join(command), file=sys.stderr)
    # `cwd` is pinned to the repo root so the invocation is the same whether a
    # Makefile, a pre-commit hook or a CI step called it: pytest.toml's
    # `testpaths` is relative, and a hook may run from anywhere.
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
