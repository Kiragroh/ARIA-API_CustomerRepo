from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urljoin, urlparse

import requests

TASK_PROFILE = "http://varian.com/fhir/v1/StructureDefinition/Task"
TASK_CATEGORY_SYSTEM = "http://varian.com/fhir/CodeSystem/activityDefinition-category"
TASK_DURATION_URL = "http://varian.com/fhir/v1/StructureDefinition/task-minutesDuration"
TASK_DURATION_SYSTEM = "http://unitsofmeasure.org"
ONCOLOGY_ROLES = {"oncologist", "primary-oncologist"}
DEFAULT_IDENTIFIER_SYSTEM = "urn:example:aria-fhir-task-trigger:v1"
DEFAULT_SCOPES = (
    "system/Patient.rs",
    "system/Practitioner.rs",
    "system/ActivityDefinition.rs",
    "system/CareTeam.rs",
    "system/Group.rs",
    "system/Task.rs",
    "system/Task.cruds",
)


class FhirExampleError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    token_url: str
    base_url: str
    client_id: str
    client_secret: str
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    verify: bool | str = True


@dataclass(frozen=True)
class OncologyRouting:
    recipients: tuple[str, ...]
    owner: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowRequest:
    patient_identifier: str
    activity_name: str
    trigger_id: str
    group_name: str
    identifier_system: str
    note: str
    duration_minutes: int
    execute: bool


def derive_urls(platform: str) -> tuple[str, str]:
    host = platform.strip()
    if not host:
        raise FhirExampleError("VARIAN_PLATFORM or explicit URLs are required")
    return (
        f"https://{host}:44333/tokenservice/connect/token",
        f"https://{host}:55370/fhir/r4",
    )


def operation_outcome_message(response) -> str:
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        return f"HTTP {response.status_code}"
    if not isinstance(body, dict) or body.get("resourceType") != "OperationOutcome":
        return f"HTTP {response.status_code}"
    parts = []
    for issue in body.get("issue", [])[:5]:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get("code") or "unknown")
        severity = str(issue.get("severity") or "unknown")
        parts.append(f"{severity}:{code}")
    suffix = ", ".join(parts) if parts else "unknown:unknown"
    return f"HTTP {response.status_code} OperationOutcome {suffix}"


