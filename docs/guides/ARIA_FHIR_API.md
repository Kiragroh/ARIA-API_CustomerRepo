# ARIA FHIR API

Die ARIA FHIR API ist ein standardisierter Datenweg fuer neue Integrationen. Sie stellt ARIA-Inhalte als FHIR-R4-Ressourcen bereit und verwendet OAuth2 Client Credentials. Dieser Einstieg zeigt generische Integrationsmuster ohne Servernamen, Zugangsdaten, Patientendaten oder organisationsspezifische Workflowbezeichnungen.

Alle Beispiele sind synthetisch und deployment-spezifisch zu validieren. Sie
stellen weder eine Herstellerzusage noch eine institutionelle Freigabe dar.

## Warum FHIR fuer neue Integrationen wichtig ist

FHIR ist ein offener HL7-Standard fuer den strukturierten Austausch von Gesundheitsdaten. Ressourcen, Referenzen, Profile, Extensions, Suchparameter und Terminologien werden maschinenlesbar beschrieben; der Austausch erfolgt sprachunabhaengig ueber HTTP und meist JSON, alternativ XML. mCODE ergaenzt strukturierte onkologische Profile, CodeX Radiation Therapy die strahlentherapeutische Semantik.

Damit ist FHIR fuer neue Integrationen langfristig anschlussfaehiger als weitere proprietaere Punkt-zu-Punkt-Loesungen. ARIA-spezifische Profile, Extensions, ValueSets und Scopes bleiben trotzdem verbindlich. Massgeblich sind der lokale ARIA API Implementation Guide und das live gelesene `CapabilityStatement`.

## Welcher Datenweg passt?

| Datenweg | Geeignet fuer | Abgrenzung |
|---|---|---|
| ARIA FHIR API | klinische und administrative Ressourcen, Dokumente, Termine und Workflows | bevorzugte standardisierte Integrationsschicht |
| ESAPI | Eclipse-nahe Planungsobjekte, Dosis, DVH, Strukturen und Planlogik | Varian-spezifische .NET-API, kein allgemeiner Austauschstandard |
| ARIA Webservice / Gateway | bestehende proprietaere Operationen und lokale FHIR-Luecken | Bestands- und Fallbackweg, nicht FHIR |
| SQL, nur lesend | Extraktion, Reporting und Audit | keine Schreibschnittstelle |
| DICOM / DICOM RT | Bild- und RT-Objekttransport | ersetzt keine Workflow- oder Termin-API |

C# kann FHIR und ESAPI in einer Anwendung kombinieren. Beide bleiben getrennte Adapter mit eigenen Berechtigungen, Modellen und Fehlergrenzen.

## Wofuer eignet sich FHIR?

| Aufgabe | FHIR-Ressource oder Operation |
|---|---|
| Patient sicher aufloesen | `Patient` ueber Identifier oder FHIR-ID |
| Dokumente suchen und laden | `DocumentReference`, bei Bedarf referenziertes `Binary` |
| PDF, DOCX oder Bild hochladen | `POST DocumentReference` mit Attachment |
| Termine lesen | `Appointment` |
| ARIA-Benutzer und Institution bestimmen | `Practitioner`, `Organization` |
| Gueltige Dokumenttypen ermitteln | `ValueSet/$expand` |
| Verfuegbare Funktionen pruefen | `metadata` / CapabilityStatement |

## Beispielhafte Scope-Matrix als Referenz

Die folgende Matrix fasst Scopes zusammen, die in einer getesteten
ARIA-Konfiguration beobachtet und mit dem installierten Implementation Guide
abgeglichen wurden. Sie ist keine Aussage ueber einen bestimmten Mandanten,
Client oder eine allgemein garantierte Produktfunktion. Eine Anwendung soll
nur die fuer ihren konkreten Ablauf benoetigte Teilmenge anfordern und die vom
Token-Service tatsaechlich gewaehrten Scopes auswerten.

