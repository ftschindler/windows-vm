$ErrorActionPreference = 'Stop'

Write-Host "=== Creating unprivileged user ==="

$username = 'user'
$password = $env:USER_PASSWORD

if (-not $password) {
    Write-Error "USER_PASSWORD environment variable not set"
    exit 1
}

# Create or update user
$securePwd = ConvertTo-SecureString -String $password -AsPlainText -Force
$userExists = Get-LocalUser -Name $username -ErrorAction SilentlyContinue

if ($userExists) {
    Write-Host "User account already exists. Resetting password..."
    Set-LocalUser -Name $username -Password $securePwd
} else {
    Write-Host "Creating user account..."
    New-LocalUser -Name $username -Password $securePwd -PasswordNeverExpires:$true -UserMayNotChangePassword:$false
}

# Ensure user is in Users group and NOT in Administrators (idempotent)
Add-LocalGroupMember -Group 'Users' -Member $username -ErrorAction SilentlyContinue
Remove-LocalGroupMember -Group 'Administrators' -Member $username -ErrorAction SilentlyContinue

Write-Host "=== User account setup complete ==="
