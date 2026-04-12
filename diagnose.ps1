$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReportPath = Join-Path $ProjectRoot "diagnostic_report.txt"
$PythonPath = "C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"
$Port = 8000
$Findings = New-Object System.Collections.Generic.List[string]
$Fixes = New-Object System.Collections.Generic.List[string]

if (Test-Path $ReportPath) {
    Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue
}

function Write-Report {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
    Add-Content -Path $ReportPath -Value $Message
}

function Add-Finding {
    param([string]$Message)
    $Findings.Add($Message) | Out-Null
    Write-Report "[FINDING] $Message" "Yellow"
}

function Add-Fix {
    param([string]$Message)
    $Fixes.Add($Message) | Out-Null
}

function Write-Section {
    param([string]$Title)
    $line = ""
    Write-Report $line
    Write-Report "=== $Title ===" "Cyan"
}

function Test-IsAdministrator {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

function Invoke-SafeWebRequest {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 5,
        [hashtable]$Headers = @{}
    )
    try {
        return Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds -Headers $Headers
    }
    catch {
        return $_
    }
}

function Get-PortListeners {
    param([int]$LocalPort)

    $listeners = @()
    try {
        $netstatOutput = & netstat -ano -p TCP | Select-String ":$LocalPort"
        foreach ($line in $netstatOutput) {
            $text = ($line.ToString() -replace "\s+", " ").Trim()
            if ($text -match "^TCP (?<local>\S+) (?<remote>\S+) (?<state>\S+) (?<pid>\d+)$") {
                $listeners += [pscustomobject]@{
                    LocalAddress = $matches["local"]
                    RemoteAddress = $matches["remote"]
                    State        = $matches["state"]
                    PID          = [int]$matches["pid"]
                }
            }
        }
    }
    catch {
    }
    return $listeners
}

function Get-IPv4AndIPv6Addresses {
    $addresses = @()
    try {
        $ipconfigOutput = & ipconfig
        $currentAdapter = ""
        foreach ($line in $ipconfigOutput) {
            if ($line -match "adapter (.+):$") {
                $currentAdapter = $matches[1].Trim()
            }
            if ($line -match "IPv4 Address.*?:\s+(.+)$") {
                $addresses += [pscustomobject]@{
                    Adapter = $currentAdapter
                    Family  = "IPv4"
                    Address = $matches[1].Trim()
                }
            }
            if ($line -match "IPv6 Address.*?:\s+(.+)$") {
                $addresses += [pscustomobject]@{
                    Adapter = $currentAdapter
                    Family  = "IPv6"
                    Address = ($matches[1].Trim() -replace "%\d+$", "")
                }
            }
            if ($line -match "Temporary IPv6 Address.*?:\s+(.+)$") {
                $addresses += [pscustomobject]@{
                    Adapter = $currentAdapter
                    Family  = "IPv6-Temporary"
                    Address = ($matches[1].Trim() -replace "%\d+$", "")
                }
            }
        }
    }
    catch {
        Add-Finding "Could not read adapter IP addresses: $($_.Exception.Message)"
    }
    return $addresses
}

function Get-FirewallProfilesSummary {
    try {
        $profiles = Get-NetFirewallProfile -ErrorAction Stop
        return $profiles | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction
    }
    catch {
        try {
            return & netsh advfirewall show allprofiles state
        }
        catch {
            return @("Unable to read firewall profile state.")
        }
    }
}

function Get-FirewallRuleSummary {
    param([string]$RuleName)
    try {
        $rule = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction Stop
        return $rule | Select-Object DisplayName, Enabled, Direction, Action
    }
    catch {
        try {
            $text = & netsh advfirewall firewall show rule name="$RuleName"
            return $text
        }
        catch {
            return @("Firewall rule lookup failed for '$RuleName'.")
        }
    }
}

function Get-NetworkProfileSummary {
    try {
        return Get-NetConnectionProfile -ErrorAction Stop | Select-Object Name, InterfaceAlias, NetworkCategory, IPv4Connectivity, IPv6Connectivity
    }
    catch {
        return @("Unable to read network profile without elevated permissions.")
    }
}

