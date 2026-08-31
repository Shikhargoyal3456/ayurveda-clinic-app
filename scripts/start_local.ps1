# start_local.ps1 - Kash ai Launcher
# Simplified working version

$ErrorActionPreference = "Stop"

# Configuration
$PythonPath = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ProjectRoot ".env"

Write-Host ""
Write-Host "=== Kash ai ===" -ForegroundColor Green
Write-Host ""

# Check if Python exists
if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Python not found at $PythonPath" -ForegroundColor Red
    Write-Host "Please ensure the Ayurveda runtime is installed correctly." -ForegroundColor Red
    exit 1
}

# Load environment variables
if (Test-Path $EnvFile) {
    Write-Host "Loading environment from .env" -ForegroundColor Green
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
} else {
    Write-Host "Warning: .env file not found. Using defaults." -ForegroundColor Yellow
}

# Local launcher uses plain HTTP. Keep production HTTPS/session-cookie guards for deployed runs,
# but start this process as development unless LOCAL_HTTPS=true is explicitly set.
$localHttpsValue = [Environment]::GetEnvironmentVariable("LOCAL_HTTPS", "Process")
if ($localHttpsValue -ne "true") {
    [Environment]::SetEnvironmentVariable("ENVIRONMENT", "development", "Process")
    [Environment]::SetEnvironmentVariable("SESSION_HTTPS_ONLY", "false", "Process")
    [Environment]::SetEnvironmentVariable("HTTPS_REDIRECT_ENABLED", "false", "Process")
}

# Get settings
$hostValue = [Environment]::GetEnvironmentVariable("HOST", "Process")
if (-not $hostValue) { $hostValue = "0.0.0.0" }

$portValue = [Environment]::GetEnvironmentVariable("PORT", "Process")
if (-not $portValue) { $portValue = "8000" }

$debugValue = [Environment]::GetEnvironmentVariable("DEBUG", "Process")
$envValue = [Environment]::GetEnvironmentVariable("ENVIRONMENT", "Process")

# Check production settings
if ($envValue -eq "production") {
    if ($debugValue -eq "true") {
        Write-Host "WARNING: DEBUG=true in production! This is insecure!" -ForegroundColor Red
    }
    if ($hostValue -eq "127.0.0.1") {
        Write-Host "WARNING: HOST=127.0.0.1 in production! External access will not work!" -ForegroundColor Red
        Write-Host "   Set HOST=0.0.0.0 in .env for external access" -ForegroundColor Yellow
    }
}

# Show configuration
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Environment: $envValue" -ForegroundColor White
Write-Host "  Debug mode: $debugValue" -ForegroundColor White
Write-Host "  Host binding: ${hostValue}:${portValue}" -ForegroundColor White
Write-Host ""

# Detect external IP (if HOST is 0.0.0.0)
if ($hostValue -eq "0.0.0.0") {
    try {
        $externalIp = (Invoke-WebRequest -Uri "http://ifconfig.me/ip" -UseBasicParsing -TimeoutSec 5).Content.Trim()
        Write-Host "Public access URL: http://${externalIp}:${portValue}" -ForegroundColor Green
    } catch {
        Write-Host "Could not detect external IP automatically" -ForegroundColor Yellow
        Write-Host "   Find your IP at: https://whatismyipaddress.com" -ForegroundColor Yellow
    }
    Write-Host "Local access URL: http://localhost:${portValue}" -ForegroundColor Cyan
    Write-Host "Health check: http://localhost:${portValue}/healthz" -ForegroundColor Cyan
} else {
    Write-Host "Local access URL: http://${hostValue}:${portValue}" -ForegroundColor Cyan
}

Write-Host ""

# Check RAG status
try {
    $ragOutput = & $PythonPath -c "from app.rag_engine import get_rag_engine; e = get_rag_engine(); s = e.get_status(); print(f'RAG Ready | Chunks: {s.get(\"indexed_chunks\", 0)} | Ollama: {s.get(\"ollama_available\", False)}')" 2>$null
    if ($ragOutput) {
        Write-Host $ragOutput -ForegroundColor Green
    } else {
        Write-Host "RAG status: Available" -ForegroundColor Green
    }
} catch {
    Write-Host "RAG status: Check skipped (not critical)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting application..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Log startup
$logDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logDir)) { 
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null 
}
$startupLog = Join-Path $logDir "startup.log"
"$(Get-Date -Format s) Starting app on ${hostValue}:${portValue}" | Out-File -FilePath $startupLog -Append

# Start the application
& $PythonPath -m uvicorn app.main:app --host $hostValue --port $portValue

# If we get here, the app stopped
Write-Host ""
Write-Host "Application stopped." -ForegroundColor Yellow
