$ErrorActionPreference = "Stop"

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "Green"
    )
    Write-Host $Message -ForegroundColor $Color
}

try {
    Write-Status "Windows SSL setup requires nginx and certbot support that is typically easier on Linux." "Yellow"
    Write-Status "Recommended Linux commands:" "Yellow"
    Write-Status "sudo apt-get install nginx certbot python3-certbot-nginx -y" "Cyan"
    Write-Status "sudo certbot --nginx -d your-domain.com" "Cyan"
    Write-Status "Configure nginx to redirect HTTP to HTTPS after certificate issuance." "Yellow"
    Write-Status "Set up renewal with: sudo systemctl enable certbot.timer" "Cyan"

    Write-Status "If you still want Windows nginx:" "Yellow"
    Write-Status "1. Download nginx for Windows" "Cyan"
    Write-Status "2. Install certbot or use DNS validation" "Cyan"
    Write-Status "3. Update nginx.prod.conf with certificate paths" "Cyan"
}
catch {
    Write-Status "SSL setup guidance failed: $($_.Exception.Message)" "Red"
    exit 1
}
