# Changelog

## Build 8 - 2026-08-18

- Trigger-unabhaengiges Python-Beispiel fuer idempotente ARIA-FHIR-Tasks mit sicherem Dry-Run ergaenzt.
- Gruppe und aktive Onkologen werden als Recipients gesetzt; genau ein Primary Oncologist wird Owner.
- OAuth2, Varian-Platform-Endpunkte, Scope-Pruefung, Read-back und Reconciliation sind ohne Infrastruktur- oder Geheimniswerte nachvollziehbar.

## Build 7 - 2026-08-13

- Oeffentliche Dokumentation von institutionellen Bezeichnungen, internen
  Namespaces und lokalen Git-/Infrastrukturhinweisen bereinigt.
- Task-Beispiel auf synthetische Rollen, Gruppen, ActivityDefinitions und
  Identifier umgestellt; beobachtetes Verhalten als deployment-spezifisch
  gekennzeichnet.
- Provider-Organisation muss im Upload-Beispiel explizit angegeben werden.
- Unabhaengigkeit, fehlende institutionelle Freigabe und notwendige lokale
  Validierung in einem eigenen Disclaimer klargestellt.

## Build 6 - 2026-08-12

- Deployment-spezifisches FHIR-Task-Muster fuer eine Arbeitsgruppe, verknuepfte Practitioner und einen eindeutigen Owner dokumentiert.
- Serverseitige ServiceRequest-Verknuepfung, Identifier-Reconciliation und Ausschluss von Appointment als Abnahmeregel festgehalten.
- Sichere lokale Access-Key-, SSPI- und TLS-Praxis fuer den getrennten Legacy-Gateway-Weg ergaenzt.
