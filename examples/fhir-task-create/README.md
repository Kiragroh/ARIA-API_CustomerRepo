# FHIR Task Creation Example

This trigger-agnostic Python example creates an idempotent ARIA FHIR `Task` for a patient. The caller supplies a stable trigger ID, a patient identifier, and the name of an active ARIA Task activity. Dry-run is the default; no `Task` is posted unless `--execute` is present.

## Configuration

Python 3.10 or newer and the `requests` package are required. Keep credentials in the local environment or an ignored `.env` file:

```text
VARIAN_PLATFORM=<Varian-Platform>
ARIA_FHIR_CLIENT_ID=<client-id>
ARIA_FHIR_CLIENT_SECRET=<local-secret>
```

The example derives the OAuth token service on port `44333` and the FHIR R4 base on port `55370` from the same Varian-Platform. Explicit `ARIA_FHIR_TOKEN_URL` and `ARIA_FHIR_BASE_URL` values override the derived URLs. Use `ARIA_FHIR_CA_BUNDLE` when a private CA is required; TLS validation is never disabled.

## Dry-run

```powershell
python .\examples\fhir-task-create\fhir_task_create_example.py `
  --patient-identifier "<ARIA-ID>" `
  --activity-name "Labor genehmigen" `
  --trigger-id "<stable-trigger-id>"
```

Patient, Practitioner, workflow-identifier, and note values are redacted in the output. Append `--execute` only after reviewing the remaining dry-run structure. Reusing the same stable trigger ID does not create a second Task.

## Routing

- `ActivityDefinition.subjectReference` supplies the active group.
- The group and all active CareTeam participants with role `oncologist` or `primary-oncologist` become `Task.restriction.recipient` entries.
- Exactly one active primary oncologist becomes `Task.owner`.
- With no unique primary, `owner` is omitted and the group Task is still created.
- The created Task is read back and checked. An uncertain POST is reconciled by identifier and is never blindly repeated.

The example creates no `Appointment`. ARIA may add a parent `ServiceRequest` server-side. Activity names, group names, available scopes, certificates, and ARIA user rights are installation-specific and must be verified against the local Implementation Guide and `CapabilityStatement`.
