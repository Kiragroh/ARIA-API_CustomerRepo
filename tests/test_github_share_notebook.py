from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "aria_fhir_github_share.ipynb"


def load_notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def notebook_source() -> str:
    notebook = load_notebook()
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def test_github_share_notebook_exists_and_is_share_safe() -> None:
    source = notebook_source()
    internal_domain_pattern = r"[A-Za-z0-9.-]+\." + r"uni-" + r"leipzig\.de"
    cookie_pattern = "JSESSION" + "ID"
    forbidden_patterns = [
        r"s\d{6,}",
        internal_domain_pattern,
        r"\\\\[^\\]+\\",
        r"C:\\tmp",
        r"eyJ[A-Za-z0-9_-]+",
        cookie_pattern,
        r"Bearer\s+[A-Za-z0-9._~-]+",
        r"\b\d{6,8}\b",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, source, flags=re.IGNORECASE)


def test_github_share_notebook_contains_key_lessons() -> None:
    source = notebook_source()
    assert "GitHub-safe" in source
    assert "Patient?name" in source
    assert "name-or-identifier" in source
    assert "ValueSet/$expand" in source
    assert "documentreference-type" in source
    assert "TemplateName ist ARIA-Metadaten" in source
    assert "PDF/Bilder als TIF" in source
    assert "Word/DOCX als Patient Document" in source
    assert "UPLOAD_PREVIEW_TEXT" in source
    assert "EXECUTE_DOCUMENT_UPLOAD = False" in source
    assert "document_category_for_attachment" in source
    assert '"docStatus": "preliminary"' in source


def test_github_share_notebook_has_no_saved_outputs_and_valid_code() -> None:
    notebook = load_notebook()
    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    assert code_cells
    for idx, cell in enumerate(code_cells, 1):
        assert cell.get("execution_count") is None
        assert cell.get("outputs", []) == []
        ast.parse("".join(cell.get("source", [])), filename=f"{NOTEBOOK.name}#cell{idx}")
