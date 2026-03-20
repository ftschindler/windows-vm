$ErrorActionPreference = 'Stop'

Write-Host "=== Preparing admin user for WinRM access ==="

$username = 'admin'
$password = $env:ADMIN_PASSWORD

if (-not $password) {
    Write-Error "ADMIN_PASSWORD environment variable not set"
    exit 1
}

# Ensure admin user exists
$userExists = Get-LocalUser -Name $username -ErrorAction SilentlyContinue
if (-not $userExists) {
    Write-Error "Admin user does not exist. Run create-admin provisioner first."
    exit 1
}

# Add admin to Remote Management Users group for WinRM access
try {
    Add-LocalGroupMember -Group 'Remote Management Users' -Member $username -ErrorAction SilentlyContinue
    Write-Host "Admin added to Remote Management Users group."
} catch {
    Write-Host "Admin already in Remote Management Users group."
}

# Test WinRM access for admin user
Write-Host "Testing WinRM access for admin user..."
try {
    $securePwd = ConvertTo-SecureString -String $password -AsPlainText -Force
    $credential = New-Object System.Management.Automation.PSCredential($username, $securePwd)

    # Test by running a simple command as admin via Invoke-Command
    $result = Invoke-Command -ScriptBlock {
        $env:USERNAME
    } -Credential $credential -ComputerName localhost -ErrorAction Stop

    if ($result -eq $username) {
        Write-Host "SUCCESS: WinRM test for admin user passed!"

        # Create flag file in synced folder to signal host
        $flagPath = "C:\vagrant\admin-ready"
        "ready" | Out-File -FilePath $flagPath -Encoding ASCII -Force
        Write-Host "Created admin-ready flag at $flagPath"

        Write-Host ""
        Write-Host "============================================"
        Write-Host "Admin user is ready for WinRM access!"
        Write-Host "Run 'vagrant reload --provision' to switch"
        Write-Host "to admin credentials and complete setup."
        Write-Host "============================================"
    } else {
        Write-Error "WinRM test failed: unexpected username returned"
        exit 1
    }
} catch {
    Write-Error "WinRM test failed for admin user: $_"
    Write-Error "Admin user will not be used for provisioning."
    exit 1
}

Write-Host "=== Admin WinRM preparation complete ==="
