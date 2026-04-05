$ErrorActionPreference = "Stop"

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "Green"
    )
    Write-Host $Message -ForegroundColor $Color
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$issues = @()
$healthUrl = "http://localhost:8000/healthz"

try {
    $pythonProcesses = Get-Process | Where-Object { $_.Path -like "*ayurveda-runtime*" -or $_.ProcessName -like "*python*" }
    if ($pythonProcesses) {
        Write-Status "Python process detected for the app runtime." "Green"
    }
    else {
        Write-Status "No Python app process detected." "Red"
        $issues += "App process not running"
    }

    try {
        $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 10
        Write-Status "Health endpoint status: $($health.status)" "Green"
    }
    catch {
        Write-Status "Health endpoint check failed: $($_.Exception.Message)" "Red"
        $issues += "Health endpoint not responding"
    }

    try {
        $externalIp = (Invoke-RestMethod -Uri "https://ifconfig.me/ip" -Method Get -TimeoutSec 10).Trim()
        Write-Status "Public access URL: http://$externalIp:8000" "Cyan"
    }
    catch {
        Write-Status "Could not determine external IP." "Yellow"
    }

    $databaseCandidates = @(
        Join-Path $projectRoot "ayurveda.db",
        Join-Path $projectRoot "ayurveda_clinic.db"
    )
    $databasePath = $databaseCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($databasePath) {
        $dbFile = Get-Item $databasePath
        Write-Status ("Database file: {0} ({1:N2} KB)" -f $dbFile.Name, ($dbFile.Length / 1KB)) "Green"
    }
    else {
        Write-Status "Database file not found." "Red"
        $issues += "Database file missing"
    }

    $backupsDir = Join-Path $projectRoot "backups"
    if (Test-Path $backupsDir) {
        $latestBackup = Get-ChildItem $backupsDir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latestBackup) {
            $age = (Get-Date) - $latestBackup.LastWriteTime
            Write-Status ("Latest backup: {0} ({1:N1} hours old)" -f $latestBackup.Name, $age.TotalHours) "Green"
        }
        else {
            Write-Status "No backups found." "Yellow"
            $issues += "No backups found"
        }
    }

    $logFile = Join-Path $projectRoot "logs\app.log"
    if (Test-Path $logFile) {
        Write-Status "Recent application logs:" "Yellow"
        Get-Content $logFile -Tail 10
    }
    else {
        Write-Status "logs/app.log not found." "Yellow"
    }
}
catch {
    Write-Status "Monitoring failed: $($_.Exception.Message)" "Red"
    $issues += $_.Exception.Message
}

if ($issues.Count -eq 0) {
    Write-Status "System appears healthy." "Green"
    exit 0
}

Write-Status "Issues detected:" "Red"
$issues | ForEach-Object { Write-Status "- $_" "Red" }
exit 1
