import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "journal_notes_fhir_fallback.py"
spec = importlib.util.spec_from_file_location("journal_notes_fhir_fallback", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules["journal_notes_fhir_fallback"] = module
spec.loader.exec_module(module)


class JournalNotesFallbackTests(unittest.TestCase):
    def test_parses_german_timestamp_as_leipzig_time(self):
        parsed = module.parse_local_timestamp("18.05.2026 00:00")

        self.assertEqual(parsed.isoformat(), "2026-05-18T00:00:00+02:00")

    def test_matches_task_authored_on_at_requested_timestamp(self):
        task = {
            "resourceType": "Task",
            "id": "Task-1",
            "authoredOn": "2026-05-18T00:00:00+02:00",
            "note": [{"text": "Journal note"}],
        }

        self.assertTrue(module.matches_task_timestamp(task, module.parse_local_timestamp("18.05.2026 00:00")))

    def test_filters_tasks_to_timestamp_and_existing_notes(self):
        tasks = [
            {"id": "Task-1", "authoredOn": "2026-05-18T00:00:00+02:00", "note": [{"text": "keep"}]},
            {"id": "Task-2", "authoredOn": "2026-05-18T00:00:00+02:00", "note": []},
            {"id": "Task-3", "authoredOn": "2026-05-19T00:00:00+02:00", "note": [{"text": "drop"}]},
        ]

        filtered = module.filter_task_notes(tasks, module.parse_local_timestamp("18.05.2026 00:00"))

        self.assertEqual([item["id"] for item in filtered], ["Task-1"])

    def test_summarizes_task_note_without_subject_reference(self):
        task = {
            "resourceType": "Task",
            "id": "Task-347786",
            "status": "completed",
            "intent": "order",
            "authoredOn": "2026-05-18T00:00:00+02:00",
            "lastModified": "2026-05-20T15:29:18+02:00",
            "code": {"coding": [{"code": "Arzt", "display": "Arzt"}]},
            "for": {"reference": "Patient/Patient-123"},
            "note": [{"text": "Journal note text", "time": None}],
        }

        summary = module.summarize_task_note(task)

        self.assertEqual(summary["task_id"], "Task-347786")
        self.assertEqual(summary["code"], "Arzt")
        self.assertEqual(summary["display"], "Arzt")
        self.assertEqual(summary["note_text"], "Journal note text")
        self.assertEqual(summary["note_count"], 1)
        self.assertNotIn("for", summary)
        self.assertNotIn("subject", summary)


if __name__ == "__main__":
    unittest.main()
