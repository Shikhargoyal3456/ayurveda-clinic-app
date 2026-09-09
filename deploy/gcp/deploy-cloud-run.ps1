param(
    [string]$ProjectId = "essential-topic-433910-r5",
    [string]$Region = "asia-south1",
    [string]$ServiceName = "kash-ai",
    [string]$Repository = "kash-ai-repo",
    [string]$ImageName = "kash-ai",
    [string]$RuntimeServiceAccountName = "kash-ai-runner",
    [string]$MigrationJobName = "kash-ai-migrate",
    [string]$EnvFile = ".env",
    [switch]$SetupSecrets,
    [switch]$SetupCloudSql,
    [switch]$SkipBuild,
    [switch]$SkipMigrations,
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Invoke-GCloud {
    param(
        [string[]]$Arguments,
        [int]$Retries = 3
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        & gcloud @Arguments
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($attempt -eq $Retries) {
            throw "gcloud command failed after $Retries attempts: gcloud $($Arguments -join ' ')"
        }
        Start-Sleep -Seconds ([Math]::Min(15, 3 * $attempt))
        Write-Log "Retrying gcloud command ($attempt/$Retries)..."
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

function Ensure-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Ensure-ArtifactRegistry {
    param([string]$Project, [string]$Location, [string]$Repo)
    & gcloud artifacts repositories describe $Repo --location $Location --project $Project *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Creating Artifact Registry repository $Repo..."
        Invoke-GCloud -Arguments @("artifacts", "repositories", "create", $Repo, "--project", $Project, "--location", $Location, "--repository-format", "docker", "--description", "Dr. Kash AI production images")
    }
}

function Ensure-ServiceAccount {
    param([string]$Project, [string]$Name)
    $email = "$Name@$Project.iam.gserviceaccount.com"
    & gcloud iam service-accounts describe $email --project $Project *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Creating service account $email..."
        Invoke-GCloud -Arguments @("iam", "service-accounts", "create", $Name, "--project", $Project, "--display-name", "Dr. Kash AI Cloud Run runtime")
    }
    return $email
}

function Ensure-ProjectServices {
    param([string]$Project)
    Write-Log "Enabling required GCP APIs..."
    Invoke-GCloud -Arguments @(
        "services", "enable",
        "run.googleapis.com",
        "artifactregistry.googleapis.com",
        "secretmanager.googleapis.com",
        "cloudbuild.googleapis.com",
        "sqladmin.googleapis.com",
        "aiplatform.googleapis.com",
        "--project", $Project
    )
}

function Ensure-CloudSqlAccess {
    param([string]$Project, [string]$ServiceAccountEmail)
    Invoke-GCloud -Arguments @(
        "projects", "add-iam-policy-binding", $Project,
        "--member", "serviceAccount:$ServiceAccountEmail",
        "--role", "roles/cloudsql.client"
    )
}

function Get-SecretBindings {
    param(
        [System.Collections.IDictionary]$EnvMap,
        [string[]]$PlainEnvKeys
    )

    $bindings = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $EnvMap.GetEnumerator()) {
        if ([string]::IsNullOrWhiteSpace($entry.Value)) {
            continue
        }
        if ($PlainEnvKeys -contains $entry.Key) {
            continue
        }
        $secretName = Convert-EnvKeyToSecretName -Key $entry.Key
        & gcloud secrets describe $secretName --project $ProjectId *> $null
        if ($LASTEXITCODE -eq 0) {
            $bindings.Add("$($entry.Key)=$secretName:latest")
        }
    }
    return $bindings
}

function New-EnvYamlFile {
    param(
        [System.Collections.IDictionary]$EnvMap,
        [string[]]$PlainEnvKeys
    )

    $filePath = Join-Path $env:TEMP "kash-ai-cloudrun-env-$([Guid]::NewGuid().ToString('N')).yaml"
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($key in $PlainEnvKeys) {
        if (-not $EnvMap.Contains($key)) {
            continue
        }
        $value = [string]$EnvMap[$key]
        $escaped = $value.Replace("'", "''")
        $lines.Add("${key}: '$escaped'")
    }
    Set-Content -LiteralPath $filePath -Value $lines -Encoding utf8
    return $filePath
}

function Test-HttpStatus {
    param(
        [string]$Url,
        [int]$ExpectedStatus,
        [string]$Label,
        [int]$Attempts = 20
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method Get -MaximumRedirection 0 -SkipHttpErrorCheck -TimeoutSec 30
            if ([int]$response.StatusCode -eq $ExpectedStatus) {
                Write-Log "$Label check passed with HTTP $ExpectedStatus."
                return
            }
        } catch {
            $statusCode = $_.Exception.Response.StatusCode.value__
            if ($statusCode -eq $ExpectedStatus) {
                Write-Log "$Label check passed with HTTP $ExpectedStatus."
                return
            }
        }
        Start-Sleep -Seconds 5
    }
    throw "$Label check failed for $Url"
}

