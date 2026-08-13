# Versionierung und Veroeffentlichung

Das oeffentliche Projekt wird mit Git versioniert. Commits und Releases duerfen
nur separat gepruefte, vollstaendig anonymisierte und
institutionsunabhaengige Inhalte enthalten.

## Arbeitsablauf

```powershell
git status
git diff --check
git add <gezielt gepruefte Dateien>
git commit -m "<kurze Aenderungsbeschreibung>"
git push origin main
```

`versionInfo.json` wird bei sichtbaren Aenderungen mitgefuehrt.

## Nicht versionieren

- `.env` und andere Secret-Ablagen
- Client-Secrets, Token, Passwoerter und AccessKeys
- produktive Servernamen, interne IP-Adressen oder Netzpfade
- Namen oder Kennungen realer Organisationen, Rollen, Gruppen und Workflows
- Patientendaten und unredigierte API-Antworten
- lokale Laufzeit-, Cache- und Binaerdateien
