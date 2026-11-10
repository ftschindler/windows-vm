#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pywinrm==0.5.0"]
# ///
"""wvm - drive the Windows VM that a windows-vm clone provisioned.

Usage:
  wvm.py where
  wvm.py configure --clone <path>
  wvm.py status
  wvm.py run [--admin] [--shell powershell|pwsh|cmd] [--cwd <dir>] [--timeout <s>] -- <command>
  wvm.py copy-to [--force] <host path> <VM path>
  wvm.py copy-from [--force] <VM path> <host path>
  wvm.py start [--headless] [--timeout <s>]
  wvm.py stop [--timeout <s>]
  wvm.py pause

Every subcommand prints JSON on stdout, except `run`, which passes the
command's output through and exits with the command's exit code.

The one per-machine fact is where the clone is, kept in
`~/.config/windows-vm/config.toml` and written by `configure`. Everything else
is read from the clone (the VM's ID, which Vagrant writes, and the passwords)
or from VirtualBox (the machine folder, the VM's state), so it cannot go stale.

Everything goes through `VBoxManage` and Guest Additions, never through
Vagrant: none of it needs provisioning, and it keeps working when an upgrade
of the host's Ruby breaks Vagrant's plugins. The two exceptions use WinRM as
`admin` on the port Vagrant forwards, because that is the only way in that is
elevated: `run --admin`, and restarting Guest Additions when a VM resumed from
a pause stops answering.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from pathlib import Path

ACCOUNT = "user"
ADMIN = "admin"
VM_ID_FILE = Path(".vagrant") / "machines" / "default" / "virtualbox" / "id"

EXE = {
    "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    "pwsh": r"C:\Program Files\PowerShell\7\pwsh.exe",
    "cmd": r"C:\Windows\System32\cmd.exe",
}

# `guestcontrol run` reports a guest exit code n > 0 as 32 + n, and keeps
# 1..31 for its own failures. 126 is as high as it goes.
GUEST_EXIT_BASE = 32
GUEST_EXIT_MAX = 126

# VBoxManage prints these when its stdout is not a terminal. They say nothing
# about the command, so they are dropped.
NOISE = re.compile(r"^VBoxManage: warning: Error getting std(out|err) handle: VERR_NOT_IMPLEMENTED\r?\n?", re.M)

POLL_SECONDS = 5


class WvmError(Exception):
    """A failure to report in one line and exit 2 on."""


# --- configuration -----------------------------------------------------------


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "windows-vm" / "config.toml"


def clone_dir() -> Path:
    path = config_path()
    if not path.is_file():
        raise WvmError(
            f"not configured: {path} does not exist. "
            "If this machine has a windows-vm clone, run `wvm.py configure --clone <path>`; "
            "if it has none, this machine has no Windows VM."
        )
    clone = tomllib.loads(path.read_text(encoding="utf-8")).get("clone")
    if not isinstance(clone, str) or not clone:
        raise WvmError(f'{path} has no `clone = "<path>"` line')
    return Path(clone)


def vm_id(clone: Path) -> str:
    path = clone / VM_ID_FILE
    if not path.is_file():
        raise WvmError(f"no VM has been created from {clone} yet ({path} does not exist)")
    return path.read_text(encoding="utf-8").strip()


def password_file(clone: Path, account: str = ACCOUNT) -> Path:
    path = clone / ".credentials" / f"{account}.txt"
    if not path.is_file():
        raise WvmError(f"no password for `{account}` at {path}")
    return path


# --- VBoxManage ----------------------------------------------------------------


def vboxmanage(*args: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("VBoxManage")
    if exe is None:
        raise WvmError("VBoxManage is not on PATH; is VirtualBox installed?")
    try:
        completed = subprocess.run(
            [exe, *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise WvmError(f"VBoxManage {args[0]} did not answer within {timeout:.0f} s") from exc
    completed.stderr = NOISE.sub("", completed.stderr)
    return completed


def machine_folder() -> str:
    for line in vboxmanage("list", "systemproperties").stdout.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "Default machine folder":
            return value.strip()
    raise WvmError("VBoxManage list systemproperties did not name a default machine folder")


def vm_info(vm: str) -> dict[str, str]:
    """`showvminfo` as a mapping, or {} when VirtualBox has no such VM.

    While a VM is being saved or started, VirtualBox briefly refuses to describe
    it at all. That is retried for a few seconds rather than reported as absent.
    """
    for _ in range(10):
        completed = vboxmanage("showvminfo", vm, "--machinereadable")
        if completed.returncode == 0:
            return dict(re.findall(r'^"?([^="\n]+)"?="([^"]*)"', completed.stdout, re.M))
        if "Could not find a registered machine" in completed.stderr:
            return {}
        time.sleep(1)
    raise WvmError(f"VirtualBox would not describe VM {vm}: {completed.stderr.strip()}")


def vm_state(vm: str) -> str:
    return vm_info(vm).get("VMState", "absent")


def launch(vm: str, kind: str) -> None:
    """`startvm`, retried while VirtualBox still holds the session of a VM it has just saved."""
    for _ in range(30):
        completed = vboxmanage("startvm", vm, "--type", kind)
        if completed.returncode == 0:
            return
        if "already locked" not in completed.stderr:
            break
        time.sleep(2)
    raise WvmError(f"VBoxManage startvm failed: {completed.stderr.strip()}")


def guest_args(clone: Path) -> list[str]:
    return ["--username", ACCOUNT, "--passwordfile", str(password_file(clone))]


def guest_ready(vm: str, clone: Path) -> bool:
    completed = vboxmanage(
        "guestcontrol", vm, "run", *guest_args(clone),
        "--timeout", "15000", "--exe", EXE["cmd"], "--", "/c", "exit 0",
        timeout=30,
    )  # fmt: skip
    return completed.returncode == 0


def free_bytes(path: str) -> int | None:
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


def require_running(vm: str) -> None:
    state = vm_state(vm)
    if state != "running":
        raise WvmError(f"the VM is {state}, not running. Start it with `wvm.py start`.")


# --- WinRM, for what needs admin -------------------------------------------------

# How long a VM resumed from a pause gets to answer before Guest Additions are
# restarted. A resumed guest sometimes refuses every new session until then.
RESUME_GRACE_SECONDS = 20


def winrm_port(vm: str) -> int:
    for key, value in vm_info(vm).items():
        # name,protocol,host ip,host port,guest ip,guest port
        name, _, _, host_port, _, guest_port = ([*value.split(","), "", "", "", "", "", ""])[:6]
        if key.startswith("Forwarding(") and name and guest_port == "5985":
            return int(host_port)
    raise WvmError("the VM has no port forwarded to WinRM (5985), so nothing can run as admin")


def winrm(vm: str, clone: Path, script: str, timeout: int) -> tuple[int, str, str]:
    """Run a PowerShell script as `admin` over WinRM. Returns exit code, stdout, stderr."""
    import winrm as pywinrm  # noqa: PLC0415 - only the admin paths pay for the import
    from requests.exceptions import RequestException  # noqa: PLC0415

    password = password_file(clone, ADMIN).read_text(encoding="utf-8").strip()
    session = pywinrm.Session(
        f"http://127.0.0.1:{winrm_port(vm)}/wsman",
        auth=(ADMIN, password),
        transport="basic",
        read_timeout_sec=timeout + 10,
        operation_timeout_sec=timeout,
    )
    try:
        result = session.run_ps(script)
    except (RequestException, pywinrm.exceptions.WinRMError) as exc:
        raise WvmError(f"WinRM as admin failed: {exc}") from exc
    out, err = (raw.decode("utf-8", errors="replace").replace("\r\n", "\n") for raw in (result.std_out, result.std_err))
    return result.status_code, out, decode_clixml(err)


def restart_guest_additions(vm: str, clone: Path) -> None:
    code, _, err = winrm(vm, clone, "Restart-Service VBoxService -Force", 120)
    if code != 0:
        raise WvmError(f"could not restart Guest Additions in the VM: {err.strip()}")


# --- run -----------------------------------------------------------------------


def powershell_script(command: str) -> str:
    return (
        "$ProgressPreference = 'SilentlyContinue'\n"
        f". {{\n{command}\n$global:wvmOk = $?\n}}\n"
        "if ($LASTEXITCODE) { exit $LASTEXITCODE }\n"
        "if (-not $global:wvmOk) { exit 1 }\n"
    )


def command_line(shell: str, command: str) -> tuple[list[str], bool]:
    """The arguments after `--` for the shell, and whether to pass them unquoted.

    PowerShell gets the command base64-encoded, because VirtualBox does not
    quote arguments the way Windows parses them and double quotes inside one
    are lost. The command runs in a dot-sourced block, so an error message
    quotes the command rather than this wrapper, and the epilogue hands a
    native program's exit code on, which PowerShell otherwise turns into 0
    or 1.
    """
    if shell in ("powershell", "pwsh"):
        encoded = base64.b64encode(powershell_script(command).encode("utf-16-le")).decode("ascii")
        return ["-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], False
    # cmd parses its own command line, so it is handed over verbatim: `/s`
    # strips exactly the outer pair of quotes and keeps everything inside.
    return ["/d", "/s", "/c", f'"{command}"'], True


def decode_clixml(text: str) -> str:
    """PowerShell's stderr, when it is not a console, is CLIXML. Make it text again."""
    if "#< CLIXML" not in text:
        return text
    out = []
    for block in re.split(r"#< CLIXML\r?\n", text):
        if "<Objs" not in block:
            out.append(block)
            continue
        for match in re.finditer(r'<S S="Error">(.*?)</S>', block, re.S):
            piece = html.unescape(match.group(1))
            piece = re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), piece)
            out.append(piece)
    return "".join(out)


