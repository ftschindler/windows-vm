---
name: windows-vm
description: Use when asked to build, test or run something on Windows, to move files to or from the Windows VM, or to start, stop or pause it. Also use to find out whether this machine has a Windows VM at all.
---

# Windows VM

Some Linux machines run a Windows 11 VM in VirtualBox, built from a clone of
[windows-vm](https://github.com/ftschindler/windows-vm). You drive it from the
host with one script, and never with `VBoxManage` or `vagrant` directly.

## The script

Every command goes through `scripts/wvm.py`, beside this file, run with
`uv run --script`. From here on, `wvm` means:

```sh
uv run --script <this skill's directory>/scripts/wvm.py
```

`wvm --help` lists the subcommands, and `wvm <subcommand> --help` explains
one. Every subcommand prints JSON, except `run`, which prints what the command
in the VM printed.

## Does this machine have a VM?

```sh
wvm where
```

This prints where the clone and the VirtualBox machine folder are, and the
VM's ID. If it says "not configured", this machine either has no Windows VM or
nobody has said where its clone is. Ask the user which; do not search the disk
for a clone, and do not guess a path.

When the user names the clone, record it once:

```sh
wvm configure --clone <path to the clone>
```

What the VM contains, its two accounts and its drives are in
[references/what-this-is.md](references/what-this-is.md). Read it before your
first command in the VM.

## Starting, stopping and pausing

```sh
wvm status   # state: running, poweroff, saved (paused) or aborted
wvm start    # boots it, or resumes it if paused, and waits for Windows
wvm pause    # saves its state to disk; `start` resumes exactly there
wvm stop     # shuts Windows down cleanly
```

`start` opens the VM's window, because the user may want to watch; add
`--headless` when they said they do not. Booting takes around a minute and
resuming around 5 to 40 seconds.

**Leave the VM in the state you found it.** If you started it, pause or stop it
when the task is done unless the user wants it running. Never power it off
with VirtualBox: that is pulling the plug, and D: holds work that survives
rebuilds. If `stop` reports that Windows did not shut down, tell the user; a
program with unsaved work is usually holding it.

## Running a command

```sh
wvm run -- '<PowerShell command>'
```

- It runs as `user`, in Windows PowerShell 5.1, in `C:\Users\user`.
- Put the whole command in single quotes on the host, so the host shell leaves
  `$` and `"` alone. Inside, write PowerShell as you would at a prompt.
- `wvm run` exits with the command's exit code, including a native program's,
  and prints its output and errors.
- `--cwd <folder>` runs it elsewhere. Work belongs on `D:\`, the Dev Drive.
- `--shell cmd` or `--shell pwsh` uses `cmd.exe` or PowerShell 7 instead.
- `--timeout <seconds>` raises the limit of 600 seconds for a long build.

`user` is an administrator, but runs unelevated. For anything needing
elevation, such as installing software or changing system settings, add
`--admin`. That runs as the `admin` account, elevated, in PowerShell 5.1 only.
Ask the user first unless they asked for the change.

## Moving files

```sh
wvm copy-to <host path> '<VM path>'
wvm copy-from '<VM path>' <host path>
```

Both copy a file, or a folder with everything in it, to exactly the
destination path given. They refuse to replace something that is already
there; add `--force` only when the user wants it replaced.

## When something fails

[references/troubleshooting.md](references/troubleshooting.md) covers each
error `wvm` reports and what to do about it.
