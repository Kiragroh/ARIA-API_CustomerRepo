# ============================================================
# ARIA FHIR Quick Test
# Tests token retrieval, scope permissions, and basic FHIR
# read-only queries against the VAIS/ARIA FHIR endpoint.
# ============================================================

# ------------------------------------------------------------
# Configuration – fill in your values
# ------------------------------------------------------------

$ClientId     = "your-client-id-here"
$ClientSecret = "your-client-secret-here"

# Token service URL (IdentityServer on port 44333)
$TokenUrl  = "https://<aria-server>:44333/tokenservice/connect/token"

# FHIR base URL (port 55370, path /fhir/r4)
$FhirBase  = "https://<aria-server>:55370/fhir/r4"

# Patient FHIR ID.
# Format: "Patient-" followed by the ARIA *serial number* (Seriennummer),
# NOT the patient ID (Patientennummer).
# Example: if the serial number in ARIA is 270, use "Patient-270".
$PatientId = "Patient-270"

# Scope to request. Use "system/<Resource>.rs" for read-only system access.
# Common values: system/Appointment.rs, system/DocumentReference.rs,
#                system/Patient.rs, system/Condition.rs, system/Observation.rs
$Scope = "system/Patient.rs system/Appointment.rs system/DocumentReference.rs system/Condition.rs system/Observation.rs"

# ------------------------------------------------------------
# TLS – accept self-signed certificates (test environments only)
# ------------------------------------------------------------

if (-not ([System.Management.Automation.PSTypeName]'TrustAllCertsPolicy').Type) {
    Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
}
"@
}
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null
[System.Net.ServicePointManager]::CertificatePolicy    = New-Object TrustAllCertsPolicy
[System.Net.ServicePointManager]::SecurityProtocol     = [System.Net.SecurityProtocolType]::Tls12

# ------------------------------------------------------------
# Helper: section header
# ------------------------------------------------------------

function Write-Section($Text) {
    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host $Text
    Write-Host ("=" * 60)
}

# ------------------------------------------------------------
# Helper: FHIR GET via curl (avoids .NET TLS issues)
# Returns parsed JSON object or $null on error.
# ------------------------------------------------------------

function Invoke-FhirGet {
    param(
        [string] $Label,
        [string] $Url,
        [string] $Token
    )

    Write-Host ""
    Write-Host "  >> $Label"
    Write-Host "     GET $Url"

    $tmp = Join-Path $env:TEMP ("fhir_" + [System.IO.Path]::GetRandomFileName() + ".json")

    curl.exe -k -s `
        -H "Authorization: Bearer $Token" `
        -H "Accept: application/fhir+json" `
        "$Url" -o "$tmp"

    if (-not (Test-Path $tmp)) {
        Write-Host "     ERROR: no response file created" -ForegroundColor Red
        return $null
    }

    $raw = Get-Content $tmp -Raw
    Remove-Item $tmp -Force

    try   { $obj = $raw | ConvertFrom-Json }
    catch { Write-Host "     ERROR: response is not valid JSON" -ForegroundColor Red; return $null }

    if ($obj.resourceType -eq "OperationOutcome") {
        Write-Host "     OperationOutcome:" -ForegroundColor Yellow
        $obj.issue | ForEach-Object { Write-Host "       [$($_.severity)] $($_.diagnostics)" }
        return $null
    }

    return $obj
}

# ------------------------------------------------------------
# 1. Request token
# ------------------------------------------------------------

Write-Section "1. Request Token"

try {
    $tokenResp = Invoke-RestMethod `
        -Method Post `
        -Uri $TokenUrl `
        -ContentType "application/x-www-form-urlencoded" `
        -Body @{ grant_type = "client_credentials"; client_id = $ClientId; client_secret = $ClientSecret; scope = $Scope } `
        -TimeoutSec 30

    Write-Host "OK – expires in $($tokenResp.expires_in)s" -ForegroundColor Green
    Write-Host "Granted scope: $($tokenResp.scope)"
    Write-Host "Token: $($tokenResp.access_token)"
    $token = $tokenResp.access_token
}
catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press ENTER to exit"
    exit
}

# ------------------------------------------------------------
# 2. FHIR read-only queries
# ------------------------------------------------------------

Write-Section "2. FHIR Read-Only Queries  (patient: $PatientId)"

$ref   = [System.Uri]::EscapeDataString("Patient/$PatientId")
$today = (Get-Date).ToString("yyyy-MM-dd")

# Patient resource
$pt = Invoke-FhirGet -Label "Patient"  -Url "$FhirBase/Patient/$PatientId"  -Token $token
if ($pt) { Write-Host "     id=$($pt.id)  family=$($pt.name.family)" }

# Appointments today
$appt = Invoke-FhirGet -Label "Appointments (today)" -Url "$FhirBase/Appointment?patient=$ref&date=$today&_count=20" -Token $token
if ($appt) { Write-Host "     total=$($appt.total)  entries=$($appt.entry.Count)" }

# All appointments
$apptAll = Invoke-FhirGet -Label "Appointments (all, max 20)" -Url "$FhirBase/Appointment?patient=$ref&_count=20" -Token $token
if ($apptAll) {
    Write-Host "     total=$($apptAll.total)"
    $apptAll.entry | Select-Object -First 5 | ForEach-Object {
        $a = $_.resource
        Write-Host "       id=$($a.id)  status=$($a.status)  start=$($a.start)"
    }
}

# DocumentReference
$docs = Invoke-FhirGet -Label "DocumentReference (max 20)" -Url "$FhirBase/DocumentReference?patient=$ref&_count=20" -Token $token
if ($docs) {
    Write-Host "     total=$($docs.total)"
    $docs.entry | Select-Object -First 5 | ForEach-Object {
        $d = $_.resource
        Write-Host "       id=$($d.id)  date=$($d.date)  desc=$($d.description)"
    }
}

# Condition
$cond = Invoke-FhirGet -Label "Condition (max 20)" -Url "$FhirBase/Condition?patient=$ref&_count=20" -Token $token
if ($cond) { Write-Host "     total=$($cond.total)  entries=$($cond.entry.Count)" }

# Observation
$obs = Invoke-FhirGet -Label "Observation (max 20)" -Url "$FhirBase/Observation?patient=$ref&_count=20" -Token $token
if ($obs) { Write-Host "     total=$($obs.total)  entries=$($obs.entry.Count)" }

# ------------------------------------------------------------

Write-Section "Done"
Read-Host "Press ENTER to exit"