def exit_code(vbox_code: int) -> int:
    if vbox_code == 0:
        return 0
    if GUEST_EXIT_BASE < vbox_code <= GUEST_EXIT_MAX:
        return vbox_code - GUEST_EXIT_BASE
    return vbox_code


def cmd_run(args: argparse.Namespace) -> int:
    command = " ".join(args.command)
    if not command.strip():
        raise WvmError("nothing to run: put the command after `--`")
    clone = clone_dir()
    vm = vm_id(clone)
    require_running(vm)
    if args.admin:
        return run_as_admin(vm, clone, args, command)
    cwd = args.cwd or rf"C:\Users\{ACCOUNT}"
    shell_args, unquoted = command_line(args.shell, command)
    completed = vboxmanage(
        "guestcontrol", vm, "run", *guest_args(clone),
        *(["--unquoted-args"] if unquoted else []),
        "--timeout", str(args.timeout * 1000), "--cwd", cwd, "--exe", EXE[args.shell],
        "--", *shell_args,
        timeout=args.timeout + 30,
    )  # fmt: skip
    sys.stdout.write(completed.stdout.replace("\r\n", "\n"))
    sys.stderr.write(decode_clixml(completed.stderr).replace("\r\n", "\n"))
    code = exit_code(completed.returncode)
    if 0 < completed.returncode <= GUEST_EXIT_BASE:
        print(f"wvm: VBoxManage failed (exit {completed.returncode}) before the command ran", file=sys.stderr)
    return code


