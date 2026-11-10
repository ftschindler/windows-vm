"""wvm.py against the real VM on this host. Opt in with `-m live`; never in CI.

Skipped unless `wvm.py status` reports a running VM that answers, so on a
machine without one this file is silent rather than red.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

WVM = Path(__file__).resolve().parent.parent / "skills" / "windows-vm" / "scripts" / "wvm.py"


def wvm(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(WVM), *args], capture_output=True, text=True, check=False)


@pytest.fixture(scope="module", autouse=True)
def running_vm() -> None:
    status = wvm("status")
    if status.returncode != 0 or not json.loads(status.stdout)["guest_ready"]:
        pytest.skip(f"no running Windows VM here: {status.stderr.strip() or status.stdout.strip()}")


def test_a_command_runs_and_its_output_comes_back():
    result = wvm("run", "--", 'Write-Output "o  k"')
    assert (result.returncode, result.stdout) == (0, "o  k\n")


def test_a_native_exit_code_comes_back():
    assert wvm("run", "--", 'cmd /c "exit 7"').returncode == 7


def test_a_file_survives_a_round_trip(tmp_path: Path):
    source = tmp_path / "round-trip.txt"
    source.write_bytes(uuid.uuid4().bytes.hex().encode())
    guest = rf"C:\Users\user\wvm-live-{uuid.uuid4().hex}.txt"
    try:
        assert wvm("copy-to", str(source), guest).returncode == 0
        assert wvm("copy-to", str(source), guest).returncode == 2
        assert wvm("copy-from", guest, str(tmp_path / "back.txt")).returncode == 0
        assert (tmp_path / "back.txt").read_bytes() == source.read_bytes()
    finally:
        wvm("run", "--", f"Remove-Item -LiteralPath '{guest}' -ErrorAction SilentlyContinue")


def test_admin_runs_elevated():
    check = "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')"
    assert wvm("run", "--", check).stdout.strip() == "False"
    assert wvm("run", "--admin", "--", check).stdout.strip() == "True"
