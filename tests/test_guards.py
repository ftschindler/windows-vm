"""Unit tests for the guards under .scripts/.

Fast and deterministic: no LLM, no network. Each test builds a crafted tree in a
temp directory and points the checker at it, so what is asserted is that the
guard *catches* things - a guard exercised only against a conformant repository
passes just as happily once it has stopped checking anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evidence_check import SCHEMA_VERSION as EVIDENCE_SCHEMA_VERSION
from evidence_check import check_all as evidence_check_all
from evidence_check import kit_files
from evidence_check import sha256_of as evidence_sha256
from kit_layout import check_all, read_frontmatter

pytestmark = pytest.mark.scripts


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill(root: Path, directory: str, *, name: str | None = "x", description: str | None = "What it does.") -> Path:
    lines = ["---"]
    if name is not None:
        lines.append(f"name: {name}")
    if description is not None:
        lines.append(f"description: {description}")
    lines += ["---", "", "# A skill", ""]
    return write(root / "skills" / directory / "SKILL.md", "\n".join(lines))


def rule(root: Path, filename: str, body: str) -> Path:
    return write(root / "rules" / filename, body)


def test_a_conformant_tree_passes(tmp_path: Path):
    skill(tmp_path, "writing", name="writing")
    rule(tmp_path, "writing.md", "---\ndescription: House prose style.\n---\n\n# Writing\n")
    assert check_all(tmp_path) == []


def test_a_skill_whose_name_does_not_match_its_directory_is_caught(tmp_path: Path):
    skill(tmp_path, "writing", name="prose")
    problems = check_all(tmp_path)
    assert len(problems) == 1
    assert "does not match its directory" in problems[0]


def test_a_skill_with_no_description_is_caught(tmp_path: Path):
    skill(tmp_path, "writing", name="writing", description=None)
    assert any("description" in problem for problem in check_all(tmp_path))


def test_a_skill_with_an_empty_description_is_caught(tmp_path: Path):
    skill(tmp_path, "writing", name="writing", description='""')
    assert any("description" in problem for problem in check_all(tmp_path))


def test_a_skill_with_no_frontmatter_at_all_is_caught(tmp_path: Path):
    write(tmp_path / "skills" / "writing" / "SKILL.md", "# A skill with nothing declared\n")
    assert len(check_all(tmp_path)) == 2


def test_unclosed_frontmatter_is_reported_rather_than_ignored(tmp_path: Path):
    write(tmp_path / "skills" / "writing" / "SKILL.md", "---\nname: writing\n\n# Oops\n")
    assert any("never closed" in problem for problem in check_all(tmp_path))


def test_a_directory_under_skills_holding_no_skill_is_caught(tmp_path: Path):
    (tmp_path / "skills" / "halfway").mkdir(parents=True)
    write(tmp_path / "skills" / "halfway" / "references.md", "# Notes\n")
    assert any("nothing here is installable" in problem for problem in check_all(tmp_path))


def test_a_loose_file_directly_under_skills_is_caught(tmp_path: Path):
    skill(tmp_path, "writing", name="writing")
    write(tmp_path / "skills" / "README.md", "# Not a skill\n")
    assert any("no loose files" in problem for problem in check_all(tmp_path))


def test_a_skill_in_a_category_directory_is_accepted(tmp_path: Path):
    """Three levels is allowed, so categorising later needs no migration."""
    skill(tmp_path, "prose/writing", name="writing")
    assert check_all(tmp_path) == []


def test_a_skill_buried_too_deep_to_be_discovered_is_caught(tmp_path: Path):
    skill(tmp_path, "a/b/c/writing", name="writing")
    assert any("deeper than" in problem for problem in check_all(tmp_path))


def test_a_rule_with_no_description_is_caught(tmp_path: Path):
    rule(tmp_path, "writing.md", "# Writing\n\nNo frontmatter, so Copilot never loads it.\n")
    assert any("description" in problem for problem in check_all(tmp_path))


def test_a_rule_whose_name_contradicts_its_filename_is_caught(tmp_path: Path):
    rule(tmp_path, "writing.md", "---\nname: prose\ndescription: House style.\n---\n\n# Writing\n")
    assert any("does not match the filename" in problem for problem in check_all(tmp_path))


def test_a_rule_that_is_not_markdown_is_caught(tmp_path: Path):
    write(tmp_path / "rules" / "writing.txt", "House style.\n")
    assert any("is not one" in problem for problem in check_all(tmp_path))


def test_an_absent_kind_directory_is_not_a_failure(tmp_path: Path):
    """`agents/` arrives when the first agent does, and not before."""
    skill(tmp_path, "writing", name="writing")
    assert check_all(tmp_path) == []


def test_frontmatter_survives_a_description_holding_a_colon(tmp_path: Path):
    path = write(
        tmp_path / "skills" / "writing" / "SKILL.md",
        '---\nname: writing\ndescription: "Use when: a draft reads as promotional."\n---\n\n# Writing\n',
    )
    frontmatter, error = read_frontmatter(path)
    assert error is None
    assert frontmatter["description"].startswith("Use when:")
    assert check_all(tmp_path) == []


# --- the evidence guard -------------------------------------------------


def evidence(root: Path, name: str, files: dict[str, Path], *, outcome: str = "pass") -> Path:
    """Write an evidence file for `name` covering `files`, hashed as they are now."""
    document = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kit": name,
        "files": [
            {"path": path.relative_to(root).as_posix(), "sha256": evidence_sha256(path)}
            for path in sorted(files.values())
        ],
        "recorded": {"at": "2026-01-01T00:00:00Z", "by": "A Contributor <a@example.com>"},
        "runs": [{"prompt": "...", "reply": "...", "assertions": []}],
        "outcome": outcome,
    }
    return write(root / "tests" / "evidence" / f"{name}.json", json.dumps(document, indent=2) + "\n")


def recorded_kit(root: Path, name: str = "writing", **kwargs) -> dict[str, Path]:
    """A conformant skill and rule, with evidence covering both."""
    files = {
        "skill": skill(root, name, name=name),
        "rule": rule(root, f"{name}.md", "---\ndescription: House prose style.\n---\n\n# Writing\n"),
    }
    evidence(root, name, files, **kwargs)
    return files


def test_a_kit_with_matching_evidence_passes(tmp_path: Path):
    recorded_kit(tmp_path)
    assert evidence_check_all(tmp_path) == []


def test_a_kit_with_no_evidence_at_all_is_caught(tmp_path: Path):
    skill(tmp_path, "writing", name="writing")
    problems = evidence_check_all(tmp_path)
    assert any("no evidence" in problem for problem in problems)


def test_a_kit_edited_after_recording_is_caught(tmp_path: Path):
    files = recorded_kit(tmp_path)
    files["skill"].write_text("---\nname: writing\ndescription: Changed.\n---\n", encoding="utf-8")
    problems = evidence_check_all(tmp_path)
    assert any("has changed since the evidence was recorded" in problem for problem in problems)


def test_a_reference_added_after_recording_is_caught(tmp_path: Path):
    """The failure a hash-only check misses: new bytes nobody has tried."""
    recorded_kit(tmp_path)
    write(tmp_path / "skills" / "writing" / "references" / "pace.md", "# Pace\n")
    problems = evidence_check_all(tmp_path)
    assert any("not covered by the evidence" in problem for problem in problems)


def test_evidence_covering_a_file_that_is_gone_is_caught(tmp_path: Path):
    files = recorded_kit(tmp_path)
    files["rule"].unlink()
    problems = evidence_check_all(tmp_path)
    assert any("no longer part of the kit" in problem for problem in problems)


def test_a_recorded_failure_is_committable_and_still_fails_the_check(tmp_path: Path):
    recorded_kit(tmp_path, outcome="fail")
    problems = evidence_check_all(tmp_path)
    assert any("recorded outcome is 'fail'" in problem for problem in problems)


def test_a_skill_and_a_rule_of_the_same_name_are_one_kit(tmp_path: Path):
    files = recorded_kit(tmp_path)
    assert set(kit_files(tmp_path)) == {"writing"}
    assert kit_files(tmp_path)["writing"] == sorted(path.relative_to(tmp_path).as_posix() for path in files.values())


def test_unreadable_evidence_is_reported_rather_than_raised(tmp_path: Path):
    recorded_kit(tmp_path)
    (tmp_path / "tests" / "evidence" / "writing.json").write_text("{not json", encoding="utf-8")
    assert any("not valid JSON" in problem for problem in evidence_check_all(tmp_path))
