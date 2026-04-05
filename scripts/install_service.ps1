$ErrorActionPreference = "Stop"

param(
    [switch]$Uninstall
)

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "Green"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator."
    }
}

try {
    Assert-Administrator

    $projectRoot = Split-Path -Parent $PSScriptRoot
    $pythonPath = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
    $serviceName = "AyurvedaClinic"
    $nssmPath = Join-Path $projectRoot "tools\nssm\nssm.exe"

    if (-not (Test-Path $pythonPath)) {
        throw "Working Python runtime not found at $pythonPath"
    }

    if ($Uninstall) {
        if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
            if (Test-Path $nssmPath) {
                & $nssmPath stop $serviceName | Out-Null
                & $nssmPath remove $serviceName confirm | Out-Null
            }
            else {
                sc.exe delete $serviceName | Out-Null
            }
            Write-Status "Service '$serviceName' removed." "Green"
        }
        else {
            Write-Status "Service '$serviceName' is not installed." "Yellow"
        }
        exit 0
    }

    if (-not (Test-Path $nssmPath)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $nssmPath -Parent) | Out-Null
        Write-Status "NSSM not found at $nssmPath." "Yellow"
        Write-Status "Download NSSM from https://nssm.cc/download and place nssm.exe at:" "Yellow"
        Write-Status $nssmPath "Cyan"
        throw "NSSM is required to install the Windows service."
    }

    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        Write-Status "Service '$serviceName' already exists. Updating configuration..." "Yellow"
    }
    else {
        & $nssmPath install $serviceName $pythonPath "run_server.py" | Out-Null
    }

    & $nssmPath set $serviceName AppDirectory $projectRoot | Out-Null
    & $nssmPath set $serviceName Start SERVICE_AUTO_START | Out-Null
    & $nssmPath set $serviceName AppStdout (Join-Path $projectRoot "logs\service_stdout.log") | Out-Null
    & $nssmPath set $serviceName AppStderr (Join-Path $projectRoot "logs\service_stderr.log") | Out-Null
    & $nssmPath set $serviceName AppRestartDelay 5000 | Out-Null

    sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
    Set-Service -Name $serviceName -StartupType Automatic
    Start-Service -Name $serviceName

    Write-Status "Service '$serviceName' installed and started." "Green"
    Get-Service -Name $serviceName | Format-Table -AutoSize Name, Status, StartType
}
catch {
    Write-Status "Service installation failed: $($_.Exception.Message)" "Red"
    exit 1
}
