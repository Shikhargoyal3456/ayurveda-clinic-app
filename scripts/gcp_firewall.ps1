$ErrorActionPreference = "Stop"

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "Green"
    )
    Write-Host $Message -ForegroundColor $Color
}

$commandText = "gcloud compute firewall-rules create allow-ayurveda-app --allow tcp:8000 --source-ranges 0.0.0.0/0 --target-tags ayurveda-app"

try {
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if (-not $gcloud) {
        Write-Status "gcloud CLI is not installed or not on PATH." "Red"
        Write-Status "Install it from: https://cloud.google.com/sdk/docs/install" "Yellow"
        Write-Status "Then run:" "Yellow"
        Write-Status $commandText "Cyan"
        exit 1
    }

    $existing = & gcloud compute firewall-rules list --filter="name=allow-ayurveda-app" --format="value(name)"
    if ($existing -and $existing.Trim() -eq "allow-ayurveda-app") {
        Write-Status "Google Cloud firewall rule 'allow-ayurveda-app' already exists." "Yellow"
    }
    else {
        Write-Status "Creating Google Cloud firewall rule..." "Green"
        & gcloud compute firewall-rules create allow-ayurveda-app --allow tcp:8000 --source-ranges 0.0.0.0/0 --target-tags ayurveda-app
        Write-Status "Firewall rule created successfully." "Green"
    }
}
catch {
    Write-Status "Failed to configure Google Cloud firewall: $($_.Exception.Message)" "Red"
    Write-Status "Run this command manually:" "Yellow"
    Write-Status $commandText "Cyan"
    exit 1
}
