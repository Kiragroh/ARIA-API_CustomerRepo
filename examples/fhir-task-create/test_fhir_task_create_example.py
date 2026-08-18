from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fhir_task_create_example as example


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


if __name__ == "__main__":
    unittest.main()
