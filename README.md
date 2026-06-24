# ARIA API / VAIS

![ARIA API / VAIS Short Setup Guide](banner.png)

GitHub-sicherer Starter fuer ARIA/VAIS FHIR R4 Workflows. Das Repository enthaelt keine produktiven Servernamen, Tokens, Passwoerter, Client-Secrets, Patientendaten oder lokalen Netzpfade. Produktive Endpunkte und Zugangsdaten werden lokal ueber Umgebung oder `.env` gesetzt.

## Getting Started

Der kompakte Einstieg liegt als PDF im Repository:

[ARIA API / VAIS - Short Setup Guide V3](docs/ARIA_API_VAIS_Short_Setup_Guide_V3.pdf)

Das PDF beschreibt die Grundidee, lokale Konfiguration, Token-Service, FHIR-Basisaufrufe und den API-Tester auf Uebersichtsebene. Die Codebeispiele hier sind absichtlich schlanker und ohne echte Infrastrukturwerte.

## Inhalt

| Pfad | Zweck |
|---|---|
| `docs/ARIA_API_VAIS_Short_Setup_Guide_V3.pdf` | kurzer Setup- und Orientierungsguide |
| `docs/ARIA-API-ImplementationGuide/` | vollstaendiger statischer ARIA API Implementation Guide als weiterfuehrende Referenz |
| `examples/examples.json/` | JSON-Beispiele und Profile aus dem Implementation Guide |
| `examples/fhir-document-upload/` | nachvollziehbares DocumentReference-Upload-Beispiel mit Dry-Run |
| `notebooks/aria_fhir_github_share.ipynb` | teilbares Notebook ohne lokale IDs, Hostnamen oder gespeicherte API-Antworten |
| `aria_fhir_cli.py` | kleine CLI fuer Token-, Metadata- und Patient-Probes |
| `patient_fhir_query.py` | fokussierte Patient-Suche ueber FHIR |

## Weiterfuehrende Quellen

- [ARIA API Implementation Guide](docs/ARIA-API-ImplementationGuide/index.html)
- [FHIR-Artefakte und JSON-Beispiele](examples/examples.json/)

Die JSON-Beispiele stammen aus dem Implementation Guide. Lokale API-Antworten, produktive Endpunkte und Patientendaten gehoeren nicht in dieses Repository.

## Lokale Konfiguration

Secrets gehoeren nicht in Code, README, Notebooks oder Commits. Lokal werden diese Variablen erwartet:

```text
ARIA_FHIR_TOKEN_URL=https://<token-host>/tokenservice/connect/token
ARIA_FHIR_BASE_URL=https://<fhir-host>/fhir/r4
ARIA_FHIR_CLIENT_ID=<client-id>
ARIA_FHIR_CLIENT_SECRET=<client-secret>
ARIA_FHIR_SCOPE=system/DocumentReference.cruds system/Patient.rs system/Organization.rs system/ValueSet.rs system/Practitioner.rs
```

Nutze `.env.example` als Vorlage. Eine lokale `.env` bleibt durch `.gitignore` ausgeschlossen.

## FHIR-Hinweise

- `Patient`: bevorzugt ueber `identifier`, `_id`, `family`, `given`, `birthdate` oder `name-or-identifier` suchen; breite Suchen koennen als zu teuer abgelehnt werden.
- `DocumentReference`: Dokumenttypen ueber `ValueSet/$expand` aufloesen, nicht hart codieren.
- `DocumentReference.type.coding` braucht ARIA-Code, System und Display.
- `TemplateName` ist ARIA-Metadaten und unabhaengig vom Dateiformat.
- Kategorie nach Dateityp setzen: PDF als `PDF`, Bilder als `TIF`, Word/DOCX als `Patient Document`.
- `docStatus="preliminary"` entspricht in ARIA nicht genehmigt / pending.

## Schnelle lokale Checks

```powershell
python .\aria_fhir_cli.py --help
python .\examples\fhir-document-upload\fhir_document_upload_example.py --help
```

Live-Schreiboperationen nur bewusst mit `--execute` ausfuehren.
