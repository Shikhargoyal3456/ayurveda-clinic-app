param(
    [string]$ProjectId = "essential-topic-433910-r5",
    [string]$Region = "asia-south1",
    [string]$InstanceName = "kash-ai-db",
    [string]$DatabaseName = "kash_ai",
    [string]$DatabaseUser = "kash_ai_user",
    [string]$DatabasePassword = "",
    [switch]$StoreDatabaseUrlSecret = $true
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Invoke-GCloud {
    param([string[]]$Arguments, [int]$Retries = 3)
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        & gcloud @Arguments
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($attempt -eq $Retries) {
            throw "gcloud command failed: gcloud $($Arguments -join ' ')"
        }
        Start-Sleep -Seconds ([Math]::Min(15, 5 * $attempt))
    }
}

if (-not $DatabasePassword) {
    $chars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^*-_"
    $DatabasePassword = -join ((1..24) | ForEach-Object { $chars[(Get-Random -Minimum 0 -Maximum $chars.Length)] })
}

Write-Log "Enabling SQL Admin API..."
Invoke-GCloud -Arguments @("services", "enable", "sqladmin.googleapis.com", "secretmanager.googleapis.com", "--project", $ProjectId)

& gcloud sql instances describe $InstanceName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Log "Creating Cloud SQL instance $InstanceName..."
    Invoke-GCloud -Arguments @(
        "sql", "instances", "create", $InstanceName,
        "--project", $ProjectId,
        "--database-version", "POSTGRES_15",
        "--region", $Region,
        "--cpu", "1",
        "--memory", "3840MiB",
        "--storage-size", "20GB",
        "--storage-type", "SSD",
        "--availability-type", "zonal",
        "--backup-start-time", "03:00"
    )
} else {
    Write-Log "Cloud SQL instance $InstanceName already exists."
}

& gcloud sql databases describe $DatabaseName --instance $InstanceName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Log "Creating database $DatabaseName..."
    Invoke-GCloud -Arguments @("sql", "databases", "create", $DatabaseName, "--instance", $InstanceName, "--project", $ProjectId)
}

Write-Log "Creating or updating database user $DatabaseUser..."
& gcloud sql users create $DatabaseUser --instance $InstanceName --password $DatabasePassword --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-GCloud -Arguments @("sql", "users", "set-password", $DatabaseUser, "--instance", $InstanceName, "--password", $DatabasePassword, "--project", $ProjectId)
}

$connectionName = (& gcloud sql instances describe $InstanceName --project $ProjectId --format "value(connectionName)").Trim()
$encodedPassword = [System.Uri]::EscapeDataString($DatabasePassword)
$databaseUrl = "postgresql+psycopg2://${DatabaseUser}:$encodedPassword@/$DatabaseName?host=/cloudsql/$connectionName"

Write-Host ""
Write-Host "Cloud SQL instance is ready."
Write-Host "Connection name: $connectionName"
Write-Host "Database URL:"
Write-Host $databaseUrl
Write-Host ""

if ($StoreDatabaseUrlSecret) {
    $secretName = "database-url"
    & gcloud secrets describe $secretName --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-GCloud -Arguments @("secrets", "create", $secretName, "--project", $ProjectId, "--replication-policy", "automatic")
    }
    $tempFile = Join-Path $env:TEMP "database-url-$([Guid]::NewGuid().ToString('N')).txt"
    try {
        Set-Content -LiteralPath $tempFile -Value $databaseUrl -NoNewline -Encoding utf8
        Invoke-GCloud -Arguments @("secrets", "versions", "add", $secretName, "--project", $ProjectId, "--data-file", $tempFile)
    } finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
    Write-Log "Stored DATABASE_URL in Secret Manager as database-url."
}
