"""wvm.py against a fake VBoxManage.

The fake answers from a state file and logs every call, so these tests assert
two things: what `wvm.py` asks VirtualBox to do, and what it tells the caller.
Nothing here touches a real VM; that is test_wvm_live.py.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fake_vboxmanage import FAKE_VM_ID, fake_machine

pytestmark = pytest.mark.scripts

REPO_ROOT = Path(__file__).resolve().parent.parent
WVM = REPO_ROOT / "skills" / "windows-vm" / "scripts" / "wvm.py"


class Machine:
    def __init__(self, root: Path, **state: object) -> None:
        self.root = root
        self.env = {**os.environ, **fake_machine(root, root / "config", **state)}
        self.state_file = Path(self.env["FAKE_VBOX_STATE"])
        self.clone = root / "windows-vm"

    def wvm(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(WVM), *args], env=self.env, capture_output=True, text=True, check=False
        )

    @property
    def state(self) -> dict:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def calls(self, verb: str) -> list[list[str]]:
        return [call for call in self.state["log"] if verb in call[:3]]


@pytest.fixture
def machine(tmp_path: Path) -> Machine:
    return Machine(tmp_path)


def decoded(call: list[str]) -> str:
    return base64.b64decode(call[call.index("-EncodedCommand") + 1]).decode("utf-16-le")


# --- where and configure ----------------------------------------------------


def test_where_reports_the_clone_the_machine_folder_and_the_vm(machine: Machine):
    result = machine.wvm("where")
    assert result.returncode == 0, result.stderr
    where = json.loads(result.stdout)
    assert where["clone"] == str(machine.clone)
    assert where["machine_folder"] == str(machine.root / "virtualbox")
    assert where["vm_id"] == FAKE_VM_ID
    assert where["free_bytes"]["clone"] > 0


def test_where_without_a_config_says_how_to_make_one(machine: Machine):
    (machine.root / "config" / "windows-vm" / "config.toml").unlink()
    result = machine.wvm("where")
    assert result.returncode == 2
    assert "configure --clone" in result.stderr


def test_configure_records_a_clone_and_refuses_a_directory_that_is_not_one(machine: Machine, tmp_path: Path):
    (machine.root / "config" / "windows-vm" / "config.toml").unlink()
    assert machine.wvm("configure", "--clone", str(tmp_path / "nothing")).returncode == 2
    assert machine.wvm("configure", "--clone", str(machine.clone)).returncode == 0
    assert json.loads(machine.wvm("where").stdout)["clone"] == str(machine.clone)


def test_the_vm_is_found_by_the_id_in_the_clone_not_by_its_name(machine: Machine):
    machine.wvm("status")
    assert machine.calls("showvminfo") == [["showvminfo", FAKE_VM_ID, "--machinereadable"]]


# --- run ----------------------------------------------------------------------


def test_run_uses_powershell_as_user_in_the_profile_folder(machine: Machine):
    result = machine.wvm("run", "--", "Write-Output", "hello")
    assert result.returncode == 0, result.stderr
    (call,) = machine.calls("run")
    assert call[call.index("--username") + 1] == "user"
    assert call[call.index("--exe") + 1].endswith(r"WindowsPowerShell\v1.0\powershell.exe")
    assert call[call.index("--cwd") + 1] == r"C:\Users\user"
    assert "Write-Output hello" in decoded(call)


def test_the_command_reaches_powershell_with_its_quotes_intact(machine: Machine):
    machine.wvm("run", "--", """Write-Output "a  b" 'c'""")
    (call,) = machine.calls("run")
    assert """Write-Output "a  b" 'c'""" in decoded(call)


def test_the_password_never_appears_on_a_command_line(machine: Machine):
    machine.wvm("run", "--", "whoami")
    machine.wvm("status")
    for call in machine.state["log"]:
        assert "not-a-real-password" not in " ".join(call)
        if "--username" in call:
            assert call[call.index("--passwordfile") + 1] == str(machine.clone / ".credentials" / "user.txt")


def test_run_passes_the_guest_output_and_exit_code_through(tmp_path: Path):
    machine = Machine(tmp_path, replies=[{"match": "build", "stdout": "compiled\r\n", "exit": 7}])
    result = machine.wvm("run", "--", "build")
    assert result.returncode == 7
    assert result.stdout == "compiled\n"


def test_run_decodes_powershell_errors_into_text(tmp_path: Path):
    clixml = (
        '#< CLIXML\r\n<Objs Version="1.1.0.1"><S S="Error">boom &amp; more_x000D__x000A_</S>'
        '<Obj S="progress"><AV>Preparing modules</AV></Obj></Objs>'
    )
    machine = Machine(tmp_path, replies=[{"match": "fail", "stderr": clixml, "exit": 1}])
    result = machine.wvm("run", "--", "fail")
    assert result.returncode == 1
    assert result.stderr == "boom & more\n"


def test_run_with_cmd_hands_the_command_over_verbatim(machine: Machine):
    machine.wvm("run", "--shell", "cmd", "--cwd", r"D:\src", "--", 'echo "a  b" & dir')
    (call,) = machine.calls("run")
    assert "--unquoted-args" in call
    assert call[call.index("--cwd") + 1] == r"D:\src"
    assert call[call.index("--") + 1 :] == ["/d", "/s", "/c", '"echo "a  b" & dir"']


def test_run_refuses_a_vm_that_is_not_running(tmp_path: Path):
    machine = Machine(tmp_path, vm_state="saved")
    result = machine.wvm("run", "--", "whoami")
    assert result.returncode == 2
    assert "wvm.py start" in result.stderr
    assert machine.calls("run") == []


def test_run_with_nothing_to_run_is_refused(machine: Machine):
    assert machine.wvm("run", "--").returncode == 2


# --- copy -----------------------------------------------------------------------


def test_copy_to_and_back_round_trips_a_file(machine: Machine, tmp_path: Path):
    source = tmp_path / "notes.txt"
    source.write_text("pelican\n", encoding="utf-8")
    assert machine.wvm("copy-to", str(source), r"C:\Users\user\notes.txt").returncode == 0
    back = tmp_path / "back.txt"
    assert machine.wvm("copy-from", r"C:\Users\user\notes.txt", str(back)).returncode == 0
    assert back.read_text(encoding="utf-8") == "pelican\n"


def test_copy_to_a_folder_is_recursive(machine: Machine, tmp_path: Path):
    (tmp_path / "src" / "sub").mkdir(parents=True)
    (tmp_path / "src" / "sub" / "a.txt").write_text("a", encoding="utf-8")
    assert machine.wvm("copy-to", str(tmp_path / "src"), r"C:\src").returncode == 0
    (call,) = machine.calls("copyto")
    assert "--recursive" in call
    assert r"C:\src\sub\a.txt" in machine.state["guest_files"]


def test_copy_to_refuses_an_existing_destination_without_force(tmp_path: Path):
    machine = Machine(tmp_path, guest_files={r"C:\Users\user\notes.txt": "old"})
    source = tmp_path / "notes.txt"
    source.write_text("new", encoding="utf-8")
    refused = machine.wvm("copy-to", str(source), r"C:\Users\user\notes.txt")
    assert refused.returncode == 2
    assert "--force" in refused.stderr
    assert machine.state["guest_files"][r"C:\Users\user\notes.txt"] == "old"
    assert machine.wvm("copy-to", "--force", str(source), r"C:\Users\user\notes.txt").returncode == 0
    assert machine.state["guest_files"][r"C:\Users\user\notes.txt"] == "new"


def test_copy_from_refuses_an_existing_destination_without_force(tmp_path: Path):
    machine = Machine(tmp_path, guest_files={r"C:\a.txt": "from the vm"})
    target = tmp_path / "a.txt"
    target.write_text("mine", encoding="utf-8")
    assert machine.wvm("copy-from", r"C:\a.txt", str(target)).returncode == 2
    assert target.read_text(encoding="utf-8") == "mine"
    assert machine.wvm("copy-from", "--force", r"C:\a.txt", str(target)).returncode == 0
    assert target.read_text(encoding="utf-8") == "from the vm"


# --- start, stop and pause --------------------------------------------------------


@pytest.mark.parametrize("before", ["poweroff", "saved", "aborted"])
def test_start_boots_or_resumes_and_waits_for_windows(tmp_path: Path, before: str):
    machine = Machine(tmp_path, vm_state=before)
    result = machine.wvm("start", "--headless")
    assert result.returncode == 0, result.stderr
    assert machine.calls("startvm") == [["startvm", FAKE_VM_ID, "--type", "headless"]]
    assert json.loads(result.stdout) == {"vm_id": FAKE_VM_ID, "was": before, "state": "running", "guest_ready": True}


def test_start_opens_a_window_by_default_and_leaves_a_running_vm_alone(tmp_path: Path):
    machine = Machine(tmp_path, vm_state="poweroff")
    machine.wvm("start")
    assert machine.calls("startvm")[0][-1] == "gui"
    machine.wvm("start")
    assert len(machine.calls("startvm")) == 1


def test_a_resumed_vm_that_does_not_answer_gets_its_guest_additions_restarted(tmp_path: Path):
    """Restarting goes over WinRM as admin; here nothing listens on the port, so the attempt is what is seen."""
    machine = Machine(tmp_path, vm_state="saved", start_makes_ready=False)
    machine.state_file.write_text(
        json.dumps({**machine.state, "forwarding": "winrm,tcp,127.0.0.1,9,,5985"}), encoding="utf-8"
    )
    (machine.clone / ".credentials" / "admin.txt").write_text("x", encoding="utf-8")
    result = machine.wvm("start", "--timeout", "1")
    assert result.returncode == 2
    assert "WinRM as admin failed" in result.stderr


def test_start_gives_up_when_windows_never_answers(tmp_path: Path):
    machine = Machine(tmp_path, vm_state="poweroff", start_makes_ready=False)
    result = machine.wvm("start", "--timeout", "0")
    assert result.returncode == 2
    assert "did not answer" in result.stderr


def test_stop_asks_windows_to_shut_down_without_forcing_it(machine: Machine):
    result = machine.wvm("stop")
    assert result.returncode == 0, result.stderr
    (call,) = machine.calls("run")
    assert call[call.index("--exe") + 1].endswith("shutdown.exe")
    assert call[call.index("--") + 1 :] == ["/s", "/t", "0"]
    assert machine.calls("controlvm") == []
    assert machine.state["vms"][FAKE_VM_ID]["state"] == "poweroff"


def test_stop_falls_back_to_the_power_button_when_windows_does_not_answer(tmp_path: Path):
    machine = Machine(tmp_path, ready=False)
    assert machine.wvm("stop").returncode == 0
    assert machine.calls("controlvm") == [["controlvm", FAKE_VM_ID, "acpipowerbutton"]]


def test_pause_saves_the_state(machine: Machine):
    assert machine.wvm("pause").returncode == 0
    assert machine.calls("controlvm") == [["controlvm", FAKE_VM_ID, "savestate"]]
    assert machine.state["vms"][FAKE_VM_ID]["state"] == "saved"


def test_nothing_ever_powers_off_hard(machine: Machine, tmp_path: Path):
    for args in (["status"], ["pause"], ["start"], ["stop"]):
        machine.wvm(*args)
    assert not [call for call in machine.state["log"] if "poweroff" in call]