def run_as_admin(vm: str, clone: Path, args: argparse.Namespace, command: str) -> int:
    if args.shell != "powershell":
        raise WvmError("--admin runs PowerShell 5.1 only; call pwsh or cmd from inside the command")
    cwd = (args.cwd or rf"C:\Users\{ADMIN}").replace("'", "''")
    code, out, err = winrm(vm, clone, f"Set-Location -LiteralPath '{cwd}'\n" + powershell_script(command), args.timeout)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return code


# --- copy ----------------------------------------------------------------------


def guest_exists(vm: str, clone: Path, path: str) -> bool:
    return vboxmanage("guestcontrol", vm, "stat", *guest_args(clone), path, timeout=60).returncode == 0


def copy(args: argparse.Namespace, direction: str) -> int:
    clone = clone_dir()
    vm = vm_id(clone)
    require_running(vm)
    if direction == "copyto":
        source = Path(args.source).resolve()
        if not source.exists():
            raise WvmError(f"{source} does not exist")
        exists = guest_exists(vm, clone, args.destination)
        recursive = source.is_dir()
        source_arg, destination = str(source), args.destination
    else:
        if not guest_exists(vm, clone, args.source):
            raise WvmError(f"{args.source} does not exist in the VM")
        destination = str(Path(args.destination).resolve())
        exists = Path(destination).exists()
        recursive = True
        source_arg = args.source
    if exists and not args.force:
        raise WvmError(f"{args.destination} already exists; pass --force to overwrite it")
    completed = vboxmanage(
        "guestcontrol", vm, direction, *guest_args(clone),
        *(["--recursive"] if recursive else []), source_arg, destination,
    )  # fmt: skip
    if completed.returncode != 0:
        raise WvmError(f"copy failed: {completed.stderr.strip()}")
    emit({"copied": source_arg, "to": destination, "overwrote": exists})
    return 0


# --- the rest ------------------------------------------------------------------


def emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def cmd_where(_: argparse.Namespace) -> int:
    clone = clone_dir()
    folder = machine_folder()
    id_file = clone / VM_ID_FILE
    emit(
        {
            "clone": str(clone),
            "machine_folder": folder,
            "vm_id": id_file.read_text(encoding="utf-8").strip() if id_file.is_file() else None,
            "free_bytes": {"clone": free_bytes(str(clone)), "machine_folder": free_bytes(folder)},
        }
    )
    return 0


def cmd_configure(args: argparse.Namespace) -> int:
    clone = Path(args.clone).expanduser().resolve()
    if not (clone / "Vagrantfile").is_file():
        raise WvmError(f"{clone} is not a windows-vm clone: it has no Vagrantfile")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # A JSON string is a valid TOML basic string, escapes included.
    path.write_text(f"clone = {json.dumps(str(clone))}\n", encoding="utf-8")
    emit({"config": str(path), "clone": str(clone)})
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    clone = clone_dir()
    vm = vm_id(clone)
    state = vm_state(vm)
    emit({"vm_id": vm, "state": state, "guest_ready": state == "running" and guest_ready(vm, clone)})
    return 0


