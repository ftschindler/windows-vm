$ErrorActionPreference = 'Stop'
$progressPreference = 'SilentlyContinue'

Write-Host "=== Installing WinGet ==="

# Ensure Windows time is running and clock is synced early to avoid TLS/certificate
# validation issues during network installs (winget, downloads). Fresh images often
# have w32time stopped which can lead to time skew and certificate mismatches.
try {
    Write-Host "Ensuring Windows Time service is running and syncing clock..."
    Start-Service w32time -ErrorAction Stop
    w32tm /resync /nowait /force | Out-Null
    Start-Sleep -Seconds 5
    Write-Host "Time sync attempted. Current time: $(Get-Date)"
} catch {
    Write-Error "Time sync failed: $_"
    exit 1
}

# Create temp directory
$tempDir = Join-Path $env:TEMP "winget-install"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

# Get latest WinGet release
Write-Host "Fetching latest WinGet release info..."
$headers = @{ 'User-Agent' = 'vagrant-dev-vm/1.0 (+https://github.com/)' }

# Strict mode: only accept GITHUB_TOKEN via environment (injected by Vagrant).
# No file-based fallbacks are used.
if ($env:GITHUB_TOKEN) {
    $headers['Authorization'] = ("token {0}" -f $env:GITHUB_TOKEN)
    Write-Host "Using GITHUB_TOKEN from environment variable for authenticated GitHub requests."
} else {
    Write-Error "Error: missing GITHUB_TOKEN (provided via environment); aborting."
    exit 1
}

$latestRelease = $null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
        $latestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/microsoft/winget-cli/releases/latest" -Headers $headers -ErrorAction Stop
        break
    } catch {
        $status = $null
        if ($_.Exception -and $_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = $_.Exception.Response.StatusCode.Value__
        }
        Write-Warning ("Fetch attempt {0} failed (status={1}): {2}" -f $attempt, $status, $_.Exception.Message)
        if ($status -eq 403) {
            Write-Error "GitHub API returned 403 Forbidden. This may indicate network filtering or rate limiting. Aborting winget installation step."
            exit 1
        }
        if ($attempt -lt 3) {
            Start-Sleep -Seconds (5 * $attempt)
        }
    }
}

if (-not $latestRelease) {
    Write-Error "Could not fetch WinGet release information after retries. Aborting."
    exit 1
}

$assets = $latestRelease.assets

# Download the main bundle
$wingetAsset = $assets | Where-Object { $_.name -like "*.msixbundle" }
if (-not $wingetAsset) {
    Write-Error "Could not find WinGet msixbundle in latest release."
    exit 1
}

$wingetUrl = $wingetAsset.browser_download_url
$wingetName = $wingetAsset.name
$wingetPath = Join-Path $tempDir $wingetName

Write-Host "Downloading ${wingetName}..."
try {
    Invoke-WebRequest -Uri $wingetUrl -OutFile $wingetPath -Headers $headers -ErrorAction Stop
} catch {
    Write-Error "Failed to download ${wingetName}: $($_.Exception.Message)"
    exit 1
}

# Download and install dependencies
$depAsset = $assets | Where-Object { $_.name -like "*Dependencies.zip" }
if ($depAsset) {
    Write-Host "Downloading dependencies..."
    $depUrl = $depAsset.browser_download_url
    $depZipPath = Join-Path $tempDir "dependencies.zip"

    try {
        Invoke-WebRequest -Uri $depUrl -OutFile $depZipPath -Headers $headers -ErrorAction Stop
    } catch {
        Write-Warning "Failed to download dependencies zip: $($_.Exception.Message). Proceeding without it."
        $depAsset = $null
    }

    if ($depAsset) {
        $depExtractPath = Join-Path $tempDir "dependencies"
        Expand-Archive -Path $depZipPath -DestinationPath $depExtractPath -Force

        # Find x64 dependencies
        $depFiles = Get-ChildItem -Path $depExtractPath -Recurse -Include "*.appx", "*.msix" | Where-Object { $_.FullName -like "*x64*" }

        if (-not $depFiles) {
            Write-Warning "No x64 dependencies found, trying all..."
            $depFiles = Get-ChildItem -Path $depExtractPath -Recurse -Include "*.appx", "*.msix"
        }

        foreach ($depFile in $depFiles) {
            Write-Host "Installing dependency: $($depFile.Name)..."
            try {
                # Try provisioning for all users first (more robust in WinRM/System context)
                Add-AppxProvisionedPackage -Online -PackagePath $depFile.FullName -SkipLicense -ErrorAction Stop
                Write-Host "  Provisioned successfully"
            } catch {
                Write-Warning "  Provisioning failed: $($_.Exception.Message). Falling back to per-user install..."
                try {
                    Add-AppxPackage -Path $depFile.FullName -ErrorAction Stop
                    Write-Host "  Installed successfully"
                } catch {
                    Write-Warning "  Failed to install dependency $($depFile.Name): $($_.Exception.Message)"
                    Write-Warning "  This dependency is optional - continuing with WinGet installation..."
                }
            }
        }
    }
} else {
    Write-Warning "Dependencies zip not found in release. Proceeding with bundle install..."
}

# Install WinGet bundle
Write-Host "Installing WinGet bundle..."
try {
    # Try provisioning for all users first
    Add-AppxProvisionedPackage -Online -PackagePath $wingetPath -SkipLicense -ErrorAction Stop
    Write-Host "WinGet provisioned successfully (system-wide)"
} catch {
    Write-Warning "Provisioning failed: $($_.Exception.Message). Falling back to per-user install..."
    try {
        Add-AppxPackage -Path $wingetPath -ForceUpdateFromAnyVersion -ErrorAction Stop
        Write-Host "WinGet installed successfully"
    } catch {
        Write-Error "Failed to install WinGet bundle: $($_.Exception.Message)"
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        exit 1
    }
}

# Cleanup
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

# Verify installation
Write-Host "Verifying WinGet installation..."
Start-Sleep -Seconds 2
try {
    $wingetVersion = winget --version
    if ($wingetVersion) {
        Write-Host "SUCCESS: WinGet $wingetVersion is ready!"
    }
} catch {
    Write-Warning "WinGet command not immediately available in current session."
    Write-Warning "This is expected - WinGet will be available after PATH refresh."
    Write-Host "WinGet installation packages were successfully installed."
}

Write-Host "=== WinGet installation complete ==="
