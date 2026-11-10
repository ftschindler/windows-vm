"""A stand-in for `VBoxManage`, for the script tests and the evidence recording.

It answers the handful of commands `wvm.py` uses, from a JSON state file named
by `FAKE_VBOX_STATE`, and appends every call it receives to that file's `log`.
It never touches VirtualBox. Install it on PATH with `install()`.

State file:

    {
      "machine_folder": "/data/virtualbox",
      "vms": {"<id>": {"state": "running", "ready": true}},
      "guest_files": {"C:\\\\Users\\\\user\\\\notes.txt": "contents"},
      "replies": [{"match": "regex on the decoded command", "stdout": "...", "exit": 0}],
      "start_makes_ready": true,
      "log": [["guestcontrol", "<id>", "run", ...], ...]
    }
"""

from __future__ import annotations

import base64
import json
import os
import re
import stat
import sys
from pathlib import Path

GUEST_EXIT_BASE = 32


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def option(args: list[str], name: str) -> str | None:
    if name in args:
        return args[args.index(name) + 1]
    return None


def decoded_command(after: list[str]) -> str:
    """The command a `run` call carries, whichever shell it was meant for."""
    if "-EncodedCommand" in after:
        script = base64.b64decode(after[after.index("-EncodedCommand") + 1]).decode("utf-16-le")
        match = re.search(r"\. \{\n(.*)\n\$global:wvmOk", script, re.S)
        return match.group(1) if match else script
    return " ".join(after)


def guest_run(state: dict, vm: dict, args: list[str]) -> int:
    if not vm.get("ready", True):
        print("VBoxManage: error: The guest execution service is not ready (yet)", file=sys.stderr)
        return 1
    after = args[args.index("--") + 1 :] if "--" in args else []
    command = decoded_command(after)
    if re.fullmatch(r'/c "?exit 0"?', command):
        return 0
    if args[args.index("--exe") + 1].lower().endswith("shutdown.exe"):
        vm["state"] = "poweroff"
        return 0
    for name, content in state.get("guest_files", {}).items():
        if name.lower() in command.lower() and re.search(r"Get-Content|\btype\b|\bcat\b|\bgc\b", command, re.I):
            sys.stdout.write(content)
            return 0
    for reply in state.get("replies", []):
        if re.search(reply["match"], command, re.I | re.S):
            sys.stdout.write(reply.get("stdout", ""))
            sys.stderr.write(reply.get("stderr", ""))
            code = int(reply.get("exit", 0))
            return GUEST_EXIT_BASE + code if code else 0
    sys.stdout.write("")
    return 0


def main(argv: list[str]) -> int:
    path = Path(os.environ["FAKE_VBOX_STATE"])
    state = load(path)
    state.setdefault("log", []).append(argv)
    code = dispatch(state, argv)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return code


def dispatch(state: dict, argv: list[str]) -> int:  # noqa: PLR0911, PLR0912 - one branch per VBoxManage command
    if argv[:2] == ["list", "systemproperties"]:
        print(f"Default machine folder:          {state.get('machine_folder', '/vms')}")
        return 0

    if not argv[1:]:
        return 1
    vm = state.get("vms", {}).get(argv[1])
    if vm is None:
        print(f"VBoxManage: error: Could not find a registered machine named '{argv[1]}'", file=sys.stderr)
        return 1

    if argv[0] == "showvminfo":
        print(f'name="Windows Development Environment"\nVMState="{vm["state"]}"\nSessionState="Unlocked"')
        if "forwarding" in state:
            print(f'Forwarding(0)="{state["forwarding"]}"')
        return 0
    if argv[0] == "startvm":
        vm["state"] = "running"
        vm["ready"] = state.get("start_makes_ready", True)
        return 0
    if argv[0] == "controlvm":
        vm["state"] = {"acpipowerbutton": "poweroff", "savestate": "saved"}.get(argv[2], vm["state"])
        return 0
    if argv[0] != "guestcontrol":
        return 1

    if vm["state"] != "running":
        print(f'VBoxManage: error: Machine "{argv[1]}" is not running', file=sys.stderr)
        return 1
    files = state.setdefault("guest_files", {})
    sub, rest = argv[2], argv[3:]
    if sub == "run":
        return guest_run(state, vm, rest)
    positional = [
        a
        for i, a in enumerate(rest)
        if not a.startswith("--") and not (i and rest[i - 1] in ("--username", "--passwordfile"))
    ]
    if sub == "stat":
        return 0 if all(p in files for p in positional) else 1
    if sub == "copyto":
        source, target = Path(positional[0]), positional[1]
        if source.is_dir():
            for item in source.rglob("*"):
                if item.is_file():
                    files[target + "\\" + str(item.relative_to(source)).replace("/", "\\")] = item.read_text(
                        encoding="utf-8"
                    )
            files[target] = ""
        else:
            files[target] = source.read_text(encoding="utf-8")
        return 0
    if sub == "copyfrom":
        source, target = positional[0], Path(positional[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[source], encoding="utf-8")
        return 0
    return 1


def install(bin_dir: Path, state_file: Path, state: dict, python: str = sys.executable) -> None:
    """Put an executable `VBoxManage` in `bin_dir` that runs this fake against `state_file`."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    shim = bin_dir / "VBoxManage"
    shim.write_text(f'#!/bin/sh\nexec "{python}" "{Path(__file__).resolve()}" "$@"\n', encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


FAKE_VM_ID = "00000000-fake-4000-8000-000000000001"


def fake_machine(root: Path, config_home: Path, **state: object) -> dict[str, str]:
    """A clone, a config file pointing at it, and the fake on PATH. Returns the env to add.

    `state` overrides the fake's defaults: a running, ready VM with no replies.
    """
    clone = root / "windows-vm"
    (clone / ".vagrant" / "machines" / "default" / "virtualbox").mkdir(parents=True, exist_ok=True)
    (clone / ".vagrant" / "machines" / "default" / "virtualbox" / "id").write_text(FAKE_VM_ID, encoding="utf-8")
    (clone / ".credentials").mkdir(exist_ok=True)
    (clone / ".credentials" / "user.txt").write_text("not-a-real-password", encoding="utf-8")
    (clone / "Vagrantfile").write_text("# fake\n", encoding="utf-8")
    (config_home / "windows-vm").mkdir(parents=True, exist_ok=True)
    (config_home / "windows-vm" / "config.toml").write_text(f"clone = {json.dumps(str(clone))}\n", encoding="utf-8")

    vm = {"state": state.pop("vm_state", "running"), "ready": state.pop("ready", True)}
    full = {"machine_folder": str(root / "virtualbox"), "vms": {FAKE_VM_ID: vm}, "replies": [], "log": []}
    full.update(state)
    state_file = root / "fake-vbox.json"
    install(root / "bin", state_file, full)
    return {
        "PATH": f"{root / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
        "XDG_CONFIG_HOME": str(config_home),
        "FAKE_VBOX_STATE": str(state_file),
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