Die Suffixe bedeuten: `c` = Create, `r` = Read, `u` = Update, `d` = Delete und `s` = Search. `cruds` ist damit ein breiter OAuth-Berechtigungsrahmen. Ob eine konkrete Operation wirklich angeboten wird, bestimmen zusaetzlich der lokale Implementation Guide, das live gelesene `CapabilityStatement` und die Rechte des zugeordneten ARIA-/VAIS-Benutzers.

### Schreibend oder mit schreibender Sonderoperation

Bei den folgenden Ressourcen kann neben Lesen/Suchen ein schreibender Scope
angeboten werden. Die Tabelle nennt die in einem installierten IG dokumentierte
praktische Reichweite; ein vorhandenes `cruds` bedeutet nicht, dass jede
denkbare FHIR-Operation lokal angeboten oder fachlich freigegeben ist.

| FHIR-Ressource | Beispielhafte Scopes je Kontext | Praktische Bedeutung in ARIA | Zusaetzliche ARIA-Rechte laut IG |
|---|---|---|---|
| `AllergyIntolerance` | `.cruds` und `.rs` | Allergien und Unvertraeglichkeiten lesen, suchen, anlegen oder aktualisieren | Vollzugriff auf Allergien; Allergien/Nebenwirkungen widerlegen |
| `Appointment` | `.cruds` und `.rs` | Termine lesen, suchen, anlegen und aktualisieren; dokumentierte Sonderoperationen sind `$checkin` und `$checkout` | Vollzugriff auf Terminplanung; blockierende Workflows beziehungsweise DICOM-Worklist-Status uebersteuern |
| `CareTeam` | `.cruds` und `.rs` | Das Behandlungsteam beziehungsweise zugeordnete Behandelnde lesen und aktualisieren | Rechte fuer Arztzuordnung sowie Patientenregistrierung und -bearbeitung |
| `Condition` | `.cruds` und `.rs` | Diagnosen und Staging lesen, suchen, anlegen und aktualisieren | Diagnose/Staging bearbeiten und freigeben |
| `DocumentReference` | `.cruds` und `.rs` | Patientendokumente suchen, laden, hochladen und Metadaten beziehungsweise Status aktualisieren | Vollzugriff, Signoff und Genehmigung von Patientendokumenten |
| `Patient` | `.cruds` und `.rs` | Patientenidentitaet und Stammdaten lesen, suchen, anlegen und aktualisieren | Patientenregistrierung und Bearbeitung demografischer Daten |
| `Practitioner` | `.cruds` und `.rs` | Behandelnde beziehungsweise ARIA-Benutzer lesen, suchen, anlegen und aktualisieren | Data Administration und Arztanlage |
| `Task` | `.cruds` und `.rs` | ARIA-Aktivitaeten und Workflow-Aufgaben lesen, suchen, anlegen und aktualisieren | Termin-/Aktivitaetsplanung, Aktivitaeten loeschen und blockierende Workflows uebersteuern |
| `ChargeItem` | `.cruds` und `.rs` | Leistungs-/Aktivitaetserfassung lesen und suchen; dokumentierte Schreiboperation `markAsExported` | Vollzugriff auf Activity Capture |
| `AuditEvent` | `.c` und `.cruds` | Audit-Ereignisse anlegen; der lokale IG dokumentiert hier nur `Create` | Im IG kein zusaetzliches benanntes Benutzerrecht |

### Nur lesend und suchend

