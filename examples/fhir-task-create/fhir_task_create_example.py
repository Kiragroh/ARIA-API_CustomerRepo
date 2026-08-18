from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib

TASK_PROFILE = "http://varian.com/fhir/v1/StructureDefinition/Task"
TASK_CATEGORY_SYSTEM = "http://varian.com/fhir/CodeSystem/activityDefinition-category"
TASK_DURATION_URL = "http://varian.com/fhir/v1/StructureDefinition/task-minutesDuration"
TASK_DURATION_SYSTEM = "http://unitsofmeasure.org"
ONCOLOGY_ROLES = {"oncologist", "primary-oncologist"}


@dataclass(frozen=True)
class OncologyRouting:
    recipients: tuple[str, ...]
    owner: str | None
    warnings: tuple[str, ...]


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
