# ARIA Webservice / Gateway

Der ARIA Webservice/Gateway ist der aeltere, proprietaere Integrationsweg fuer bestehende ARIA-Access- und Gateway-Ablaeufe. Er bleibt fuer bereits etablierte oder noch nicht ueber FHIR abbildbare Funktionen relevant, ist aber kein FHIR-Endpunkt und soll bei neuen Integrationen nicht automatisch die erste Wahl sein.

FHIR nutzt dagegen offene und versionierte Standards: HL7 FHIR R4 fuer Ressourcen und Beziehungen, HTTP mit JSON/XML fuer den Austausch sowie mCODE und CodeX Radiation Therapy fuer onkologische beziehungsweise strahlentherapeutische Semantik. Deshalb ist FHIR die bevorzugte, langfristig anschlussfaehige Integrationsschicht, sofern das lokale ARIA-Profil die benoetigte Funktion anbietet.

## Typische Einsatzfaelle

- bestehende, vom Hersteller freigegebene Gateway-Integration weiter betreiben
- Dokumente ueber einen vorhandenen `Process`-Workflow an ARIA uebergeben
- Funktionen nutzen, die im lokalen FHIR-Profil noch nicht verfuegbar sind
- einen FHIR-Workflow kontrolliert gegen den bisherigen Transportweg vergleichen

Die lokale Herstellerdokumentation und die End-of-Life-Informationen liegen unter:

```text
docs/WebService-Interface (WayBeforFHIR)/
```

Zugangsschluessel aus diesem Bereich duerfen nicht in README, Hub, Git, Tickets oder Logs kopiert werden.

## Sichere lokale Access-Key-Handhabung

Access-Key-Dateien bleiben ausschliesslich lokal und per `.gitignore` vom
Repository ausgeschlossen. Ein Client liest den Wert erst zur Laufzeit in den
Speicher; Dateipfad, Wert und Request-Header werden weder protokolliert noch in
Fehlerobjekte kopiert.

Die Gateway-Authentisierung besteht aus zwei getrennten Teilen:

1. Windows SSPI/Negotiate authentisiert den ausfuehrenden Windows-Kontext.
2. Der lokale Access Key autorisiert die konkrete Gateway-Faehigkeit im
   `ApiKey`-Header.

Beides ist von FHIR OAuth2 und dessen Bearer-Token getrennt. Ein Gateway-Key ist
kein FHIR-Client-Secret und darf nicht zwischen den Schnittstellen
wiederverwendet werden. Die in der Herstellerverwaltung angezeigte Angabe
`allows-access-to` beschreibt die freigegebene Operationsfaehigkeit; sie ersetzt
weder die fachliche Payload-Pruefung noch die Auswertung der Antwort.

TLS-Zertifikatspruefung bleibt aktiviert. Interne Zertifikate werden ueber die
Windows-Vertrauenskette oder eine kontrollierte lokale CA bereitgestellt; ein
`verify=False`, globaler Zertifikats-Callback oder anderer Bypass ist fuer
Produktionscode nicht zulaessig.

Auch bei HTTP 200 muss der Antwortkoerper auf `ApplicationError`,
`GatewayError` und den operationseigenen Erfolgsstatus geprueft werden. Nur ein
HTTP-Status ohne semantische Antwortpruefung ist kein Erfolgsnachweis.

Eine konkrete Gateway-Ressource vom Typ Doctor beziehungsweise ein
operationseigenes Ressourcenfeld ist nicht gleichbedeutend mit der FHIR-Staff-
Gruppe `Arzt`. Die Gruppe wird im FHIR-Task-Workflow aus
`ActivityDefinition.subjectReference` als `Group` aufgeloest. Der Gateway-Weg
bleibt dokumentierter Legacy-/Fallbackpfad; der produktive
Zentrallabor-Task-Workflow verwendet ausschliesslich FHIR.

## Beispiel: Dokument ueber das Gateway hochladen

Ein robuster bestehender Upload fuehrt diese Schritte explizit aus:

1. Patientenbezug, Dokumenttyp, Template-Name und `DateOfService` pruefen.
2. Datei als echte Bytes einlesen; Dateiendung, MIME-Typ und tatsaechlicher Container muessen zusammenpassen.
3. Den freigegebenen Gateway-Request mit Windows-/ARIA-Kontext und Access-Berechtigung senden.
4. Nicht nur den HTTP-Status pruefen: Auch eine HTTP-200-Antwort kann einen `GatewayError` im Antwortkoerper enthalten.
5. Das Dokument nach dem Upload in ARIA oeffnen und bei editierbaren Word-Dokumenten auch Speichern und erneutes Oeffnen pruefen.

