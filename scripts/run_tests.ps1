$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePython = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$baseTemp = Join-Path $projectRoot "logs\pytest-temp-root"

if (-not (Test-Path $runtimePython)) {
    Write-Error "Clean runtime not found at $runtimePython. Recreate it before running tests."
}

New-Item -ItemType Directory -Force -Path $baseTemp | Out-Null
$env:TMP = $baseTemp
$env:TEMP = $baseTemp
$env:PYTEST_DEBUG_TEMPROOT = $baseTemp

Set-Location $projectRoot

& $runtimePython -m pytest -v
