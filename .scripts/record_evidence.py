#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Try a kit on a real assistant, and record what it did into tests/evidence/.

This is the layer the other two cannot reach. Conformance reads what is
committed and the script tests read the guards; neither can tell you that a
model, handed this skill, actually follows it. Only asking one can.

It runs against **the assistant you already have authenticated**, rather than
installing one: a CI runner has no credentials, and opencode's free models are
out of quota there, so the run happens here, on your machine, and what CI sees
is the recording. The offline half of the contract is `.scripts/check_evidence.py`, which fails the
build when a kit has changed since its recording.

The agent itself is disposable. HOME and every XDG directory point into a temp
tree holding only the kit under test, so the reply is a reaction to that kit and
not to whatever else is installed on this machine. Your opencode credentials are
the one thing copied in, read-only, and they are never written to the recording.

Usage:
  record_evidence.py <kit> [--model PROVIDER/MODEL] [--keep]

  <kit>      a directory under skills/ or a file stem under rules/
  --model    passed to `opencode run --model`; defaults to opencode's own
  --keep     leave the sandbox on disk and print how to enter it
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBES_DIR = REPO_ROOT / "tests" / "probes"
SANDBOX_DIR = REPO_ROOT / "tests" / "sandbox"
EVIDENCE_DIR = REPO_ROOT / "tests" / "evidence"

SCHEMA_VERSION = 1

# One allowance per probe. A run is a model driving tools, so its duration swings
# with the path it picks; a genuinely stuck one is caught here rather than left.
RUN_TIMEOUT = 600

NOT_PART_OF_A_KIT = ("__pycache__", ".ruff_cache", ".pytest_cache")

# Variables that would point the sandbox back at the real setup. Redirecting HOME
# is not enough on its own: OPENCODE_CONFIG_DIR overrides config lookup outright,
# and PWD arrives stale and absolute, naming the repository under test.
LEAKY_PREFIX = "OPENCODE"
LEAKY_VARS = ("PWD", "OLDPWD")


def fail(message: str) -> None:
    sys.exit(f"record_evidence: {message}")


def kit_parts(name: str) -> tuple[Path | None, Path | None, list[Path]]:
    """Locate a kit by name: its skill directory, its rule file, and every file in it."""
    skill = next((p.parent for p in (REPO_ROOT / "skills").rglob("SKILL.md") if p.parent.name == name), None)
    rule = REPO_ROOT / "rules" / f"{name}.md"
    rule = rule if rule.is_file() else None
    if skill is None and rule is None:
        fail(f"no kit called {name!r} under skills/ or rules/")

    files: list[Path] = []
    if skill is not None:
        files += [
            path
            for path in sorted(skill.rglob("*"))
            if path.is_file() and not any(part in NOT_PART_OF_A_KIT for part in path.parts)
        ]
    if rule is not None:
        files.append(rule)
    return skill, rule, files


def frontmatter_stripped(text: str) -> str:
    """A rule's instruction, without the frontmatter a harness consumes separately."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).lstrip("\n")
    return text


def prepare_machine(kit: str, home: Path, work: Path, env: dict[str, str]) -> None:
    """Let a kit set up the machine its probes expect, through `tests/sandbox/<kit>.py`.

    Added for windows-vm, whose skill drives a VM: its sandbox puts a fake
    VirtualBox on PATH, so a recording needs no running VM. The hook edits `env`
    and the sandbox's files; the kit itself never learns it ran in one.
    """
    path = SANDBOX_DIR / f"{kit}.py"
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location(f"sandbox_{kit.replace('-', '_')}", path)
    if spec is None or spec.loader is None:
        fail(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare(home, work, env)


def build_sandbox(root: Path, skill: Path | None, rule: Path | None) -> tuple[Path, Path, dict[str, str]]:
    """A home holding only this kit, with the real opencode credentials copied in."""
    home = root / "home"
    work = home / "work"
    work.mkdir(parents=True, exist_ok=True)

    env = {k: v for k, v in os.environ.items() if not k.startswith(LEAKY_PREFIX) and k not in LEAKY_VARS}
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "PWD": str(work),
        }
    )

    if skill is not None:
        destination = home / ".agents" / "skills" / skill.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill, destination, ignore=shutil.ignore_patterns(*NOT_PART_OF_A_KIT))

    if rule is not None:
        # A rule applies without being opened, which for opencode means AGENTS.md.
        (work / "AGENTS.md").write_text(frontmatter_stripped(rule.read_text(encoding="utf-8")), encoding="utf-8")

    config_dir = home / ".config" / "opencode"
    config_dir.mkdir(parents=True, exist_ok=True)
    # `opencode run` is non-interactive, so a permission prompt is auto-rejected,
    # and the skills sit outside the working directory.
    (config_dir / "opencode.json").write_text(
        json.dumps(
            {"$schema": "https://opencode.ai/config.json", "permission": {"external_directory": "allow"}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    copy_credentials(home, env)
    return home, work, env


def copy_credentials(home: Path, env: dict[str, str]) -> None:
    """Copy this machine's opencode credentials into the sandbox.

    The whole point of this layer is a run against the assistant you have already
    authenticated, so the sandbox needs the token and nothing else from your real
    profile. It is copied rather than shared, so the run cannot write to it.
    """
    real_data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    for relative in ("opencode/auth.json", "opencode/mcp-auth.json"):
        source = real_data / relative
        if not source.is_file():
            continue
        target = Path(env["XDG_DATA_HOME"]) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o600)
    if not (Path(env["XDG_DATA_HOME"]) / "opencode" / "auth.json").is_file():
        fail(
            "no opencode credentials found. Log in with `opencode auth login` first: "
            "this layer runs against the assistant you have already authenticated."
        )


def assistant_text(stdout: str) -> str:
    """The assistant's own words, out of the JSON event stream."""
    chunks = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = event.get("part", {})
        if event.get("type") == "text" and "text" in part:
            chunks.append(part["text"])
    return "\n".join(chunks)