function Test-GcpMetadata {
    try {
        $response = Invoke-WebRequest -Uri "http://metadata.google.internal/computeMetadata/v1/instance/id" -UseBasicParsing -TimeoutSec 2 -Headers @{ "Metadata-Flavor" = "Google" }
        if ($response.StatusCode -eq 200) {
            return $true
        }
    }
    catch {
    }
    return $false
}

function Test-LocalApp {
    param([string]$Url)
    $result = Invoke-SafeWebRequest -Url $Url -TimeoutSeconds 5
    if ($result -is [System.Management.Automation.ErrorRecord]) {
        return [pscustomobject]@{
            Success = $false
            Detail  = $result.Exception.Message
        }
    }
    return [pscustomobject]@{
        Success = $true
        Detail  = "HTTP $($result.StatusCode)"
    }
}

function Show-TableOrText {
    param([object]$Value)
    if ($null -eq $Value) {
        return
    }
    if ($Value -is [System.Array] -or $Value -is [System.Collections.IEnumerable]) {
        try {
            ($Value | Format-Table -AutoSize | Out-String).TrimEnd() | ForEach-Object { Write-Report $_ }
            return
        }
        catch {
        }
    }
    Write-Report ($Value | Out-String).TrimEnd()
}

Write-Report "Kash ai - External Access Diagnostic Report"
Write-Report "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
Write-Report "Project Root: $ProjectRoot"
Write-Report "Python Runtime: $PythonPath"
Write-Report "Target Port: $Port"
Write-Report ""

$isAdmin = Test-IsAdministrator
Write-Section "Privileges"
if ($isAdmin) {
    Write-Report "Running with Administrator privileges." "Green"
}
else {
    Write-Report "Running without Administrator privileges. Some firewall and socket checks may be limited." "Yellow"
    Add-Fix "Re-run PowerShell as Administrator for the most complete firewall and listener diagnostics."
}

Write-Section "1. Application Process And Local Listener"
$pythonProcesses = @()
try {
    $pythonProcesses = Get-Process -ErrorAction Stop | Where-Object {
        $_.ProcessName -like "*python*" -or $_.ProcessName -like "*uvicorn*" -or $_.ProcessName -like "*gunicorn*"
    } | Select-Object ProcessName, Id, Path
}
catch {
    Add-Finding "Unable to inspect running processes: $($_.Exception.Message)"
}

if ($pythonProcesses.Count -gt 0) {
    Write-Report "Python-related processes found:" "Green"
    Show-TableOrText $pythonProcesses
}
else {
    Add-Finding "No active Python/Uvicorn process was found from this PowerShell session."
    Add-Fix "Start the app again with: powershell -ExecutionPolicy Bypass -File .\start_local.ps1"
}

$listeners = Get-PortListeners -LocalPort $Port
if ($listeners.Count -gt 0) {
    Write-Report "Port $Port listener(s) found:" "Green"
    Show-TableOrText $listeners

    $hasWildcard = $listeners | Where-Object { $_.LocalAddress -match "0\.0\.0\.0:$Port$" -or $_.LocalAddress -match "\[::\]:$Port$" }
    if (-not $hasWildcard) {
        Add-Finding "Port $Port is listening, but not on a wildcard external interface like 0.0.0.0 or [::]."
        Add-Fix "Ensure the app starts with HOST=0.0.0.0 and that your runner does not override it."
    }
}
else {
    Add-Finding "No TCP listener was detected on port $Port."
    Add-Fix "If Uvicorn says it started but no listener appears, stop all old instances and restart the app from the project root using the known-good runtime."
}

$localHealth = Test-LocalApp -Url "http://127.0.0.1:$Port/healthz"
if ($localHealth.Success) {
    Write-Report "Local HTTP health check succeeded: $($localHealth.Detail)" "Green"
}
else {
    Add-Finding "Local HTTP health check to http://127.0.0.1:$Port/healthz failed: $($localHealth.Detail)"
    Add-Fix "First fix local reachability before debugging public access. If localhost fails, the browser and cloud are not the primary problem."
}

