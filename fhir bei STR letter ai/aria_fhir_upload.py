from __future__ import annotations

import base64
import mimetypes
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

import requests
import urllib3

from .text_utils import clean_ws
from .aria_upload import ARIA_DOMAIN, ARIA_USER, parse_date_of_service_value

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


FHIR_TOKEN_URL = os.getenv(
    "ARIA_FHIR_TOKEN_URL",
    "",
)
FHIR_BASE_URL = os.getenv("ARIA_FHIR_BASE_URL", "")
FHIR_CLIENT_ID = os.getenv("ARIA_FHIR_CLIENT_ID", "")
FHIR_CLIENT_SECRET = os.getenv("ARIA_FHIR_CLIENT_SECRET", "")
FHIR_SCOPE = os.getenv(
    "ARIA_FHIR_SCOPE",
    "system/DocumentReference.cruds system/Patient.rs system/Organization.rs system/ValueSet.rs system/Practitioner.rs",
)
FHIR_ORGANIZATION_NAMES = tuple(
    name.strip()
    for name in os.getenv(
        "ARIA_FHIR_ORGANIZATION_NAMES",
        "Uniklinikum Leipzig;Leipzig;MedVZ;Universitätsklinikum Leipzig;Universitaetsklinikum Leipzig",
    ).split(";")
    if name.strip()
)

DOCUMENT_TYPE_SYSTEM = "http://varian.com/fhir/CodeSystem/DocumentReference/documentreference-type"
DOCUMENT_TYPE_VALUESET = "http://varian.com/fhir/ValueSet/documentreference-type"
DOCUMENT_CLASS_SYSTEM = "http://varian.com/fhir/CodeSystem/DocumentReference/documentreference-class"
TEMPLATE_NAME_EXTENSION_URL = "http://varian.com/fhir/v1/StructureDefinition/documentreference-templateName"
DOCUMENT_LOCATION_EXTENSION_URL = "http://varian.com/fhir/v1/StructureDefinition/documentreference-documentLocation"
SUPERVISOR_EXTENSION_URL = "http://varian.com/fhir/v1/StructureDefinition/documentreference-supervisor"
WORD_CONTENT_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def upload_docx_to_aria_fhir(
    *,
    file_path: Path,
    patient_id: str,
    date_of_service: str,
    doc_type: str,
    template_name: str,
) -> dict:
    file_path = Path(file_path)
    if not file_path.is_file():
        raise RuntimeError(f"DOCX nicht gefunden: {file_path}")
    if not FHIR_BASE_URL:
        raise RuntimeError("ARIA_FHIR_BASE_URL fehlt. Lokal per Umgebung oder .env setzen.")
    patient_id = clean_ws(patient_id).replace(" ", "")
    if not patient_id:
        raise RuntimeError("Patienten-ID fuer ARIA-FHIR-Upload fehlt.")

    session = _fhir_session()
    patient_fhir_id = _patient_fhir_id(session, patient_id)
    organization_id, organization_note = _best_organization_id(session)
    user_reference, user_note, windows_user = _windows_user_reference(session)
    document_types = _valid_document_types(session, organization_id)
    doc_match = _document_type_match(document_types, doc_type)
    if not doc_match:
        examples = ", ".join(
            f"{item.get('code')}={item.get('display')}" for item in document_types[:12]
        )
        raise RuntimeError(
            f"Dokumenttyp '{doc_type}' ist im ARIA-FHIR-ValueSet nicht vorhanden. "
            f"Publisher={organization_id or '(leer)'}. Beispiele: {examples}"
        )
    doc_ref = _document_reference(
        patient_fhir_id=patient_fhir_id,
        file_path=file_path,
        date_of_service=date_of_service,
        doc_code=doc_match["code"],
        doc_system=doc_match.get("system") or DOCUMENT_TYPE_SYSTEM,
        doc_type=doc_match.get("display") or doc_type,
        template_name=template_name,
        description=template_name or file_path.name,
        user_reference=user_reference,
        custodian_reference=_organization_reference(organization_id),
    )

    response = session.post(
        f"{FHIR_BASE_URL}/DocumentReference",
        json=doc_ref,
        headers={"Content-Type": "application/fhir+json"},
        timeout=600,
        verify=False,
    )
    if response.ok:
        payload = response.json() if response.text.strip() else {}
        document_reference_id = payload.get("id", "") or _id_from_location_header(response.headers.get("Location", ""))
        fhir_document_date = doc_ref.get("date", "")
        return {
            "ok": True,
            "interface": "FHIR",
            "status_code": response.status_code,
            "patient_id": patient_id,
            "patient_fhir_id": patient_fhir_id,
            "organization_fhir_id": organization_id,
            "organization_note": organization_note,
            "windows_user": windows_user,
            "fhir_author_reference": user_reference.get("reference", "") if user_reference else "",
            "fhir_author_display": user_reference.get("display", "") if user_reference else "",
            "fhir_user_note": user_note,
            "fhir_custodian_reference": doc_ref.get("custodian", {}).get("reference", ""),
            "document_reference_id": document_reference_id,
            "date_of_service": date_of_service,
            "fhir_document_date": fhir_document_date,
            "fhir_document_date_local": _fhir_local_display(fhir_document_date),
            "fhir_document_date_note": "FHIR sendet UTC; ARIA zeigt die lokale Europe/Berlin-Zeit",
            "fhir_doc_status": doc_ref.get("docStatus", ""),
            "aria_status": "Pending / nicht genehmigt",
            "approved": False,
            "doc_type": doc_match.get("display") or doc_type,
            "doc_code": doc_match["code"],
            "doc_system": doc_match.get("system") or DOCUMENT_TYPE_SYSTEM,
            "template_name": template_name,
            "filename": file_path.name,
        }
    snippet = (response.text or "")[:1000].strip()
    raise RuntimeError(f"ARIA-FHIR-Upload fehlgeschlagen: HTTP {response.status_code}. {snippet}")


