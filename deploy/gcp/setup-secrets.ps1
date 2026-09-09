param(
    [string]$ProjectId = "essential-topic-433910-r5",
    [string]$Region = "asia-south1",
    [string]$ServiceAccountEmail = "kash-ai-runner@essential-topic-433910-r5.iam.gserviceaccount.com",
    [string]$EnvFile = ".env"
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
        Start-Sleep -Seconds ([Math]::Min(15, 3 * $attempt))
    }
}

function Get-EnvMap {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Environment file not found: $Path"
    }
    $map = [ordered]@{}
    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $map[$key] = $value
    }
    return $map
}

function Convert-EnvKeyToSecretName {
    param([string]$Key)
    return ($Key.ToLowerInvariant() -replace "_", "-")
}

function Set-SecretValue {
    param(
        [string]$SecretName,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    & gcloud secrets describe $SecretName --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Creating secret $SecretName..."
        Invoke-GCloud -Arguments @("secrets", "create", $SecretName, "--project", $ProjectId, "--replication-policy", "automatic")
    }

    $tempFile = Join-Path $env:TEMP "secret-$SecretName-$([Guid]::NewGuid().ToString('N')).txt"
    try {
        Set-Content -LiteralPath $tempFile -Value $Value -NoNewline -Encoding utf8
        Invoke-GCloud -Arguments @("secrets", "versions", "add", $SecretName, "--project", $ProjectId, "--data-file", $tempFile)
    } finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
}

$envMap = Get-EnvMap -Path $EnvFile
$requestedKeys = @(
    "VERTEX_AI_PROJECT",
    "VERTEX_AI_LOCATION",
    "GEMINI_MODEL",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "EMAIL_USER",
    "EMAIL_PASSWORD",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GROQ_API_KEY",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "GOOGLE_MAPS_API_KEY",
    "GOOGLE_SPEECH_API_KEY",
    "SECRET_KEY",
    "DATABASE_URL"
)

Write-Log "Enabling Secret Manager API..."
Invoke-GCloud -Arguments @("services", "enable", "secretmanager.googleapis.com", "--project", $ProjectId)

foreach ($key in $requestedKeys) {
    if ($envMap.Contains($key) -and -not [string]::IsNullOrWhiteSpace([string]$envMap[$key])) {
        $secretName = Convert-EnvKeyToSecretName -Key $key
        Write-Log "Syncing secret for $key..."
        Set-SecretValue -SecretName $secretName -Value ([string]$envMap[$key])
        Invoke-GCloud -Arguments @(
            "secrets", "add-iam-policy-binding", $secretName,
            "--project", $ProjectId,
            "--member", "serviceAccount:$ServiceAccountEmail",
            "--role", "roles/secretmanager.secretAccessor"
        )
    }
}

Write-Log "Secret Manager setup completed."
