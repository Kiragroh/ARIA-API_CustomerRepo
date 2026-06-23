import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "aria_fhir_cli.py"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("aria_fhir_cli", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules["aria_fhir_cli"] = module
spec.loader.exec_module(module)


class AriaFhirCliTests(unittest.TestCase):
    def test_has_expected_modes(self):
        parser = module.create_parser()
        choices = module.mode_choices(parser)

        self.assertIn("patient", choices)
        self.assertIn("journal", choices)
        self.assertIn("token", choices)
        self.assertIn("metadata", choices)

    def test_patient_mode_parses_safe_defaults(self):
        parser = module.create_parser()
        args = parser.parse_args(["patient", "--identifier", "TEST-PATIENT-ID", "--redact"])

        self.assertEqual(args.mode, "patient")
        self.assertEqual(args.identifier, "TEST-PATIENT-ID")
        self.assertFalse(args.allow_broad)
        self.assertFalse(args.include_http)
        self.assertTrue(args.redact)

    def test_journal_mode_parses_patient_and_timestamp(self):
        parser = module.create_parser()
        args = parser.parse_args(["journal", "--patient", "TEST-PATIENT-ID", "--timestamp", "01.01.2026 00:00", "--redact"])

        self.assertEqual(args.mode, "journal")
        self.assertEqual(args.patient, "TEST-PATIENT-ID")
        self.assertEqual(args.timestamp, "01.01.2026 00:00")
        self.assertTrue(args.redact)

    def test_token_mode_is_redacted_by_default(self):
        parser = module.create_parser()
        args = parser.parse_args(["token"])

        self.assertEqual(args.mode, "token")
        self.assertFalse(args.show_token)

    def test_metadata_mode_supports_search_params(self):
        parser = module.create_parser()
        args = parser.parse_args(["metadata", "--resource", "Patient", "--search-params"])

        self.assertEqual(args.mode, "metadata")
        self.assertEqual(args.resource, "Patient")
        self.assertTrue(args.search_params)


if __name__ == "__main__":
    unittest.main()