def _id_from_location_header(location: str) -> str:
    if not location:
        return ""
    return location.rstrip("/").rsplit("/", 1)[-1]


def _fhir_session() -> requests.Session:
    if not FHIR_TOKEN_URL:
        raise RuntimeError("ARIA_FHIR_TOKEN_URL fehlt. Lokal per Umgebung oder .env setzen.")
    if not FHIR_CLIENT_ID:
        raise RuntimeError("ARIA_FHIR_CLIENT_ID fehlt. Lokal per Umgebung oder .env setzen.")
    if not FHIR_CLIENT_SECRET:
        raise RuntimeError("ARIA_FHIR_CLIENT_SECRET fehlt. Lokal per Umgebung oder .env setzen.")
    errors: list[str] = []
    for scope in _fhir_scope_candidates():
        response = requests.post(
            FHIR_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": FHIR_CLIENT_ID,
                "client_secret": FHIR_CLIENT_SECRET,
                "scope": scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
            verify=False,
        )
        if response.ok:
            token = response.json().get("access_token")
            if not token:
                raise RuntimeError("FHIR-Tokenantwort enthaelt kein access_token.")

            session = requests.Session()
            session.headers.update(
                {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/fhir+json",
                }
            )
            session.aria_fhir_scope = scope
            return session
        snippet = (response.text or "")[:1000].strip()
        errors.append(f"HTTP {response.status_code}. {snippet}")
    raise RuntimeError(f"FHIR-Token konnte nicht geholt werden: {' | '.join(errors)}")


def _fhir_scope_candidates() -> list[str]:
    scopes = [scope for scope in FHIR_SCOPE.split() if scope]
    joined = " ".join(scopes)
    candidates = [joined]
    practitioner_scope = "system/Practitioner.rs"
    if practitioner_scope in scopes:
        fallback = " ".join(scope for scope in scopes if scope != practitioner_scope)
        if fallback:
            candidates.append(fallback)
    return list(dict.fromkeys(candidates))


def _patient_fhir_id(session: requests.Session, patient_id: str) -> str:
    try:
        return _search_first_resource_id(session, "Patient", {"identifier": patient_id})
    except RuntimeError:
        if patient_id.startswith("Patient-"):
            response = session.get(f"{FHIR_BASE_URL}/Patient/{patient_id}", timeout=60, verify=False)
            if response.ok:
                return patient_id
        raise


def _best_organization_id(session: requests.Session) -> tuple[str, str]:
    errors: list[str] = []
    for name in FHIR_ORGANIZATION_NAMES:
        try:
            organization_id = _search_first_resource_id(
                session,
                "Organization",
                {"name": name, "type": "prov", "active": "true"},
            )
            return organization_id, f"Organization gesucht mit name={name}"
        except RuntimeError as exc:
            errors.append(f"{name}: {exc}")
    try:
        organization_id = _search_first_resource_id(
            session,
            "Organization",
            {"type": "prov", "active": "true"},
        )
        return organization_id, "Organization gesucht mit type=prov, active=true"
    except RuntimeError as exc:
        errors.append(f"prov active fallback: {exc}")
    return "", "; ".join(errors)


def _search_first_resource(session: requests.Session, profile: str, search: dict[str, str]) -> dict:
    params = {**search, "_pretty": "true"}
    response = session.get(f"{FHIR_BASE_URL}/{profile}", params=params, timeout=60, verify=False)
    if not response.ok:
        snippet = (response.text or "")[:600].strip()
        raise RuntimeError(f"{profile}-Suche fehlgeschlagen: HTTP {response.status_code}. {snippet}")
    payload = response.json()
    entries = payload.get("entry") or []
    if not entries:
        raise RuntimeError(f"{profile}-Suche ohne Treffer fuer {search}.")
    resource = entries[0].get("resource") or {}
    if not resource:
        raise RuntimeError(f"{profile}-Treffer ohne resource.")
    return resource


