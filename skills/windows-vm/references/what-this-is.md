# What the Windows VM is

A Windows 11 VM in VirtualBox, built by Vagrant from a clone of
[windows-vm](https://github.com/ftschindler/windows-vm). The clone's
[README](https://github.com/ftschindler/windows-vm/blob/main/README.md) is the
full account; this is what an agent needs from it.

## Accounts

| Account | Used for | Elevated |
| --- | --- | --- |
| `user` | everything `wvm run` does, and the person at the screen | no, although an administrator: UAC asks first |
| `admin` | `wvm run --admin`, and Vagrant's provisioning | yes, over WinRM |

The VM logs `user` on automatically when it boots. The passwords are random,
generated on the host into the clone's `.credentials/`, and `wvm` hands them
to VirtualBox as files. Never print or copy them.

## Drives and folders

- **`C:`** is the system drive. It is rebuilt when the VM is destroyed and
  provisioned again.
- **`D:`** is a 500 GB Dev Drive, stored as `devdrive.vdi` in the clone. It
  survives rebuilds, so it is where source code and builds belong.
- **`C:\vagrant`** is the clone, shared from the host. It is slow for builds;
  use `wvm copy-to` and `copy-from` to move files instead.

## Installed tools

Git, Node.js, Python and the other tools listed in the clone's
`provision_install_tools.ps1`, installed with WinGet. Check before assuming
one is there:

```sh
wvm run -- 'Get-Command git, node, python | Format-Table Name, Version'
```

Installing more needs `--admin`, and usually `winget install --id <id>
--silent --accept-source-agreements --accept-package-agreements`.

## What `wvm` does not do

It does not create, provision or destroy the VM. Those go through
`vagrant_provision.bash` and `vagrant.sh` in the clone, take hours or destroy
work, and are the user's to start.
