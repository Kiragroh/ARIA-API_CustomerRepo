import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "patient_fhir_query.py"
spec = importlib.util.spec_from_file_location("patient_fhir_query", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules["patient_fhir_query"] = module
spec.loader.exec_module(module)


class PatientFhirQueryTests(unittest.TestCase):
    def test_cli_defaults_do_not_make_broad_requests(self):
        parser = module.create_parser()
        args = parser.parse_args([])

        self.assertEqual(args.count, 10)
        self.assertFalse(args.allow_broad)
        self.assertFalse(args.include_http)

    def test_builds_identifier_query(self):
        query = module.build_patient_query(identifier="TEST-PATIENT-ID", count=5)

        self.assertEqual(query.path, "Patient")
        self.assertEqual(query.params, {"identifier": "TEST-PATIENT-ID", "_count": "5"})

    def test_builds_direct_patient_id_query(self):
        query = module.build_patient_query(fhir_id="Patient-123")

        self.assertEqual(query.path, "Patient/Patient-123")
        self.assertEqual(query.params, {})

    def test_rejects_unfiltered_query_without_opt_in(self):
        with self.assertRaises(ValueError):
            module.build_patient_query(count=20)

    def test_allows_broad_query_with_opt_in(self):
        query = module.build_patient_query(count=20, allow_broad=True)

        self.assertEqual(query.path, "Patient")
        self.assertEqual(query.params, {"_count": "20"})

    def test_summarizes_patient_redacted(self):
        patient = {
            "resourceType": "Patient",
            "id": "Patient-123",
            "identifier": [{"value": "TEST-PATIENT-ID"}],
            "name": [{"family": "Mustermann", "given": ["Max"]}],
            "birthDate": "1980-01-02",
            "gender": "male",
            "active": True,
            "telecom": [{"value": "123"}],
            "address": [{"city": "Leipzig"}],
        }

        summary = module.summarize_patient(patient, redact=True)

        self.assertEqual(summary["id"], "Patient-123")
        self.assertEqual(summary["identifier_count"], 1)
        self.assertEqual(summary["name_count"], 1)
        self.assertEqual(summary["birthDate_present"], True)
        self.assertNotIn("names", summary)
        self.assertNotIn("identifiers", summary)

    def test_summarizes_patient_unredacted_for_local_script_output(self):
        patient = {
            "resourceType": "Patient",
            "id": "Patient-123",
            "identifier": [{"system": "aria", "value": "TEST-PATIENT-ID"}],
            "name": [{"family": "Mustermann", "given": ["Max"]}],
            "birthDate": "1980-01-02",
        }

        summary = module.summarize_patient(patient, redact=False)

        self.assertEqual(summary["identifiers"][0]["value"], "TEST-PATIENT-ID")
        self.assertEqual(summary["names"][0]["text"], "Max Mustermann")
        self.assertEqual(summary["birthDate"], "1980-01-02")


if __name__ == "__main__":
    unittest.main()
