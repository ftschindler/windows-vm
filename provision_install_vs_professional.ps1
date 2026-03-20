# PowerShell provisioner that installs Visual Studio Professional system-wide.
# Runs the bootstrapper with visible GUI and blocks until installation completes.
# Fails loudly on any error.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

Write-Host "=== Installing Visual Studio Professional ==="

$bootstrapperUrl = 'https://aka.ms/vs/17/release/vs_professional.exe'
$winTmp = Join-Path $env:WINDIR 'Temp'
$bootstrapper = Join-Path $winTmp 'vs_bootstrapper.exe'

if (-not (Test-Path $winTmp)) {
    New-Item -ItemType Directory -Path $winTmp -Force | Out-Null
}

# Prefer a host-provided copy in the synced folder
if (Test-Path 'C:\vagrant\vs_bootstrapper.exe') {
    Write-Host "Using host-provided bootstrapper from C:\vagrant\vs_bootstrapper.exe"
    Copy-Item -Path 'C:\vagrant\vs_bootstrapper.exe' -Destination $bootstrapper -Force
} else {
    Write-Host "Downloading bootstrapper from $bootstrapperUrl (this may take a few minutes)..."
    Invoke-WebRequest -Uri $bootstrapperUrl -OutFile $bootstrapper -UseBasicParsing
}

if (-not (Test-Path $bootstrapper) -or ((Get-Item $bootstrapper).Length -eq 0)) {
    throw "Bootstrapper not available or empty: $bootstrapper"
}

Write-Host "Bootstrapper size: $((Get-Item $bootstrapper).Length) bytes"

# Verify we're running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "This script must run as Administrator to install Visual Studio system-wide"
}

$installPath = 'C:\Program Files\Microsoft Visual Studio\2022\Professional'

$args = @(
    '--passive',  # Shows progress UI but requires no user interaction
    '--norestart',
    "--installPath=`"$installPath`"",
    '--add', 'Microsoft.VisualStudio.Workload.ManagedDesktop',
    '--add', 'Microsoft.VisualStudio.Workload.NativeDesktop',
    '--add', 'Microsoft.Net.Component.4.8.TargetingPack',
    '--add', 'Microsoft.NetCore.Component.Runtime.6.0',
    '--add', 'Microsoft.NetCore.Component.SDK',
    '--add', 'Microsoft.VisualStudio.Component.VC.ASAN',
    '--add', 'Microsoft.VisualStudio.Component.VC.ATLMFC',
    '--add', 'Microsoft.VisualStudio.Component.VC.CLI.Support',
    '--add', 'Microsoft.VisualStudio.Component.VC.CMake.Project',
    '--add', 'Microsoft.VisualStudio.Component.VC.Llvm.Clang',
    '--add', 'Microsoft.VisualStudio.Component.VC.Llvm.ClangToolset',
    '--add', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
    '--add', 'Microsoft.VisualStudio.Component.VC.v141.ATL',
    '--add', 'Microsoft.VisualStudio.Component.VC.v141.MFC',
    '--add', 'Microsoft.VisualStudio.Component.Vcpkg',
    '--add', 'Microsoft.VisualStudio.Component.Windows11SDK.26100',
    '--add', 'Microsoft.VisualStudio.ComponentGroup.NativeDesktop.Llvm.Clang'
)

Write-Host ""
Write-Host "Launching Visual Studio installer..."
Write-Host "This will take 20-40 minutes depending on your internet connection."
Write-Host "Progress will be visible in the VM GUI window."
Write-Host "This script will block until installation completes."
Write-Host ""
Write-Host "Command: $bootstrapper $($args -join ' ')"
Write-Host ""

# Launch installer with visible GUI (no -NoNewWindow flag)
$proc = Start-Process -FilePath $bootstrapper -ArgumentList $args -Wait -PassThru

if ($proc.ExitCode -ne 0) {
    throw "Visual Studio installation failed with exit code: $($proc.ExitCode)"
}

# Verify installation actually succeeded by checking for VS binaries
$vsDevEnv = Join-Path $installPath 'Common7\IDE\devenv.exe'
if (-not (Test-Path $vsDevEnv)) {
    Write-Host ""
    Write-Host "WARNING: Visual Studio installer returned success but binaries are not found!"
    Write-Host "This can happen due to network issues or catalog loading failures."
    Write-Host "Expected path: $vsDevEnv"
    Write-Host ""
    throw "Visual Studio installation verification failed - devenv.exe not found"
}

Write-Host ""
Write-Host "=== Visual Studio installation completed successfully ==="
Write-Host "Verified: $vsDevEnv exists"
Write-Host ""
