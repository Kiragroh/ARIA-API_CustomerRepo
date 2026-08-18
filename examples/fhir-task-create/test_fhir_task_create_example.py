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
        client_secret="secret",
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
            client_secret="secret",
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
        self.assertEqual(form["client_secret"], "secret")

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


if __name__ == "__main__":
    unittest.main()
