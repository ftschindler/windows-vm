# Troubleshooting the Windows VM

Each section starts with what `wvm` printed.

## "not configured"

`~/.config/windows-vm/config.toml` does not exist. Ask the user whether this
machine has a windows-vm clone and where, then run
`wvm configure --clone <path>`. Do not search for one.

## "no VM has been created from ... yet"

The clone exists, but Vagrant never created a VM from it, or it was destroyed.
Creating one is provisioning, which takes hours and is the user's to start
with `bash ./vagrant_provision.bash` in the clone.

## "VirtualBox has no VM ..."

The clone names a VM that VirtualBox no longer knows, usually after a
`vagrant destroy` or a VirtualBox reinstall. Tell the user; do not delete
anything.

## "the VM is saved, not running" (or poweroff, aborted)

Run `wvm start`. `aborted` means the VM was killed, for example by the host
shutting down; Windows boots normally and may check its disks.

## "Windows did not answer within ... s"

The VM is running but Guest Additions, which `wvm` talks through, do not
answer.

- After a boot, Windows may still be installing updates. Run `wvm status`
  in a few minutes; the window shows what it is doing.
- After resuming from a pause, `wvm start` has already restarted Guest
  Additions over WinRM once. If that did not help, `wvm stop` and
  `wvm start` boots it afresh.

## "WinRM as admin failed"

WinRM is what `run --admin` and the recovery after a pause use. It needs the
port Vagrant forwards to 5985 and the password in the clone's
`.credentials/admin.txt`. A refused connection usually means Windows is still
booting; try again in a minute.

## "Windows did not shut down"

A program refused to close, usually over unsaved work. Tell the user, who can
see it in the VM's window. Do not power the VM off.

## "VBoxManage failed (exit ...) before the command ran"

VirtualBox could not start the command at all. Its own message is printed
above. "The guest execution service is not ready" means the same as "Windows
did not answer", above.

## Vagrant itself fails

`wvm` does not need Vagrant, but provisioning does. After the host's Ruby is
upgraded, every `vagrant` command can fail with "The plugins failed to
initialize correctly". `vagrant plugin repair` fixes it; the clone's
`JOURNAL.md` has the details.
