# ARIA FHIR Task Creation Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public, trigger-agnostic Python example that creates an idempotent ARIA FHIR `Task`, routes it to the configured group and linked oncologists, and assigns exactly one primary oncologist as owner.

**Architecture:** Keep the example self-contained in one executable Python module plus one standard-library `unittest` module and a focused README. Separate pure routing/payload functions from the HTTP client and the CLI workflow so routing, idempotency, privacy, and Dry-Run behavior can be tested without contacting a real Varian-Platform.

**Tech Stack:** Python 3.10+, `requests`, standard-library `argparse`, `dataclasses`, `hashlib`, `json`, `unittest`, ARIA/VAIS FHIR R4, OAuth2 Client Credentials.

---

## File map

- Create `examples/fhir-task-create/fhir_task_create_example.py`: configuration, OAuth2, paginated FHIR reads, routing, payload, idempotent workflow, redacted Dry-Run, CLI.
- Create `examples/fhir-task-create/test_fhir_task_create_example.py`: isolated unit tests with fake sessions/clients; no live network.
- Create `examples/fhir-task-create/README.md`: setup, Dry-Run, execute mode, routing semantics, safety limits.
- Modify `README.md`: add the example to the repository map and quick checks.
- Modify `CHANGELOG.md`: prepend Build 7 entry.
- Modify `versionInfo.json`: increment to Build 7 and describe the example.

## Task 1: Pure workflow identifier, routing, and Task payload

**Files:**
- Create: `examples/fhir-task-create/test_fhir_task_create_example.py`
- Create: `examples/fhir-task-create/fhir_task_create_example.py`

- [ ] **Step 1: Write failing domain tests**

Create the test module with an import path for the sibling example and tests for deterministic identifiers, recipient deduplication, owner selection, and owner omission:

```python
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fhir_task_create_example as example


class DomainTests(unittest.TestCase):
    def test_workflow_value_is_stable_and_trigger_specific(self):
        first = example.workflow_value("event-42")
        self.assertEqual(first, example.workflow_value(" event-42 "))
        self.assertNotEqual(first, example.workflow_value("event-43"))
        self.assertEqual(len(first), 64)

    def test_routing_deduplicates_group_and_active_oncologists(self):
        teams = [{
            "status": "active",
            "participant": [
                {"role": [{"coding": [{"code": "oncologist"}]}], "member": {"reference": "Practitioner/2"}},
                {"role": [{"coding": [{"code": "primary-oncologist"}]}], "member": {"reference": "Practitioner/1"}},
                {"role": [{"coding": [{"code": "oncologist"}]}], "member": {"reference": "Practitioner/2"}},
            ],
        }]
        practitioners = {
            "Practitioner/1": {"active": True},
            "Practitioner/2": {"active": True},
        }

        routing = example.resolve_oncology_routing(teams, practitioners)

        self.assertEqual(routing.recipients, ("Practitioner/1", "Practitioner/2"))
        self.assertEqual(routing.owner, "Practitioner/1")

    def test_no_unique_primary_omits_owner_but_keeps_recipients(self):
        routing = example.OncologyRouting(
            recipients=("Practitioner/1", "Practitioner/2"),
            owner=None,
            warnings=("multiple_primary_oncologists",),
        )
        payload = example.build_task_payload(
            patient_reference="Patient/10",
            activity_reference="ActivityDefinition/20",
            group_reference="Group/30",
            group_name="Arzt",
            routing=routing,
            identifier_system="urn:example:aria-fhir-task-trigger:v1",
            identifier_value="abc",
            authored_on=datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc),
            duration_minutes=10,
            note="Clinical review",
        )

        self.assertNotIn("owner", payload)
        self.assertEqual(
            [item["reference"] for item in payload["restriction"]["recipient"]],
            ["Group/30", "Practitioner/1", "Practitioner/2"],
        )
        self.assertEqual(payload["code"]["coding"][0]["code"], "Arzt")
        self.assertEqual(payload["restriction"]["period"]["end"], "2026-08-18T08:10:00+00:00")

    def test_multiple_primary_oncologists_produce_no_owner(self):
        teams = [{
            "status": "active",
            "participant": [
                {"role": [{"coding": [{"code": "primary-oncologist"}]}], "member": {"reference": "Practitioner/1"}},
                {"role": [{"coding": [{"code": "primary-oncologist"}]}], "member": {"reference": "Practitioner/2"}},
            ],
        }]
        routing = example.resolve_oncology_routing(teams, {
            "Practitioner/1": {"active": True},
            "Practitioner/2": {"active": True},
        })

        self.assertIsNone(routing.owner)
        self.assertEqual(routing.recipients, ("Practitioner/1", "Practitioner/2"))
        self.assertIn("multiple_primary_oncologists", routing.warnings)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the domain tests and verify RED**

Run:

```powershell
python -m unittest discover -s examples/fhir-task-create -p "test_*.py" -v
```

Expected: FAIL because `fhir_task_create_example` does not exist.

- [ ] **Step 3: Implement the minimal pure domain layer**

Create `fhir_task_create_example.py` with constants and pure functions:

```python
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
```

- [ ] **Step 4: Run the domain tests and verify GREEN**

Run the same `unittest discover` command.

Expected: 3 tests PASS.

- [ ] **Step 5: Commit the domain layer**

```powershell
git add -- examples/fhir-task-create/test_fhir_task_create_example.py examples/fhir-task-create/fhir_task_create_example.py
git commit -m "feat: add ARIA Task routing domain"
```

## Task 2: Secure endpoint configuration, OAuth2, and paginated FHIR reads

**Files:**
- Modify: `examples/fhir-task-create/test_fhir_task_create_example.py`
- Modify: `examples/fhir-task-create/fhir_task_create_example.py`

- [ ] **Step 1: Add failing client tests**

Add lightweight fake HTTP objects and tests:

```python
class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.content = b"{}"
        self.text = "{}"
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}
        self.verify = True

    def _next(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)


