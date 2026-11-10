#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Check that this repository is a well-formed akit source.

akit finds a part by walking fixed directories and reading frontmatter: a skill
is a `SKILL.md`, a rule or an agent is any `*.md`, under `skills/`, `rules/` or
`agents/`. Nothing is registered and nothing is declared, so a part that is
malformed is not rejected anywhere - it is silently not found, or found and
never loaded. That failure reaches a subscriber's machine, not ours, which is
why it is guarded here at commit time.

What this enforces, and why each one is a real failure rather than a preference:

- **A skill directory holds a `SKILL.md`.** A directory under `skills/` that
  does not, and holds no skill beneath it either, is a part nobody will ever
  install.
- **`name` and `description` are present and non-empty.** Both installers skip
  a part missing either, with a warning quiet enough to miss.
- **A skill's `name` equals its directory name.** They are two different
  handles: the directory is what a subscription names, the frontmatter is what
  the part installs as. Where they disagree, `akit add <dir-name>` resolves and
  then lands somewhere else.
- **Nothing sits deeper than three levels.** That is how far discovery walks.
  A part below it exists and is invisible.
- **A rule or agent declares a `description`.** A rule with no frontmatter is
  discovered by GitHub Copilot and never loaded, because `.github/instructions/`
  attaches a file by matching its `description` or its `applyTo` glob.

Usage:
  check_kit_layout.py [path ...]

Given paths, only the parts they belong to are checked, which is what the
pre-commit hook passes. Given none, the whole repository is checked.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# The directories akit looks in, and what it looks for in each. Mirrored from
# DESIGN.md section 5; the harness-specific directories it also reads are not
# listed, because a repository that is its own source must not keep hand-written
# input where its own render output lands.
KINDS = {
    "skills": "SKILL.md",
    "rules": "*.md",
    "agents": "*.md",
}

# `<dir>/<name>/`, `<dir>/<category>/<name>/`, and one category deeper.
MAX_DEPTH = 3


def frontmatter_block(path: Path) -> tuple[str | None, str | None]:
    """Return the raw YAML between a file's opening and closing `---`.

    A missing block and an unreadable one are different answers: the first is a
    file with nothing declared, the second is a file that meant to declare
    something and failed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return None, f"not valid UTF-8 ({exc})"
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index]), None
    return None, "frontmatter opens with `---` and is never closed"


def read_frontmatter(path: Path) -> tuple[dict, str | None]:
    """Return the YAML frontmatter of `path`, and an error message if unreadable.

    A file with no frontmatter block returns an empty mapping rather than an
    error: whether that is allowed is the caller's question, and it differs
    between a skill and a rule.
    """
    block, error = frontmatter_block(path)
    if block is None:
        return {}, error
    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return {}, f"frontmatter is not valid YAML ({exc})"
    if loaded is None:
        return {}, None
    if not isinstance(loaded, dict):
        return {}, "frontmatter is not a mapping"
    return loaded, None


def check_metadata(path: Path, *, root: Path, require_name: str | None) -> list[str]:
    """Check one part's frontmatter. `require_name` is the value `name` must hold."""
    relative = path.relative_to(root).as_posix()
    frontmatter, error = read_frontmatter(path)
    if error:
        return [f"{relative}: {error}"]

    problems = []
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append(f"{relative}: needs a non-empty `description` in its frontmatter")

    name = frontmatter.get("name")
    if require_name is None:
        # A rule or an agent is identified by its filename, so `name` is
        # optional - but a wrong one is worse than none, so it is checked when
        # it is there.
        if name is not None and name != path.stem:
            problems.append(f"{relative}: `name: {name}` does not match the filename `{path.stem}`")
        return problems

    if not isinstance(name, str) or not name.strip():
        problems.append(f"{relative}: needs a non-empty `name` in its frontmatter")
    elif name != require_name:
        problems.append(
            f"{relative}: `name: {name}` does not match its directory `{require_name}`. "
            "The directory is the handle a subscription names; the frontmatter is what it installs as."
        )
    return problems


def depth_of(path: Path, root: Path) -> int:
    """How many levels below `root` the part at `path` sits."""
    return len(path.relative_to(root).parts)


def find_skills(skills_dir: Path) -> list[Path]:
    """Every directory under `skills/` holding a SKILL.md."""
    return sorted(p.parent for p in skills_dir.rglob("SKILL.md") if p.is_file())


def check_skills(root: Path = REPO_ROOT) -> list[str]:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    problems = []
    found = find_skills(skills_dir)
    for skill in found:
        # The SKILL.md itself is one level below the directory, so a skill
        # directory at the depth limit puts its file one past it.
        if depth_of(skill / "SKILL.md", skills_dir) > MAX_DEPTH:
            problems.append(
                f"{(skill / 'SKILL.md').relative_to(root).as_posix()}: "
                f"sits deeper than {MAX_DEPTH} levels under skills/, which is as far as discovery walks"
            )
        problems += check_metadata(skill / "SKILL.md", root=root, require_name=skill.name)

    for entry in sorted(skills_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_file():
            problems.append(
                f"{entry.relative_to(root).as_posix()}: skills/ holds one directory per skill, and no loose files"
            )
        elif not any(skill == entry or entry in skill.parents for skill in found):
            problems.append(
                f"{entry.relative_to(root).as_posix()}: "
                "holds no SKILL.md, and no skill beneath it either, so nothing here is installable"
            )
    return problems


def check_flat_kind(kind: str, root: Path = REPO_ROOT) -> list[str]:
    """Check `rules/` or `agents/`: markdown files, each declaring a description."""
    directory = root / kind
    if not directory.is_dir():
        return []
    problems = []
    for path in sorted(directory.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix != ".md":
            problems.append(f"{relative}: {kind}/ holds markdown files, and this is not one")
            continue
        if depth_of(path, directory) > MAX_DEPTH:
            problems.append(
                f"{relative}: sits deeper than {MAX_DEPTH} levels under {kind}/, which is as far as discovery walks"
            )
        problems += check_metadata(path, root=root, require_name=None)
    return problems


def check_all(root: Path = REPO_ROOT) -> list[str]:
    """Every check this script knows, over one repository tree.

    `root` is a parameter rather than a constant so the tests can point it at a
    crafted tree: a checker exercised only against a conformant repository is
    one that passes just as happily when it has stopped checking anything.
    """
    return check_skills(root) + check_flat_kind("rules", root) + check_flat_kind("agents", root)


def main(argv: list[str]) -> int:
    # The hook passes staged paths, but a part is checked as a whole: a renamed
    # directory and an edited SKILL.md are the same question. Any path inside a
    # kind directory therefore re-checks that kind, which costs milliseconds on
    # a repository of markdown.
    kinds = {part for part in KINDS if any(Path(arg).as_posix().startswith(f"{part}/") for arg in argv)}
    if not argv:
        problems = check_all()
    else:
        problems = []
        if "skills" in kinds:
            problems += check_skills()
        for kind in ("rules", "agents"):
            if kind in kinds:
                problems += check_flat_kind(kind)

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        print(
            f"\n{len(problems)} problem(s). See CONTRIBUTING.md > Authoring a kit for what each kind must carry.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
