# ARIA-API

GitHub-sichere Sammlung von Beispielen, Tests und Notizen fuer ARIA/VAIS FHIR R4 Workflows. Die Dateien enthalten keine produktiven Servernamen, Tokens, Passwoerter, Client-Secrets, Patientendaten oder lokalen Netzpfade. Produktive Endpunkte und Zugangsdaten werden ausschliesslich lokal ueber Umgebung oder `.env` gesetzt.

## Struktur

| Pfad | Zweck |
|---|---|
| `docs/` | nur bewusst bereinigte Referenznotizen; volle IG, interne Unterlagen und API-Dumps bleiben lokal ausgeschlossen |
| `notebooks/aria_fhir_github_share.ipynb` | GitHub-sicheres Notebook ohne lokale IDs, Hostnamen oder gespeicherte API-Antworten |
| `examples/fhir-document-upload/` | schlankes DocumentReference-Upload-Beispiel |
| `examples/legacy-share/` | alte weitergebbare Demo-/Quicktest-Dateien |
| `tools/diagnostics/` | Token-, Scope- und Quicktest-Skripte |
| `skill-prep/` | Skill-Draft, IG-Karte und Aufgaben-Backlog |
| `fhir bei STR letter ai/` | lokale FHIR-Tester-/Upload-App; oeffentliche Config ist leer, echte Werte gehoeren in `settings.local.json` oder `.env` |

## Credentials

Secrets gehoeren nicht in Code, README, Notebooks, Skill-Dateien oder Commits. Lokal werden diese Variablen erwartet:

```text
ARIA_FHIR_TOKEN_URL=https://<token-host>/tokenservice/connect/token
ARIA_FHIR_BASE_URL=https://<fhir-host>/fhir/r4
ARIA_FHIR_CLIENT_ID=<client-id>
ARIA_FHIR_CLIENT_SECRET=<client-secret>
ARIA_FHIR_SCOPE=system/DocumentReference.cruds system/Patient.rs system/Organization.rs system/ValueSet.rs system/Practitioner.rs
```

Die lokale `.env` bleibt durch `.gitignore` geschuetzt. Verwende `.env.example` als Vorlage.

## Wichtige FHIR-Einstiege

- `Patient`: Suche ueber `identifier`, `_id`, `family`, `given`, `birthdate` oder `name-or-identifier`; breite Suchen koennen vom Server als zu teuer abgelehnt werden.
- `DocumentReference`: Upload ueber `POST <FHIR_BASE_URL>/DocumentReference`, Update per `PUT`, Dokumenttypen ueber `ValueSet/$expand`.
- `Appointment`: Search/Create/Update/Read sowie optionale Operationen wie Check-in/Check-out, falls vom lokalen Server unterstuetzt.
- `Task`: relevant fuer Aufgaben-/Aktivitaets-Workflows und Journal-Note-Fallbacks.
- Scopes: nach Resource und Operation klein halten, z.B. `system/DocumentReference.cruds` oder `system/Patient.rs`.

## DocumentReference-Kernregeln

- Dokumenttypen nicht hart codieren, sondern ueber `ValueSet/$expand?url=http://varian.com/fhir/ValueSet/documentreference-type` aufloesen.
- `type.coding` braucht ARIA-Code, System und Display.
- `docStatus="preliminary"` entspricht in ARIA "nicht genehmigt / pending".
- `TemplateName` ist ARIA-Metadaten und unabhaengig davon, ob die Datei PDF, DOCX oder etwas anderes ist.
- Kategorie nach Dateityp setzen: PDF/Bilder als `TIF`, Word/DOCX als `Patient Document`.
- Preview-/Beschreibungstext ist optional; dort koennen weiterfuehrende Infos abgelegt werden.

## Schnelle Checks

```powershell
python -B -m pytest .\tests '.\fhir bei STR letter ai\test_aria_fhir_upload.py'
python .\examples\fhir-document-upload\fhir_document_upload_example.py --help
```

Live-Schreiboperationen nur mit bewusstem `--execute` ausfuehren.
