# Security Notes

This repository is intended to be shareable without local infrastructure details.

Do not commit:

- real ARIA/FHIR server hostnames or internal network paths
- OAuth client secrets, access tokens, refresh tokens or passwords
- real client IDs unless the owner explicitly classifies them as public
- patient identifiers, names, birth dates, document text or unredacted API responses
- generated PDFs, DOCX files, screenshots, logs or exported clinical data

The curated `docs/ARIA_API_VAIS_Short_Setup_Guide_V3.pdf` is intentionally public documentation. Do not add patient-specific or environment-specific PDFs.

Use `.env`, environment variables, Windows Credential Manager or a local `settings.local.json` for live credentials and endpoints.

Before publishing, run:

```powershell
rg -n -i "(client_secret|access_token|bearer |password|passwort|https://s[0-9]+|\\\\[A-Za-z0-9.-]+\\)" .
```
