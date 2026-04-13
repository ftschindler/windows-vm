$ErrorActionPreference = 'Stop'

Write-Host "=== Configuring User Account Control (UAC) ==="

# UAC Registry Path
$registryPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

Write-Host "Setting UAC registry values..."

# ConsentPromptBehaviorAdmin: How UAC prompts administrators
# 0 = Elevate without prompting (UAC disabled for admins)
# 1 = Prompt for credentials on secure desktop
# 2 = Prompt for consent on secure desktop
# 3 = Prompt for credentials
# 4 = Prompt for consent
# 5 = Prompt for consent for non-Windows binaries (recommended for development)
Set-ItemProperty -Path $registryPath -Name "ConsentPromptBehaviorAdmin" -Value 5 -Type DWord
Write-Host "  ConsentPromptBehaviorAdmin = 5 (Prompt for consent, non-Windows binaries)"

# EnableLUA: Enable User Account Control
# 0 = Disabled (not recommended)
# 1 = Enabled (recommended)
Set-ItemProperty -Path $registryPath -Name "EnableLUA" -Value 1 -Type DWord
Write-Host "  EnableLUA = 1 (UAC enabled)"

# PromptOnSecureDesktop: Show UAC prompts on secure desktop
# 0 = Prompts on normal desktop
# 1 = Prompts on secure desktop (dimmed screen, more secure)
Set-ItemProperty -Path $registryPath -Name "PromptOnSecureDesktop" -Value 1 -Type DWord
Write-Host "  PromptOnSecureDesktop = 1 (Secure desktop for prompts)"

# ValidateAdminCodeSignatures: Only elevate signed executables
# 0 = Disabled (elevate all, recommended for development)
# 1 = Enabled (only signed binaries can elevate)
Set-ItemProperty -Path $registryPath -Name "ValidateAdminCodeSignatures" -Value 0 -Type DWord
Write-Host "  ValidateAdminCodeSignatures = 0 (Allow unsigned development tools)"

Write-Host ""
Write-Host "Verifying UAC configuration..."

# Read back and verify settings
$consentBehavior = Get-ItemProperty -Path $registryPath -Name "ConsentPromptBehaviorAdmin" | Select-Object -ExpandProperty ConsentPromptBehaviorAdmin
$enableLUA = Get-ItemProperty -Path $registryPath -Name "EnableLUA" | Select-Object -ExpandProperty EnableLUA
$secureDesktop = Get-ItemProperty -Path $registryPath -Name "PromptOnSecureDesktop" | Select-Object -ExpandProperty PromptOnSecureDesktop
$validateSigs = Get-ItemProperty -Path $registryPath -Name "ValidateAdminCodeSignatures" | Select-Object -ExpandProperty ValidateAdminCodeSignatures

Write-Host "Current UAC Settings:"
Write-Host "  ConsentPromptBehaviorAdmin: $consentBehavior (Expected: 5)"
Write-Host "  EnableLUA: $enableLUA (Expected: 1)"
Write-Host "  PromptOnSecureDesktop: $secureDesktop (Expected: 1)"
Write-Host "  ValidateAdminCodeSignatures: $validateSigs (Expected: 0)"

# Validate
$success = $true
if ($consentBehavior -ne 5) {
    Write-Warning "ConsentPromptBehaviorAdmin is $consentBehavior, expected 5"
    $success = $false
}
if ($enableLUA -ne 1) {
    Write-Warning "EnableLUA is $enableLUA, expected 1"
    $success = $false
}
if ($secureDesktop -ne 1) {
    Write-Warning "PromptOnSecureDesktop is $secureDesktop, expected 1"
    $success = $false
}
if ($validateSigs -ne 0) {
    Write-Warning "ValidateAdminCodeSignatures is $validateSigs, expected 0"
    $success = $false
}

if ($success) {
    Write-Host ""
    Write-Host "SUCCESS: UAC configured correctly!" -ForegroundColor Green
    Write-Host ""
    Write-Host "UAC Behavior:"
    Write-Host "  - User account has administrator privileges"
    Write-Host "  - Administrative actions will prompt for consent (Yes/No)"
    Write-Host "  - No password required (one-click elevation)"
    Write-Host "  - Provides security while maintaining development convenience"
} else {
    Write-Error "UAC configuration validation failed"
    exit 1
}

Write-Host ""
Write-Host "=== UAC configuration complete ==="
