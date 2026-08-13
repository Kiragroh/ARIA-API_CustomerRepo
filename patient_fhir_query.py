from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import urllib3


TOKEN_URL = os.getenv(
    "ARIA_FHIR_TOKEN_URL",
    "",
)
FHIR_BASE_URL = os.getenv("ARIA_FHIR_BASE_URL", "")
CLIENT_ID = os.getenv("ARIA_FHIR_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ARIA_FHIR_CLIENT_SECRET", "")
SCOPE = os.getenv("ARIA_FHIR_SCOPE", "")
VERIFY_TLS = os.getenv("ARIA_FHIR_VERIFY_TLS", "false").lower() in {"1", "true", "yes"}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass(frozen=True)
class PatientQuery:
    path: str
    params: dict[str, str]


def load_dotenv(path: Path | None = None) -> None:
    candidates = [path] if path else [Path(".env"), Path(__file__).resolve().parent / ".env"]
    for candidate in candidates:
        if not candidate or not candidate.exists():
            continue
        for raw in candidate.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def clean_patient_id(value: str) -> str:
    cleaned = value.strip()
    return cleaned.removeprefix("Patient/")


def clamp_count(count: int) -> int:
    return max(1, min(int(count), 100))


def build_patient_query(
    *,
    identifier: str = "",
    fhir_id: str = "",
    name_or_identifier: str = "",
    family: str = "",
    given: str = "",
    birthdate: str = "",
    active: str = "",
    test_patient: str = "",
    count: int = 10,
    allow_broad: bool = False,
) -> PatientQuery:
    if fhir_id.strip():
        return PatientQuery(path=f"Patient/{clean_patient_id(fhir_id)}", params={})

    params: dict[str, str] = {}
    if identifier.strip():
        params["identifier"] = identifier.strip()
    if name_or_identifier.strip():
        params["name-or-identifier"] = name_or_identifier.strip()
    if family.strip():
        params["family"] = family.strip()
    if given.strip():
        params["given"] = given.strip()
    if birthdate.strip():
        params["birthdate"] = birthdate.strip()
    if active.strip():
        params["active"] = active.strip()
    if test_patient.strip():
        params["testPatient"] = test_patient.strip()

    if not params and not allow_broad:
        raise ValueError(
            "Ungefilterte Patient-Suche ist blockiert. Nutze z.B. --identifier, --name-or-identifier "
            "oder setze bewusst --allow-broad."
        )
    params["_count"] = str(clamp_count(count))
    return PatientQuery(path="Patient", params=params)


def get_token(client_id: str, client_secret: str, scope: str) -> tuple[str, dict[str, Any]]:
    if not TOKEN_URL:
        raise RuntimeError("Token URL fehlt. Setze ARIA_FHIR_TOKEN_URL in .env oder Umgebung.")
    if not client_id:
        raise RuntimeError("Client ID fehlt.")
    if not client_secret:
        raise RuntimeError("Client Secret fehlt. Setze ARIA_FHIR_CLIENT_SECRET in .env oder uebergib --client-secret.")

    request_info = {
        "method": "POST",
        "url": TOKEN_URL,
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "form": {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": "<redacted>",
            "scope": scope or "<empty: client default scope>",
        },
    }
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
    response_info: dict[str, Any] = {
        "http_status": response.status_code,
        "ok": response.ok,
        "headers": redacted_headers(response.headers),
    }
    if not response.ok:
        response_info["body"] = safe_json_or_text(response)
        raise RuntimeError(json.dumps({"token_request": request_info, "token_response": response_info}, ensure_ascii=False))

    body = response.json()
    access_token = str(body.get("access_token") or "")
    if not access_token:
        raise RuntimeError("Token-Response enthaelt kein access_token.")
    response_info["body"] = {
        "access_token": "<redacted>",
        "token_type": body.get("token_type"),
        "expires_in": body.get("expires_in"),
        "scope_count": len(str(body.get("scope") or "").split()),
    }
    return access_token, {"token_request": request_info, "token_response": response_info}


def redacted_headers(headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, str]:
    keep = {"content-type", "cache-control", "date"}
    return {key: value for key, value in headers.items() if key.lower() in keep}


def safe_json_or_text(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"text": response.text[:500]}


def fhir_get(token: str, query: PatientQuery) -> tuple[Any, dict[str, Any]]:
    if not FHIR_BASE_URL:
        raise RuntimeError("FHIR Base URL fehlt. Setze ARIA_FHIR_BASE_URL in .env oder Umgebung.")
    url = f"{FHIR_BASE_URL.rstrip('/')}/{query.path}"
    request_info = {
        "method": "GET",
        "url": url,
        "params": query.params,
        "headers": {"Authorization": "Bearer <redacted>", "Accept": "application/fhir+json"},
    }
    response = requests.get(
        url,
        params=query.params,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
        timeout=60,
        verify=VERIFY_TLS,
    )
    payload = safe_json_or_text(response)
    response_info = {
        "http_status": response.status_code,
        "ok": response.ok,
        "final_url": response.url,
        "headers": redacted_headers(response.headers),
    }
    if not response.ok:
        response_info["body"] = payload
        raise RuntimeError(json.dumps({"patient_request": request_info, "patient_response": response_info}, ensure_ascii=False))
    return payload, {"patient_request": request_info, "patient_response": response_info}


