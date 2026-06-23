from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import urllib3
from zoneinfo import ZoneInfo


TOKEN_URL = os.getenv(
    "ARIA_FHIR_TOKEN_URL",
    "",
)
FHIR_BASE_URL = os.getenv("ARIA_FHIR_BASE_URL", "")
CLIENT_ID = os.getenv("ARIA_FHIR_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ARIA_FHIR_CLIENT_SECRET", "")
SCOPE = os.getenv("ARIA_FHIR_SCOPE", "")
VERIFY_TLS = os.getenv("ARIA_FHIR_VERIFY_TLS", "false").lower() in {"1", "true", "yes"}
LOCAL_TZ = ZoneInfo("Europe/Berlin")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def parse_local_timestamp(value: str) -> datetime:
    parsed = datetime.strptime(value.strip(), "%d.%m.%Y %H:%M")
    return parsed.replace(tzinfo=LOCAL_TZ)


def parse_fhir_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def get_token(client_id: str, client_secret: str, scope: str) -> str:
    if not TOKEN_URL:
        raise RuntimeError("Token URL fehlt. Setze ARIA_FHIR_TOKEN_URL in .env oder Umgebung.")
    if not client_id:
        raise RuntimeError("Client ID fehlt.")
    if not client_secret:
        raise RuntimeError("Client Secret fehlt. Setze ARIA_FHIR_CLIENT_SECRET in .env oder uebergib --client-secret.")

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
        verify=VERIFY_TLS,
    )
    if not response.ok:
        raise RuntimeError(f"Token-Request fehlgeschlagen: HTTP {response.status_code} {response.text[:500]}")
    access_token = response.json().get("access_token")
    if not access_token:
        raise RuntimeError("Token-Response enthaelt kein access_token.")
    return str(access_token)


def fhir_get(session: requests.Session, path: str, params: dict[str, str]) -> dict[str, Any]:
    if not FHIR_BASE_URL:
        raise RuntimeError("FHIR Base URL fehlt. Setze ARIA_FHIR_BASE_URL in .env oder Umgebung.")
    response = session.get(
        f"{FHIR_BASE_URL.rstrip('/')}/{path.lstrip('/')}",
        params=params,
        timeout=60,
        verify=VERIFY_TLS,
    )
    if not response.ok:
        raise RuntimeError(f"FHIR GET {path} fehlgeschlagen: HTTP {response.status_code} {response.text[:500]}")
    return response.json()


def bundle_resources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("resourceType") == "Bundle":
        return [(entry.get("resource") or {}) for entry in payload.get("entry") or [] if entry.get("resource")]
    return [payload] if payload.get("resourceType") else []


def resolve_patient_fhir_id(session: requests.Session, patient_identifier: str) -> str:
    if patient_identifier.startswith("Patient-"):
        return patient_identifier
    payload = fhir_get(session, "Patient", {"identifier": patient_identifier, "_count": "5"})
    patients = bundle_resources(payload)
    if not patients:
        raise RuntimeError(f"Kein FHIR-Patient fuer ARIA PatID {patient_identifier} gefunden.")
    if len(patients) > 1:
        raise RuntimeError(f"Mehrere FHIR-Patienten fuer ARIA PatID {patient_identifier} gefunden.")
    patient_id = str(patients[0].get("id") or "")
    if not patient_id:
        raise RuntimeError("Patient gefunden, aber ohne FHIR-ID.")
    return patient_id


def matches_task_timestamp(task: dict[str, Any], target: datetime, tolerance_seconds: int = 59) -> bool:
    authored_on = parse_fhir_datetime(str(task.get("authoredOn") or ""))
    if not authored_on:
        return False
    return abs((authored_on - target).total_seconds()) <= tolerance_seconds


def filter_task_notes(tasks: list[dict[str, Any]], target: datetime) -> list[dict[str, Any]]:
    return [task for task in tasks if matches_task_timestamp(task, target) and task.get("note")]


def task_code(task: dict[str, Any]) -> tuple[str, str]:
    coding = ((task.get("code") or {}).get("coding") or [{}])[0]
    return str(coding.get("code") or ""), str(coding.get("display") or "")


def summarize_task_note(task: dict[str, Any], redact: bool = False) -> dict[str, Any]:
    notes = task.get("note") or []
    code, display = task_code(task)
    note_texts = [str(note.get("text") or "") for note in notes if note.get("text")]
    combined_text = "\n\n".join(note_texts)
    return {
        "task_id": task.get("id", ""),
        "status": task.get("status", ""),
        "intent": task.get("intent", ""),
        "authoredOn": task.get("authoredOn", ""),
        "lastModified": task.get("lastModified", ""),
        "code": code,
        "display": display,
        "note_count": len(notes),
        "note_text_length": len(combined_text),
        "note_text": "[redacted]" if redact and combined_text else combined_text,
    }


def search_task_notes(session: requests.Session, patient_fhir_id: str, target: datetime, count: int = 100) -> list[dict[str, Any]]:
    payload = fhir_get(session, "Task", {"patient": f"Patient/{patient_fhir_id}", "_count": str(count)})
    return filter_task_notes(bundle_resources(payload), target)


def fetch_journal_notes(
    patient_identifier: str = "",
    timestamp: str = "01.01.2026 00:00",
    client_id: str | None = None,
    client_secret: str | None = None,
    scope: str | None = None,
    redact: bool = False,
) -> dict[str, Any]:
    load_dotenv()
    if not patient_identifier.strip():
        raise RuntimeError("Patienten-Identifier fehlt. Uebergib --patient oder patient_identifier.")
    client_id = client_id if client_id is not None else os.getenv("ARIA_FHIR_CLIENT_ID", CLIENT_ID)
    client_secret = client_secret if client_secret is not None else os.getenv("ARIA_FHIR_CLIENT_SECRET", CLIENT_SECRET)
    scope = scope if scope is not None else os.getenv("ARIA_FHIR_SCOPE", SCOPE)

    target = parse_local_timestamp(timestamp)
    token = get_token(client_id, client_secret, scope)
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"})

    patient_fhir_id = resolve_patient_fhir_id(session, patient_identifier)
    tasks = search_task_notes(session, patient_fhir_id, target)
    return {
        "source": "FHIR Task.note",
        "patient_identifier": patient_identifier,
        "patient_fhir_id": patient_fhir_id,
        "requested_timestamp": timestamp,
        "requested_timestamp_fhir": target.isoformat(timespec="seconds"),
        "count": len(tasks),
        "items": [summarize_task_note(task, redact=redact) for task in tasks],
    }


def fetch_onkologischer_verlauf(**kwargs: Any) -> dict[str, Any]:
    return fetch_journal_notes(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimaler FHIR-Fallback fuer ARIA Journal Notes via Task.note.")
    parser.add_argument("--patient", required=True, help="ARIA PatID oder Patient-... FHIR-ID.")
    parser.add_argument("--timestamp", default="01.01.2026 00:00", help="Lokale Zeit in Leipzig, Format dd.mm.yyyy HH:MM.")
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--client-secret", default=None)
    parser.add_argument("--scope", default=None, help="Leer lassen nutzt den fuer den Client konfigurierten Default-Scope.")
    parser.add_argument("--redact", action="store_true", help="Notiztext nicht ausgeben, nur Laengen/Metadaten.")
    args = parser.parse_args()

    result = fetch_journal_notes(
        patient_identifier=args.patient,
        timestamp=args.timestamp,
        client_id=args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
        redact=args.redact,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        raise SystemExit(1)
