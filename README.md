# Windows Development Environment with Vagrant

> Automated Windows 11 development VM setup using Vagrant and VirtualBox, designed for developers who need a clean, reproducible Windows development environment.

This project provides a fully automated way to provision a Windows 11 virtual machine with proper security practices (no hardcoded passwords), a dedicated development drive, and common development tools pre-installed.

## Features

- 🔧 **500GB Dev Drive** (D:) - Dedicated ReFS volume optimized for development work
- 🔐 **Secure credential management** - Random passwords generated locally, never committed to source control
- 👥 **Dual user setup** - `admin` account for WinRM management, `user` account for daily development
- 🛡️ **UAC configured** - User has admin rights with one-click elevation for installs and system changes
- ⚡ **Fully automated provisioning** - One-command setup with multi-phase credential switching
- 🎯 **Auto-login configured** - VM boots directly into the `user` account with a welcome screen
- 📦 **Pre-installed development tools** - Git, Node.js, Python, and more via WinGet
- 🔄 **Guest Additions** - Automatically managed via vagrant-vbguest plugin

## Prerequisites

- **VirtualBox** - Virtualization platform ([installed](https://www.virtualbox.org/) on the host)
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

## Quick Start

```bash
bash ./vagrant_provision.bash
```

This automated script:

1. Auto-installs `vagrant-vbguest` plugin if needed
2. Generates random passwords (stored in `.credentials/`)
3. Provisions the VM through three phases with automatic reloads
4. Installs development tools (see below)
5. Configures autologon for the `user` account

**After provisioning**: View the VM GUI to see auto-login and welcome popup.

**Installed tools**: See [provision_install_tools.ps1](provision_install_tools.ps1) for the full list.

## Provisioning Flow

The provisioning happens in three phases with automatic credential switching:

| Phase | Credentials | Actions |
| --- | --- | --- |
| **Phase 1** | `vagrant:vagrant` | Create 500GB Dev Drive, create `admin` and `user` accounts, install WinGet, create admin-ready flag, reload VM |
| **Phase 2** | `vagrant:vagrant` | Install Git and development tools via WinGet, reload VM |
| **Phase 3** | `admin:ADMIN_PASSWORD` | Configure UAC for user account, setup welcome popup, remove vagrant user, configure autologon for `user` |

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

## User Account Control (UAC)

The `user` account is a member of the Administrators group but protected by User Account Control:

- **Installing software** - UAC prompts "Do you want to allow this app to make changes?" - click **Yes**
- **System modifications** - Protected by UAC consent prompts (no password required, just click confirmation)
- **Development work** - Runs with standard user privileges until elevation is needed
- **Security + Convenience** - Prevents accidental system changes while allowing one-click elevation

**Why two accounts?**

- `user` - Your daily development account (auto-login, UAC-protected admin rights)
- `admin` - Reserved for Vagrant/WinRM infrastructure operations only

This setup follows Windows development best practices: admin privileges when needed, UAC protection always active.

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

**Verify UAC settings (from within VM):**

Open PowerShell as administrator and run:

```powershell
Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" | Select-Object EnableLUA, ConsentPromptBehaviorAdmin
```

Expected output: `EnableLUA = 1`, `ConsentPromptBehaviorAdmin = 5`

**Check if user is in Administrators group (from within VM):**

```powershell
Get-LocalGroupMember -Group "Administrators"
```

Should show both `admin` and `user` accounts.

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

Modify the `devdrive.vdi` size in [provision_setup_drives.ps1](provision_setup_drives.ps1).

## Contributing

Contributions are welcome! This project is in the public domain (see License below).

If you have improvements or bug fixes:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

Feel free to open issues for bugs, feature requests, or questions.

## License

This project is released into the **public domain** under the [Unlicense](UNLICENSE.md).

You are free to use, modify, and distribute this code for any purpose without restriction.

## Acknowledgments

- Built with [Vagrant](https://www.vagrantup.com/) and [VirtualBox](https://www.virtualbox.org/)
- Uses [WinGet](https://github.com/microsoft/winget-cli) for package management
- Inspired by the need for reproducible Windows development environments