$localHttps = Test-LocalApp -Url "https://127.0.0.1:$Port/healthz"
if ($localHttps.Success) {
    Write-Report "Local HTTPS health check succeeded unexpectedly: $($localHttps.Detail)" "Yellow"
}
else {
    Write-Report "Local HTTPS probe failed, which is expected if the app serves plain HTTP only." "Yellow"
}

Write-Section "2. Network Configuration"
$addresses = Get-IPv4AndIPv6Addresses
if ($addresses.Count -gt 0) {
    Write-Report "Detected adapter addresses:" "Green"
    Show-TableOrText $addresses
}
else {
    Add-Finding "No adapter IP addresses could be parsed from ipconfig."
}

$firewallProfiles = Get-FirewallProfilesSummary
Write-Report "Firewall profile summary:"
Show-TableOrText $firewallProfiles

$firewallRule = Get-FirewallRuleSummary -RuleName "Kash ai"
Write-Report "Firewall rule summary for 'Kash ai':"
Show-TableOrText $firewallRule

$ruleText = ($firewallRule | Out-String)
if ($ruleText -match "No rules match" -or $ruleText -match "not found" -or $ruleText -match "failed") {
    Add-Finding "Windows Firewall rule 'Kash ai' was not confirmed."
    Add-Fix "Run as Administrator: powershell -ExecutionPolicy Bypass -File .\scripts\open_firewall.ps1"
}

$networkProfiles = Get-NetworkProfileSummary
Write-Report "Network profile summary:"
Show-TableOrText $networkProfiles

Write-Section "3. Google Cloud And External Reachability"
$isGcp = Test-GcpMetadata
if ($isGcp) {
    Write-Report "This machine appears to be running inside Google Cloud." "Green"
}
else {
    Write-Report "This machine does not appear to be a Google Cloud VM from local metadata checks." "Yellow"
}

$externalIp = $null
try {
    $externalIp = (Invoke-RestMethod -Uri "https://ifconfig.me/ip" -Method Get -TimeoutSec 5).Trim()
    Write-Report "Detected external/public IP: $externalIp" "Green"
}
catch {
    Add-Finding "Could not detect external/public IP automatically."
}

try {
    $tnc = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
    Write-Report "Local Test-NetConnection to 127.0.0.1:${Port}:"
    Show-TableOrText ($tnc | Select-Object ComputerName, RemotePort, TcpTestSucceeded)
    if (-not $tnc.TcpTestSucceeded) {
        Add-Finding "Test-NetConnection confirms that localhost:$Port is not reachable right now."
    }
}
catch {
    Add-Finding "Test-NetConnection local probe failed: $($_.Exception.Message)"
}

if ($externalIp) {
    try {
        $publicTcp = Test-NetConnection -ComputerName $externalIp -Port $Port -WarningAction SilentlyContinue
        Write-Report "Self-test to public IP ${externalIp}:${Port}:"
        Show-TableOrText ($publicTcp | Select-Object ComputerName, RemotePort, TcpTestSucceeded)
        if (-not $publicTcp.TcpTestSucceeded) {
            Add-Finding "Self-test to the public IP on port $Port failed."
            Add-Fix "If you are behind a home router or mobile hotspot, external clients may not reach your machine without router/NAT forwarding. On Google Cloud, confirm the VM has an external IP and the firewall tag/rule are applied."
        }
    }
    catch {
        Add-Finding "Public-IP socket test failed: $($_.Exception.Message)"
    }
}

Write-Section "4. Browser HTTPS / HSTS / SSL Error Analysis"
Write-Report "Observed symptom to investigate: ERR_SSL_PROTOCOL_ERROR while trying an http:// URL."
Write-Report "That usually means the browser or an intermediate layer attempted HTTPS against a plain HTTP service."

