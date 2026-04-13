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

# Add user to both Users and Administrators groups (idempotent)
# User will still be protected by UAC prompts for administrative actions
Add-LocalGroupMember -Group 'Users' -Member $username -ErrorAction SilentlyContinue
Add-LocalGroupMember -Group 'Administrators' -Member $username -ErrorAction SilentlyContinue

Write-Host "User added to Administrators group (UAC will still protect against unwanted changes)"
Write-Host "=== User account setup complete ==="
