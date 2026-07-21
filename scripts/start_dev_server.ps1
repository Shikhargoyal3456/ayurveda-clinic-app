$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonPath = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$env:ENVIRONMENT = "development"
$env:SESSION_HTTPS_ONLY = "false"
$env:HTTPS_REDIRECT_ENABLED = "false"
$env:HOST = "127.0.0.1"
$env:PORT = "8000"

Set-Location $ProjectRoot

& $PythonPath run_server_dev.py --port 8000
