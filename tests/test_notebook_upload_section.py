from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "aria_fhir_github_share.ipynb"


def notebook_source() -> str:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def test_notebook_contains_guarded_upload_example() -> None:
    source = notebook_source()
    assert 'EXECUTE_DOCUMENT_UPLOAD = False' in source
    assert "TemplateName ist ARIA-Metadaten" in source
    assert 'UPLOAD_PREVIEW_TEXT = ""' in source
    assert "weiterfuehrende Infos" in source
    assert "template_name=UPLOAD_TEMPLATE_NAME" in source
    assert "is_word_document(file_path)" not in source
    assert "document_category_for_attachment(content_type)" in source
    assert '"code": "TIF"' in source
    assert '"code": "Patient Document"' in source
    assert '"description": UPLOAD_TEMPLATE_NAME' not in source
    assert '"docStatus": "preliminary"' in source


def test_notebook_upload_example_avoids_saved_outputs() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    assert all(cell.get("execution_count") is None for cell in code_cells)
    assert sum(len(cell.get("outputs", [])) for cell in code_cells) == 0
