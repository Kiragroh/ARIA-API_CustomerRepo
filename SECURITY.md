# Security Notes

This repository is intended to be shareable without local infrastructure details.

It is a personal, independent reference and must not imply publication,
approval, sponsorship, or support by an employer, healthcare provider, or
vendor. Use synthetic organization, role, workflow, endpoint, and identifier
values in all maintained examples.

Do not commit:

- real ARIA/FHIR server hostnames or internal network paths
- OAuth client secrets, access tokens, refresh tokens or passwords
- real client IDs unless the owner explicitly classifies them as public
- patient identifiers, names, birth dates, document text or unredacted API responses
- generated PDFs, DOCX files, screenshots, logs or exported clinical data

The curated `docs/ARIA_API_VAIS_Short_Setup_Guide_V3.pdf`, `docs/ARIA-API-ImplementationGuide/` and `examples/examples.json/` are intentionally public documentation. Do not add patient-specific exports, live API responses or environment-specific PDFs.

Use `.env`, environment variables, Windows Credential Manager or a local `settings.local.json` for live credentials and endpoints.

Before publishing, run:

```powershell
python .\tests\public_safety_check.py
```
