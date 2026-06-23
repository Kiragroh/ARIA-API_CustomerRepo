from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

import requests
import urllib3


DEFAULT_TOKEN_URL = ""
DEFAULT_BASE_URL = ""
DEFAULT_CLIENT_ID = ""
DEFAULT_SCOPE = (
    "system/DocumentReference.cruds system/Patient.rs system/Organization.rs "
    "system/ValueSet.rs system/Practitioner.rs"
)

DOCUMENT_TYPE_VALUESET = "http://varian.com/fhir/ValueSet/documentreference-type"
DOCUMENT_TYPE_SYSTEM = "http://varian.com/fhir/CodeSystem/DocumentReference/documentreference-type"
DOCUMENT_CLASS_SYSTEM = "http://varian.com/fhir/CodeSystem/DocumentReference/documentreference-class"
TEMPLATE_NAME_EXTENSION_URL = "http://varian.com/fhir/v1/StructureDefinition/documentreference-templateName"
DOCUMENT_LOCATION_EXTENSION_URL = "http://varian.com/fhir/v1/StructureDefinition/documentreference-documentLocation"
SUPERVISOR_EXTENSION_URL = "http://varian.com/fhir/v1/StructureDefinition/documentreference-supervisor"
WORD_CONTENT_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def load_env() -> None:
    root = Path(__file__).resolve().parents[2]
    for env_file in (root / ".env", Path.cwd() / ".env"):
        if not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                os.environ.setdefault("ARIA_FHIR_CLIENT_SECRET", line)
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run oder POST fuer ARIA FHIR DocumentReference.")
    parser.add_argument("--patient-identifier", help="Sichtbare ARIA-Patienten-ID, wird via Patient?identifier aufgeloest.")
    parser.add_argument("--patient-fhir-id", help="FHIR Patient-ID, falls schon bekannt, z.B. Patient-123.")
    parser.add_argument("--file", required=True, type=Path, help="PDF, DOCX oder andere Upload-Datei.")
    parser.add_argument("--document-type", required=True, help="ARIA-Dokumenttyp, z.B. RT-Plan-Verifikation.")
    parser.add_argument("--template-name", default="", help="Optionale ARIA TemplateName-Metadaten.")
    parser.add_argument("--preview-text", default="", help="Optionaler Text fuer DocumentReference.description.")
    parser.add_argument("--document-time", default="now-10min", help="now-10min, ISO oder dd.mm.yyyy HH:MM.")
    parser.add_argument("--windows-user", default=os.getenv("ARIA_USER") or os.getenv("USERNAME") or "")
    parser.add_argument("--organization-name", action="append", default=[], help="Provider-Organisation bevorzugt nach Name suchen.")
    parser.add_argument("--execute", action="store_true", help="Ohne diese Option wird kein POST ausgefuehrt.")
    parser.add_argument("--verify-tls", action="store_true", help="TLS-Zertifikat pruefen. Intern meist nicht nutzbar.")
    parser.add_argument("--token-url", default=os.getenv("ARIA_FHIR_TOKEN_URL", DEFAULT_TOKEN_URL))
    parser.add_argument("--base-url", default=os.getenv("ARIA_FHIR_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--client-id", default=os.getenv("ARIA_FHIR_CLIENT_ID", DEFAULT_CLIENT_ID))
    parser.add_argument("--client-secret", default=os.getenv("ARIA_FHIR_CLIENT_SECRET", ""))
    parser.add_argument("--scope", default=os.getenv("ARIA_FHIR_SCOPE", DEFAULT_SCOPE))
    return parser


def request_token(args: argparse.Namespace) -> tuple[str, dict]:
    if not args.token_url:
        raise SystemExit("ARIA_FHIR_TOKEN_URL fehlt. In .env oder Umgebung setzen.")
    if not args.client_id:
        raise SystemExit("ARIA_FHIR_CLIENT_ID fehlt. In .env oder Umgebung setzen.")
    if not args.client_secret:
        raise SystemExit("ARIA_FHIR_CLIENT_SECRET fehlt. In .env oder Umgebung setzen.")
    response = requests.post(
        args.token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "scope": args.scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
        verify=args.verify_tls,
    )
    if not response.ok:
        raise SystemExit(f"Token-Anfrage fehlgeschlagen: HTTP {response.status_code} {response.text[:800]}")
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise SystemExit("Token-Antwort enthaelt kein access_token.")
    return token, {
        "http_status": response.status_code,
        "token_type": payload.get("token_type"),
        "expires_in": payload.get("expires_in"),
        "scope_count": len(str(payload.get("scope", "")).split()),
    }


def fhir_get(session: requests.Session, base_url: str, resource: str, params: dict[str, str]) -> dict:
    response = session.get(f"{base_url.rstrip('/')}/{resource}", params=params, timeout=60)
    if not response.ok:
        raise RuntimeError(f"{resource}-GET fehlgeschlagen: HTTP {response.status_code} {response.text[:800]}")
    return response.json()


def first_resource(session: requests.Session, base_url: str, resource: str, params: dict[str, str]) -> dict:
    payload = fhir_get(session, base_url, resource, {**params, "_count": "1"})
    entries = payload.get("entry") or []
    if not entries:
        raise RuntimeError(f"Keine Treffer fuer {resource} mit {params}.")
    return entries[0].get("resource") or {}


def patient_reference(args: argparse.Namespace, session: requests.Session) -> str:
    if args.patient_fhir_id:
        patient_id = args.patient_fhir_id.removeprefix("Patient/")
        return f"Patient/{patient_id}"
    if not args.patient_identifier:
        raise SystemExit("--patient-identifier oder --patient-fhir-id ist erforderlich.")
    patient = first_resource(session, args.base_url, "Patient", {"identifier": args.patient_identifier})
    patient_id = patient.get("id")
    if not patient_id:
        raise RuntimeError("Patient-Treffer ohne id.")
    return f"Patient/{patient_id}"


def organization_reference(args: argparse.Namespace, session: requests.Session) -> str:
    names = args.organization_name or [
        "Uniklinikum Leipzig",
        "Universitaetsklinikum Leipzig",
        "Leipzig",
        "MedVZ",
    ]
    errors: list[str] = []
    for name in names:
        try:
            org = first_resource(
                session,
                args.base_url,
                "Organization",
                {"name": name, "type": "prov", "active": "true"},
            )
            if org.get("id"):
                return f"Organization/{org['id']}"
        except RuntimeError as exc:
            errors.append(str(exc))
    try:
        org = first_resource(session, args.base_url, "Organization", {"type": "prov", "active": "true"})
        if org.get("id"):
            return f"Organization/{org['id']}"
    except RuntimeError as exc:
        errors.append(str(exc))
    raise RuntimeError("Provider-Organization nicht gefunden: " + " | ".join(errors[:3]))


def practitioner_reference(args: argparse.Namespace, session: requests.Session) -> dict:
    windows_user = args.windows_user.strip().replace("/", "\\")
    if not windows_user:
        return {}
    username = windows_user.rsplit("\\", 1)[-1]
    for params in ({"identifier": windows_user}, {"identifier": username}, {"name": username}):
        try:
            resource = first_resource(session, args.base_url, "Practitioner", params)
            if resource.get("id"):
                return {"reference": f"Practitioner/{resource['id']}", "display": display_name(resource, username)}
        except RuntimeError:
            continue
    return {"display": windows_user}


def display_name(resource: dict, fallback: str) -> str:
    for name in resource.get("name") or []:
        if name.get("text"):
            return " ".join(str(name["text"]).split())
        family = str(name.get("family") or "").strip()
        given = " ".join(str(part).strip() for part in name.get("given") or [] if str(part).strip())
        combined = f"{given} {family}".strip()
        if combined:
            return combined
    return fallback


def expand_document_types(args: argparse.Namespace, session: requests.Session, organization_ref: str) -> list[dict]:
    publisher = organization_ref.removeprefix("Organization/")
    params = {"url": DOCUMENT_TYPE_VALUESET}
    if publisher:
        params["publisher"] = publisher
    response = session.get(f"{args.base_url.rstrip('/')}/ValueSet/$expand", params=params, timeout=60)
    if not response.ok and publisher:
        response = session.get(
            f"{args.base_url.rstrip('/')}/ValueSet/$expand",
            params={"url": DOCUMENT_TYPE_VALUESET},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"ValueSet/$expand fehlgeschlagen: HTTP {response.status_code} {response.text[:800]}")
    resource = response.json()
    resources = [resource]
    if resource.get("resourceType") == "Bundle":
        resources = [(entry.get("resource") or {}) for entry in resource.get("entry") or []]
    result: list[dict] = []
    for item_resource in resources:
        for item in (item_resource.get("expansion") or {}).get("contains") or []:
            if item.get("code") and item.get("display"):
                result.append(
                    {
                        "code": str(item["code"]),
                        "display": str(item["display"]),
                        "system": str(item.get("system") or DOCUMENT_TYPE_SYSTEM),
                    }
                )
    return result


def match_document_type(document_types: list[dict], wanted: str) -> dict:
    normalized = wanted.strip().casefold()
    for item in document_types:
        if item["display"].strip().casefold() == normalized or item["code"].strip().casefold() == normalized:
            return item
    for item in document_types:
        if normalized and normalized in item["display"].strip().casefold():
            return item
    examples = ", ".join(f"{item['code']}={item['display']}" for item in document_types[:12])
    raise RuntimeError(f"Dokumenttyp nicht gefunden: {wanted}. Beispiele: {examples}")


def parse_document_time(value: str) -> str:
    tz = ZoneInfo("Europe/Berlin") if ZoneInfo else datetime.now().astimezone().tzinfo
    if value.strip().lower() in {"", "now-10min", "now"}:
        local_dt = datetime.now(tz) - timedelta(minutes=10)
    else:
        raw = value.strip()
        try:
            local_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
                try:
                    local_dt = datetime.strptime(raw, fmt)
                    if fmt == "%d.%m.%Y":
                        local_dt = local_dt.replace(hour=12)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Unbekanntes Datumsformat: {value}") from None
        if local_dt.tzinfo is None:
            local_dt = local_dt.replace(tzinfo=tz)
    latest_safe = datetime.now(tz) - timedelta(minutes=10)
    if local_dt.astimezone(tz) > latest_safe:
        local_dt = latest_safe
    return local_dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def document_category(content_type: str) -> dict[str, str]:
    code = "Patient Document" if content_type in WORD_CONTENT_TYPES else "TIF"
    return {"system": DOCUMENT_CLASS_SYSTEM, "code": code, "display": code}


def build_document_reference(
    *,
    args: argparse.Namespace,
    patient_ref: str,
    organization_ref: str,
    practitioner_ref: dict,
    document_type: dict,
) -> dict:
    file_path = args.file
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    document_time = parse_document_time(args.document_time)
    extensions = [{"url": DOCUMENT_LOCATION_EXTENSION_URL, "valueString": "file-server"}]
    if args.template_name.strip():
        extensions.insert(0, {"url": TEMPLATE_NAME_EXTENSION_URL, "valueString": args.template_name.strip()})
    if practitioner_ref.get("reference"):
        extensions.append({"url": SUPERVISOR_EXTENSION_URL, "valueReference": practitioner_ref})

    payload = {
        "resourceType": "DocumentReference",
        "extension": extensions,
        "status": "current",
        "docStatus": "preliminary",
        "subject": {"reference": patient_ref},
        "date": document_time,
        "type": {
            "coding": [
                {
                    "system": document_type["system"],
                    "code": document_type["code"],
                    "display": document_type["display"],
                }
            ]
        },
        "category": [{"coding": [document_category(content_type)]}],
        "content": [
            {
                "attachment": {
                    "contentType": content_type,
                    "data": base64.b64encode(file_path.read_bytes()).decode("ascii"),
                    "title": file_path.name,
                    "creation": document_time,
                }
            }
        ],
    }
    if args.preview_text.strip():
        payload["description"] = args.preview_text.strip()
    if organization_ref:
        payload["custodian"] = {"reference": organization_ref}
    if practitioner_ref:
        payload["author"] = [practitioner_ref]
    return payload


def redacted_payload(payload: dict, file_size: int) -> dict:
    copy = deepcopy(payload)
    attachment = copy["content"][0]["attachment"]
    attachment["data"] = f"<base64 redacted, source bytes={file_size}>"
    return copy


def main() -> int:
    load_env()
    args = build_parser().parse_args()
    if not args.base_url:
        raise SystemExit("ARIA_FHIR_BASE_URL fehlt. In .env oder Umgebung setzen.")
    if not args.verify_tls:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if not args.file.is_file():
        raise SystemExit(f"Datei nicht gefunden: {args.file}")

    token, token_meta = request_token(args)
    session = requests.Session()
    session.verify = args.verify_tls
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"})

    patient_ref = patient_reference(args, session)
    organization_ref = organization_reference(args, session)
    practitioner_ref = practitioner_reference(args, session)
    document_types = expand_document_types(args, session, organization_ref)
    document_type = match_document_type(document_types, args.document_type)
    payload = build_document_reference(
        args=args,
        patient_ref=patient_ref,
        organization_ref=organization_ref,
        practitioner_ref=practitioner_ref,
        document_type=document_type,
    )

    post_url = f"{args.base_url.rstrip('/')}/DocumentReference"
    planned = {
        "execute": args.execute,
        "token": token_meta,
        "request": {
            "method": "POST",
            "url": post_url,
            "headers": {
                "Authorization": "Bearer <redacted>",
                "Accept": "application/fhir+json",
                "Content-Type": "application/fhir+json",
            },
            "payload": redacted_payload(payload, args.file.stat().st_size),
        },
    }
    print(json.dumps(planned, ensure_ascii=False, indent=2))

    if not args.execute:
        print("\nDry-run: kein POST ausgefuehrt. Fuer Live-Upload --execute anhaengen.")
        return 0

    response = session.post(
        post_url,
        json=payload,
        headers={"Content-Type": "application/fhir+json"},
        timeout=600,
    )
    result = {
        "http_status": response.status_code,
        "ok": response.ok,
        "location": response.headers.get("Location", ""),
        "body": response.json() if response.text.strip().startswith("{") else response.text[:1000],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if response.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