Wichtig fuer Word:

- Eine DOCX-Datei darf nicht nur in `.doc` umbenannt werden.
- Erwartet der Altworkflow ein binaeres DOC, muss eine echte Konvertierung erfolgen.
- Erwartet der Workflow DOCX, werden die unveraenderten OpenXML-Bytes mit passender Endung und passendem Content-Type gesendet.

PDF-Dateien werden ebenfalls als echte PDF-Bytes uebergeben. Ein Zeitstempel in der Zukunft kann vom Gateway abgelehnt werden; `DateOfService` wird deshalb vor dem Upload gegen die aktuelle lokale ARIA-Zeit geprueft.

## Lesen und Download

Beim Webservice gibt es keinen generischen FHIR-Request wie `GET /DocumentReference`. Dokumentlisten und Downloads erfolgen ueber die jeweils definierte ARIA-Access-Operation. Request-Name, Parameter und Antwortstruktur muessen deshalb gegen den lokalen Reference Guide und die freigegebenen Rechte geprueft werden. Dateiinhalte werden binaer unveraendert gespeichert und anhand der zurueckgegebenen Metadaten validiert.

## Termine

Auch Terminzugriffe sind operationenbezogen. Es gibt keine automatisch austauschbare Entsprechung zu `Appointment?patient=...`. Wenn ein bestehender Webservice-Ablauf Termine liefert, muessen Status, Startzeit, Ressource und Patientenzuordnung aus genau dieser Operation ausgewertet werden. Fuer neue Terminabfragen ist FHIR `Appointment` vorzuziehen, sofern das lokale CapabilityStatement und die Scopes den Zugriff erlauben.

## FHIR, ESAPI und Gateway im direkten Vergleich

| Merkmal | ARIA FHIR API | ESAPI | ARIA Webservice / Gateway |
|---|---|---|---|
| Modell | FHIR-R4-Ressourcen und Referenzen | Eclipse-Planungsobjekte in .NET | proprietaere Operationen |
| Authentisierung | OAuth2 Client Credentials | Eclipse-/ESAPI-Ausfuehrungskontext | Windows-/ARIA-Kontext und Access-Freigabe |
| Primaerer Zweck | systemuebergreifende klinische und administrative Integration | Plan, Strukturen, Dosis, DVH und freigegebene Planlogik | vorhandene operationenbasierte Workflows |
| Dokumente / Termine | `DocumentReference`, `Appointment` | nicht der allgemeine OIS-Datenweg | operationenspezifischer Request |
| Typen und Faehigkeiten | Profile, `ValueSet`, `metadata` | ESAPI-Objektmodell und installierte Version | Reference Guide und freigegebene Operationen |
| Fehler | HTTP plus `OperationOutcome` | .NET-/ESAPI-Ausnahmen | HTTP plus Gateway-Fehler im Body |
| Empfehlung | Standard fuer neue, unterstuetzte Ablaeufe | Eclipse-nahe Planungsaufgaben | Bestand, Fallback oder nicht in FHIR verfuegbare Funktion |

FHIR ersetzt ESAPI nicht. C# kann beide Schnittstellen verbinden, sollte sie aber als getrennte Adapter mit eigenen Berechtigungen, Modellen und Fehlergrenzen behandeln.

Die ausfuehrliche Entscheidung und sichere C#-Muster stehen in `docs/ARCHITECTURE_AND_CSHARP_PATTERNS.md`.

## Weiterfuehrende Ressourcen

- [ARIA API II: ARIA API Resources](https://www.gatewayscripts.com/post/aria-api-ii-aria-api-resources)
- [ARIA API III: Practical C# Patterns for Clinical Development](https://www.gatewayscripts.com/post/aria-api-iii-practical-c-patterns-for-clinical-development)
- [HL7 FHIR](https://hl7.org/fhir/)
- [mCODE](https://hl7.org/fhir/us/mcode/)
- [CodeX Radiation Therapy](https://build.fhir.org/ig/HL7/codex-radiation-therapy/)

## Git-Workflow

Die Dokumentation wird im lokalen `ARIA-API`-Repository gepflegt:

```powershell
git status
git add README.md docs/guides versionInfo.json
git commit -m "docs: separate ARIA gateway workflow"
git push origin main
```

Vor jedem Push ist eine separate Sicherheitspruefung erforderlich. Secrets,
AccessKeys, produktive Endpunkte, Patientendaten und echte Antworten bleiben
lokal und ausserhalb von Git.
