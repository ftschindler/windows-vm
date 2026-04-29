$ErrorActionPreference = 'Stop'
$progressPreference = 'SilentlyContinue'

Write-Host "=== Uninstalling Bloat Ware ==="

$packages = @(
    'Feedback Hub',
    'Game Bar',
    'Game Speech Window',
    'Microsoft 365 (Office)',
    'Microsoft Bing',
    'Microsoft Clipchamp',
    'Microsoft News',
    'Microsoft OneDrive',
    'Microsoft Photos',
    'Microsoft To Do',
    'MSN Weather',
    'Outlook for Windows',
    'Paint',
    'Phone Link',
    'Solitaire & Casual Games',
    'Windows Camera',
    'Windows Sound Recorder',
    'Xbox',
    'Xbox Identity Provider',
    'Xbox TCUI'
)

foreach ($package in $packages) {
    Write-Host "Uninstalling $package..."
    winget uninstall "$package"
}

Write-Host "=== Uninstalling Bloat Ware complete ==="