def wait_for(predicate: Callable[[], bool], timeout: int, what: str) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise WvmError(f"{what} within {timeout} s")
        time.sleep(POLL_SECONDS)


def cmd_start(args: argparse.Namespace) -> int:
    clone = clone_dir()
    vm = vm_id(clone)
    state = vm_state(vm)
    if state == "absent":
        raise WvmError(f"VirtualBox has no VM {vm}; it was destroyed or never registered")
    if state != "running":
        launch(vm, "headless" if args.headless else "gui")
    deadline = time.monotonic() + args.timeout
    if state == "saved":
        try:
            wait_for(lambda: guest_ready(vm, clone), min(RESUME_GRACE_SECONDS, args.timeout), "")
        except WvmError:
            restart_guest_additions(vm, clone)
    wait_for(lambda: guest_ready(vm, clone), max(0, int(deadline - time.monotonic())), "Windows did not answer")
    emit({"vm_id": vm, "was": state, "state": "running", "guest_ready": True})
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    clone = clone_dir()
    vm = vm_id(clone)
    state = vm_state(vm)
    if state == "running":
        # Windows ignores the ACPI power button while someone is logged on, so
        # the shutdown is asked for from inside. It is not forced: a program
        # holding unsaved work still gets to refuse. The power button is the
        # fallback for a guest whose Guest Additions do not answer.
        asked = vboxmanage(
            "guestcontrol", vm, "run", *guest_args(clone),
            "--timeout", "30000", "--exe", r"C:\Windows\System32\shutdown.exe", "--", "/s", "/t", "0",
            timeout=60,
        )  # fmt: skip
        if asked.returncode != 0:
            vboxmanage("controlvm", vm, "acpipowerbutton")
        wait_for(
            lambda: vm_state(vm) == "poweroff",
            args.timeout,
            "Windows did not shut down (an unsaved document may be holding it; look at the VM window)",
        )
    elif state != "poweroff":
        raise WvmError(f"the VM is {state}; only a running VM can be shut down")
    emit({"vm_id": vm, "was": state, "state": "poweroff"})
    return 0


def cmd_pause(_: argparse.Namespace) -> int:
    clone = clone_dir()
    vm = vm_id(clone)
    state = vm_state(vm)
    if state == "running":
        completed = vboxmanage("controlvm", vm, "savestate")
        if completed.returncode != 0:
            raise WvmError(f"VBoxManage savestate failed: {completed.stderr.strip()}")
    elif state != "saved":
        raise WvmError(f"the VM is {state}; only a running VM can be paused")
    emit({"vm_id": vm, "was": state, "state": "saved"})
    return 0


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="wvm.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = top.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("where", help="where the clone and the VirtualBox machine folder are").set_defaults(func=cmd_where)

    p = sub.add_parser("configure", help="record where this machine's clone is")
    p.add_argument("--clone", required=True)
    p.set_defaults(func=cmd_configure)

    sub.add_parser("status", help="the VM's state").set_defaults(func=cmd_status)

    p = sub.add_parser("run", help="run one command in the VM")
    p.add_argument("--admin", action="store_true", help="run elevated as `admin`, over WinRM (PowerShell only)")
    p.add_argument("--shell", choices=sorted(EXE), default="powershell")
    p.add_argument("--cwd", help=r"working directory in the VM (default: C:\Users\user)")
    p.add_argument("--timeout", type=int, default=600, help="seconds (default: 600)")
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_run)

    for name, src, dst in (("copy-to", "host path", "VM path"), ("copy-from", "VM path", "host path")):
        p = sub.add_parser(name, help=f"copy a file or folder from {src} to {dst}")
        p.add_argument("--force", action="store_true", help="overwrite an existing destination")
        p.add_argument("source", metavar=src.replace(" ", "_"))
        p.add_argument("destination", metavar=dst.replace(" ", "_"))
        p.set_defaults(func=lambda a, d="copyto" if name == "copy-to" else "copyfrom": copy(a, d))

    p = sub.add_parser("start", help="boot the VM, or resume it if paused, and wait for Windows")
    p.add_argument("--headless", action="store_true", help="no window")
    p.add_argument("--timeout", type=int, default=600)
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("stop", help="shut Windows down cleanly")
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(func=cmd_stop)

    sub.add_parser("pause", help="save the VM's state to disk").set_defaults(func=cmd_pause)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.subcommand == "run" and args.command[:1] == ["--"]:
        args.command = args.command[1:]
    try:
        return args.func(args)
    except WvmError as exc:
        print(f"wvm: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
