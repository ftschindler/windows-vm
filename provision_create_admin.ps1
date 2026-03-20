$ErrorActionPreference = 'Stop'

Write-Host "=== Creating admin user ==="

$username = 'admin'
$password = $env:ADMIN_PASSWORD

if (-not $password) {
    Write-Error "ADMIN_PASSWORD environment variable not set"
    exit 1
}

# Create or update admin user
$securePwd = ConvertTo-SecureString -String $password -AsPlainText -Force
$userExists = Get-LocalUser -Name $username -ErrorAction SilentlyContinue

if ($userExists) {
    Write-Host "Admin user already exists. Resetting password..."
    Set-LocalUser -Name $username -Password $securePwd
} else {
    Write-Host "Creating admin user..."
    New-LocalUser -Name $username -Password $securePwd -PasswordNeverExpires:$true -UserMayNotChangePassword:$false
}

# Add to Administrators group (idempotent)
Add-LocalGroupMember -Group 'Administrators' -Member $username -ErrorAction SilentlyContinue

Write-Host "=== Admin user setup complete ==="