def scrub(text: str, *, home: Path) -> str:
    """Remove this machine from the recording.

    A transcript carries the sandbox path, which carries the username, and a
    recording committed to a shared repository has no business naming either.
    """
    text = text.replace(str(home), "<sandbox>")
    text = text.replace(str(REPO_ROOT), "<repo>")
    try:
        user = getpass.getuser()
    except (KeyError, OSError):  # pragma: no cover - a machine with no login name
        user = ""
    if user:
        text = re.sub(rf"\b{re.escape(user)}\b", "<user>", text)
    return text


def evaluate(assertion: dict, reply: str) -> tuple[bool, str]:
    """Run one assertion against a reply. Returns the outcome and what was seen."""
    haystack = reply.lower()
    kind = assertion.get("kind")

    if kind == "contains_none":
        hits = [needle for needle in assertion["values"] if needle.lower() in haystack]
        return not hits, ("none present" if not hits else f"present: {', '.join(hits)}")

    if kind == "contains_all":
        missing = [needle for needle in assertion["values"] if needle.lower() not in haystack]
        return not missing, ("all present" if not missing else f"missing: {', '.join(missing)}")

    if kind == "contains_any":
        hits = [needle for needle in assertion["values"] if needle.lower() in haystack]
        return bool(hits), (f"present: {', '.join(hits)}" if hits else "none of them present")

    fail(f"unknown assertion kind {kind!r}")
    raise AssertionError  # unreachable; keeps the type checker honest


def run_probe(opencode: str, probe: dict, *, work: Path, env: dict[str, str], model: str | None) -> dict:
    command = [opencode, "run", "--format", "json"]
    if model:
        command += ["--model", model]
    command.append(probe["prompt"])

    print(f"  asking: {probe['prompt'][:70]}...", file=sys.stderr)
    completed = subprocess.run(
        command,
        cwd=work,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"`opencode run` exited {completed.returncode}:\n{completed.stderr.strip()}")
    return {"stdout": completed.stdout, "reply": assistant_text(completed.stdout)}


def opencode_version(opencode: str) -> str:
    completed = subprocess.run([opencode, "--version"], capture_output=True, text=True, check=False)
    return completed.stdout.strip() or "unknown"


def git_identity() -> str:
    def config(key: str) -> str:
        return subprocess.run(
            ["git", "config", key], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()

    return f"{config('user.name')} <{config('user.email')}>".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kit", help="a directory under skills/ or a file stem under rules/")
    parser.add_argument("--model", help="passed to `opencode run --model`")
    parser.add_argument("--keep", action="store_true", help="leave the sandbox on disk")
    args = parser.parse_args()

    opencode = shutil.which("opencode")
    if opencode is None:
        fail("`opencode` is not on PATH. This layer runs against your own installed assistant.")

    probes_path = PROBES_DIR / f"{args.kit}.json"
    if not probes_path.is_file():
        fail(f"no probes at {probes_path.relative_to(REPO_ROOT).as_posix()}; write them before recording")
    probes = json.loads(probes_path.read_text(encoding="utf-8"))["probes"]

    skill, rule, files = kit_parts(args.kit)

    root = Path(tempfile.mkdtemp(prefix=f"evidence-{args.kit}-"))
    home, work, env = build_sandbox(root, skill, rule)
    prepare_machine(args.kit, home, work, env)
    print(f"sandbox at {root}, asking {len(probes)} probe(s)", file=sys.stderr)

    runs = []
    outcome = "pass"
    for probe in probes:
        result = run_probe(opencode, probe, work=work, env=env, model=args.model)
        reply = scrub(result["reply"], home=home)
        assertions = []
        for assertion in probe["assertions"]:
            passed, seen = evaluate(assertion, reply)
            assertions.append(
                {
                    "name": assertion["name"],
                    "kind": assertion["kind"],
                    "values": assertion["values"],
                    "outcome": "pass" if passed else "fail",
                    "seen": seen,
                }
            )
            if not passed:
                outcome = "fail"
        runs.append({"prompt": probe["prompt"], "reply": reply, "assertions": assertions})

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "kit": args.kit,
        "files": [
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in files
        ],
        "recorded": {
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "by": git_identity(),
            "opencode_version": opencode_version(opencode),
            "model": args.model or "opencode default",
            "platform": sys.platform,
        },
        "runs": runs,
        "outcome": outcome,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE_DIR / f"{args.kit}.json"
    # Canonical JSON: sorted keys, two-space indent, LF, trailing newline. That is
    # already the fixed point of every formatting hook in this repository, so a
    # recording is not silently edited after it was recorded.
    destination.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {destination.relative_to(REPO_ROOT).as_posix()}: {outcome}", file=sys.stderr)

    if args.keep:
        print(f"sandbox kept at {root}", file=sys.stderr)
    else:
        shutil.rmtree(root, ignore_errors=True)

    return 0 if outcome == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
