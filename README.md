# Windows Development Environment with Vagrant

> Automated Windows 11 development VM setup using Vagrant with VirtualBox or KVM/libvirt, designed for developers who need a clean, reproducible Windows development environment.

This project provides a fully automated way to provision a Windows 11 virtual machine with proper security practices (no hardcoded passwords), a dedicated development drive, and common development tools pre-installed.

**Supported providers:** libvirt/KVM (default, recommended for Linux and CI) and VirtualBox (opt-in for cross-platform GUI)

## Features

- 🔧 **500GB Dev Drive** (D:) - Dedicated ReFS volume optimized for development work
- 🔐 **Secure credential management** - Random passwords generated locally, never committed to source control
- 👥 **Dual user setup** - `admin` account for WinRM management, `user` account for daily development
- ⚡ **Fully automated provisioning** - One-command setup with multi-phase credential switching
- 🎯 **Auto-login configured** - VM boots directly into the `user` account with a welcome screen
- 📦 **Pre-installed development tools** - Git, Node.js, Python, and more via WinGet
- 🔄 **Multi-provider support** - Works with KVM/libvirt (default, headless/CI) or VirtualBox (opt-in GUI)

## Prerequisites

### Required for All Setups

- **Vagrant** - VM orchestration tool ([installed](https://www.vagrantup.com/) on the host)
- **GitHub Personal Access Token** - Required for WinGet installation to avoid API rate limiting

   Create a `.env` file in the project root with your GitHub token:

   ```bash
   echo "GITHUB_TOKEN=$(gh auth token)" > .env
   ```

   Or manually create `.env` with:

   ```bash
   GITHUB_TOKEN=your_token_here
   ```

### Provider-Specific Requirements

Choose **one** provider based on your host OS and use case:

#### KVM/libvirt (Default - Linux only)

**Recommended** - This is the default provider and what CI uses for testing.

**Arch Linux setup:**

```bash
# Install virtualization packages
sudo pacman -S qemu-full libvirt virt-manager dnsmasq iptables-nft \
               ebtables dmidecode bridge-utils openbsd-netcat

# Install vagrant-libvirt plugin
vagrant plugin install vagrant-libvirt

# Enable and start libvirt service
sudo systemctl enable --now libvirtd.service
sudo systemctl enable --now virtlogd.service

# Add your user to libvirt group (logout/login required)
sudo usermod -aG libvirt $USER

# Verify KVM support
lsmod | grep kvm  # Should show kvm_intel or kvm_amd

# Test libvirt connection
virsh -c qemu:///system list --all
```

**Note:** KVM/libvirt runs headless by default. To view the VM GUI:

```bash
# Find the VM domain name
virsh -c qemu:///system list --all

# Connect with virt-viewer (install: sudo pacman -S virt-viewer)
virt-viewer -c qemu:///system windows-dev-throwaway
```

#### VirtualBox (Opt-in - All platforms)

Best for: Local development with GUI on any OS (Windows, macOS, Linux)

- **VirtualBox** - [Download and install](https://www.virtualbox.org/)
- **vagrant-vbguest plugin** - Auto-installed by provisioning script

```bash
vagrant plugin install vagrant-vbguest
```

**Using VirtualBox provider:**

```bash
# Specify provider when running vagrant commands
./vagrant.sh up --provider=virtualbox

# Or set default provider
export VAGRANT_DEFAULT_PROVIDER=virtualbox
./vagrant.sh up
```

## Quick Start

**KVM/libvirt (default):**

```bash
bash ./vagrant_provision.bash
```

**VirtualBox (opt-in):**

```bash
# Set provider and run
export VAGRANT_DEFAULT_PROVIDER=virtualbox
bash ./vagrant_provision.bash
```

This automated script:

1. Auto-installs required Vagrant plugins if needed
2. Generates random passwords (stored in `.credentials/`)
3. Provisions the VM through three phases with automatic reloads
4. Installs development tools (see below)
5. Configures autologon for the `user` account

**After provisioning**:

- **KVM/libvirt (default):** Connect with `virt-viewer -c qemu:///system windows-dev-throwaway`
- **VirtualBox (opt-in):** View the VM GUI to see auto-login and welcome popup

**Installed tools**: See [provision_install_tools.ps1](provision_install_tools.ps1) for the full list.

## Provisioning Flow

The provisioning happens in three phases with automatic credential switching:

| Phase | Credentials | Actions |
| --- | --- | --- |
| **Phase 1** | `vagrant:vagrant` | Create 500GB Dev Drive, create `admin` and `user` accounts, install WinGet, create admin-ready flag, reload VM |
| **Phase 2** | `vagrant:vagrant` | Install Git and development tools via WinGet, reload VM |
| **Phase 3** | `admin:ADMIN_PASSWORD` | Setup welcome popup, remove vagrant user, configure autologon for `user` |

The Vagrantfile detects the admin-ready flag and switches credentials automatically between phases.

## Manual Workflow

If you prefer step-by-step control instead of the automated script:

```bash
# 1. Create .env file with GITHUB_TOKEN (see Prerequisites)

# 2. Generate credentials (optional, auto-generated if missing)
bash ./generate-credentials.sh

# 3. Run Phases 1 & 2 (user creation, WinGet, tools installation)
./vagrant.sh up

# 4. Run Phase 3 (switch to admin credentials, finalize setup)
./vagrant.sh reload --provision

# 5. Final reload to activate autologon
./vagrant.sh reload
```

## Credentials

Passwords are stored in `.credentials/` (git-ignored):

- `admin.txt` - Admin user password (for WinRM access)
- `user.txt` - User account password (for autologon)

Credentials are passed to VM only via environment variables, never hardcoded.

## Common Commands

The [vagrant.sh](vagrant.sh) wrapper ensures correct env setup.

```bash
# Access VM via WinRM as admin
./vagrant.sh winrm

# Check VM status
./vagrant.sh status

# Shutdown VM
./vagrant.sh halt

# Start existing VM
./vagrant.sh up

# Destroy and recreate from scratch
./vagrant.sh destroy -f
bash ./vagrant_provision.bash
```

## Troubleshooting

**Missing credentials error:**

```bash
bash ./generate-credentials.sh
```

**Start over (destroy and recreate):**

```bash
./vagrant.sh destroy -f
bash ./vagrant_provision.bash
```

**Check if admin-ready flag exists:**

```bash
ls synced/admin-ready
```

## Project Structure

```text
.
├── Vagrantfile                        # Main Vagrant configuration
├── vagrant.sh                         # Wrapper script for Vagrant commands
├── vagrant_provision.bash             # Automated provisioning orchestrator
├── generate-credentials.sh            # Random password generator
├── provision_*.ps1                    # PowerShell provisioning scripts
├── synced/                           # Shared folder between host and VM
│   ├── admin-ready                   # Flag file for phase detection
└── .credentials/                     # Generated passwords (git-ignored)
```

## Customization

### Adding More Tools

Edit [provision_install_tools.ps1](provision_install_tools.ps1) and add your desired WinGet package IDs:

```powershell
winget install --id YourPackage.ID --silent --accept-source-agreements --accept-package-agreements
```

### Adjusting Dev Drive Size

**KVM/libvirt (default):** Modify the disk size in the Vagrantfile libvirt provider configuration (`libvirt.storage :file, size: '500G'`).

**VirtualBox (opt-in):** The disk size is configured when creating `devdrive.vdi`. To change it, delete the `.vdi` file and modify the size in the Vagrantfile (line with `VBoxManage createhd`).

## Continuous Integration

This project includes comprehensive CI workflows to ensure code quality and verify VM provisioning works correctly.

## License

This project is released into the **public domain** under the [Unlicense](UNLICENSE.md).

You are free to use, modify, and distribute this code for any purpose without restriction.