def _settings():
    return example.Settings(
        token_url="https://Varian-Platform:44333/tokenservice/connect/token",
        base_url="https://Varian-Platform:55370/fhir/r4",
        client_id="client",
        client_secret="<client-secret>",
        scopes=(),
        verify=True,
    )


class ClientTests(unittest.TestCase):
    def test_platform_builds_both_service_urls(self):
        token_url, base_url = example.derive_urls("Varian-Platform")
        self.assertEqual(token_url, "https://Varian-Platform:44333/tokenservice/connect/token")
        self.assertEqual(base_url, "https://Varian-Platform:55370/fhir/r4")

    def test_authentication_checks_granted_scopes(self):
        settings = example.Settings(
            token_url="https://Varian-Platform:44333/tokenservice/connect/token",
            base_url="https://Varian-Platform:55370/fhir/r4",
            client_id="client",
            client_secret="<client-secret>",
            scopes=("system/Patient.rs", "system/Task.cruds"),
            verify=True,
        )
        session = FakeSession([FakeResponse(payload={
            "access_token": "token",
            "scope": "system/Patient.rs system/Task.cruds",
        })])
        client = example.FhirClient(settings, session=session)

        client.authenticate()

        self.assertEqual(session.headers["Authorization"], "Bearer token")
        form = session.calls[0][2]["data"]
        self.assertEqual(form["grant_type"], "client_credentials")
        self.assertEqual(form["client_id"], "client")
        self.assertEqual(form["client_secret"], "<client-secret>")

    def test_search_follows_same_origin_next_link(self):
        session = FakeSession([
            FakeResponse(payload={
                "entry": [{"resource": {"id": "one"}}],
                "link": [{"relation": "next", "url": "https://Varian-Platform:55370/fhir/r4/Patient?page=2"}],
            }),
            FakeResponse(payload={"entry": [{"resource": {"id": "two"}}]}),
        ])
        client = example.FhirClient(_settings(), session=session)

        resources = client.search("Patient", {"identifier": "123"})

        self.assertEqual([item["id"] for item in resources], ["one", "two"])

    def test_search_rejects_cross_origin_next_link(self):
        session = FakeSession([FakeResponse(payload={
            "link": [{"relation": "next", "url": "https://other.example/fhir/r4/Patient?page=2"}],
        })])
        client = example.FhirClient(_settings(), session=session)

        with self.assertRaisesRegex(example.FhirExampleError, "Cross-origin"):
            client.search("Patient", {"identifier": "123"})

    def test_operation_outcome_reports_only_severity_and_code(self):
        response = FakeResponse(status_code=400, payload={
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "invalid",
                "diagnostics": "Patient P-123 must never be printed",
            }],
        })

        message = example.operation_outcome_message(response)

        self.assertEqual(message, "HTTP 400 OperationOutcome error:invalid")
        self.assertNotIn("P-123", message)
