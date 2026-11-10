# Plan: a `windows-vm` skill and rule for akit

Goal: make this repository an akit source. Subscribe to it with

```sh
uvx --from federated-agent-kits akit add ftschindler/windows-vm windows-vm
```

so that an agent on a Linux host can explain, provision, start and use the
Windows VM. Conventions follow
[agent-kits](https://github.com/ftschindler/agent-kits) (its `CONTRIBUTING.md`):
the skill and rule share a name, `references/` holds the detail, every
deterministic step is a uv-shebanged PEP 723 script in `scripts/`, the scripts
have pytest tests, and each kit has a probe and recorded evidence (the "test
certificate").

## Status

The skill does three of its four jobs. Setting up a new machine is the one
left.

| Job (section of `SKILL.md`) | State | What it is |
| --- | --- | --- |
| 1. Explain what this is | done | `SKILL.md` "Does this machine have a VM?", `references/what-this-is.md` |
| 2. Get started and provision | **not started** | `check-host`, `provision`, `references/provisioning.md` |
| 3. Start, stop and pause | done | `start`, `stop`, `pause`, `status` |
| 4. Run a command, move files | done | `run` (with `--admin`), `copy-to`, `copy-from` |

Also done: `where` and `configure`, the rule, `references/troubleshooting.md`,
script, live and conformance tests, recorded evidence, CI, the guards copied
from agent-kits, the MIT licence and the README section.

Still to do:

1. **`wvm.py check-host`**: VirtualBox and its kernel modules, the
   `vboxusers` group, Vagrant and its plugins (including plugins left under an
   older Ruby), `.env`, credentials, and free space on the clone's and the
   machine folder's drives. Details in "Step 4 details" below.
2. **`wvm.py provision`**: run `vagrant_provision.bash` from the clone, in the
   background, and report progress through `status`.
3. **`references/provisioning.md`** and **section 2 of `SKILL.md`**: choosing
   the drive, installing VirtualBox and Vagrant on Manjaro, moving the machine
   folder, and asking before every `sudo` and every change to where VMs live.
4. **Probes for setting up**, and the evidence recorded again.
5. **Optional: update the Guest Additions** in the guest from 7.2.6 to the
   host's 7.2.16, and see whether a VM resumed from a pause then answers on
   its own. If it does, `start` no longer needs to restart them over WinRM.

Where the build differed from this plan, the sections below say what was
built, and [JOURNAL.md](../../JOURNAL.md) says why.

## Order of work

1. **Run a command in the VM** (section 4 of the skill). The VM is running now,
   so this can be tested end to end straight away.
2. **Start a provisioned VM** (section 3).
3. **Explain what this is** (section 1). Short, mostly taken from `README.md`.
4. **Get started and provision** (section 2). Last, because it takes hours to
   run and destroys nothing only if it is written carefully.

The rule, the tests and the evidence grow with each step rather than arriving
at the end.

## What I found on this host

- VM name `Windows Development Environment`, state `running`.
- VirtualBox default machine folder is `/data/virtualbox`; the VM's `.vbox` is
  at `/data/virtualbox/Windows Development Environment/`.
- The clone is `/home/felix/Projects/public/windows-vm/main`, and
  `devdrive.vdi` (500 GB) is created inside the clone. So the clone, not only
  the VirtualBox folder, has to sit on a drive with space.
- `vagrant` failed to start ("The plugins failed to initialize correctly")
  after a Ruby upgrade. Fixed on 2026-11-09; cause and fix are in
  [JOURNAL.md](../../JOURNAL.md), and the setup step has to handle it.
- `README.md`'s "Nuclear cleanup" hard-codes
  `/home/felix/.virtualbox_vms/`, which is no longer the machine folder
  (`/data/virtualbox`). `references/troubleshooting.md` uses `wvm.py where`
  instead, and the README line gets fixed alongside.
- `VBoxManage guestcontrol ... run --username user --passwordfile
  .credentials/user.txt` works today and returned `desktop-1if78k6\user`.
  Guest Additions are therefore installed and usable.

## Layout

```text
skills/windows-vm/
  SKILL.md
  references/
    what-this-is.md        # section 1 in full: accounts, phases, Dev Drive
    provisioning.md        # section 2 in full (to do)
    troubleshooting.md     # Vagrant plugin repair, WinRM timeouts, guestcontrol errors
  scripts/
    wvm.py                 # one entry point, subcommands below
rules/windows-vm.md
.scripts/                  # guards copied from agent-kits
tests/
  fake_vboxmanage.py       # shared by the script tests and the evidence recording
  test_wvm.py              # script tests against the fake
  test_wvm_live.py         # opt-in, real VM, local only
  test_conformance.py      # kit shape
  probes/windows-vm.json
  evidence/windows-vm.json
.github/workflows/tests.yml
Makefile                   # test, test_conformance, test_scripts, record_evidence, check
LICENSE                    # MIT, replacing UNLICENSE.md
```

`skills/` and `rules/` at the repository root are where akit looks, so no
manifest is needed. Nothing in the existing provisioning files moves.

## Hosts

Linux only. The provisioning is bash and Vagrant on Linux, and `wvm.py` calls
`VBoxManage` as found on `PATH`. A Windows or macOS host is out of scope, and
CI runs on Ubuntu only.

## Where things are on disk

Both the clone and the VirtualBox machine folder must be on a large drive, and
that drive differs per machine. Nothing in the kit hard-codes it.

- `~/.config/windows-vm/config.toml` holds `clone = "<path>"`. It is the only
  per-machine fact, written once.
- The VirtualBox machine folder is not stored. `wvm.py` reads it from
  `VBoxManage list systemproperties` each time, so it cannot go stale.
- The VM is found by the ID Vagrant writes to
  `<clone>/.vagrant/machines/default/virtualbox/id`, not by its name. A VM
  created without this clone cannot be driven, which is intended.
- `wvm.py where` prints the clone, the machine folder, the VM ID and the free
  space on both drives. With no config it fails with "not configured, run
  `wvm.py configure --clone <path>`".
- Until the setup step exists, the user runs `configure` once by hand.

`wvm.py` reads no environment variable for any of this. How it is tested is
not its business (see Tests).

## `scripts/wvm.py`

One script, `requires-python >= 3.11` (for `tomllib`). Its one dependency is
`pywinrm`, for the two things that need WinRM. Every
subcommand prints JSON on stdout, except `run`, which passes the guest's output
through and exits with the guest's exit code.

| Subcommand | Does | State |
| --- | --- | --- |
| `where` | clone, machine folder, VM ID, free space | done |
| `configure --clone <path>` | write the config file | done |
| `status` | state (`running`, `poweroff`, `saved`, `absent`) and whether Guest Additions answer | done |
| `run [--admin] [--shell powershell\|pwsh\|cmd] [--cwd <dir>] [--timeout <s>] -- <command>` | run one command in the VM | done |
| `copy-to [--force] <host path> <VM path>` | copy a file or folder into the VM | done |
| `copy-from [--force] <VM path> <host path>` | copy a file or folder out of the VM | done |
| `start [--headless]` | boot a stopped VM or resume a paused one, then wait for Guest Additions | done |
| `stop` | clean Windows shutdown, then wait | done |
| `pause` | save the VM's state to disk | done |
| `check-host` | VirtualBox, Vagrant and its plugins, `.env`, credentials, free space | to do |
| `provision` | run `vagrant_provision.bash` from the clone | to do |

### `run`

- Uses `VBoxManage guestcontrol <id> run`, not `vagrant winrm`. It keeps
  working when Vagrant breaks (see [JOURNAL.md](../../JOURNAL.md)) and needs no
  WinRM port forwarding.
- Runs as `user`. Because of UAC, that is unelevated even though `user` is an
  administrator. `--admin` runs as `admin` over WinRM instead, because
  `guestcontrol` is never elevated; the skill says to use it only for
  installing software or changing system settings.
- The shell is always `powershell.exe -NoProfile -NonInteractive
  -EncodedCommand` unless `--shell` names `pwsh` or `cmd`. Windows ships `powershell.exe`, and
  the setup step checks it is there.
- Runs in the user's profile folder unless `--cwd` names another.
- The password goes in with `--passwordfile <clone>/.credentials/<user>.txt`,
  so it never appears in `ps` or in the agent's transcript.
- Fails at once with a clear message when the VM is not running ("run
  `wvm.py start`") or Guest Additions do not answer yet.
- Default timeout 10 minutes.

### `copy-to` and `copy-from`

- Use `VBoxManage guestcontrol <id> copyto` and `copyfrom`, so any path in the
  VM works, not only the shared folder. Folders are copied with their contents.
- Refuse when the destination exists, naming it, unless `--force`.
- Run as `user`; there is no `--admin` for copies.

### `start`, `stop` and `pause`

- `start` runs `VBoxManage startvm <id> --type gui` (or `headless`). The same
  call boots a stopped VM and resumes a paused one, so there is no `resume`.
  It then polls `guestcontrol run ... cmd /c exit 0` until it succeeds or 10
  minutes pass, and prints the status.
- `stop` runs `shutdown /s /t 0` in the guest, because Windows ignores the
  ACPI power button while `user` is logged on, and falls back to the button
  when the guest does not answer. It waits for `poweroff`. `wvm.py` never
  offers a hard power-off.
- `start` after a pause restarts Guest Additions over WinRM when the guest
  does not answer within 20 seconds.
- `pause` runs `controlvm <id> savestate`.
- None of these go through Vagrant: none of them needs provisioning.
  `./vagrant.sh up` stays documented in `references/` for when a provisioner
  must run.

## `SKILL.md`

Frontmatter `name: windows-vm`. `description` says when to use it: "Use when
asked to run, build or test something on Windows, to move files to or from the
Windows VM, to start, stop or pause it, or to set one up on this host."

Body, one short section each, detail in `references/`:

1. **What this is**: a VirtualBox Windows 11 VM provisioned by this
   repository; two accounts; D: is a Dev Drive that survives rebuilds. Starts
   with `wvm.py where`, which also says whether this machine has a VM at all.
   Links `references/what-this-is.md`.
2. **Getting started**: `check-host`, clone onto a large drive, put the
   VirtualBox machine folder on the same drive, `.env`, `provision`,
   `configure`. Links `references/provisioning.md`.
3. **Starting and stopping**: `status`, `start`, `pause`, `stop`.
4. **Running a command and moving files**: `run`, quoting, when to use
   `--admin`, `copy-to` and `copy-from`.

## Step 4 details: getting started (later)

- **Clone location**: ask the user which drive. `check-host` lists mounts with
  free space and flags anything under 600 GB (500 GB Dev Drive plus the system
  disk). Clone with `git clone https://github.com/ftschindler/windows-vm <path>`.
- **VirtualBox**: on Manjaro, `sudo pacman -S virtualbox
  linux<kernel>-virtualbox-host-modules`, add the user to `vboxusers`, load
  `vboxdrv`. The skill gives the commands and asks before running anything
  with `sudo`; the script only checks.
- **VirtualBox machine folder**: `VBoxManage setproperty machinefolder
  <drive>/virtualbox`, only after asking, since it changes where every future
  VM goes.
- **Vagrant**: `sudo pacman -S vagrant`, then `vagrant plugin install
  vagrant-vbguest vagrant-reload`. `check-host` also catches plugins installed
  under an older Ruby and suggests the repair recorded in
  [JOURNAL.md](../../JOURNAL.md).
- **PowerShell**: the provisioning checks `powershell.exe` is present, since
  `run` relies on it.
- `.env` from `gh auth token`, then `wvm.py provision`, which runs for hours;
  the skill says to run it in the background and check `status`.
- `configure --clone` is written last, so the config only ever points at a
  clone that exists.

## Rule: `rules/windows-vm.md`

A pointer and nothing else, worded to stay true on a machine without a VM,
since it is subscribed globally on several hosts:

> To build, test or run anything on Windows, load the `windows-vm` skill. It
> says whether this machine has a Windows VM.

Frontmatter `description` is required.

## Tests

- **Script tests** (`tests/test_wvm.py`): `tests/fake_vboxmanage.py` sits first
  on `PATH` as `VBoxManage`, records its arguments and replays canned output.
  They check that:
  - `run` builds the right guestcontrol call, as `user` by default, in the
    profile folder, with `powershell.exe`;
  - the password never appears on a command line;
  - the guest's exit code comes back unchanged;
  - `run` refuses when the VM is not running;
  - `where` fails clearly with no config and finds the VM by its ID;
  - `copy-to` and `copy-from` refuse an existing destination without
    `--force`;
  - `start` resumes a saved VM, polls until the fake answers and times out
    when it never does;
  - `stop` and `pause` send `acpipowerbutton` and `savestate`, never
    `poweroff`.
- **Live test** (`tests/test_wvm_live.py`, `-m live`): skipped unless the VM
  is running. `wvm.py run -- 'Write-Output ok'` returns `ok`, and a copy round
  trip returns the same bytes. Local only, never in CI.
- **Conformance** (`tests/test_conformance.py`): name equals directory,
  `description` on the skill and the rule, every file in `references/` linked
  from `SKILL.md`, and the scripts carry the uv shebang and a PEP 723 header.
- **Recorded evidence** (`tests/probes/windows-vm.json`,
  `tests/evidence/windows-vm.json`): `record_evidence.py` gives the throwaway
  agent a fake VM. It puts `fake_vboxmanage.py` first on `PATH` and writes a
  `config.toml` pointing at a fake clone with a Vagrant ID file and
  credentials. The agent follows the skill for real against canned output, so
  the evidence shows it reaches for the skill and can follow it, without a
  running VM. Example probes:
  - "What Windows version is the VM running? Reply with the version only."
    Asserts the fake's version string, and no `vagrant winrm`.
  - "Copy notes.txt from here to the VM's desktop." Asserts a `copy-to` call
    in the fake's log.

  The skill and `wvm.py` know nothing of this setup.

### Guards copied from agent-kits

Copied into `.scripts/`: `record_evidence.py`, `check_evidence.py`,
`check_kit_layout.py`, `run-tests.py`, `extract-deps.py`, and the test helpers
`tests/kit_layout.py` and `tests/evidence_check.py` that they import. Changes
are limited to what assumes the agent-kits layout, plus the fake VM in
`record_evidence.py`. The commit names the agent-kits commit they came from, so
drift can be diffed later. Add matching `Makefile` targets and the kit-layout
and kit-evidence hooks to the existing `.pre-commit-config.yaml`.

### CI

`.github/workflows/tests.yml`, like agent-kits but on `ubuntu-latest` only:
conformance, script tests with the fake `VBoxManage`, evidence check and
`make check`. Live tests never run in CI.

## Licence

The project moves from the Unlicense to MIT: `UNLICENSE.md` becomes `LICENSE`,
and the README's licence section changes with it. Felix is the only author in
the history, so no one else has to agree. The copied scripts are MIT already
and need no separate notice.

## README

Add a short section with the `akit add` line, as the agent-kits README has, and
fix the "Nuclear cleanup" path.

## Decisions

1. Kit name `windows-vm`, subscribed globally, on this host and others.
2. Linux hosts only; CI on Ubuntu only.
3. Clone path in `~/.config/windows-vm/config.toml`; the VM is found by the ID
   Vagrant writes into the clone.
4. `run` as `user`, with `powershell.exe`, in the profile folder.
5. `copy-to` and `copy-from` in the first version; they refuse to overwrite
   without `--force`.
6. `stop` shuts down cleanly, `pause` saves state, `start` boots or resumes.
7. The rule only points at the skill, and stays true without a VM.
8. Evidence is recorded against a fake VM set up by `record_evidence.py`; the
   skill and `wvm.py` know nothing of testing.
9. Guards copied from agent-kits.
10. Licence MIT for the whole project.
11. Vagrant plugins repaired; recorded in [JOURNAL.md](../../JOURNAL.md) for the
    setup step.
