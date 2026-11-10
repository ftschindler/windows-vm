#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# ///
"""Extract the union of PEP 723 inline dependencies from all skill scripts.

Usage:
  extract-deps.py [skills_dir]

Outputs a space-separated list of unique dependency names (without versions)
suitable for passing to uvx --with.
"""

import re
import sys
from pathlib import Path


def extract_deps(script_path: Path) -> list[str]:
    """Parse PEP 723 metadata from a script and return dependency names."""
    content = script_path.read_text(encoding="utf-8")
    match = re.search(r"# /// script\s*\n(.*?)# ///", content, re.DOTALL)
    if not match:
        return []

    metadata = match.group(1)
    deps_match = re.search(r"dependencies\s*=\s*\[(.*?)\]", metadata, re.DOTALL)
    if not deps_match:
        return []

    deps_str = deps_match.group(1)
    # Extract package names from quoted strings, ignoring version specifiers
    packages = re.findall(r'"([^"]+)"', deps_str)
    # Strip version specifiers: "ruamel.yaml>=0.18" → "ruamel.yaml"
    return [pkg.split(">=")[0].split("==")[0].split("<")[0].strip() for pkg in packages]


def main() -> None:
    skills_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("skills")
    scripts = list(skills_dir.glob("**/*"))

    all_deps: set[str] = set()
    for script in scripts:
        if script.is_file():
            try:
                all_deps.update(extract_deps(script))
            except (UnicodeDecodeError, PermissionError):
                # Skip non-text files or unreadable files
                pass

    # Output as uvx --with flags for direct Makefile consumption
    if all_deps:
        print(" ".join(f"--with {pkg}" for pkg in sorted(all_deps)))


if __name__ == "__main__":
    main()