| FHIR-Ressource | Beispielhafte Scopes je Kontext | Praktische Bedeutung in ARIA |
|---|---|---|
| `ActivityDefinition` | `.rs` | Definitionen von ARIA-Aktivitaeten und Workflows lesen |
| `BodyStructure` | `.rs` | Anatomische Strukturen beziehungsweise Ziel- und Koerperstrukturen lesen |
| `CarePlan` | `.rs` | Behandlungs- und Versorgungskontext lesen |
| `Device` | `.rs` | Geraete und technische Ressourcen lesen |
| `Group` | `.rs` | Gruppen beziehungsweise Kohorten lesen |
| `HealthcareService` | `.rs` | Klinische Leistungen und Dienste lesen |
| `Location` | `.rs` | Standorte, Raeume und organisatorische Orte lesen |
| `Observation` | `.rs` | Beobachtungen und Messwerte, im lokalen Profil insbesondere Vitalwerte, lesen |
| `Organization` | `.rs` | Institutionen, Leistungserbringer und Organisationseinheiten lesen |
| `Procedure` | `.rs` | Durchgefuehrte radiotherapeutische Kurse, Phasen und Plaene als Zusammenfassung lesen |
| `ServiceRequest` | `.rs` | Geplante radiotherapeutische Verordnungen, Kurse, Phasen und Plaene lesen |
| `ValueSet` | `.rs` | Gueltige ARIA-Codes und Auswahllisten suchen und mit `$expand` aufloesen |

`system/...` ist fuer einen technischen Client ohne interaktive Benutzeranmeldung vorgesehen. `user/...` repraesentiert denselben Ressourcenzugriff in einem delegierten Benutzerkontext. Fuer einen Headless-Dienst sind normalerweise die `system/...`-Scopes relevant. Eine Tester-Seite zeigt dagegen nur die auf dem jeweiligen Server vorhandenen Profile und Operationen und ist keine vollstaendige Aussage ueber die Berechtigung eines bestimmten Clients.

## Beispiel 1: Dokument hochladen

Das versionierte Beispiel liegt unter:

```text
examples/fhir-document-upload/fhir_document_upload_example.py
```

Ein Aufruf ohne `--execute` ist ein Dry-Run. Erst `--execute` sendet das Dokument:

```powershell
python .\examples\fhir-document-upload\fhir_document_upload_example.py `
  --patient-identifier "<ARIA-Patienten-ID>" `
  --file "C:\temp\brief.docx" `
  --document-type "Arztbriefe (intern)" `
  --template-name "Abschlussbrief_Behandlungsregion" `
  --organization-name "<Provider-Organisation>"
