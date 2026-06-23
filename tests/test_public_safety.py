from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_PATHS = [
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "GITHUB_EXPORT_MANIFEST.md",
    ROOT / ".env.example",
    ROOT / "aria_fhir_cli.py",
    ROOT / "patient_fhir_query.py",
    ROOT / "journal_notes_fhir_fallback.py",
    ROOT / "examples",
    ROOT / "notebooks" / "aria_fhir_github_share.ipynb",
    ROOT / "tests",
    ROOT / "fhir bei STR letter ai",
]

EXCLUDED_NAMES = {
    ".fhir_tester.pid",
    "__pycache__",
    ".pytest_cache",
    "settings.local.json",
}

INTERNAL_DOMAIN_PATTERN = r"[A-Za-z0-9.-]+\." + r"uni-" + r"leipzig\.de"
SESSION_COOKIE_PATTERN = "JSESSION" + "ID"

FORBIDDEN_PATTERNS = [
    re.compile(r"https://s\d{6,}", re.IGNORECASE),
    re.compile(INTERNAL_DOMAIN_PATTERN, re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9.-]+\\[^\s`\"']+", re.IGNORECASE),
    re.compile(r"Bearer\s+(?!<redacted>|<access_token>)[A-Za-z0-9._~-]{20,}", re.IGNORECASE),
    re.compile(SESSION_COOKIE_PATTERN + r"=[A-Za-z0-9]+", re.IGNORECASE),
    re.compile(r"client_secret\s*[:=]\s*[\"'][A-Za-z0-9._~-]{8,}[\"']", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*[\"'][^\"']+[\"']", re.IGNORECASE),
]


def iter_public_files() -> list[Path]:
    files: list[Path] = []
    for path in PUBLIC_PATHS:
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        for file_path in path.rglob("*"):
            if any(part in EXCLUDED_NAMES for part in file_path.parts):
                continue
            if file_path.is_file() and file_path.suffix.lower() in {".py", ".md", ".json", ".js", ".html", ".css", ".ps1", ".ipynb", ".bat", ".txt"}:
                files.append(file_path)
    return sorted(set(files))


def test_public_files_do_not_contain_common_secret_or_infrastructure_patterns() -> None:
    offenders: list[str] = []
    for file_path in iter_public_files():
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                offenders.append(str(file_path.relative_to(ROOT)))
                break

    assert offenders == []