def _search_first_resource_id(session: requests.Session, profile: str, search: dict[str, str]) -> str:
    resource = _search_first_resource(session, profile, search)
    resource_id = resource.get("id")
    if not resource_id:
        raise RuntimeError(f"{profile}-Treffer ohne id.")
    return resource_id


def _organization_reference(organization_id: str) -> dict:
    if not organization_id:
        return {}
    return {"reference": f"Organization/{organization_id}"}


def _windows_domain_user() -> str:
    user = clean_ws(
        os.getenv("ARIA_USER")
        or os.getenv("ARIA_FHIR_WINDOWS_USER")
        or os.getenv("USERNAME")
        or ARIA_USER
    ).replace("/", "\\")
    if "\\" in user:
        parts = [part.strip() for part in user.split("\\") if part.strip()]
        if len(parts) >= 2:
            return f"{parts[-2]}\\{parts[-1]}"
        return parts[0] if parts else ""
    domain = clean_ws(
        os.getenv("ARIA_DOMAIN")
        or os.getenv("ARIA_FHIR_WINDOWS_DOMAIN")
        or os.getenv("USERDOMAIN")
        or ARIA_DOMAIN
    )
    if domain and user:
        return f"{domain}\\{user}"
    return user


def _windows_username(domain_user: str) -> str:
    value = clean_ws(domain_user).replace("/", "\\")
    return value.rsplit("\\", 1)[-1] if "\\" in value else value


def _windows_user_reference(session: requests.Session | None) -> tuple[dict, str, str]:
    windows_user = _windows_domain_user()
    if not windows_user:
        return {}, "Windows-User nicht ermittelbar.", ""

    username = _windows_username(windows_user)
    explicit_reference = clean_ws(os.getenv("ARIA_FHIR_PRACTITIONER_REFERENCE") or "")
    if explicit_reference:
        reference = explicit_reference
        if not reference.startswith("Practitioner/"):
            reference = f"Practitioner/{reference}"
        return (
            {"reference": reference, "display": username or windows_user},
            "Practitioner aus ARIA_FHIR_PRACTITIONER_REFERENCE gesetzt.",
            windows_user,
        )

    if session:
        errors: list[str] = []
        for search in _windows_user_practitioner_searches(windows_user):
            try:
                resource = _search_first_resource(session, "Practitioner", search)
                resource_id = clean_ws(resource.get("id", ""))
                if not resource_id:
                    raise RuntimeError("Practitioner-Treffer ohne id.")
                display = _practitioner_display(resource, username or windows_user)
                return (
                    {"reference": f"Practitioner/{resource_id}", "display": display},
                    f"Practitioner gesucht mit {search}.",
                    windows_user,
                )
            except RuntimeError as exc:
                errors.append(f"{search}: {exc}")

    return (
        {"display": windows_user},
        "Practitioner nicht aufgeloest; Windows-User nur als FHIR-Reference-Display gesetzt.",
        windows_user,
    )


def _windows_user_practitioner_searches(windows_user: str) -> list[dict[str, str]]:
    username = _windows_username(windows_user)
    candidates = [
        {"identifier": windows_user},
        {"identifier": username},
        {"name": username},
    ]
    if username != windows_user:
        candidates.append({"name": windows_user})
    return [candidate for candidate in candidates if next(iter(candidate.values()), "")]


def _practitioner_display(resource: dict, fallback: str) -> str:
    for name in resource.get("name") or []:
        text = clean_ws(name.get("text", ""))
        if text:
            return text
        family = clean_ws(name.get("family", ""))
        given = " ".join(clean_ws(item) for item in name.get("given") or [] if clean_ws(item))
        combined = clean_ws(f"{given} {family}")
        if combined:
            return combined
    return fallback


def _valid_document_types(session: requests.Session, publisher: str) -> list[dict[str, str]]:
    params = {"url": DOCUMENT_TYPE_VALUESET}
    if publisher:
        params["publisher"] = publisher
    response = session.get(f"{FHIR_BASE_URL}/ValueSet/$expand", params=params, timeout=60, verify=False)
    if not response.ok and publisher:
        response = session.get(
            f"{FHIR_BASE_URL}/ValueSet/$expand",
            params={"url": DOCUMENT_TYPE_VALUESET},
            timeout=60,
            verify=False,
        )
    if not response.ok:
        return []
    payload = response.json()
    resources = [payload]
    if payload.get("resourceType") == "Bundle":
        resources = [(entry.get("resource") or {}) for entry in payload.get("entry") or []]
    document_types: list[dict[str, str]] = []
    for resource in resources:
        expansion = resource.get("expansion") or {}
        for item in expansion.get("contains") or []:
            code = str(item.get("code") or "")
            display = str(item.get("display") or "")
            if code and display:
                document_types.append(
                    {
                        "code": code,
                        "display": display,
                        "system": str(item.get("system") or DOCUMENT_TYPE_SYSTEM),
                    }
                )
    return document_types


