# Journal

Things learned while building the `windows-vm` kit that the onboarding and
setup step (step 4 of [the plan](skills/windows-vm/PLAN.md)) has to handle.

## 2026-11-09: Vagrant plugins break when pacman upgrades Ruby

**Symptom.** Every `vagrant` command, even `vagrant global-status`, failed
before doing anything:

```text
Vagrant failed to initialize at a very early stage:
The plugins failed to initialize correctly.
```

**Cause.** Manjaro had upgraded `ruby` from 3.4.8 to 3.4.10. Vagrant 2.4.9 is
the Arch package and runs on the system Ruby, so its plugin gems live in a
directory named after the Ruby version: `~/.vagrant.d/gems/<ruby-version>/`.
The plugins (`vagrant-reload` 0.0.1, `vagrant-vbguest` 0.32.0) were installed
under `3.4.8/`, and `3.4.10/` did not exist yet.

**Fix.**

1. `vagrant plugin repair` created `~/.vagrant.d/gems/3.4.10/` and installed
   gems into it, but still reported "Unable to resolve dependency: user
   requested 'vagrant-reload (= 0.0.1)'".
2. `vagrant plugin expunge --reinstall` then stopped at a confirmation prompt
   because it had no TTY. By then `vagrant plugin list`, `vagrant status` and
   `./vagrant.sh winrm -c whoami` all worked, so it was not run again.

**For the setup step.**

- `check-host` should check that `~/.vagrant.d/gems/$(ruby -e 'print
  RUBY_VERSION')/` exists whenever `~/.vagrant.d/plugins.json` lists plugins,
  and if it does not, suggest `vagrant plugin repair`. If that is not enough,
  suggest `vagrant plugin expunge --reinstall`, which needs a terminal (or
  `--force`) and asks before running.
- This comes back after every Ruby upgrade, not just at first setup. Starting
  and running commands in the VM therefore use `VBoxManage guestcontrol` and do
  not depend on Vagrant.
- `~/.vagrant.d/gems/3.4.8/` is now stale and can be removed once nothing
  needs it.

## 2026-11-10: What VirtualBox's guest control does that the plan did not expect

Found while building `wvm.py` against the running VM (VirtualBox 7.2.16 on the
host, Guest Additions 7.2.6 in the guest).

- **Arguments after `--` are argv[1] onwards.** Passing the program name
  again, as `-- powershell.exe -Command ...`, starts a second PowerShell
  inside the first, which looked like broken exit codes and quoting.
- **Double quotes inside an argument are lost.** `wvm.py` therefore hands
  PowerShell the command base64-encoded (`-EncodedCommand`), and hands `cmd`
  its command line verbatim (`--unquoted-args` with `/s /c "..."`).
- **A guest exit code n comes back as 32 + n.** 1 to 31 are VBoxManage's own
  failures.
- **PowerShell's stderr is CLIXML** when it is not a console. `wvm.py`
  decodes it back to text.
- **`guestcontrol` never runs elevated**, not even as `admin`: UAC filters
  every local administrator except the built-in one. WinRM as `admin` on the
  port Vagrant forwards is elevated, so `run --admin` goes over WinRM
  (`pywinrm`, basic auth, as Vagrant itself does).
- **Windows ignores the ACPI power button while `user` is logged on.** `stop`
  runs `shutdown /s /t 0` in the guest instead, which is not forced.
- **After resuming from a saved state, Guest Additions sometimes refuse every
  new session** ("Error starting guest session (current status is:
  terminated)") and do not recover on their own. Restarting `VBoxService` in
  the guest fixes it, so `start` does that over WinRM when a resumed VM does
  not answer within 20 seconds. Updating the Guest Additions to match the
  host may fix the cause; not tried yet.
- **Right after `savestate`, VirtualBox holds the VM's session for a few
  seconds** and refuses both `showvminfo` and `startvm`. Both are retried.
