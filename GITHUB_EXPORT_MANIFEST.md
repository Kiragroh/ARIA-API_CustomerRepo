# GitHub Export Manifest

Use this list as the intended public scope for a clean GitHub update.

Safe to publish after tests pass:

- `README.md`
- `SECURITY.md`
- `.env.example`
- `aria_fhir_cli.py`
- `patient_fhir_query.py`
- `journal_notes_fhir_fallback.py`
- `examples/fhir-document-upload/`
- `examples/legacy-share/`
- `notebooks/aria_fhir_github_share.ipynb`
- `tests/`
- `fhir bei STR letter ai/` with `settings.json` only as a placeholder template

Keep local/private:

- `.env` and `.env.*`
- `settings.local.json`
- full ARIA Implementation Guide exports
- ARIA AccessKeys or reference-guide key files
- generated documents, logs, API response dumps and patient-adjacent artifacts
