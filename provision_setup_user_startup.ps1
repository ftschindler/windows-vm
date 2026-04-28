$ErrorActionPreference = 'Stop'

Write-Host "=== Setting up user welcome message ==="

# Create a PowerShell script that shows the welcome message once
$scriptDir = "C:\ProgramData\DevVMSetup"
$psScript = Join-Path $scriptDir "show-welcome.ps1"
$flagFile = Join-Path $scriptDir "welcome-shown.flag"

# Create directory
if (-not (Test-Path $scriptDir)) {
    New-Item -ItemType Directory -Path $scriptDir -Force | Out-Null
}

# Create PowerShell script that checks flag, shows message, then creates flag
$psContent = @"
`$flagFile = '$flagFile'

if (Test-Path `$flagFile) {
    exit 0
}

`$msg = "Hello! This is your first login as the 'user' account.``n``n"
`$msg += "Theme / Appearance scripts are available in C:\vagrant\:``n"
`$msg += "  - win11_appearance_dump.ps1  (export current settings)``n"
`$msg += "  - win11_appearance_load.ps1  (restore saved settings)``n``n"

if (Test-Path "C:\vagrant\Win11AppearanceExport") {
    `$msg += "A saved appearance export was detected.``n"
    `$msg += "Run the load script to restore your settings:``n"
    `$msg += "  powershell -File C:\vagrant\win11_appearance_load.ps1``n``n"
}

`$msg += "This message will only appear once."

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    `$msg,
    "Welcome to Windows Dev Environment",
    [System.Windows.MessageBoxButton]::OK,
    [System.Windows.MessageBoxImage]::Information
)

New-Item -ItemType File -Path `$flagFile -Force | Out-Null
"@

Write-Host "Creating welcome script at: $psScript"
Set-Content -Path $psScript -Value $psContent -Encoding UTF8 -Force

# Create scheduled task to run on user logon
Write-Host "Creating scheduled task for user logon..."
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$psScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "user"
$principal = New-ScheduledTaskPrincipal -UserId "user" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "WelcomeUser" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "=== User welcome message configured ==="
Write-Host "A welcome popup will appear on next 'user' login."
