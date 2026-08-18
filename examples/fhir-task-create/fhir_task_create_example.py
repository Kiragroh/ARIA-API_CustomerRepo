from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from urllib.parse import urljoin, urlparse

import requests

TASK_PROFILE = "http://varian.com/fhir/v1/StructureDefinition/Task"
TASK_CATEGORY_SYSTEM = "http://varian.com/fhir/CodeSystem/activityDefinition-category"
TASK_DURATION_URL = "http://varian.com/fhir/v1/StructureDefinition/task-minutesDuration"
TASK_DURATION_SYSTEM = "http://unitsofmeasure.org"
ONCOLOGY_ROLES = {"oncologist", "primary-oncologist"}
DEFAULT_SCOPES = (
    "system/Patient.rs",
    "system/Practitioner.rs",
    "system/ActivityDefinition.rs",
    "system/CareTeam.rs",
    "system/DocumentReference.rs",
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
