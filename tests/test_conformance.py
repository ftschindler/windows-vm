"""The kits in this repository are shaped the way akit discovers one.

This layer reads what is committed and nothing else: no network, no agent, no
subprocess. It is the test that fails when a skill is renamed in one place and
not the other, which is a failure that otherwise only appears on somebody else's
machine as a part that silently does not exist.

The checker itself is unit-tested against crafted trees in test_scripts.py. Both
halves are needed: this one would keep passing if the checker stopped checking,
and that one would keep passing while the real kits rotted.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from evidence_check import check_all as evidence_check_all
from evidence_check import kit_files
from kit_layout import REPO_ROOT, check_all, check_flat_kind, check_skills, frontmatter_block

pytestmark = pytest.mark.conformance

CHECK_KIT_LAYOUT = REPO_ROOT / ".scripts" / "check_kit_layout.py"
CHECK_EVIDENCE = REPO_ROOT / ".scripts" / "check_evidence.py"


def test_every_skill_is_discoverable_and_installs_under_its_own_name():
    assert check_skills() == []


def test_every_rule_declares_what_it_is_for():
    assert check_flat_kind("rules") == []


def test_every_agent_declares_what_it_is_for():
    assert check_flat_kind("agents") == []


def test_the_whole_repository_passes_its_own_layout_check():
    assert check_all() == []


def test_the_checker_runs_as_a_command_and_reports_success():
    """The hook and CI run it as a script, so the script's exit code is the contract.

    Calling the functions directly, as the tests above do, would keep passing
    through a broken `main()` - a missing dependency, an argument parsed wrongly,
    a non-zero exit on a clean tree. That is what the hook actually invokes.
    """
    result = subprocess.run(
        [sys.executable, str(CHECK_KIT_LAYOUT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_no_kit_directory_holds_a_part_too_deep_to_find():
    """Three levels is as far as akit walks, and a part below it is invisible.

    Covered by the checks above too, which is deliberate: this states the rule
    by name so a failure says which one broke rather than only where.
    """
    for kind in ("skills", "rules", "agents"):
        directory = REPO_ROOT / kind
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.md"):
            depth = len(path.relative_to(directory).parts)
            assert depth <= 3, f"{path.relative_to(REPO_ROOT)} sits {depth} levels deep"


def test_a_part_is_not_committed_where_a_render_would_land():
    """`.agents/` is output, so a source directory there would be read as input.

    akit subtracts its own render record from discovery, but a *committed*
    `.agents/` predates any record and would be discovered as a hand-written
    part - doubling every kit it holds on the next render.
    """
    rendered = subprocess.run(
        ["git", "ls-files", ".agents"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert rendered.stdout.strip() == "", "`.agents/` is rendered output and must not be committed"


def test_at_least_one_kit_is_shipped():
    """An empty repository passes every check above by having nothing to check.

    That is the state this repository was in for exactly one commit, and a suite
    that stays green through it tells a contributor nothing. Now that a kit is
    here, this is what notices if the directory holding it disappears.
    """
    kits = list((REPO_ROOT / "skills").glob("*/")) + list((REPO_ROOT / "rules").glob("*.md"))
    assert kits, "no skills and no rules: this repository ships nothing"


def reference_files() -> list[Path]:
    return sorted(REPO_ROOT.glob("skills/*/references/*.md"))


def test_a_reference_carries_no_frontmatter():
    """A reference is a digest the skill ships, not a wiki concept it copied.

    The pages these are distilled from are Open Knowledge Format concepts, and
    their frontmatter carries `type`, `tags`, `status` and a `generated` stamp
    that would be false the moment the digest diverges. A reader of the skill
    has no use for any of it, and the model reading the file pays for it.
    """
    for path in reference_files():
        block, error = frontmatter_block(path)
        assert error is None, f"{path.relative_to(REPO_ROOT)}: {error}"
        assert block is None, f"{path.relative_to(REPO_ROOT)}: carries frontmatter the skill has no use for"


def test_every_reference_is_reachable_from_its_skill():
    """A reference nothing links to is one the model never opens.

    The whole reason these ship beside the skill rather than as URLs is that a
    link out to the web does not get followed. An unlinked file is the same
    failure one step earlier.
    """
    for path in reference_files():
        skill = path.parent.parent / "SKILL.md"
        linked = f"references/{path.name}" in skill.read_text(encoding="utf-8")
        assert linked, f"{path.relative_to(REPO_ROOT)} is not linked from {skill.relative_to(REPO_ROOT)}"


def test_every_kit_carries_evidence_matching_the_bytes_committed():
    """A kit nobody has tried, or tried before its last edit, is caught here.

    This layer cannot tell you the run happened; it can only tell you the
    recording still describes what is committed. The run itself is
    `.scripts/record_evidence.py`, on a contributor's own machine.
    """
    assert evidence_check_all() == []


def test_every_kit_has_probes_to_record_against():
    """Probes are the questions; evidence is the answers. A kit needs both."""
    kits = set(kit_files(REPO_ROOT))
    probes = {path.stem for path in (REPO_ROOT / "tests" / "probes").glob("*.json")}
    assert kits - probes == set(), "every kit needs tests/probes/<kit>.json"


def test_the_evidence_checker_runs_as_a_command_and_reports_success():
    result = subprocess.run(
        [sys.executable, str(CHECK_EVIDENCE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_every_skill_script_needs_nothing_but_uv():
    """A skill is installed by copying its directory, so a script has to carry its own dependencies.

    The uv shebang and a PEP 723 header are what make `uv run --script` all a
    subscriber needs.
    """
    scripts = sorted(path for path in REPO_ROOT.glob("skills/*/scripts/*.py"))
    assert scripts, "no skill scripts found"
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env -S uv run --script\n"), f"{path.relative_to(REPO_ROOT)}: no uv shebang"
        assert "# /// script\n" in text, f"{path.relative_to(REPO_ROOT)}: no PEP 723 header"
