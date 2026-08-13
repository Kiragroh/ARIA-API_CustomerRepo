# ARIA API: Architektur und praktische C#-Muster

Diese Referenz ordnet die Datenwege im ARIA-/Eclipse-Umfeld ein und uebertraegt die nuetzlichen Muster aus den ARIA-API-Blogposts und dem begleitenden C#-Repository in eine produktionsnahe Form. Sie enthaelt keine produktiven Endpunkte, Zugangsdaten oder Patientendaten.

## 1. Warum FHIR die strategische Integrationsschicht ist

Die ARIA FHIR API verwendet HL7 FHIR R4 als offenes Modell fuer klinische und administrative Daten. FHIR beschreibt Ressourcen, Referenzen, Suchparameter, Operationen, Profile, Extensions sowie Terminologien. Der technische Austausch erfolgt sprachunabhaengig ueber HTTP und in der Regel JSON; XML ist ebenfalls Teil des Standards. ARIA kombiniert dies mit OAuth2 Client Credentials.

Fuer die Onkologie baut mCODE strukturierte onkologische FHIR-Profile auf. CodeX Radiation Therapy erweitert diesen Ansatz um strahlentherapeutische Konzepte. In ARIA wird damit beispielsweise zwischen geplanter beziehungsweise verordneter Therapie (`ServiceRequest`) und tatsaechlich durchgefuehrter Therapie (`Procedure`) unterschieden.

Das ist zukunftsfaehig, weil Daten und Beziehungen nicht nur als proprietaere Einzeloperationen beschrieben werden, sondern durch versionierte, herstelleruebergreifend nutzbare Standards. Es ist dennoch keine Garantie fuer vollstaendige Herstellerunabhaengigkeit: ARIA-spezifische Profile, Extensions, Scopes und ValueSets bleiben relevant. Fuer jede produktive Funktion gelten daher in dieser Reihenfolge:

1. lokaler ARIA API Implementation Guide,
2. live gelesenes `CapabilityStatement` unter `metadata`,
3. freigegebene OAuth2-Scopes,
4. erst danach der allgemeine FHIR-R4-Standard.

## 2. FHIR, ESAPI, Gateway, SQL oder DICOM?

| Datenweg | Verwenden fuer | Nicht als Ersatz fuer | Technischer Charakter |
|---|---|---|---|
| ARIA FHIR API | systemuebergreifende klinische, administrative und Workflow-Daten; Dokumente; Termine | Eclipse-interne Planberechnung und DICOM-Objekttransport | HL7 FHIR R4, REST/HTTP, JSON/XML, OAuth2, Profile und Terminologien |
| ESAPI | Eclipse-Planungsobjekte, Strukturen, Dosis, DVH, Planpruefung und freigegebene Planmanipulation | allgemeine OIS-Integration | Varian-spezifische .NET-API, Eclipse-nah |
| ARIA Webservice / Gateway | bestehende proprietaere Operationen oder lokale Funktionen, die im FHIR-Profil fehlen | neue allgemeine FHIR-Workflows | operationenbasiert, proprietaere Requests/Responses und eigene Authentisierung |
| SQL, nur lesend | definierte Extraktion, Reporting, Audit und interne Datenaufbereitung | klinische Schreibschnittstelle | schema- und versionsabhaengige Datenbankabfragen |
| DICOM / DICOM RT | Bilddaten sowie RTSTRUCT, RTPLAN und RTDOSE | Patienten-, Termin- oder Dokumentworkflow | etablierter Objekt- und Bildaustauschstandard |

**Entscheidungsregel:** Neue fachliche Integrationen zuerst im lokalen FHIR-Profil suchen. ESAPI bleibt fuer Eclipse-nahe Planungslogik zustaendig. Gateway nur bewusst fuer Bestand oder echte FHIR-Luecken verwenden. SQL bleibt read-only. DICOM transportiert Bild- und RT-Objekte.

Eine C#-Anwendung darf FHIR und ESAPI kombinieren, etwa um einen in Eclipse selektierten Plan mit OIS-Workflowdaten anzureichern. Die Anwendung muss die beiden Schnittstellen trotzdem als getrennte Adapter behandeln: eigener Client, eigene Berechtigungen, eigene Modelle und eigene Fehlergrenzen.

## 3. Spec-first statt Trial-and-error

Vor dem ersten Request:

1. Ressource und passendes ARIA-Profil im lokalen Implementation Guide oeffnen.
2. Unter **Differential** die ARIA-Abweichungen vom Basisprofil pruefen; unter **Snapshot** den vollstaendigen effektiven Aufbau lesen.
3. Kardinalitaeten, Must-Support-Flags, Constraints und Terminologie-Bindings beachten.
4. Die Seite **Operations** und die freigegebenen **Search Parameters** lesen. Ein Element im Datenmodell bedeutet nicht automatisch, dass danach gesucht oder darauf geschrieben werden darf.
5. Benoetigte Scopes mit der Scope-Matrix abgleichen.
6. Request zuerst im ARIA API Tester beziehungsweise mit einer nicht patientenbezogenen Probe nachvollziehen.

Wichtige Ressourcengruppen sind:

- Foundation: beispielsweise `ValueSet`, `AuditEvent`, `DocumentReference`
- Base: beispielsweise `Patient`, `Organization`, `Activity`
- Clinical / Radiotherapy: beispielsweise `Procedure` als Radiotherapy Course Summary und `ServiceRequest` als Planned Phase
- Financial: beispielsweise `ChargeItem`

## 4. Praktische C#-Muster

Die folgenden Muster sind von den verlinkten Praxisbeispielen abgeleitet und um Produktionsgrenzen ergaenzt.

### 4.1 Benutzer-Identifier eindeutig in eine FHIR-ID aufloesen

Suchwerte immer URL-kodieren und nicht blind den ersten Treffer verwenden. Null, genau ein und mehrere Treffer sind drei verschiedene Ergebnisse.

```csharp
var value = Uri.EscapeDataString($"{identifierSystem}|{patientIdentifier}");
var bundle = await fhir.GetJsonAsync(
    $"Patient?identifier={value}&_count=2",
    cancellationToken);

var patients = bundle.RootElement
    .GetProperty("entry")
    .EnumerateArray()
    .Select(entry => entry.GetProperty("resource"))
    .ToList();

if (patients.Count != 1)
{
    throw new InvalidOperationException(
        $"Patient-Identifier ist nicht eindeutig: {patients.Count} Treffer.");
}

var patientFhirId = patients[0].GetProperty("id").GetString();
```

Fuer breite Patientensuchen kann der Server `too-costly` melden. Dann mit einem unterstuetzten Identifier, `_id`, `family`, `given` oder einem anderen im lokalen Profil dokumentierten Parameter enger suchen.

### 4.2 Referenzen bewusst aufloesen

FHIR-Ressourcen verweisen aufeinander, beispielsweise `Appointment.participant.actor.reference = "Device/123"`. Die Referenz wird getrennt gelesen und kann fuer einen Request-Lauf gecacht werden.

```csharp
private readonly ConcurrentDictionary<string, JsonElement> referenceCache = new();

public async Task<JsonElement> ResolveReferenceAsync(
    string reference,
    CancellationToken cancellationToken)
{
    if (referenceCache.TryGetValue(reference, out var cached))
        return cached;

    var resource = (await fhir.GetJsonAsync(reference, cancellationToken))
        .RootElement.Clone();
    referenceCache[reference] = resource;
    return resource;
}
```

So lassen sich zum Beispiel Patient -> Appointment -> Device oder DocumentReference -> Binary nachvollziehbar aufloesen. Cache nur innerhalb eines fachlich passenden Zeitraums verwenden und keine patientenbezogenen Antworten dauerhaft protokollieren.

### 4.3 Alle Bundle-Seiten lesen

FHIR-Suchergebnisse sind `Bundle`-Ressourcen und koennen paginiert sein. Nicht Offset-Werte erraten, sondern dem Link mit `relation="next"` folgen, bis er fehlt.

```csharp
var next = "Appointment?patient=Patient/123&_count=50";

while (!string.IsNullOrWhiteSpace(next))
{
    using var page = await fhir.GetJsonAsync(next, cancellationToken);
    ProcessEntries(page.RootElement.GetProperty("entry"));

    next = page.RootElement.GetProperty("link")
        .EnumerateArray()
        .Where(link => link.GetProperty("relation").GetString() == "next")
        .Select(link => link.GetProperty("url").GetString())
        .SingleOrDefault();
}
```

Vor dem Folgen eines absoluten `next`-Links Host und FHIR-Basispfad gegen die konfigurierte Basis pruefen. So gelangt das Bearer-Token nicht versehentlich an ein fremdes Ziel.

### 4.4 ValueSets statt hart codierter ARIA-Codes

