import os
import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parent

package = types.ModuleType("str_letter_ai")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("str_letter_ai", package)

text_utils = types.ModuleType("str_letter_ai.text_utils")
text_utils.clean_ws = lambda value: str(value or "").strip()
sys.modules.setdefault("str_letter_ai.text_utils", text_utils)

aria_upload = types.ModuleType("str_letter_ai.aria_upload")
aria_upload.ARIA_DOMAIN = "EXAMPLE"
aria_upload.ARIA_USER = "tester"
aria_upload.parse_date_of_service_value = (
    lambda value, **_: (datetime.strptime(value, "%d.%m.%Y"), False)
)
sys.modules.setdefault("str_letter_ai.aria_upload", aria_upload)

spec = importlib.util.spec_from_file_location("str_letter_ai.aria_fhir_upload", ROOT / "aria_fhir_upload.py")
fhir = importlib.util.module_from_spec(spec)
sys.modules["str_letter_ai.aria_fhir_upload"] = fhir
assert spec and spec.loader
spec.loader.exec_module(fhir)


class AriaFhirUploadTests(unittest.TestCase):
    def _category_code(self, doc_ref):
        return doc_ref["category"][0]["coding"][0]["code"]

    def test_document_reference_carries_windows_practitioner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "brief.docx"
            file_path.write_bytes(b"PK\x03\x04docx")

            practitioner = {
                "reference": "Practitioner/Practitioner-9665",
                "display": "tester",
            }
            custodian = {
                "reference": "Organization/Organization-Prov-1",
                "display": "Example Hospital",
            }

            doc_ref = fhir._document_reference(
                patient_fhir_id="Patient-9365",
                file_path=file_path,
                date_of_service="19.05.2026",
                doc_code="1055",
                doc_system=fhir.DOCUMENT_TYPE_SYSTEM,
                doc_type="Nachsorgebrief",
                template_name="MedVZ Nachsorgebrief*",
                description="MedVZ Nachsorgebrief*",
                user_reference=practitioner,
                custodian_reference=custodian,
            )

        self.assertEqual(doc_ref["author"], [practitioner])
        self.assertEqual(doc_ref["custodian"], custodian)
        supervisor_extensions = [
            extension
            for extension in doc_ref["extension"]
            if extension.get("url") == fhir.SUPERVISOR_EXTENSION_URL
        ]
        self.assertEqual(len(supervisor_extensions), 1)
        self.assertEqual(supervisor_extensions[0]["valueReference"], practitioner)

    def test_document_reference_uses_patient_document_category_for_docx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "brief.docx"
            file_path.write_bytes(b"PK\x03\x04docx")

            doc_ref = fhir._document_reference(
                patient_fhir_id="Patient-9365",
                file_path=file_path,
                date_of_service="19.05.2026",
                doc_code="1055",
                doc_system=fhir.DOCUMENT_TYPE_SYSTEM,
                doc_type="Nachsorgebrief",
                template_name="MedVZ Nachsorgebrief*",
                description="MedVZ Nachsorgebrief*",
            )

        self.assertEqual(self._category_code(doc_ref), "Patient Document")

    def test_document_reference_uses_tif_category_for_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "plan.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")

            doc_ref = fhir._document_reference(
                patient_fhir_id="Patient-9365",
                file_path=file_path,
                date_of_service="19.05.2026",
                doc_code="1052",
                doc_system=fhir.DOCUMENT_TYPE_SYSTEM,
                doc_type="RT-Plan-Verifikation",
                template_name="RT-Plan-Verifikation",
                description="",
            )

        self.assertEqual(doc_ref["content"][0]["attachment"]["contentType"], "application/pdf")
        self.assertEqual(self._category_code(doc_ref), "TIF")

    def test_windows_domain_user_prefers_aria_user_over_fhir_override(self):
        with patch.dict(
            os.environ,
            {
                "ARIA_DOMAIN": "EXAMPLE",
                "ARIA_USER": "test_user",
                "ARIA_FHIR_WINDOWS_DOMAIN": "FHIR",
                "ARIA_FHIR_WINDOWS_USER": "vais_user",
            },
            clear=False,
        ):
            self.assertEqual(fhir._windows_domain_user(), "EXAMPLE\\test_user")

        with patch.dict(os.environ, {"ARIA_USER": "EXAMPLE/tester"}, clear=False):
            self.assertEqual(fhir._windows_domain_user(), "EXAMPLE\\tester")

    def test_windows_domain_user_falls_back_to_package_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fhir._windows_domain_user(), "EXAMPLE\\tester")

    def test_windows_practitioner_reference_prefers_fhir_lookup(self):
        session = Mock()
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Practitioner",
                        "id": "Practitioner-9665",
                            "name": [{"text": "tester"}],
                    }
                }
            ],
        }
        session.get.return_value = response

        with patch.dict(
            os.environ,
            {"ARIA_FHIR_WINDOWS_DOMAIN": "EXAMPLE", "ARIA_FHIR_WINDOWS_USER": "tester"},
            clear=False,
        ):
            reference, note, windows_user = fhir._windows_user_reference(session)

        self.assertEqual(windows_user, "EXAMPLE\\tester")
        self.assertEqual(
            reference,
            {"reference": "Practitioner/Practitioner-9665", "display": "tester"},
        )
        self.assertIn("Practitioner gesucht", note)


if __name__ == "__main__":
    unittest.main()
