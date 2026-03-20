$ErrorActionPreference = 'Stop'

Write-Host "=== Finalization: Cleanup and Autologon Setup ==="

# Verify we're running as admin user
$currentUser = $env:USERNAME
if ($currentUser -ne "admin") {
    Write-Error "This provisioner must run as admin user. Current user: $currentUser"
    Write-Error "Please run 'vagrant reload' to switch to admin credentials first."
    exit 1
}

Write-Host "Running as admin user: $currentUser"

# Step 1: Delete vagrant user
Write-Host ""
Write-Host "Step 1: Removing vagrant user..."
try {
    Remove-LocalUser -Name "vagrant" -ErrorAction Stop
    Write-Host "SUCCESS: Vagrant user removed"
} catch {
    if ($_.Exception.Message -like "*cannot find*") {
        Write-Host "Vagrant user already removed"
    } else {
        Write-Error "Failed to remove vagrant user: $($_.Exception.Message)"
        exit 1
    }
}

# Step 2: Download and configure Autologon
Write-Host ""
Write-Host "Step 2: Setting up Autologon for 'user' account..."

$password = $env:USER_PASSWORD
if (-not $password) {
    Write-Error "USER_PASSWORD environment variable not set"
    exit 1
}

$tempDir = Join-Path $env:TEMP "autologon-setup"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

$zipPath = Join-Path $tempDir "Autologon.zip"
$autologonExe = Join-Path $tempDir "Autologon.exe"

Write-Host "Downloading Autologon.exe..."
try {
    $headers = @{ 'User-Agent' = 'vagrant-dev-vm/1.0' }
    Invoke-WebRequest -Uri 'https://download.sysinternals.com/files/AutoLogon.zip' `
        -OutFile $zipPath -Headers $headers -ErrorAction Stop

    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force

    if (-not (Test-Path $autologonExe)) {
        # Try alternate spelling (capitalization)
        $autologonExe = Join-Path $tempDir "Autologon.exe"
        if (-not (Test-Path $autologonExe)) {
            # Try lowercase
            $autologonExe = Join-Path $tempDir "autologon.exe"
            if (-not (Test-Path $autologonExe)) {
                Write-Error "Autologon.exe not found after extraction"
                exit 1
            }
        }
    }

    Write-Host "Autologon.exe downloaded and extracted"
} catch {
    Write-Error "Failed to download Autologon: $($_.Exception.Message)"
    exit 1
}

Write-Host "Configuring autologon for user 'user'..."
try {
    # Run Autologon.exe: username domain password /accepteula
    # For local machine, domain is the computer name or "."
    & $autologonExe /accepteula "user" "." $password | Out-Null
    Write-Host "SUCCESS: Autologon configured for 'user'"
} catch {
    Write-Error "Failed to configure autologon: $($_.Exception.Message)"
    exit 1
}

# Cleanup
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "============================================"
Write-Host "Finalization complete!"
Write-Host "- Vagrant user has been removed"
Write-Host "- Autologon configured for 'user' account"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Run 'vagrant reload' to reboot"
Write-Host "2. The VM will auto-login as 'user'"
Write-Host "3. You'll see a welcome popup on first login"
Write-Host "============================================"