def _document_type_match(document_types: list[dict[str, str]], doc_type: str) -> dict[str, str]:
    wanted = clean_ws(doc_type).casefold()
    for item in document_types:
        if clean_ws(item.get("display", "")).casefold() == wanted:
            return item
    for item in document_types:
        if wanted and wanted in clean_ws(item.get("display", "")).casefold():
            return item
    return {}


def _document_reference(
    *,
    patient_fhir_id: str,
    file_path: Path,
    date_of_service: str,
    doc_code: str,
    doc_system: str,
    doc_type: str,
    template_name: str,
    description: str,
    user_reference: dict | None = None,
    custodian_reference: dict | None = None,
) -> dict:
    content_type = (
        mimetypes.guess_type(file_path.name)[0]
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document_date = _fhir_document_datetime(date_of_service)
    doc_ref = {
        "resourceType": "DocumentReference",
        "extension": _document_reference_extensions(template_name, user_reference),
        "status": "current",
        "docStatus": "preliminary",
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "date": document_date,
        "description": description or file_path.name,
        "type": {
            "coding": [
                {
                    "system": doc_system,
                    "code": doc_code,
                    "display": doc_type,
                }
            ]
        },
        "category": [
            {
                "coding": [
                    _document_reference_category(content_type)
                ]
            }
        ],
        "content": [
            {
                "attachment": {
                    "contentType": content_type,
                    "data": base64.b64encode(file_path.read_bytes()).decode("ascii"),
                    "title": file_path.name,
                    "creation": document_date,
                }
            }
        ],
    }
    if user_reference:
        doc_ref["author"] = [dict(user_reference)]
    if custodian_reference:
        doc_ref["custodian"] = dict(custodian_reference)
    return doc_ref


def _document_reference_category(content_type: str) -> dict[str, str]:
    code = "Patient Document" if content_type in WORD_CONTENT_TYPES else "TIF"
    return {
        "system": DOCUMENT_CLASS_SYSTEM,
        "code": code,
        "display": code,
    }


def _document_reference_extensions(template_name: str, user_reference: dict | None = None) -> list[dict]:
    extensions = [
        {
            "url": DOCUMENT_LOCATION_EXTENSION_URL,
            "valueString": "file-server",
        }
    ]
    if user_reference and user_reference.get("reference"):
        extensions.append(
            {
                "url": SUPERVISOR_EXTENSION_URL,
                "valueReference": dict(user_reference),
            }
        )
    cleaned = clean_ws(template_name)
    if cleaned:
        extensions.insert(
            0,
            {
                "url": TEMPLATE_NAME_EXTENSION_URL,
                "valueString": cleaned,
            },
        )
    return extensions


def _fhir_document_datetime(date_of_service: str) -> str:
    tz = ZoneInfo("Europe/Berlin") if ZoneInfo else datetime.now().astimezone().tzinfo
    requested_raw, explicit_time = parse_date_of_service_value(date_of_service, error_context="ARIA-FHIR-Upload")
    requested = requested_raw.date()
    now = datetime.now(tz)
    if requested > now.date():
        raise RuntimeError(
            f"Briefdatum {requested.strftime('%d.%m.%Y')} liegt in der Zukunft; "
            "ARIA-FHIR akzeptiert keine zukuenftigen Dokumentdaten."
        )
    if explicit_time:
        target = requested_raw.replace(second=0, microsecond=0, tzinfo=tz)
        latest_safe = now - timedelta(minutes=10)
        if target > latest_safe:
            target = latest_safe.replace(second=0, microsecond=0)
    elif requested == now.date():
        target = now - timedelta(minutes=10)
    else:
        target = datetime.combine(requested, time(12, 0), tzinfo=tz)
    return target.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _fhir_local_display(fhir_datetime: str) -> str:
    if not fhir_datetime:
        return ""
    try:
        value = datetime.fromisoformat(fhir_datetime.replace("Z", "+00:00"))
    except ValueError:
        return fhir_datetime
    tz = ZoneInfo("Europe/Berlin") if ZoneInfo else datetime.now().astimezone().tzinfo
    return value.astimezone(tz).strftime("%d.%m.%Y %H:%M:%S")
