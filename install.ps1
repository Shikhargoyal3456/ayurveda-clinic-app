$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimePython = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$installDir = Join-Path ${env:ProgramFiles} "AyurvedaClinicManagementSystem"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Ayurveda Clinic Management System.lnk"

if (-not (Test-Path $runtimePython)) {
    throw "Working Python runtime not found at $runtimePython"
}

Write-Host "Installing application to $installDir"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
foreach ($dir in @("logs", "data", "backups", "vector_store", "samhita_pdfs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $installDir $dir) | Out-Null
}

Copy-Item -Path (Join-Path $projectRoot "*") -Destination $installDir -Recurse -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installDir "launch_helper.bat"
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Ayurveda Clinic Management System"
$shortcut.Save()

$startupChoice = Read-Host "Add the app launcher to Windows startup? (y/N)"
if ($startupChoice -match "^(y|Y)$") {
    $startupFolder = [Environment]::GetFolderPath("Startup")
    $startupShortcut = Join-Path $startupFolder "Ayurveda Clinic Management System.lnk"
    Copy-Item $shortcutPath $startupShortcut -Force
    Write-Host "Startup shortcut created at $startupShortcut"
}

Write-Host "Installation complete."
