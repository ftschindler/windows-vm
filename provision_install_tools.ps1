$ErrorActionPreference = 'Stop'
$progressPreference = 'SilentlyContinue'

Write-Host "=== Installing Tools ==="

$packages = @(
    <#
    We need WindowsTerminal before Git to ensure creation of a Git Bash profile.
    #>
    'Microsoft.WindowsTerminal',
    'Git.Git',
    <#
    Ordering of the below should not matter.
    #>
    '7zip.7zip',
    'astral-sh.uv',
    'BurntSushi.ripgrep.MSVC',
    'Chocolatey.Chocolatey',
    'cURL.cURL',
    'dandavison.delta',
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
    'Mozilla.Firefox.DeveloperEdition',
    'OpenJS.NodeJS.LTS',
    'Python.Python.3.13'
)

foreach ($package in $packages) {
    Write-Host "Installing $package..."
    winget install -e --id $package --accept-package-agreements --accept-source-agreements
}

Write-Host "=== Tools installation complete ==="
