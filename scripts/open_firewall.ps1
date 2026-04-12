$ErrorActionPreference = "Stop"

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "Green"
    )
    Write-Host $Message -ForegroundColor $Color
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator."
    }

    $ruleName = "Kash ai"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existingRule) {
        Write-Status "Firewall rule '$ruleName' already exists." "Yellow"
    }
    else {
        New-NetFirewallRule `
            -DisplayName $ruleName `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort 8000 | Out-Null
        Write-Status "Created Windows Firewall rule '$ruleName' for TCP port 8000." "Green"
    }

    Get-NetFirewallRule -DisplayName $ruleName | Format-Table -AutoSize DisplayName, Enabled, Direction, Action
}
catch {
    Write-Status "Failed to configure Windows Firewall: $($_.Exception.Message)" "Red"
    exit 1
}