```

- [ ] **Step 2: Run client tests and verify RED**

Run:

```powershell
python -m unittest discover -s examples/fhir-task-create -p "test_*.py" -v
```

Expected: FAIL because `derive_urls`, `Settings`, and `FhirClient` are absent.

- [ ] **Step 3: Implement settings, safe errors, OAuth, reads, and pagination**

Add imports and the following production structures:

```python
from dataclasses import dataclass
import json
from urllib.parse import urljoin, urlparse
import requests

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
    if body.get("resourceType") != "OperationOutcome":
        return f"HTTP {response.status_code}"
    parts = []
    for issue in body.get("issue", [])[:5]:
        code = str(issue.get("code") or "unknown")
        severity = str(issue.get("severity") or "unknown")
        parts.append(f"{severity}:{code}")
    return f"HTTP {response.status_code} OperationOutcome " + ", ".join(parts)


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
        missing = sorted(set(self.settings.scopes) - set(str(body.get("scope") or "").split()))
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
                if link.get("relation") == "next"
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
```

- [ ] **Step 4: Run all tests and verify GREEN**

Expected: all domain and client tests PASS.

- [ ] **Step 5: Commit the client layer**

```powershell
git add -- examples/fhir-task-create/test_fhir_task_create_example.py examples/fhir-task-create/fhir_task_create_example.py
git commit -m "feat: add secure ARIA FHIR client example"
```

## Task 3: Resolve Patient, ActivityDefinition, Group, and CareTeam routing

**Files:**
- Modify: `examples/fhir-task-create/test_fhir_task_create_example.py`
- Modify: `examples/fhir-task-create/fhir_task_create_example.py`

- [ ] **Step 1: Add failing dependency-resolution tests**

Use a `StubClient` that records `search` and `read` calls. Add tests proving that a patient and activity must be unique, the activity must point to the expected active group, inactive practitioners are excluded, and one primary is selected:

```python
class StubResolveClient:
    resolve_patient = example.FhirClient.resolve_patient
    resolve_activity_and_group = example.FhirClient.resolve_activity_and_group
    resolve_routing = example.FhirClient.resolve_routing

    def __init__(self, searches, reads):
        self.searches = searches
        self.reads = reads

    def search(self, resource, params):
        return self.searches[(resource, tuple(sorted(params.items())))]

    def read(self, reference):
        return self.reads[reference]