Ensure-Command -Name "gcloud"
Ensure-Command -Name "docker"

$envMap = Get-EnvMap -Path $EnvFile
$plainEnvKeys = @(
    "APP_ENV",
    "APP_NAME",
    "APP_VERSION",
    "ENVIRONMENT",
    "DEBUG",
    "HOST",
    "PORT",
    "UVICORN_RELOAD",
    "GOOGLE_REDIRECT_URI",
    "PILOT_BYPASS_SUBSCRIPTIONS",
    "SESSION_HTTPS_ONLY",
    "CSRF_ENABLED",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "RAZORPAY_MODE",
    "ALLOWED_ORIGINS",
    "TRUSTED_HOSTS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_PERIOD",
    "API_IP_RATE_LIMIT_REQUESTS",
    "API_IP_RATE_LIMIT_PERIOD",
    "API_USER_RATE_LIMIT_REQUESTS",
    "API_USER_RATE_LIMIT_PERIOD",
    "MAX_CONCURRENT_REQUESTS",
    "OVERLOAD_QUEUE_TIMEOUT_SECONDS",
    "CACHE_ENABLED",
    "CACHE_TTL",
    "BACKUP_ENABLED",
    "BACKUP_RETENTION_DAYS",
    "CLOUD_RUN_MEMORY",
    "CLOUD_RUN_CONCURRENCY",
    "HTTPS_REDIRECT_ENABLED",
    "REQUIRE_HTTPS_IN_PRODUCTION"
)

if (-not $envMap.Contains("ENVIRONMENT") -and -not $envMap.Contains("APP_ENV")) {
    $envMap["ENVIRONMENT"] = "production"
}
if (-not $envMap.Contains("DEBUG")) {
    $envMap["DEBUG"] = "false"
}
if (-not $envMap.Contains("PORT")) {
    $envMap["PORT"] = "8080"
}
if (-not $envMap.Contains("CLOUD_RUN_MEMORY")) {
    $envMap["CLOUD_RUN_MEMORY"] = "1Gi"
}
if (-not $envMap.Contains("CLOUD_RUN_CONCURRENCY")) {
    $envMap["CLOUD_RUN_CONCURRENCY"] = "80"
}

Ensure-ProjectServices -Project $ProjectId
Invoke-GCloud -Arguments @("config", "set", "project", $ProjectId)
Ensure-ArtifactRegistry -Project $ProjectId -Location $Region -Repo $Repository
$runtimeServiceAccount = Ensure-ServiceAccount -Project $ProjectId -Name $RuntimeServiceAccountName

if ($SetupSecrets) {
    Write-Log "Running secret setup..."
    & pwsh -File (Join-Path $PSScriptRoot "setup-secrets.ps1") -ProjectId $ProjectId -Region $Region -ServiceAccountEmail $runtimeServiceAccount -EnvFile $EnvFile
    if ($LASTEXITCODE -ne 0) {
        throw "Secret setup failed."
    }
}

if ($SetupCloudSql) {
    Write-Log "Running Cloud SQL setup..."
    & pwsh -File (Join-Path $PSScriptRoot "setup-cloud-sql.ps1") -ProjectId $ProjectId -Region $Region
    if ($LASTEXITCODE -ne 0) {
        throw "Cloud SQL setup failed."
    }
}

$secretBindings = Get-SecretBindings -EnvMap $envMap -PlainEnvKeys $plainEnvKeys
$envYaml = New-EnvYamlFile -EnvMap $envMap -PlainEnvKeys $plainEnvKeys
$cloudSqlInstanceName = "kash-ai-db"
$cloudSqlConnection = "${ProjectId}:${Region}:${cloudSqlInstanceName}"
& gcloud sql instances describe $cloudSqlInstanceName --project $ProjectId *> $null
$cloudSqlExists = $LASTEXITCODE -eq 0