class FhirClient:
    def __init__(self, settings: Settings, session=None):
        if settings.verify is False:
            raise FhirExampleError("TLS certificate verification cannot be disabled")
        self.settings = settings
        self.session = session or requests.Session()
        self.session.verify = settings.verify
        self.session.headers.update({"Accept": "application/fhir+json"})

    def _raise(self, response) -> None:
        if not response.ok:
            raise FhirExampleError(operation_outcome_message(response))

    def authenticate(self) -> None:
        response = self.session.post(
            self.settings.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "scope": " ".join(self.settings.scopes),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )
        self._raise(response)
        body = response.json()
        token = str(body.get("access_token") or "")
        granted_scopes = set(str(body.get("scope") or "").split())
        missing = sorted(set(self.settings.scopes) - granted_scopes)
        if not token or missing:
            raise FhirExampleError("Token or required scopes missing: " + ",".join(missing))
        self.session.headers["Authorization"] = f"Bearer {token}"

    def _url(self, resource: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/{resource.lstrip('/')}"

    def _same_origin(self, url: str) -> str:
        absolute = urljoin(self.settings.base_url.rstrip("/") + "/", url)
        base = urlparse(self.settings.base_url)
        target = urlparse(absolute)
        if (target.scheme, target.netloc) != (base.scheme, base.netloc):
            raise FhirExampleError("Cross-origin pagination link rejected")
        return absolute

    def search(self, resource: str, params: dict[str, str]) -> list[dict]:
        response = self.session.get(self._url(resource), params=params, timeout=60)
        self._raise(response)
        body = response.json()
        resources: list[dict] = []
        while True:
            resources.extend(
                entry["resource"]
                for entry in body.get("entry", [])
                if isinstance(entry, dict) and isinstance(entry.get("resource"), dict)
            )
            next_url = next((
                link.get("url")
                for link in body.get("link", [])
                if isinstance(link, dict) and link.get("relation") == "next"
            ), None)
            if not next_url:
                return resources
            response = self.session.get(self._same_origin(str(next_url)), timeout=60)
            self._raise(response)
            body = response.json()

    def read(self, reference: str) -> dict:
        response = self.session.get(self._url(reference), timeout=60)
        self._raise(response)
        return response.json()

    def find_tasks(self, identifier_system: str, identifier_value: str) -> list[dict]:
        return self.search("Task", {
            "identifier": f"{identifier_system}|{identifier_value}",
            "_count": "3",
        })

    def create_task(self, payload: dict) -> dict:
        response = self.session.post(
            self._url("Task"),
            json=payload,
            headers={"Content-Type": "application/fhir+json"},
            timeout=60,
        )
        self._raise(response)
        return response.json() if response.content else {}

    def resolve_patient(self, patient_identifier: str) -> dict:
        matches = self.search("Patient", {"identifier": patient_identifier, "_count": "2"})
        if len(matches) != 1:
            raise FhirExampleError("Patient lookup must return exactly one match")
        return matches[0]

    def resolve_activity_and_group(self, activity_name: str, group_name: str) -> tuple[dict, dict]:
        matches = [
            item for item in self.search("ActivityDefinition", {
                "name": activity_name,
                "status": "active",
                "kind": "Task",
                "_count": "3",
            })
            if item.get("name") == activity_name
            and item.get("status") == "active"
            and item.get("kind") == "Task"
        ]
        if len(matches) != 1:
            raise FhirExampleError("ActivityDefinition lookup must return exactly one active Task")
        reference = str(matches[0].get("subjectReference", {}).get("reference") or "")
        if not reference.startswith("Group/"):
            raise FhirExampleError("ActivityDefinition.subjectReference must reference Group")
        group = self.read(reference)
        if group.get("active") is not True or group.get("name") != group_name:
            raise FhirExampleError("ActivityDefinition does not reference the expected active Group")
        return matches[0], group

    def resolve_routing(self, patient_reference: str) -> OncologyRouting:
        teams = self.search("CareTeam", {"patient": patient_reference, "_count": "100"})
        references = {
            str(participant.get("member", {}).get("reference") or "")
            for team in teams
            if team.get("status") == "active"
            for participant in team.get("participant", [])
            if str(participant.get("member", {}).get("reference") or "").startswith("Practitioner/")
        }
        practitioners: dict[str, dict] = {}
        for reference in sorted(references):
            try:
                practitioners[reference] = self.read(reference)
            except FhirExampleError:
                practitioners[reference] = {"active": False}
        return resolve_oncology_routing(teams, practitioners)


def workflow_value(trigger_id: str) -> str:
    normalized = trigger_id.strip()
    if not normalized:
        raise ValueError("trigger_id must not be empty")
    return hashlib.sha256(f"v1|{normalized}".encode("utf-8")).hexdigest()


def _role_codes(participant: dict) -> set[str]:
    return {
        str(coding.get("code"))
        for role in participant.get("role", [])
        for coding in role.get("coding", [])
        if coding.get("code")
    }


def resolve_oncology_routing(
    care_teams: list[dict],
    practitioners_by_reference: dict[str, dict],
) -> OncologyRouting:
    recipients: set[str] = set()
    primary: set[str] = set()
    warnings: set[str] = set()
    for team in care_teams:
        if team.get("status") != "active":
            continue
        for participant in team.get("participant", []):
            roles = _role_codes(participant)
            reference = str(participant.get("member", {}).get("reference") or "")
            if not roles.intersection(ONCOLOGY_ROLES) or not reference.startswith("Practitioner/"):
                continue
            practitioner = practitioners_by_reference.get(reference)
            if practitioner is None or practitioner.get("active") is not True:
                warnings.add("inactive_or_unreadable_oncologist")
                continue
            recipients.add(reference)
            if "primary-oncologist" in roles:
                primary.add(reference)
    if len(primary) > 1:
        warnings.add("multiple_primary_oncologists")
    owner = next(iter(primary)) if len(primary) == 1 else None
    return OncologyRouting(tuple(sorted(recipients)), owner, tuple(sorted(warnings)))


def build_task_payload(
    *,
    patient_reference: str,
    activity_reference: str,
    group_reference: str,
    group_name: str,
    routing: OncologyRouting,
    identifier_system: str,
    identifier_value: str,
    authored_on: datetime,
    duration_minutes: int,
    note: str,
) -> dict:
    recipients = sorted({group_reference, *routing.recipients})
    payload = {
        "resourceType": "Task",
        "meta": {"profile": [TASK_PROFILE]},
        "identifier": [{"system": identifier_system, "value": identifier_value}],
        "extension": [{
            "url": TASK_DURATION_URL,
            "valueQuantity": {
                "value": duration_minutes,
                "unit": "Minutes",
                "system": TASK_DURATION_SYSTEM,
                "code": "Minutes",
            },
        }],
        "status": "ready",
        "intent": "order",
        "priority": "routine",
        "code": {"coding": [{
            "system": TASK_CATEGORY_SYSTEM,
            "code": group_name,
            "display": group_name,
        }]},
        "focus": {"reference": activity_reference},
        "for": {"reference": patient_reference},
        "authoredOn": authored_on.isoformat(),
        "restriction": {
            "period": {"end": (authored_on + timedelta(minutes=duration_minutes)).isoformat()},
            "recipient": [{"reference": reference} for reference in recipients],
        },
    }
    if note.strip():
        payload["note"] = [{"text": note.strip()}]
    if routing.owner:
        payload["owner"] = {"reference": routing.owner}
    return payload


def redacted_payload(payload: dict) -> dict:
    copy = json.loads(json.dumps(payload))
    copy["for"]["reference"] = "Patient/<redacted>"
    if "owner" in copy:
        copy["owner"]["reference"] = "Practitioner/<redacted>"
    for recipient in copy.get("restriction", {}).get("recipient", []):
        kind = str(recipient.get("reference") or "Reference").split("/", 1)[0]
        recipient["reference"] = f"{kind}/<redacted>"
    for note in copy.get("note", []):
        if isinstance(note, dict) and "text" in note:
            note["text"] = "<redacted>"
    copy["identifier"][0]["value"] = "<sha256>"
    return copy


def verify_task_readback(actual: dict, expected: dict) -> None:
    if actual.get("status") not in {"ready", "in-progress"}:
        raise FhirExampleError("Task read-back has unexpected status")
    for field in ("focus", "for", "owner"):
        if actual.get(field, {}).get("reference") != expected.get(field, {}).get("reference"):
            raise FhirExampleError(f"Task read-back differs at {field}")
    expected_recipients = {
        item.get("reference") for item in expected.get("restriction", {}).get("recipient", [])
    }
    actual_recipients = {
        item.get("reference") for item in actual.get("restriction", {}).get("recipient", [])
    }
    if not expected_recipients.issubset(actual_recipients):
        raise FhirExampleError("Task read-back is missing recipients")
    expected_identifiers = {
        (item.get("system"), item.get("value")) for item in expected.get("identifier", [])
    }
    actual_identifiers = {
        (item.get("system"), item.get("value")) for item in actual.get("identifier", [])
    }
    if not expected_identifiers.issubset(actual_identifiers):
        raise FhirExampleError("Task read-back is missing the workflow identifier")


def run_workflow(client: FhirClient, request: WorkflowRequest, now_fn=datetime.now) -> dict:
    patient = client.resolve_patient(request.patient_identifier)
    patient_reference = f"Patient/{patient['id']}"
    activity, group = client.resolve_activity_and_group(request.activity_name, request.group_name)
    routing = client.resolve_routing(patient_reference)
    identifier_value = workflow_value(request.trigger_id)
    authored_on = now_fn().astimezone()
    payload = build_task_payload(
        patient_reference=patient_reference,
        activity_reference=f"ActivityDefinition/{activity['id']}",
        group_reference=f"Group/{group['id']}",
        group_name=request.group_name,
        routing=routing,
        identifier_system=request.identifier_system,
        identifier_value=identifier_value,
        authored_on=authored_on,
        duration_minutes=request.duration_minutes,
        note=request.note,
    )
    existing = client.find_tasks(request.identifier_system, identifier_value)
    if len(existing) > 1:
        raise FhirExampleError("Multiple Tasks use the same workflow identifier")
    if len(existing) == 1:
        verify_task_readback(existing[0], payload)
        return {"status": "already_exists", "request": redacted_payload(payload)}
    if not request.execute:
        return {"status": "dry_run", "request": redacted_payload(payload)}
    try:
        created = client.create_task(payload)
    except requests.RequestException:
        reconciled = client.find_tasks(request.identifier_system, identifier_value)
        if len(reconciled) != 1:
            raise FhirExampleError("Task POST outcome is uncertain; no retry was attempted")
        created = reconciled[0]
    if created.get("id"):
        created = client.read(f"Task/{created['id']}")
    else:
        reconciled = client.find_tasks(request.identifier_system, identifier_value)
        if len(reconciled) != 1:
            raise FhirExampleError("Task POST returned no readable Task; no retry was attempted")
        created = reconciled[0]
    verify_task_readback(created, payload)
    return {"status": "created", "request": redacted_payload(payload)}


def load_env() -> None:
    root = Path(__file__).resolve().parents[2]
    for env_file in (root / ".env", Path.cwd() / ".env"):
        if not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an idempotent ARIA FHIR Task from any external trigger."
    )
    parser.add_argument("--patient-identifier", required=True)
    parser.add_argument("--activity-name", required=True)
    parser.add_argument("--trigger-id", required=True)
    parser.add_argument("--group-name", default="Arzt")
    parser.add_argument("--identifier-system", default=DEFAULT_IDENTIFIER_SYSTEM)
    parser.add_argument("--note", default="Automatically created by an external workflow.")
    parser.add_argument("--duration-minutes", type=int, default=10)
    parser.add_argument("--token-url", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--ca-bundle", default="")
    parser.add_argument("--execute", action="store_true")
    return parser


def settings_from_environment(
    env=os.environ,
    *,
    token_url_override: str = "",
    base_url_override: str = "",
    ca_bundle_override: str = "",
) -> Settings:
    platform = str(env.get("VARIAN_PLATFORM") or "").strip()
    derived_token, derived_base = derive_urls(platform) if platform else ("", "")
    token_url = str(token_url_override or env.get("ARIA_FHIR_TOKEN_URL") or derived_token).strip()
    base_url = str(base_url_override or env.get("ARIA_FHIR_BASE_URL") or derived_base).strip()
    client_id = str(env.get("ARIA_FHIR_CLIENT_ID") or "").strip()
    client_secret = str(env.get("ARIA_FHIR_CLIENT_SECRET") or "").strip()
    ca_bundle = str(ca_bundle_override or env.get("ARIA_FHIR_CA_BUNDLE") or "").strip()
    if not token_url or not base_url or not client_id or not client_secret:
        raise FhirExampleError("FHIR URLs, client ID, and client secret are required")
    if any(urlparse(url).scheme.lower() != "https" or not urlparse(url).netloc for url in (token_url, base_url)):
        raise FhirExampleError("FHIR token and base URLs must use HTTPS")
    return Settings(
        token_url=token_url,
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        scopes=DEFAULT_SCOPES,
        verify=ca_bundle or True,
    )


def main(argv=None) -> int:
    load_env()
    args = build_parser().parse_args(argv)
    if args.duration_minutes <= 0:
        raise SystemExit("--duration-minutes must be positive")
    try:
        settings = settings_from_environment(
            token_url_override=args.token_url,
            base_url_override=args.base_url,
            ca_bundle_override=args.ca_bundle,
        )
        client = FhirClient(settings)
        client.authenticate()
        result = run_workflow(client, WorkflowRequest(
            patient_identifier=args.patient_identifier,
            activity_name=args.activity_name,
            trigger_id=args.trigger_id,
            group_name=args.group_name,
            identifier_system=args.identifier_system,
            note=args.note,
            duration_minutes=args.duration_minutes,
            execute=args.execute,
        ))
    except requests.RequestException:
        print("FHIR request failed; response details were suppressed.", file=sys.stderr)
        return 2
    except FhirExampleError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "dry_run":
        print("\nDry-run: no Task POST was performed. Add --execute for a live write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