Dokumenttypen und andere gebundene Codes dynamisch ueber das im Profil angegebene `ValueSet` beziehungsweise `ValueSet/$expand` aufloesen. Speichern beziehungsweise vergleichen:

- `system`
- `code`
- `display`

Ein `CodeSystem` definiert Codes und Bedeutungen. Ein `ValueSet` legt fest, welche Codes in einem konkreten Kontext erlaubt sind. Anzeigenamen sind keine stabilen technischen IDs.

### 4.5 Fehler als FHIR-Inhalt behandeln

Bei Fehlerantworten nach Moeglichkeit `OperationOutcome.issue` auswerten und eine redigierte Diagnose aus Severity, Code, Details und Diagnostics bilden. Patientendaten, Attachment-Inhalt, Token und Secrets nicht loggen.

## 5. Produktionscheckliste fuer C#

- `HttpClient` wiederverwenden, beispielsweise ueber `IHttpClientFactory`; keinen neuen Client pro Request erzeugen.
- Durchgehend `async`/`await` und `CancellationToken` verwenden; `.Result` und `.Wait()` vermeiden.
- OAuth2-Token bis kurz vor Ablauf cachen und kontrolliert erneuern; Token niemals ausgeben.
- Parameter mit `Uri.EscapeDataString` kodieren.
- Timeouts definieren und `OperationOutcome` fachlich auswerten.
- Retries nur fuer transiente Fehler und idempotente Lesezugriffe einsetzen. Schreibzugriffe nicht blind wiederholen.
- Bei Schreiboperationen zuerst Patient, Ressourcentyp, Datum, Dokumenttyp und Status in einer redigierten Vorschau pruefen.
- Referenzen innerhalb eines Laufs cachen, damit kein unkontrolliertes N+1-Requestmuster entsteht.
- Zertifikatspruefung nicht global deaktivieren. Interne Zertifikate ueber den vorgesehenen Trust Store bereitstellen.
- Secrets aus Environment, `.env` ausserhalb von Git oder einem Secret Store laden.

## 6. Sicherheit der verlinkten Beispiele

Die Gateway-Scripts-Beispiele sind eine hilfreiche Lern- und Diskussionsgrundlage, aber kein unveraendert zu uebernehmendes Produktionsgeruest. Insbesondere folgende Demo-Muster sind in produktivem Code unzulaessig:

- hart codierte Client-Secrets oder Passwoerter,
- Ausgabe eines Access-Tokens in Konsole oder Log,
- globale Umgehung der TLS-Zertifikatspruefung,
- synchrone Blockierung asynchroner Requests mit `.Result`,
- ungepruefte Auswahl des ersten Suchtreffers.

Beim Uebernehmen eines Snippets nur die fachliche Idee verwenden und Authentisierung, Fehlerbehandlung, Logging und Transport entsprechend dieser Checkliste neu aufsetzen.

## 7. Ressourcen

### Praxis und ARIA-Einordnung

- [ARIA API II: ARIA API Resources](https://www.gatewayscripts.com/post/aria-api-ii-aria-api-resources) - Profile, Ressourcen, Operationen, Suchparameter, Terminologien sowie Abgrenzung und RT-Modell
- [ARIA API III: Practical C# Patterns for Clinical Development](https://www.gatewayscripts.com/post/aria-api-iii-practical-c-patterns-for-clinical-development) - Identifier-Aufloesung, Referenzen, Termine und Bundle-Paginierung
- [Gateway-Scripts/ARIAAPI_Snippets](https://github.com/Gateway-Scripts/ARIAAPI_Snippets) - begleitende Lernsnippets; nur unter Beachtung der oben genannten Sicherheitsgrenzen verwenden

### Offene Standards

- [HL7 FHIR](https://hl7.org/fhir/) - offizieller Standard und Grundmodell
- [mCODE Implementation Guide](https://hl7.org/fhir/us/mcode/) - strukturierte onkologische FHIR-Profile
- [CodeX Radiation Therapy](https://build.fhir.org/ig/HL7/codex-radiation-therapy/) - strahlentherapeutische Erweiterung auf Basis von mCODE

### Lokale Herstellerreferenz

- [ARIA API Implementation Guide](ARIA-API-ImplementationGuide/index.html)
- [FHIR JSON-Beispiele](../examples/examples.json/)

Die lokalen Herstellerunterlagen sind fuer die konkret installierte ARIA-Version und deren freigegebene Profile massgeblich.