class ResolutionTests(unittest.TestCase):
    def test_activity_group_and_primary_oncologist_are_resolved(self):
        searches = {
            ("Patient", (("_count", "2"), ("identifier", "P-1"))): [{"id": "patient-1"}],
            ("ActivityDefinition", (("_count", "3"), ("kind", "Task"), ("name", "Review"), ("status", "active"))): [{
                "id": "activity-1", "name": "Review", "kind": "Task", "status": "active",
                "subjectReference": {"reference": "Group/group-1"},
            }],
            ("CareTeam", (("_count", "100"), ("patient", "Patient/patient-1"))): [{
                "status": "active",
                "participant": [{
                    "role": [{"coding": [{"code": "primary-oncologist"}]}],
                    "member": {"reference": "Practitioner/practitioner-1"},
                }],
            }],
        }
        reads = {
            "Group/group-1": {"id": "group-1", "name": "Arzt", "active": True},
            "Practitioner/practitioner-1": {"id": "practitioner-1", "active": True},
        }
        client = StubResolveClient(searches, reads)

        patient = client.resolve_patient("P-1")
        activity, group = client.resolve_activity_and_group("Review", "Arzt")
        routing = client.resolve_routing("Patient/patient-1")

        self.assertEqual(patient["id"], "patient-1")
        self.assertEqual(activity["id"], "activity-1")
        self.assertEqual(group["id"], "group-1")
        self.assertEqual(routing.owner, "Practitioner/practitioner-1")
```

- [ ] **Step 2: Run resolution tests and verify RED**

Expected: FAIL because the three resolution methods do not exist.

- [ ] **Step 3: Implement strict dependency resolution**

Add methods to `FhirClient`:

```python
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
```

- [ ] **Step 4: Run all tests and verify GREEN**

Expected: all tests PASS.

- [ ] **Step 5: Commit dependency resolution**

```powershell
git add -- examples/fhir-task-create/test_fhir_task_create_example.py examples/fhir-task-create/fhir_task_create_example.py
git commit -m "feat: resolve ARIA Task recipients"
```

## Task 4: Idempotent Dry-Run, POST, reconciliation, and read-back

**Files:**
- Modify: `examples/fhir-task-create/test_fhir_task_create_example.py`
- Modify: `examples/fhir-task-create/fhir_task_create_example.py`

- [ ] **Step 1: Add failing workflow tests**

Add a `FakeWorkflowClient` with counters and test three paths:

```python
class FakeWorkflowClient:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.posted = []
        self.created = None

    def resolve_patient(self, _identifier):
        return {"id": "patient-1"}

    def resolve_activity_and_group(self, _activity, _group):
        return ({"id": "activity-1"}, {"id": "group-1", "name": "Arzt"})

    def resolve_routing(self, _patient_reference):
        return example.OncologyRouting(("Practitioner/2",), "Practitioner/2", ())

    def find_tasks(self, _system, _value):
        return list(self.existing)

    def create_task(self, payload):
        self.posted.append(payload)
        self.created = {
            **payload,
            "id": "task-1",
            "basedOn": [{"reference": "ServiceRequest/1"}],
        }
        return {"id": "task-1"}

    def read(self, reference):
        if reference != "Task/task-1" or self.created is None:
            raise AssertionError(f"Unexpected Task read: {reference}")
        return self.created


