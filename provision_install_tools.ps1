$ErrorActionPreference = 'Stop'
$progressPreference = 'SilentlyContinue'

Write-Host "=== Installing Tools ==="

$packages = @(
    '7zip.7zip',
    'astral-sh.uv',
    'BurntSushi.ripgrep.MSVC',
    'Chocolatey.Chocolatey',
    'cURL.cURL',
    'dandavison.delta',
    'Git.Git',
    'GitHub.cli',
    'GnuWin32.Tar',
    'GnuWin32.UnZip',
    'GnuWin32.Zip',
    'junegunn.fzf',
    'Kitware.CMake',
    'Microsoft.NuGet',
    'Microsoft.PowerShell',
    'Microsoft.PowerToys',
    'Microsoft.VisualStudioCode',
    'Microsoft.WindowsTerminal',
    'Mozilla.Firefox.DeveloperEdition',
    'OpenJS.NodeJS.LTS',
    'Python.Python.3.13'
)

foreach ($package in $packages) {
    Write-Host "Installing $package..."
    winget install -e --id $package --accept-package-agreements --accept-source-agreements
}

# Install rsync via Cygwin (required for Vagrant rsync synced folders with libvirt)
Write-Host "Installing rsync into Cygwin..."
# Find the Cygwin setup executable (installed by the base box)
$cygwinSetup = "C:\cygwin64\setup-x86_64.exe"
if (-not (Test-Path $cygwinSetup)) {
    # Fall back to winget-installed CygwinSetup
    winget install -e --id Cygwin.CygwinSetup --accept-package-agreements --accept-source-agreements
    # Winget installs the setup executable into a versioned subdirectory under ProgramData or Program Files;
    # search common locations for setup-x86_64.exe
    $cygwinSetup = Get-ChildItem -Path 'C:\ProgramData', 'C:\Program Files', 'C:\Program Files (x86)' `
        -Filter 'setup-x86_64.exe' -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (Test-Path $cygwinSetup) {
    & $cygwinSetup --quiet-mode --no-desktop --no-shortcuts --no-startmenu `
        --site https://mirrors.kernel.org/sourceware/cygwin/ `
        -P rsync
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Cygwin rsync installation failed with exit code: $LASTEXITCODE"
        exit 1
    }
    Write-Host "rsync installed successfully via Cygwin"
} else {
    Write-Error "Could not find Cygwin setup to install rsync"
    exit 1
}

Write-Host "=== Tools installation complete ==="
