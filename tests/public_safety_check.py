#!/usr/bin/env python3
"""Fail when maintained public files contain local deployment identifiers."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    "ARIA-API-ImplementationGuide",
    "examples.json",
}
TEXT_SUFFIXES = {
    ".cfg",
    ".config",
    ".env",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
FORBIDDEN = {
    "institution name": re.compile(
        r"(?:UKL|Leipzig|Universit[aä]tsklinikum|Uniklinikum)",
        re.IGNORECASE,
    ),
    "institution namespace": re.compile(r"urn:ukl", re.IGNORECASE),
    "internal domain": re.compile(
        r"(?:medizin\.uni-leipzig\.de|prz-smb|GitUKL)",
        re.IGNORECASE,
    ),
    "private IPv4": re.compile(
        r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b"
    ),
}


def maintained_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in {".env.example", ".gitignore"}:
            yield path
        elif path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def main() -> int:
    findings = []
    for path in maintained_files():
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        for label, pattern in FORBIDDEN.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    f"{path.relative_to(ROOT)}:{line}: {label}: {match.group(0)}"
                )
    if findings:
        print("Public-safety check failed:")
        print("\n".join(findings))
        return 1
    print("Public-safety check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