class WorkflowTests(unittest.TestCase):
    def _request(self, execute=False):
        return example.WorkflowRequest(
            patient_identifier="P-1",
            activity_name="Review",
            trigger_id="event-1",
            group_name="Arzt",
            identifier_system="urn:example:aria-fhir-task-trigger:v1",
            note="Review document",
            duration_minutes=10,
            execute=execute,
        )

    def _existing_task(self):
        return {
            "resourceType": "Task",
            "identifier": [{
                "system": "urn:example:aria-fhir-task-trigger:v1",
                "value": example.workflow_value("event-1"),
            }],
            "status": "ready",
            "focus": {"reference": "ActivityDefinition/activity-1"},
            "for": {"reference": "Patient/patient-1"},
            "owner": {"reference": "Practitioner/2"},
            "restriction": {
                "recipient": [
                    {"reference": "Group/group-1"},
                    {"reference": "Practitioner/2"},
                ]
            },
        }

    def test_dry_run_builds_redacted_plan_without_post(self):
        client = FakeWorkflowClient()
        result = example.run_workflow(client, self._request(), now_fn=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(client.posted, [])
        serialized = str(result)
        self.assertNotIn("Patient/patient-1", serialized)
        self.assertNotIn("Practitioner/2", serialized)

    def test_existing_task_prevents_post(self):
        client = FakeWorkflowClient(existing=[self._existing_task()])
        result = example.run_workflow(client, self._request(execute=True))
        self.assertEqual(result["status"], "already_exists")
        self.assertEqual(client.posted, [])

    def test_execute_posts_once_and_verifies_readback(self):
        client = FakeWorkflowClient()
        result = example.run_workflow(client, self._request(execute=True))
        self.assertEqual(result["status"], "created")
        self.assertEqual(len(client.posted), 1)
```

- [ ] **Step 2: Run workflow tests and verify RED**

Expected: FAIL because `WorkflowRequest`, `run_workflow`, idempotency, and read-back verification are absent.

- [ ] **Step 3: Implement workflow and FHIR Task methods**

Add:

```python
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


def redacted_payload(payload: dict) -> dict:
    copy = json.loads(json.dumps(payload))
    copy["for"]["reference"] = "Patient/<redacted>"
    if "owner" in copy:
        copy["owner"]["reference"] = "Practitioner/<redacted>"
    for recipient in copy.get("restriction", {}).get("recipient", []):
        kind = str(recipient.get("reference") or "Reference").split("/", 1)[0]
        recipient["reference"] = f"{kind}/<redacted>"
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
```

Add methods to `FhirClient`:

```python
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
```

Refine the fake client so `read("Task/task-1")` returns the created payload with `id` and `basedOn`; do not call test assertions from the fake itself.

- [ ] **Step 4: Run all tests and verify GREEN**

Expected: domain, client, resolution, and workflow tests all PASS.

- [ ] **Step 5: Commit idempotent workflow behavior**

```powershell
git add -- examples/fhir-task-create/test_fhir_task_create_example.py examples/fhir-task-create/fhir_task_create_example.py
git commit -m "feat: create idempotent ARIA FHIR Tasks"
```

## Task 5: CLI, environment loading, and privacy-safe output

**Files:**
- Modify: `examples/fhir-task-create/test_fhir_task_create_example.py`
- Modify: `examples/fhir-task-create/fhir_task_create_example.py`

- [ ] **Step 1: Add failing CLI/configuration tests**

Add tests for platform-derived URLs, explicit URL overrides, mandatory credentials, positive duration, Dry-Run default, and output redaction:

```python
class CliTests(unittest.TestCase):
    def test_parser_defaults_to_dry_run(self):
        args = example.build_parser().parse_args([
            "--patient-identifier", "P-1",
            "--activity-name", "Review",
            "--trigger-id", "event-1",
        ])
        self.assertFalse(args.execute)
        self.assertEqual(args.group_name, "Arzt")
        self.assertEqual(args.duration_minutes, 10)

    def test_settings_use_one_varian_platform_for_both_services(self):
        env = {
            "VARIAN_PLATFORM": "Varian-Platform",
            "ARIA_FHIR_CLIENT_ID": "client",
            "ARIA_FHIR_CLIENT_SECRET": "secret",
        }
        settings = example.settings_from_environment(env)
        self.assertEqual(settings.token_url, "https://Varian-Platform:44333/tokenservice/connect/token")
        self.assertEqual(settings.base_url, "https://Varian-Platform:55370/fhir/r4")
        self.assertTrue(settings.verify)

    def test_explicit_urls_override_platform_derived_urls(self):
        env = {
            "VARIAN_PLATFORM": "Varian-Platform",
            "ARIA_FHIR_CLIENT_ID": "client",
            "ARIA_FHIR_CLIENT_SECRET": "secret",
        }
        settings = example.settings_from_environment(
            env,
            token_url_override="https://auth.example/token",
            base_url_override="https://fhir.example/fhir/r4",
        )
        self.assertEqual(settings.token_url, "https://auth.example/token")
        self.assertEqual(settings.base_url, "https://fhir.example/fhir/r4")
```

- [ ] **Step 2: Run CLI tests and verify RED**

Expected: FAIL because parser/configuration/main functions do not exist.

- [ ] **Step 3: Implement CLI and main without exposing secrets**

Add `argparse`, `os`, and `Path` imports. Implement:

```python
import argparse
import os
from pathlib import Path

DEFAULT_IDENTIFIER_SYSTEM = "urn:example:aria-fhir-task-trigger:v1"


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
    parser = argparse.ArgumentParser(description="Create an idempotent ARIA FHIR Task from any external trigger.")
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
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "dry_run":
        print("\nDry-run: no Task POST was performed. Add --execute for a live write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, compile, and inspect help**

Run:

```powershell
python -m unittest discover -s examples/fhir-task-create -p "test_*.py" -v
python -m py_compile examples/fhir-task-create/fhir_task_create_example.py examples/fhir-task-create/test_fhir_task_create_example.py
python examples/fhir-task-create/fhir_task_create_example.py --help
```

Expected: tests PASS, compilation succeeds, help lists required identifiers and `--execute`; no network call occurs for `--help`.

- [ ] **Step 5: Commit CLI behavior**

```powershell
git add -- examples/fhir-task-create/test_fhir_task_create_example.py examples/fhir-task-create/fhir_task_create_example.py
git commit -m "feat: add ARIA FHIR Task example CLI"
```

## Task 6: Public README and release metadata

**Files:**
- Create: `examples/fhir-task-create/README.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `versionInfo.json`

- [ ] **Step 1: Write the example README**

Document:

```markdown
# FHIR Task Creation Example

This trigger-agnostic example creates an ARIA FHIR `Task` for a patient. The caller supplies a stable trigger ID, patient identifier, and active ARIA activity name. Dry-Run is the default.

## Configuration

```text
VARIAN_PLATFORM=<Varian-Platform>
ARIA_FHIR_CLIENT_ID=<client-id>
ARIA_FHIR_CLIENT_SECRET=<local-secret>
```

The example derives the OAuth token service on port `44333` and FHIR R4 base on port `55370` from the same Varian-Platform. Explicit `ARIA_FHIR_TOKEN_URL` and `ARIA_FHIR_BASE_URL` values override the derived URLs. Use `ARIA_FHIR_CA_BUNDLE` when a private CA is required; TLS validation is never disabled.

## Dry-Run

```powershell
python .\examples\fhir-task-create\fhir_task_create_example.py `
  --patient-identifier "<ARIA-ID>" `
  --activity-name "Labor genehmigen" `
  --trigger-id "<stable-trigger-id>"
```

## Live creation

Append `--execute` only after reviewing the redacted Dry-Run payload.

## Routing

- `ActivityDefinition.subjectReference` supplies the active group.
- The group and all active CareTeam participants with role `oncologist` or `primary-oncologist` are `Task.restriction.recipient` entries.
- Exactly one active primary oncologist becomes `Task.owner`.
- With no unique primary, `owner` is omitted and the group Task is still created.
- The stable trigger identifier prevents duplicate Task creation.

The example creates no `Appointment`. ARIA may add a parent `ServiceRequest` server-side.
```

Keep the README concise and explicitly state that activity names, groups, scopes, certificates, and user rights are installation-specific.

- [ ] **Step 2: Add repository discovery links**

Modify the root README table with:

```markdown
| `examples/fhir-task-create/` | trigger-unabhaengiges ARIA-FHIR-Task-Beispiel mit Gruppen-/Onkologen-Routing und Dry-Run |
```

Add to quick checks:

```powershell
python .\examples\fhir-task-create\fhir_task_create_example.py --help
```

- [ ] **Step 3: Add Build 7 release metadata**

Prepend to `CHANGELOG.md`:

```markdown
## Build 7 - 2026-08-18

- Trigger-unabhaengiges Python-Beispiel fuer idempotente ARIA-FHIR-Tasks mit sicherem Dry-Run ergaenzt.
- Gruppe und aktive Onkologen werden als Recipients gesetzt; genau ein Primary Oncologist wird Owner.
- OAuth2, Varian-Platform-Endpunkte, Scope-Pruefung, Read-back und Reconciliation sind ohne Infrastruktur- oder Geheimniswerte nachvollziehbar.
```

Set `versionInfo.json` to build 7, date `2026-08-18`, and prepend:

```json
{
  "build": 7,
  "date": "2026-08-18",
  "title": "Ausfuehrbares ARIA-FHIR-Task-Beispiel ergaenzt",
  "changes": [
    "Das neue Python-Beispiel erstellt trigger-unabhaengige, idempotente ARIA-FHIR-Tasks mit Dry-Run und bewusstem Execute-Schalter.",
    "Aktive Gruppe und Onkologen werden als Recipients gesetzt; genau ein Primary Oncologist wird Owner.",
    "OAuth2, Varian-Platform-Endpunkte, Scope-Pruefung, Read-back und sichere Reconciliation sind ohne produktive Infrastrukturwerte dokumentiert."
  ]
}
```

Set `lastChange` to `Trigger-unabhaengiges ARIA-FHIR-Task-Beispiel mit Gruppen- und Onkologen-Routing ergaenzt`.

- [ ] **Step 4: Validate documentation and release JSON**

Run:

```powershell
python -c "import json, pathlib; json.loads(pathlib.Path('versionInfo.json').read_text(encoding='utf-8')); print('versionInfo OK')"
git diff --check
```

Expected: `versionInfo OK`; no whitespace errors.

- [ ] **Step 5: Commit docs and release metadata**

```powershell
git add -- examples/fhir-task-create/README.md README.md CHANGELOG.md versionInfo.json
git commit -m "docs: publish ARIA FHIR Task example"
```

## Task 7: Full verification and publication

**Files:**
- Verify all files changed on `codex/fhir-task-create-example`

- [ ] **Step 1: Run focused automated checks**

```powershell
python -m unittest discover -s examples/fhir-task-create -p "test_*.py" -v
python -m py_compile examples/fhir-task-create/fhir_task_create_example.py examples/fhir-task-create/test_fhir_task_create_example.py
python examples/fhir-task-create/fhir_task_create_example.py --help
python -c "import json, pathlib; json.loads(pathlib.Path('versionInfo.json').read_text(encoding='utf-8')); print('versionInfo OK')"
git diff --check
```

Expected: all tests PASS, compilation succeeds, help exits 0, JSON parses, and diff check is empty.

- [ ] **Step 2: Run a public-safety scan**

Scan only intended public files for local hostnames, patient IDs, UNC paths, access tokens, and assigned secrets:

```powershell
rg -n -i "s050[0-9]+|medizin\.uni-leipzig|05183131|access_token\s*[:=]\s*['\"][^<]|client_secret\s*[:=]\s*['\"][^<]|\\\\medizin" `
  examples/fhir-task-create README.md CHANGELOG.md versionInfo.json docs/superpowers
```

Expected: no real infrastructure, patient, token, or secret values. Variable names and placeholder values such as `<local-secret>` are allowed.

- [ ] **Step 3: Review exact Git scope**

```powershell
git status -sb
git diff origin/main...HEAD --stat
git diff origin/main...HEAD -- examples/fhir-task-create README.md CHANGELOG.md versionInfo.json docs/superpowers
```

Expected: only the design, plan, example, tests, README, changelog, and version metadata are included. `Flint/` remains untracked and unstaged.

- [ ] **Step 4: Push the feature branch**

```powershell
git push -u origin codex/fhir-task-create-example
```

Expected: remote branch created successfully.

- [ ] **Step 5: Open a Draft PR**

```powershell
gh pr create --draft --base main --head codex/fhir-task-create-example `
  --title "Add executable ARIA FHIR Task example" `
  --body "Adds a trigger-agnostic ARIA FHIR Task example with OAuth2, Dry-Run, group and oncologist routing, unique-primary ownership, idempotency, and read-back verification. Validation uses isolated unit tests and performs no live FHIR write."
```

The PR body must summarize behavior, privacy boundary, tests, and the fact that no live FHIR write was performed during validation.
