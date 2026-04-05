$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePython = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$taskName = "AyurvedaClinicDailyBackup"
$backupCommand = "`"$runtimePython`" `"$projectRoot\scripts\backup_db.py`""

if (-not (Test-Path $runtimePython)) {
    throw "Working Python runtime not found at $runtimePython"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command $backupCommand"
$trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

$email = Read-Host "Optional failure alert email address (leave blank to skip)"
if ($email) {
    Write-Host "Email alert placeholder configured for $email. Wire SMTP settings before production use."
}

Write-Host "Daily backup task registered as $taskName"
