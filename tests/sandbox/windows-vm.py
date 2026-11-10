"""The machine the windows-vm kit's evidence is recorded on: a fake VM.

`.scripts/record_evidence.py` calls `prepare()` while building the throwaway
home, before the agent starts. The agent then follows the skill for real, but
every `VBoxManage` it reaches is `tests/fake_vboxmanage.py`, answering from a
state file. So a recording shows the agent reaches for the skill and can follow
it, without needing a running VM; whether the real VM works is
`tests/test_wvm_live.py`'s question.

Nothing here is visible to the skill or to `wvm.py`: they find a config file and
a `VBoxManage` on PATH, as on any machine.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fake_vboxmanage import fake_machine

# A build number no model would guess, so a reply carrying it came from the VM.
WINDOWS_VERSION = "10.0.26100.4242"


def prepare(home: Path, work: Path, env: dict[str, str]) -> None:
    (work / "notes.txt").write_text("pelican-7781\n", encoding="utf-8")
    env.update(
        fake_machine(
            home / ".fake-machine",
            Path(env["XDG_CONFIG_HOME"]),
            replies=[
                {
                    "match": r"\bver\b|OSVersion|Win32_OperatingSystem|ComputerInfo|CurrentVersion|systeminfo|winver",
                    "stdout": f"Microsoft Windows [Version {WINDOWS_VERSION}]\r\n",
                }
            ],
        )
    )
