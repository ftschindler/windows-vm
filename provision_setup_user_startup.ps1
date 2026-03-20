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

# Exit if already shown
if (Test-Path `$flagFile) {
    exit 0
}

# Show welcome message
Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    "Hello! This is your first login as the 'user' account.``n``nThis message will only appear once.",
    "Welcome to Windows Dev Environment",
    [System.Windows.MessageBoxButton]::OK,
    [System.Windows.MessageBoxImage]::Information
)

# Create flag to prevent showing again
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