Add-Fix "Test in an Incognito window and explicitly type http:// not https://."
Add-Fix "In Chrome, open chrome://net-internals/#hsts and clear any HSTS entry for the host or domain."
Add-Fix "Temporarily disable browser extensions that auto-upgrade HTTP to HTTPS."
Add-Fix "If you are using an IPv6 literal, test IPv4 too: http://192.168.29.212:8000 and your real external IPv4 if available."

Write-Report "Chrome HSTS clear steps:"
Write-Report "1. Open chrome://net-internals/#hsts"
Write-Report "2. In 'Delete domain security policies', enter the host name and delete it"
Write-Report "3. Close all Chrome windows"
Write-Report "4. Re-open and test again with explicit http://"

Write-Section "5. IPv4 / IPv6 Access Guidance"
$ipv4Entries = $addresses | Where-Object { $_.Family -eq "IPv4" }
$ipv6Entries = $addresses | Where-Object { $_.Family -like "IPv6*" }

if ($ipv4Entries.Count -gt 0) {
    Write-Report "IPv4 test URLs:"
    foreach ($entry in $ipv4Entries) {
        Write-Report "http://$($entry.Address):$Port"
    }
}

if ($ipv6Entries.Count -gt 0) {
    Write-Report "IPv6 test URLs:"
    foreach ($entry in $ipv6Entries) {
        Write-Report "http://[$($entry.Address)]:$Port"
    }
}

Add-Fix "If IPv6 fails but IPv4 works, prefer exposing the app through IPv4 first or place nginx in front with proper dual-stack support."
Add-Fix "If the browser only fails on the bracketed IPv6 URL, that points to IPv6 routing, browser policy, or ISP exposure rather than the FastAPI app alone."

Write-Section "6. Test Commands You Can Run Manually"
Write-Report "Local HTTP:"
Write-Report "Invoke-WebRequest http://127.0.0.1:8000/healthz"
Write-Report "Local IPv4:"
Write-Report "Invoke-WebRequest http://192.168.29.212:8000/healthz"
Write-Report "IPv6 literal:"
Write-Report "Invoke-WebRequest 'http://[2405:201:4039:7036:6012:7791:485:a1ed]:8000/healthz'"
Write-Report "Listener check:"
Write-Report "netstat -ano -p TCP | findstr :8000"
Write-Report "Firewall rule check:"
Write-Report "netsh advfirewall firewall show rule name=`"Kash ai`""
Write-Report "GCP firewall command:"
Write-Report "gcloud compute firewall-rules create allow-ayurveda-app --allow tcp:8000 --source-ranges 0.0.0.0/0 --target-tags ayurveda-app"

Write-Section "7. Root Cause Summary"
if (-not $localHealth.Success -and $listeners.Count -eq 0) {
    Add-Finding "Primary root cause from this diagnostic run: the app is not actually reachable on localhost:$Port right now, so public/browser access cannot work yet."
}

if ($localHealth.Success -and -not $localHttps.Success) {
    Add-Finding "The service appears to be plain HTTP. ERR_SSL_PROTOCOL_ERROR points to the browser or network trying HTTPS against a non-TLS endpoint."
}

if ($ipv6Entries.Count -gt 0) {
    Add-Finding "You are testing an IPv6 literal address. If IPv4 access works but IPv6 does not, the issue is likely IPv6 routing/firewall/browser behavior rather than FastAPI binding."
}

Write-Report "Findings summary:"
foreach ($finding in $Findings) {
    Write-Report "- $finding" "Yellow"
}

Write-Section "FIX THIS - Recommended Next Steps"
$dedupedFixes = $Fixes | Select-Object -Unique
if ($dedupedFixes.Count -eq 0) {
    $dedupedFixes = @("No immediate fixes were generated. Review the findings above.")
}
foreach ($fix in $dedupedFixes) {
    Write-Report "- $fix" "Green"
}

Write-Report ""
Write-Report "Diagnostic report saved to: $ReportPath" "Cyan"
