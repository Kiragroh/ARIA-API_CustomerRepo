"""
Minimal example: upload one DOCX to ARIA through either interface.

This file is intentionally a demo for sharing with colleagues:
- all secrets are "xxx"
- DRY_RUN is the default
- both interfaces build the same clinical intent:
  patient + document type + template name + DOCX content + document date

FHIR vs. legacy Gateway, in practical ARIA terms:

0. Authentication
   Gateway:
       Windows/SSPI login + ApiKey.
   FHIR:
       OAuth2 client credentials:
       POST /tokenservice/connect/token with client_id, client_secret and scopes.
   Meaning:
       No password or token is hard-coded in this demo. Replace the "xxx" values
       locally, and keep the requested scopes as small as possible.

1. Patient
   Gateway:
       payload["PatientId"]["ID1"] = patient_id
   FHIR:
       GET /Patient?identifier=<patient_id>
       DocumentReference.subject.reference = "Patient/<returned FHIR id>"
   Meaning:
       In FHIR we do not write the local patient number directly into
       DocumentReference.subject. We first resolve it to ARIA's FHIR Patient id.
       If you think in ARIA database terms: the user supplies the visible PatID,
       while the script discovers the internal FHIR Patient reference
       (for example Patient/Patient-9365). That reference is the value written
       into the DocumentReference. You do not manually type a PatientSer here.

2. Institution / provider / publisher
   Gateway:
       No explicit institution lookup is needed in this minimal example.
       The service resolves context from the authenticated user / gateway.
   FHIR:
       GET /Organization?type=prov&active=true
       Optional: add name=<institution name> if your ARIA has several providers.
       The returned Organization id is used as the "publisher" parameter for
       the document-type ValueSet expansion.
   Meaning:
       ARIA FHIR document types are provider/institution-specific. Therefore
       the script discovers the provider Organization and uses its id to ask
       ARIA which document types are valid for that provider.
       If --institution-name is omitted, the first active provider Organization
       is used. If you pass --institution-name, the script filters by
       Organization.name and still writes the Organization id, not the text name.

3. Document type
   Gateway:
       payload["DocumentType"]["DocumentTypeDescription"] = "Arztbriefe (intern)"
   FHIR:
       GET /ValueSet/$expand?url=<documentreference-type>&publisher=<Organization id>
       DocumentReference.type.coding = {system, code, display}
   Meaning:
       FHIR wants the ARIA code, display and CodeSystem URL. The human label
       alone is not enough. The script finds the code by matching display.

4. Template name
   Gateway:
       payload["TemplateName"] = template_name
   FHIR:
       DocumentReference.extension[documentreference-templateName] = template_name
   Meaning:
       Template name is ARIA-specific metadata in FHIR, so it is carried as a
       Varian extension instead of a core FHIR field.

5. Date
   Gateway:
       DateOfService and DateEntered use the old /Date(milliseconds)/ format.
   FHIR:
       DocumentReference.date and content.attachment.creation use FHIR dateTime.
   Meaning:
       Both should represent the letter date, not "now", and must not be in
       the future relative to the ARIA server clock.
       In this local setup, FHIR is sent as a true UTC instant. A Leipzig
       12:00 letter date is therefore sent as 10:00Z in summer time and still
       appears as 12:00 in ARIA. The legacy Gateway example encodes the wanted
       ARIA wall-clock as UTC milliseconds, because otherwise the import can
       appear two hours early.

6. DOCX content
   Gateway:
       FileFormat = 2 and BinaryContent = base64(docx)
   FHIR:
       content.attachment.contentType + data + title
   Meaning:
       Both upload the DOCX bytes as base64, but FHIR uses an Attachment.

7. Approval state
   Gateway:
       Approval depends on the InsertDocumentRequest/user workflow.
   FHIR:
       docStatus = "preliminary" means "not approved / pending" in ARIA.
       A final/approved document would use a different approval workflow and
       ARIA-specific authenticated metadata.

Install for real testing:
    pip install requests requests-negotiate-sspi

Dry run:
    python aria_dual_upload_demo.py --file example.docx --patient 12345 --date 20260519 --method both

Dry run with explicit institution filter:
    python aria_dual_upload_demo.py --file example.docx --patient 12345 --date 20260519 --method fhir --institution-name "MedVZ"

Real upload after filling configuration:
    python aria_dual_upload_demo.py --file example.docx --patient 12345 --date 20260519 --method fhir --execute
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from datetime import datetime, time, timezone
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# Configuration placeholders
# ---------------------------------------------------------------------------

GATEWAY_HOST = "xxx"
GATEWAY_PORT = 55051
GATEWAY_API_KEY = "xxx"
GATEWAY_DOMAIN_USER = r"xxx\\xxx"

FHIR_TOKEN_URL = "https://xxx:44333/tokenservice/connect/token"
FHIR_BASE_URL = "https://xxx:55370/fhir/r4"
FHIR_CLIENT_ID = "xxx"
FHIR_CLIENT_SECRET = "xxx"
FHIR_SCOPE = "system/DocumentReference.cruds system/Patient.rs system/Organization.rs system/ValueSet.rs"

DOCUMENT_TYPE_VALUESET = "http://varian.com/fhir/ValueSet/documentreference-type"
DOCUMENT_LOCATION_EXTENSION = "http://varian.com/fhir/v1/StructureDefinition/documentreference-documentLocation"
TEMPLATE_NAME_EXTENSION = "http://varian.com/fhir/v1/StructureDefinition/documentreference-templateName"


def upload_gateway_docx(
    *,
    file_path: Path,
    patient_id: str,
    date_of_service: str,
    doc_type: str,
    template_name: str,
    execute: bool,
    institution_name: str = "",
) -> dict:
    """Legacy ARIA Gateway upload: SSPI + ApiKey + InsertDocumentRequest."""
    try:
        from requests_negotiate_sspi import HttpNegotiateAuth
    except ModuleNotFoundError:
        HttpNegotiateAuth = None

    payload = {
        "__type": "InsertDocumentRequest:http://services.varian.com/Patient/Documents",
        "PatientId": {"ID1": patient_id},
        "DateOfService": f"/Date({gateway_ms(date_of_service)})/",
        "DateEntered": f"/Date({gateway_ms(date_of_service)})/",
        "BinaryContent": base64.b64encode(file_path.read_bytes()).decode("ascii"),
        "FileFormat": 2,  # DOCX
        "AuthoredByUser": {"SingleUserId": GATEWAY_DOMAIN_USER},
        "SupervisedByUser": {"SingleUserId": GATEWAY_DOMAIN_USER},
        "EnteredByUser": {"SingleUserId": GATEWAY_DOMAIN_USER},
        "TemplateName": template_name,
        "DocumentType": {"DocumentTypeDescription": doc_type},
    }

    url = f"https://{GATEWAY_HOST}:{GATEWAY_PORT}/Gateway/service.svc/interop/rest/Process"
    if not execute:
        return {
            "dry_run": True,
            "interface": "Gateway",
            "url": url,
            "arrives_as": {
                "document_type": doc_type,
                "template_name": template_name,
                "file_format": "DOCX",
                "aria_service_time": gateway_local_display(date_of_service),
                "gateway_payload": f"/Date({gateway_ms(date_of_service)})/",
            },
            "payload_keys": sorted(payload.keys()),
        }
    if HttpNegotiateAuth is None:
        raise RuntimeError("requests-negotiate-sspi is required for Gateway upload.")

    response = requests.post(
        url,
        data=json.dumps(payload),
        headers={"ApiKey": GATEWAY_API_KEY, "Content-Type": "application/json"},
        auth=HttpNegotiateAuth(),
        verify=False,
        timeout=600,
    )
    response.raise_for_status()
    return {"interface": "Gateway", "status_code": response.status_code, "response": response.text[:1000]}


def upload_fhir_docx(
    *,
    file_path: Path,
    patient_id: str,
    date_of_service: str,
    doc_type: str,
    template_name: str,
    institution_name: str,
    execute: bool,
) -> dict:
    """FHIR upload: OAuth token + Patient/Organization search + DocumentReference create."""
    if execute:
        session = fhir_session()
        # 1) Resolve the visible/local patient number to ARIA's FHIR Patient id.
        patient_fhir_id = first_resource_id(session, "Patient", {"identifier": patient_id})

        # 2) Resolve the provider/institution. Its Organization id is needed as
        # the publisher for ARIA's provider-specific document type ValueSet.
        organization_id = organization_publisher_id(session, institution_name)

        # 3) Convert the human document type display to the ARIA FHIR code.
        doc_code, doc_display, doc_system = document_type_code(session, organization_id, doc_type)
    else:
        patient_fhir_id = "Patient-xxx"
        organization_id = "Organization-Prov-xxx"
        doc_code, doc_display, doc_system = "xxx", doc_type, "http://varian.com/fhir/CodeSystem/DocumentReference/documentreference-type"

    doc_ref = document_reference(
        file_path=file_path,
        patient_fhir_id=patient_fhir_id,
        date_of_service=date_of_service,
        doc_code=doc_code,
        doc_display=doc_display,
        doc_system=doc_system,
        template_name=template_name,
    )

    if not execute:
        return {
            "dry_run": True,
            "interface": "FHIR",
            "url": f"{FHIR_BASE_URL}/DocumentReference",
            "arrives_as": {
                "resource": "DocumentReference",
                "patient": f"Patient/{patient_fhir_id}",
                "document_type": f"{doc_display} ({doc_code})",
                "template_name_extension": template_name,
                "doc_status": "preliminary",
                "approved": False,
                "aria_service_time": fhir_local_display(doc_ref["date"]),
                "fhir_utc_date": doc_ref["date"],
            },
            "lookup_plan": {
                "oauth_token": f"POST {FHIR_TOKEN_URL} (client_credentials, scopes from FHIR_SCOPE)",
                "patient_fhir_id": f"GET {FHIR_BASE_URL}/Patient?identifier={patient_id}",
                "institution_publisher": organization_lookup_description(institution_name),
                "document_type_code": (
                    f"GET {FHIR_BASE_URL}/ValueSet/$expand?"
                    f"url={DOCUMENT_TYPE_VALUESET}&publisher={organization_id}"
                ),
                "create_document": f"POST {FHIR_BASE_URL}/DocumentReference",
            },
            "payload_keys": sorted(doc_ref.keys()),
        }

    response = session.post(
        f"{FHIR_BASE_URL}/DocumentReference",
        json=doc_ref,
        headers={"Content-Type": "application/fhir+json"},
        verify=False,
        timeout=600,
    )
    response.raise_for_status()
    body = response.json() if response.text.strip() else {}
    return {
        "interface": "FHIR",
        "status_code": response.status_code,
        "document_reference_id": body.get("id", ""),
        "approved": False,
        "doc_status": "preliminary",
    }


def fhir_session() -> requests.Session:
    response = requests.post(
        FHIR_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": FHIR_CLIENT_ID,
            "client_secret": FHIR_CLIENT_SECRET,
            "scope": FHIR_SCOPE,
        },
        verify=False,
        timeout=60,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"})
    return session


def first_resource_id(session: requests.Session, resource: str, params: dict[str, str]) -> str:
    response = session.get(f"{FHIR_BASE_URL}/{resource}", params=params, verify=False, timeout=60)
    response.raise_for_status()
    entries = response.json().get("entry") or []
    if not entries:
        raise RuntimeError(f"No {resource} found for {params}")
    return entries[0]["resource"]["id"]


def organization_publisher_id(session: requests.Session, institution_name: str = "") -> str:
    """Return the provider Organization id used as publisher for document types."""
    params = {"type": "prov", "active": "true"}
    if institution_name.strip():
        params["name"] = institution_name.strip()
    return first_resource_id(session, "Organization", params)


def organization_lookup_description(institution_name: str = "") -> str:
    params = "type=prov&active=true"
    if institution_name.strip():
        params = f"name={institution_name.strip()}&{params}"
    return f"GET {FHIR_BASE_URL}/Organization?{params}"


def document_type_code(session: requests.Session, publisher: str, doc_type: str) -> tuple[str, str, str]:
    response = session.get(
        f"{FHIR_BASE_URL}/ValueSet/$expand",
        params={"url": DOCUMENT_TYPE_VALUESET, "publisher": publisher},
        verify=False,
        timeout=60,
    )
    response.raise_for_status()
    for entry in response.json().get("entry") or []:
        expansion = entry.get("resource", {}).get("expansion", {})
        for item in expansion.get("contains") or []:
            if item.get("display") == doc_type:
                return item["code"], item["display"], item["system"]
    raise RuntimeError(f"Document type not found in ARIA ValueSet: {doc_type}")


def document_reference(
    *,
    file_path: Path,
    patient_fhir_id: str,
    date_of_service: str,
    doc_code: str,
    doc_display: str,
    doc_system: str,
    template_name: str,
) -> dict:
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    document_date = fhir_datetime(date_of_service)
    return {
        "resourceType": "DocumentReference",
        "extension": [
            {"url": TEMPLATE_NAME_EXTENSION, "valueString": template_name},
            {"url": DOCUMENT_LOCATION_EXTENSION, "valueString": "file-server"},
        ],
        "status": "current",
        "docStatus": "preliminary",  # ARIA shows this as Pending / not approved.
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "date": document_date,
        "description": template_name,
        "type": {"coding": [{"system": doc_system, "code": doc_code, "display": doc_display}]},
        "category": [{"coding": [{"code": "Patient Document", "display": "Patient Document"}]}],
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


def fhir_datetime(yyyymmdd: str) -> str:
    date_value = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    tz = ZoneInfo("Europe/Berlin") if ZoneInfo else datetime.now().astimezone().tzinfo
    local_noon = datetime.combine(date_value, time(12, 0), tzinfo=tz)
    return local_noon.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def gateway_ms(yyyymmdd: str) -> int:
    date_value = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return int(datetime.combine(date_value, time(12, 0), tzinfo=timezone.utc).timestamp() * 1000)


def fhir_local_display(fhir_value: str) -> str:
    tz = ZoneInfo("Europe/Berlin") if ZoneInfo else datetime.now().astimezone().tzinfo
    return datetime.fromisoformat(fhir_value.replace("Z", "+00:00")).astimezone(tz).strftime("%d.%m.%Y %H:%M:%S")


def gateway_local_display(yyyymmdd: str) -> str:
    date_value = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return datetime.combine(date_value, time(12, 0)).strftime("%d.%m.%Y %H:%M:%S")


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo for ARIA Gateway and ARIA FHIR DOCX uploads.")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--doc-type", default="Arztbriefe (intern)")
    parser.add_argument("--template", default="Abschlussbrief Beispiel")
    parser.add_argument("--method", choices=["gateway", "fhir", "both"], default="both")
    parser.add_argument(
        "--institution-name",
        default="",
        help="Optional FHIR Organization.name filter. If omitted, the first active provider Organization is used.",
    )
    parser.add_argument("--execute", action="store_true", help="Actually upload. Default is dry run.")
    args = parser.parse_args()

    methods = ["gateway", "fhir"] if args.method == "both" else [args.method]
    results = []
    for method in methods:
        fn = upload_gateway_docx if method == "gateway" else upload_fhir_docx
        results.append(
            fn(
                file_path=args.file,
                patient_id=args.patient,
                date_of_service=args.date,
                doc_type=args.doc_type,
                template_name=args.template,
                institution_name=args.institution_name,
                execute=args.execute,
            )
        )
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
