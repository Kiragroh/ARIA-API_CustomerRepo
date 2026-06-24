# FHIR DocumentReference Upload Example

Dieses Beispiel baut einen ARIA `DocumentReference`-Upload nachvollziehbar auf. Standard ist ein Dry-Run: Patient, Organisation und Dokumenttyp werden aufgeloest, der geplante POST wird aber nur ohne Base64-Inhalt angezeigt.

## Voraussetzungen

Eine lokale `.env` im Repository-Root oder gesetzte Umgebungsvariablen:

```text
ARIA_FHIR_CLIENT_SECRET=<lokal>
ARIA_FHIR_CLIENT_ID=<client-id>
ARIA_FHIR_TOKEN_URL=https://<token-host>/tokenservice/connect/token
ARIA_FHIR_BASE_URL=https://<fhir-host>/fhir/r4
```

Wenn `.env` nur eine einzelne Zeile ohne `KEY=VALUE` enthaelt, wird sie als `ARIA_FHIR_CLIENT_SECRET` interpretiert.

## Dry-Run

```powershell
python .\examples\fhir-document-upload\fhir_document_upload_example.py `
  --patient-identifier "<ARIA-Patienten-ID>" `
  --file "C:\tmp\beispiel.pdf" `
  --document-type "RT-Plan-Verifikation" `
  --template-name "RT-Plan-Verifikation" `
  --preview-text "Optionale weiterfuehrende Infos"
```

## Live-Upload

```powershell
python .\examples\fhir-document-upload\fhir_document_upload_example.py `
  --patient-identifier "<ARIA-Patienten-ID>" `
  --file "C:\tmp\beispiel.pdf" `
  --document-type "RT-Plan-Verifikation" `
  --template-name "RT-Plan-Verifikation" `
  --execute
```

## Semantik

- `--document-type` wird ueber `ValueSet/$expand` gegen ARIA-Codes aufgeloest.
- `--template-name` schreibt die Varian-Extension `documentreference-templateName`.
- `--preview-text` schreibt optional `DocumentReference.description`; leer bedeutet kein Preview-Text.
- PDF wird als Kategorie `PDF` gesendet.
- Bilder werden als Kategorie `TIF` gesendet.
- Word/DOCX wird als Kategorie `Patient Document` gesendet.
- `docStatus` ist `preliminary`, also nicht genehmigt/pending.