```

Fuer einen PDF- oder Bild-Upload wird nur die Datei ausgetauscht. Das Beispiel setzt die ARIA-Dokumentklasse passend zum Format:

- PDF: `PDF`
- DOC/DOCX: `Patient Document`
- Bilddatei: `TIF`

Der Dokumenttyp wird vor dem Upload ueber das ARIA-`ValueSet` aufgeloest. `TemplateName` ist eine eigene ARIA-Metainformation und nicht der Dateiname. `docStatus="preliminary"` bedeutet in ARIA ausstehend beziehungsweise nicht genehmigt; `final` steht fuer genehmigt.

## Beispiel 2: Dokument suchen und herunterladen

Der typische Leseweg ist:

1. ARIA-Patienten-ID mit `Patient?identifier=...` in eine FHIR-ID aufloesen.
2. Dokumente gezielt ueber den Patienten und einen engen Zeitraum suchen.
3. Gewuenschtes `DocumentReference` anhand von Typ, Datum und Status waehlen.
4. `content.attachment.data` Base64-dekodieren oder eine vorhandene `content.attachment.url` mit demselben Bearer-Token abrufen.
5. Dateityp aus `contentType` und Titel ableiten und die Bytes unveraendert speichern.

Beispielhafte Requests:

```text
GET /Patient?identifier=<ARIA-Patienten-ID>&_count=1
GET /DocumentReference?subject=Patient/<FHIR-ID>&date=ge2026-07-01&_count=50
GET /DocumentReference/<DocumentReference-ID>
```

Breite, ungefilterte Patient- oder Dokumentabfragen werden vermieden. Fuer klinische Prozesse muessen Dokumenttyp, Patient, Datum und Genehmigungsstatus gemeinsam geprueft werden.

## Beispiel 3: Termine lesen

Termine werden patientenbezogen und mit Datumsfenster abgefragt:

```text
GET /Appointment?patient=Patient/<FHIR-ID>&date=ge2026-08-01&_count=50
```

Ausgewertet werden insbesondere `status`, `start`, `end`, Terminart und die `participant`-Eintraege. Abgesagte oder bereits vergangene Termine duerfen nicht als naechster klinischer Termin verwendet werden. Datumsangaben aus FHIR sind zeitzonenbewusst; fuer die Anzeige in ARIA wird kontrolliert nach Europe/Berlin umgerechnet.

## Beispiel 4: Generisches Task-Routing

Fuer neue ARIA-Workflowaufgaben ist `Task` der bevorzugte Ressourcenweg. Das
in einer getesteten Konfiguration installierte Task-Profil begrenzt
`Task.owner` auf maximal eine Referenz vom Typ
`Practitioner` oder `PractitionerRole`; eine `Group` ist dort nicht zulaessig.
`Task.restriction.recipient` kann dagegen mehrere Referenzen enthalten und
erlaubt unter anderem `Group` und `Practitioner`.

Ein generisches Routing fuer eine fachliche Pruefaufgabe kann so aussehen:

- Eine aktive Arbeitsgruppe ist Recipient und niemals Owner.
- Aktive Practitioner mit einer lokal konfigurierten Fachrolle koennen weitere
  Recipients sein.
- Genau ein eindeutig bestimmter verantwortlicher Practitioner kann Owner
  werden. Bei keinem oder mehreren Kandidaten bleibt `owner` weg; ob die
  Gruppentask dennoch erstellt werden darf, ist lokal festzulegen.
- Die aktive `ActivityDefinition` wird anhand eines konfigurierten technischen
  Schluessels aufgeloest, muss `kind=Task` besitzen und auf die erwartete Gruppe
  verweisen. Anzeigenamen werden nicht als FHIR-ID verwendet.

Bereinigtes Strukturbeispiel:

```json
{
  "resourceType": "Task",
  "meta": {
    "profile": [
      "http://varian.com/fhir/v1/StructureDefinition/Task"
    ]
  },
  "identifier": [
    {
      "system": "urn:example:workflow:clinical-review-task:v1",
      "value": "synthetic-idempotency-key"
    }
  ],
  "status": "ready",
  "intent": "order",
  "code": {
    "coding": [
      {
        "code": "clinical-review"
      }
    ]
  },
  "focus": {
    "reference": "ActivityDefinition/example-clinical-review"
  },
  "for": {
    "reference": "Patient/example"
  },
  "owner": {
    "reference": "Practitioner/example-responsible-clinician"
  },
  "restriction": {
    "recipient": [
      {
        "reference": "Group/example-clinical-review-team"
      },
      {
        "reference": "Practitioner/example-participant"
      }
    ]
  }
}
```

In einer getesteten ARIA-Konfiguration wurde serverseitig eine
`ServiceRequest`-Referenz als Parent der eigenstaendigen Task ergaenzt, ohne
dass der Client ein `Appointment` erzeugte. Dieses Verhalten ist
deployment-spezifisch und keine Produktzusage. Ein Client sollte nach jedem
Write einen Task-Read-back ausfuehren; eine Identifier-Suche vor dem POST dient
der Idempotenz. Ein Timeout oder eine leere beziehungsweise unklare
Erfolgsantwort darf keinen blinden zweiten POST ausloesen, sondern nur eine
erneute Identifier-Suche.

Minimale Hintergrundprozesse benoetigen fuer diesen Ablauf Task-Create/Search,
Patient-, Practitioner-, ActivityDefinition-, CareTeam-, DocumentReference-
und Group-Read/Search-Scopes. Der konkret angeforderte Scope bleibt auf den
tatsaechlich genutzten Ablauf begrenzt und wird gegen den vom Token-Service
zurueckgegebenen Scope geprueft.

## Robuster Ablauf

1. Token mit kleinstmoeglichen Scopes anfordern.
2. Im lokalen Profil Differential, Snapshot, Operationen, Suchparameter, Bindings und Constraints pruefen.
3. `metadata` pruefen, wenn eine Ressource oder Suchoption neu genutzt wird.
4. Patienten-, Provider- und Dokumenttyp-Referenzen serverseitig aufloesen.
5. Suchparameter URL-kodieren und null/einen/mehrere Treffer explizit behandeln.
6. Bei Bundles dem Link `relation="next"` bis zur letzten Seite folgen.
7. Bei Schreibvorgaengen zuerst einen redigierten Dry-Run anzeigen.
8. `OperationOutcome` fachlich auswerten; ein HTTP-Fehler ist nicht die einzige moegliche Fehlerform.
9. Service-Datum nie in die Zukunft setzen und UTC-/Lokalzeit-Unterschiede sichtbar behandeln.

## C#-Praxis

Fuer produktive Clients gelten zusaetzlich:

- `HttpClient` wiederverwenden und durchgehend `async`/`await` mit `CancellationToken` nutzen.
- OAuth2-Token kontrolliert cachen und erneuern; Token oder Secrets nie protokollieren.
- Referenzen wie `Device/123` gezielt aufloesen und innerhalb eines Laufs cachen.
- Retries nur fuer transiente, idempotente Lesezugriffe einsetzen; Writes nicht blind wiederholen.
- TLS-Zertifikatspruefung nicht deaktivieren.

Ausfuehrliche, bereinigte Muster fuer Identifier-Aufloesung, Referenzen, Bundle-Paginierung und Terminologien stehen in `docs/ARCHITECTURE_AND_CSHARP_PATTERNS.md`.

## Abgrenzung zum ARIA Webservice / Gateway

FHIR arbeitet ressourcenorientiert mit JSON, Bearer-Token, FHIR-Suchparametern und standardisierten Antworten. Der ARIA Webservice/Gateway ist ein aelterer, operationenbasierter Weg mit eigener Authentisierung und proprietaeren Request-/Response-Strukturen. Neue Ablaeufe sollen FHIR verwenden, sofern die benoetigte Funktion dort freigegeben ist. Bestehende Gateway-Ablaeufe werden nicht stillschweigend auf FHIR umgedeutet.

## Git-Workflow

Fuer eine Aenderung:

```powershell
git status
git add README.md docs/guides versionInfo.json examples
git commit -m "docs: update ARIA FHIR workflow"
git push origin main
```

Vor jedem Push ist eine separate Sicherheitspruefung erforderlich. `.env`,
Secrets, Token, AccessKeys, produktive Endpunkte, Patientendaten und echte
API-Antworten gehoeren nie in Git.

## Weiterfuehrende Dateien

- `README.md`: sicherer Projekteinstieg und lokale Konfiguration
- `examples/fhir-document-upload/`: ausfuehrbares Upload-Beispiel mit Dry-Run
- `aria_fhir_cli.py`: Token-, Metadata- und Patient-Probes
- `patient_fhir_query.py`: gezielte Patientensuche
- `docs/ARIA-API-ImplementationGuide/`: lokale Herstellerreferenz
- `docs/ARCHITECTURE_AND_CSHARP_PATTERNS.md`: Schnittstellenentscheidung und sichere C#-Muster

## Externe Ressourcen

- [ARIA API II: ARIA API Resources](https://www.gatewayscripts.com/post/aria-api-ii-aria-api-resources)
- [ARIA API III: Practical C# Patterns for Clinical Development](https://www.gatewayscripts.com/post/aria-api-iii-practical-c-patterns-for-clinical-development)
- [Gateway-Scripts/ARIAAPI_Snippets](https://github.com/Gateway-Scripts/ARIAAPI_Snippets) - Lernsnippets, nicht unveraendert als Produktionscode uebernehmen
- [HL7 FHIR](https://hl7.org/fhir/)
- [mCODE](https://hl7.org/fhir/us/mcode/)
- [CodeX Radiation Therapy](https://build.fhir.org/ig/HL7/codex-radiation-therapy/)
