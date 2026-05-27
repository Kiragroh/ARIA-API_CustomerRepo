# ARIA API – Customer Repository

Scripts for accessing the ARIA/VAIS FHIR API via PowerShell.

## Scripts

### `aria-fhir-quicktest.ps1`

Quick-start PowerShell script to verify FHIR API access.  
Tests token retrieval (OAuth2 client credentials flow) and runs read-only FHIR queries for a given patient.

**Requirements:**
- PowerShell 5.1 or later
- `curl.exe` available (built-in on Windows 10+)
- Client credentials (client ID + secret) with appropriate FHIR scopes

**Setup:**
1. Open `aria-fhir-quicktest.ps1`
2. Fill in the four configuration variables at the top:
   - `$ClientId`, `$ClientSecret`
   - `$TokenUrl` and `$FhirBase` with your server hostname
   - `$PatientId` – format: `Patient-<Seriennummer>` (ARIA serial number, **not** the patient ID)
3. Run in PowerShell

**Queries included:**
- Patient resource
- Appointments (today + all)
- DocumentReference
- Condition
- Observation

**Scopes used:** `system/Patient.rs system/Appointment.rs system/DocumentReference.rs system/Condition.rs system/Observation.rs`
