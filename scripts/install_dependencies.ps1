$ErrorActionPreference = "Stop"

$PythonPath = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "Green"
    )
    Write-Host $Message -ForegroundColor $Color
}

try {
    if (-not (Test-Path $PythonPath)) {
        throw "Working Python runtime not found at $PythonPath"
    }

    Write-Status "Using Python runtime: $PythonPath" "Green"

    foreach ($directory in @("logs", "backups", "data", "temp")) {
        $target = Join-Path $ProjectRoot $directory
        if (-not (Test-Path $target)) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            Write-Status "Created directory: $target" "Green"
        } else {
            Write-Status "Directory already exists: $target" "Yellow"
        }
    }

    $packages = @(
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "python-multipart",
        "jinja2",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "python-dotenv",
        "requests",
        "aiosqlite",
        "pydantic",
        "slowapi",
        "psutil"
    )

    Write-Status "Installing Python packages..." "Green"
    & $PythonPath -m pip install @packages

    if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
        Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $ProjectRoot ".env")
        Write-Status "Created .env from .env.example" "Green"
    } else {
        Write-Status ".env already exists; leaving it unchanged" "Yellow"
    }

    Write-Status "Running database migration..." "Green"
    & $PythonPath (Join-Path $ProjectRoot "scripts\migrate_db.py")

    $Desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $Desktop "Kash ai.lnk"
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "powershell.exe"
    $Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$ProjectRoot\start_local.ps1`""
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.Description = "Launch Kash ai"
    $Shortcut.Save()
    Write-Status "Created desktop shortcut: $ShortcutPath" "Green"

    Write-Status "Installation completed successfully." "Green"
}
catch {
    Write-Status "Installation failed: $($_.Exception.Message)" "Red"
    exit 1
}