def bundle_resources(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        return [(entry.get("resource") or {}) for entry in payload.get("entry") or [] if entry.get("resource")]
    if isinstance(payload, dict) and payload.get("resourceType"):
        return [payload]
    return []


def human_name(name: dict[str, Any]) -> str:
    if name.get("text"):
        return str(name["text"])
    parts = [str(item) for item in name.get("given") or [] if item]
    if name.get("family"):
        parts.append(str(name["family"]))
    return " ".join(parts)


def summarize_patient(patient: dict[str, Any], redact: bool = False) -> dict[str, Any]:
    identifiers = patient.get("identifier") or []
    names = patient.get("name") or []
    summary: dict[str, Any] = {
        "resourceType": patient.get("resourceType", ""),
        "id": patient.get("id", ""),
        "active": patient.get("active") if "active" in patient else None,
        "gender": patient.get("gender", ""),
        "identifier_count": len(identifiers),
        "name_count": len(names),
        "birthDate_present": bool(patient.get("birthDate")),
        "telecom_count": len(patient.get("telecom") or []),
        "address_count": len(patient.get("address") or []),
    }
    if not redact:
        summary["identifiers"] = [
            {"system": item.get("system", ""), "value": item.get("value", "")}
            for item in identifiers
        ]
        summary["names"] = [{"text": human_name(item), "use": item.get("use", "")} for item in names]
        summary["birthDate"] = patient.get("birthDate", "")
    return summary


def summarize_operation_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "resourceType": "OperationOutcome",
        "issues": [
            {
                "severity": issue.get("severity", ""),
                "code": issue.get("code", ""),
                "text": (issue.get("details") or {}).get("text", ""),
                "diagnostics": issue.get("diagnostics", ""),
            }
            for issue in outcome.get("issue") or []
        ],
    }


def query_patients(
    *,
    identifier: str = "",
    fhir_id: str = "",
    name_or_identifier: str = "",
    family: str = "",
    given: str = "",
    birthdate: str = "",
    active: str = "",
    test_patient: str = "",
    count: int = 10,
    allow_broad: bool = False,
    raw: bool = False,
    redact: bool = False,
    include_http: bool = False,
    client_id: str | None = None,
    client_secret: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    load_dotenv()
    effective_client_id = client_id if client_id is not None else os.getenv("ARIA_FHIR_CLIENT_ID", CLIENT_ID)
    effective_secret = client_secret if client_secret is not None else os.getenv("ARIA_FHIR_CLIENT_SECRET", CLIENT_SECRET)
    effective_scope = scope if scope is not None else os.getenv("ARIA_FHIR_SCOPE", SCOPE)
    query = build_patient_query(
        identifier=identifier,
        fhir_id=fhir_id,
        name_or_identifier=name_or_identifier,
        family=family,
        given=given,
        birthdate=birthdate,
        active=active,
        test_patient=test_patient,
        count=count,
        allow_broad=allow_broad,
    )

    token, token_http = get_token(effective_client_id, effective_secret, effective_scope)
    payload, patient_http = fhir_get(token, query)
    resources = bundle_resources(payload)
    patients = [resource for resource in resources if resource.get("resourceType") == "Patient"]
    outcomes = [summarize_operation_outcome(resource) for resource in resources if resource.get("resourceType") == "OperationOutcome"]
    result: dict[str, Any] = {
        "query": {"path": query.path, "params": query.params},
        "count": len(patients),
        "patients": payload if raw else [summarize_patient(patient, redact=redact) for patient in patients],
    }
    if outcomes:
        result["operation_outcomes"] = outcomes
    if include_http:
        result["http"] = {**token_http, **patient_http}
    return result


def write_or_print(result: dict[str, Any], output_path: str = "") -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ARIA FHIR Patient-Abfrage ueber OAuth Client Credentials.")
    parser.add_argument("--identifier", default="", help="Sichtbare ARIA PatID, z.B. <patient-identifier>.")
    parser.add_argument("--id", dest="fhir_id", default="", help="FHIR-ID, z.B. Patient-123.")
    parser.add_argument("--name-or-identifier", default="", help="Freitextsuche ueber Name oder ID.")
    parser.add_argument("--family", default="", help="Nachname.")
    parser.add_argument("--given", default="", help="Vorname.")
    parser.add_argument("--birthdate", default="", help="Geburtsdatum im FHIR-Format YYYY-MM-DD.")
    parser.add_argument("--active", default="", choices=["", "true", "false"])
    parser.add_argument("--test-patient", default="", choices=["", "true", "false"])
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--allow-broad", action="store_true", help="Erlaubt bewusst eine ungefilterte Suche.")
    parser.add_argument("--raw", action="store_true", help="Gibt die rohe FHIR-Antwort aus.")
    parser.add_argument("--redact", action="store_true", help="Redigiert Identifier, Namen und Geburtsdatum in der Summary.")
    parser.add_argument("--include-http", action="store_true", help="Gibt Request/Response-Metadaten mit redigiertem Token aus.")
    parser.add_argument("--out", default="", help="JSON-Ausgabedatei statt Konsole.")
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--client-secret", default=None)
    parser.add_argument("--scope", default=None, help="Leer lassen nutzt den Client-Default-Scope.")
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    result = query_patients(
        identifier=args.identifier,
        fhir_id=args.fhir_id,
        name_or_identifier=args.name_or_identifier,
        family=args.family,
        given=args.given,
        birthdate=args.birthdate,
        active=args.active,
        test_patient=args.test_patient,
        count=args.count,
        allow_broad=args.allow_broad,
        raw=args.raw,
        redact=args.redact,
        include_http=args.include_http,
        client_id=args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
    )
    write_or_print(result, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        raise SystemExit(1)
