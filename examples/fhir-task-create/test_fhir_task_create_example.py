from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
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
