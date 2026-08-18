# ARIA FHIR Task Creation Example Design

## Ziel

Das Repository erhält ein öffentlich nutzbares, trigger-unabhängiges Python-Beispiel, das zeigt, wie eine vorhandene ARIA-Aktivität als FHIR-`Task` für einen Patienten angelegt wird. Der aufrufende Prozess liefert lediglich eine eindeutige Trigger-ID, eine Patientenkennung und den Namen der gewünschten `ActivityDefinition`. Ob der Aufruf aus einem Dokumentenworkflow, einem Watcher oder einer anderen Automation stammt, bleibt außerhalb des Beispiels.

## Öffentliche Dateien

- `examples/fhir-task-create/fhir_task_create_example.py`
- `examples/fhir-task-create/test_fhir_task_create_example.py`
- `examples/fhir-task-create/README.md`
- Verweise in der Repository-`README.md`, im `CHANGELOG.md` und in `versionInfo.json`

Das Beispiel enthält keine echten Hostnamen, Zugangsdaten, Patientenkennungen oder internen Pfade.

## Bedienung

Der CLI-Aufruf verwendet mindestens:

```powershell
python .\examples\fhir-task-create\fhir_task_create_example.py `
  --patient-identifier "<ARIA-ID>" `
  --activity-name "Labor genehmigen" `
  --trigger-id "<eindeutige-id>"
```

Optionale Argumente sind `--group-name` mit Standard `Arzt`, `--identifier-system`, `--note`, `--duration-minutes`, explizite URL-Overrides und `--execute`. Ohne `--execute` läuft das Beispiel als Dry-Run und führt keinen FHIR-Schreibzugriff aus.

## Konfiguration und Authentifizierung

Die Standardeinstellung verwendet einen anonymisierten Hostnamen `VARIAN_PLATFORM` und leitet daraus ab:

- Token-Service: `https://<Varian-Platform>:44333/tokenservice/connect/token`
- FHIR R4: `https://<Varian-Platform>:55370/fhir/r4`

Andere Installationen können `ARIA_FHIR_TOKEN_URL` und `ARIA_FHIR_BASE_URL` explizit überschreiben. Client-ID und Secret kommen ausschließlich aus `ARIA_FHIR_CLIENT_ID` und `ARIA_FHIR_CLIENT_SECRET`. Der OAuth2-Request verwendet `grant_type=client_credentials`; die zurückgegebenen Scopes werden gegen die benötigten Scopes geprüft.

TLS-Zertifikatsprüfung ist immer aktiv. Optional kann ein lokales CA-Bundle angegeben werden. Das Beispiel bietet keinen `verify=False`-Schalter und gibt weder Token noch Secret aus.

## Datenfluss

1. OAuth2-Token anfordern und benötigte Scopes prüfen.
2. Patient mit `Patient?identifier=...&_count=2` eindeutig auflösen.
3. Genau eine aktive `ActivityDefinition` mit dem angegebenen Namen und `kind=Task` auflösen.
4. `ActivityDefinition.subjectReference` lesen, die referenzierte aktive `Group` auflösen und ihren Namen gegen `--group-name` prüfen. Diese Gruppe wird Pflicht-Recipient.
5. Aktive `CareTeam`-Ressourcen des Patienten lesen. Aktive Practitioner mit den Rollen `oncologist` oder `primary-oncologist` werden zusätzliche Recipients.
6. Genau ein aktiver `primary-oncologist` wird `Task.owner`. Bei keinem oder mehreren Primary-Kandidaten bleibt `owner` leer; die Gruppentask wird dennoch erzeugt.
7. Aus der Trigger-ID einen stabilen SHA-256-Workflow-Identifier bilden und vor jedem POST mit `Task?identifier=...` nach einer vorhandenen Task suchen.
8. Den geplanten Request ohne Patientenkennung, Token oder Secret ausgeben.
9. Nur mit `--execute` `POST /Task` ausführen und die erzeugte Task anschließend zurücklesen.

Alle Bundle-Suchen folgen `Bundle.link[relation=next]`. Null, ein oder mehrere Treffer werden explizit unterschieden; das Beispiel nimmt nie stillschweigend den ersten Treffer.

## Task-Payload

Der Request enthält mindestens:

- ARIA-Task-Profil in `Task.meta.profile`
- stabilen Workflow-Identifier mit konfigurierbarem System in `Task.identifier`
- `status=ready`, `intent=order` und `priority=routine`
- `Task.code` mit dem System `http://varian.com/fhir/CodeSystem/activityDefinition-category` und dem validierten Gruppennamen, standardmäßig `Arzt`
- die aufgelöste `ActivityDefinition` in `Task.focus`
- den Patienten in `Task.for`
- die aktive Gruppe und alle aktiven Onkologen in `Task.restriction.recipient`
- eine optionale Notiz und eine kurze Fälligkeit/Dauer
- `Task.owner` nur bei genau einem aktiven Primary Oncologist

Es wird kein `Appointment` erzeugt. Eine vom ARIA-Server ergänzte `ServiceRequest`-Verknüpfung wird beim Read-back akzeptiert und dokumentiert.

## Fehler- und Idempotenzverhalten

- Fehlen Pflichtkonfiguration, Scopes oder eindeutige FHIR-Abhängigkeiten, endet das Beispiel vor dem POST.
- Eine bereits vorhandene Task mit dem Workflow-Identifier wird validiert und nicht erneut erzeugt.
- Mehrere Tasks mit demselben Identifier sind ein Fehler.
- Nach einem unklaren POST-Ergebnis wird ausschließlich über den Workflow-Identifier reconciled; der POST wird nicht blind wiederholt.
- `OperationOutcome.issue` wird in einer gekürzten, patientenfreien Fehlermeldung ausgewertet.

## Tests

Die Implementierung beginnt mit fehlschlagenden Standardbibliothek-`unittest`-Tests. Abgedeckt werden:

- stabiler Workflow-Identifier
- Task-Kategorie entspricht der validierten Zielgruppe
- Gruppe und alle aktiven Onkologen als deduplizierte Recipients
- genau ein Primary als Owner
- kein Owner bei null oder mehreren Primary-Kandidaten
- Payload ohne Owner erzeugt weiterhin eine Gruppentask
- Dry-Run führt keinen POST aus
- vorhandene Task verhindert einen zweiten POST
- Read-back erkennt abweichenden Owner, Focus, Patient oder fehlende Recipients
- öffentliche Ausgabe enthält keine Patientenkennung, Token oder Secrets

Netzwerkzugriffe werden in Unit-Tests nicht gegen eine reale Varian-Platform ausgeführt.

## Dokumentation und Veröffentlichung

Die Beispiel-README erklärt Voraussetzungen, Dry-Run, Live-Aufruf, FHIR-Semantik, Routingregeln und die Anpassung der Aktivität an die jeweilige ARIA-Installation. Die Repository-README verlinkt den neuen Ordner. Changelog und Versionsmetadaten erhalten einen fokussierten Eintrag.

Die Änderung wird auf `codex/fhir-task-create-example` entwickelt, vollständig getestet, auf sensible Muster geprüft und als Draft-PR gegen `main` veröffentlicht. Das vorhandene unversionierte Verzeichnis `Flint/` bleibt unverändert und wird nicht gestaged.