try {
    Invoke-GCloud -Arguments @("auth", "configure-docker", "$Region-docker.pkg.dev", "--quiet")

    $imageTag = Get-Date -Format "yyyyMMdd-HHmmss"
    $imageUri = "${Region}-docker.pkg.dev/$ProjectId/$Repository/${ImageName}:$imageTag"
    $latestUri = "${Region}-docker.pkg.dev/$ProjectId/$Repository/${ImageName}:latest"

    if (-not $SkipBuild) {
        Write-Log "Building Docker image $imageUri..."
        & docker build -t $imageUri -t $latestUri .
        if ($LASTEXITCODE -ne 0) {
            throw "Docker build failed."
        }

        Write-Log "Pushing Docker image tags..."
        & docker push $imageUri
        if ($LASTEXITCODE -ne 0) {
            throw "Docker push failed for $imageUri."
        }
        & docker push $latestUri
        if ($LASTEXITCODE -ne 0) {
            throw "Docker push failed for $latestUri."
        }
    }

    Ensure-CloudSqlAccess -Project $ProjectId -ServiceAccountEmail $runtimeServiceAccount

    if (-not $SkipMigrations) {
        Write-Log "Creating or updating Cloud Run migration job..."
        $jobArgs = @(
            "run", "jobs", "deploy", $MigrationJobName,
            "--project", $ProjectId,
            "--region", $Region,
            "--image", $imageUri,
            "--service-account", $runtimeServiceAccount,
            "--memory", "1Gi",
            "--cpu", "1",
            "--task-timeout", "300",
            "--max-retries", "1",
            "--command", "alembic",
            "--args", "upgrade,head",
            "--env-vars-file", $envYaml
        )
        if ($secretBindings.Count -gt 0) {
            $jobArgs += @("--set-secrets", ($secretBindings -join ","))
        }
        if ($cloudSqlExists) {
            $jobArgs += @("--set-cloudsql-instances", $cloudSqlConnection)
        }
        Invoke-GCloud -Arguments $jobArgs

        Write-Log "Executing Cloud Run migration job..."
        Invoke-GCloud -Arguments @("run", "jobs", "execute", $MigrationJobName, "--project", $ProjectId, "--region", $Region, "--wait")
    }

    Write-Log "Deploying Cloud Run service..."
    $deployArgs = @(
        "run", "deploy", $ServiceName,
        "--project", $ProjectId,
        "--region", $Region,
        "--platform", "managed",
        "--image", $imageUri,
        "--service-account", $runtimeServiceAccount,
        "--allow-unauthenticated",
        "--port", "8080",
        "--memory", "1Gi",
        "--cpu", "1",
        "--concurrency", "80",
        "--timeout", "300",
        "--env-vars-file", $envYaml
    )
    if ($secretBindings.Count -gt 0) {
        $deployArgs += @("--set-secrets", ($secretBindings -join ","))
    }
    if ($cloudSqlExists) {
        $deployArgs += @("--add-cloudsql-instances", $cloudSqlConnection)
    }
    Invoke-GCloud -Arguments $deployArgs

    $serviceUrl = (& gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)").Trim()
    Write-Log "Cloud Run URL: $serviceUrl"

    if (-not $SkipVerification) {
        Test-HttpStatus -Url "$serviceUrl/health" -ExpectedStatus 200 -Label "Health"
        Test-HttpStatus -Url "$serviceUrl/static/images/favicon.svg" -ExpectedStatus 200 -Label "Static asset"

        if ($envMap.Contains("GOOGLE_CLIENT_ID") -and $envMap.Contains("GOOGLE_CLIENT_SECRET") -and $envMap.Contains("GOOGLE_REDIRECT_URI")) {
            Test-HttpStatus -Url "$serviceUrl/auth/google/login" -ExpectedStatus 302 -Label "Google login redirect"
        }

        if ($envMap.Contains("VERTEX_AI_PROJECT") -and $envMap.Contains("VERTEX_AI_LOCATION") -and $envMap.Contains("GEMINI_MODEL")) {
            Write-Log "Verifying Vertex AI Gemini via REST API..."
            $token = (& gcloud auth print-access-token).Trim()
            $vertexUrl = "https://$($envMap['VERTEX_AI_LOCATION'])-aiplatform.googleapis.com/v1/projects/$($envMap['VERTEX_AI_PROJECT'])/locations/$($envMap['VERTEX_AI_LOCATION'])/publishers/google/models/$($envMap['GEMINI_MODEL']):generateContent"
            $body = @{
                contents = @(
                    @{
                        role = "user"
                        parts = @(
                            @{ text = "Reply with OK" }
                        )
                    }
                )
            } | ConvertTo-Json -Depth 6
            $vertexResponse = Invoke-RestMethod -Method Post -Uri $vertexUrl -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body $body
            if (-not $vertexResponse.candidates) {
                throw "Vertex AI verification returned no candidates."
            }
            Write-Log "Vertex AI verification passed."
        }
    }

    Write-Log "Deployment completed successfully."
} finally {
    if (Test-Path -LiteralPath $envYaml) {
        Remove-Item -LiteralPath $envYaml -Force
    }
}
