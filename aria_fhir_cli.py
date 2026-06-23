from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

import journal_notes_fhir_fallback
import patient_fhir_query


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--client-secret", default=None)
    parser.add_argument("--scope", default=None, help="Leer lassen nutzt den Client-Default-Scope.")


def add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", default="", help="JSON-Ausgabedatei statt Konsole.")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ARIA FHIR CMD-App mit Modi fuer Patient, Journal Notes, Token und Metadata.",
        epilog=(
            "Beispiele:\n"
            "  python aria_fhir_cli.py patient --identifier <patient-identifier> --redact\n"
            "  python aria_fhir_cli.py journal --patient <patient-identifier> --timestamp \"01.01.2026 00:00\" --redact\n"
            "  python aria_fhir_cli.py token\n"
            "  python aria_fhir_cli.py metadata --resource Patient --search-params"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    parser._aria_mode_choices = ["patient", "journal", "token", "metadata"]  # noqa: SLF001

    patient = subparsers.add_parser("patient", help="Patient suchen oder per FHIR-ID lesen.")
    patient.add_argument("--identifier", default="", help="Sichtbare ARIA PatID, z.B. <patient-identifier>.")
    patient.add_argument("--id", dest="fhir_id", default="", help="FHIR-ID, z.B. Patient-123.")
    patient.add_argument("--name-or-identifier", default="")
    patient.add_argument("--family", default="")
    patient.add_argument("--given", default="")
    patient.add_argument("--birthdate", default="", help="YYYY-MM-DD.")
    patient.add_argument("--active", default="", choices=["", "true", "false"])
    patient.add_argument("--test-patient", default="", choices=["", "true", "false"])
    patient.add_argument("--count", type=int, default=10)
    patient.add_argument("--allow-broad", action="store_true", help="Erlaubt bewusst Patient?_count=... .")
    patient.add_argument("--raw", action="store_true", help="Rohe FHIR-Antwort ausgeben.")
    patient.add_argument("--redact", action="store_true", help="Namen, Identifier und Geburtsdatum redigieren.")
    patient.add_argument("--include-http", action="store_true", help="Redigierte HTTP-Kommunikation mit ausgeben.")
    add_auth_args(patient)
    add_output_args(patient)

    journal = subparsers.add_parser("journal", help="Journal Notes via FHIR Task.note lesen.")
    journal.add_argument("--patient", required=True, help="ARIA PatID oder Patient-... FHIR-ID.")
    journal.add_argument("--timestamp", default="01.01.2026 00:00", help="dd.mm.yyyy HH:MM in Europe/Berlin.")
    journal.add_argument("--redact", action="store_true", help="Notiztext nicht ausgeben.")
    add_auth_args(journal)
    add_output_args(journal)

    token = subparsers.add_parser("token", help="Token holen und redigierte Token-Metadaten anzeigen.")
    token.add_argument("--show-token", action="store_true", help="Gibt den echten Bearer Token lokal aus.")
    add_auth_args(token)
    add_output_args(token)

    metadata = subparsers.add_parser("metadata", help="FHIR CapabilityStatement / Ressourcen anzeigen.")
    metadata.add_argument("--resource", default="", help="Optional Resource filtern, z.B. Patient oder Task.")
    metadata.add_argument("--search-params", action="store_true", help="SearchParameter je Resource mit ausgeben.")
    metadata.add_argument("--include-http", action="store_true", help="Redigierte HTTP-Kommunikation mit ausgeben.")
    add_auth_args(metadata)
    add_output_args(metadata)
    return parser


def mode_choices(parser: argparse.ArgumentParser) -> list[str]:
    return list(getattr(parser, "_aria_mode_choices", []))


def effective_auth(args: argparse.Namespace) -> tuple[str, str, str]:
    patient_fhir_query.load_dotenv()
    client_id = args.client_id if args.client_id is not None else os.getenv("ARIA_FHIR_CLIENT_ID", patient_fhir_query.CLIENT_ID)
    client_secret = (
        args.client_secret
        if args.client_secret is not None
        else os.getenv("ARIA_FHIR_CLIENT_SECRET", patient_fhir_query.CLIENT_SECRET)
    )
    scope = args.scope if args.scope is not None else os.getenv("ARIA_FHIR_SCOPE", patient_fhir_query.SCOPE)
    return client_id, client_secret, scope


def command_patient(args: argparse.Namespace) -> dict[str, Any]:
    return patient_fhir_query.query_patients(
        identifier=args.identifier,
        fhir_id=args.fhir_id,
        name_or_identifier=args.name_or_identifier,
        family=args.family,
        given=args.given,
        birthdate=args.birthdate,
        active=args.active,
        test_patient=args.test_patient,
        count=args.count,
        allow_broad=args.allow_broad,
        raw=args.raw,
        redact=args.redact,
        include_http=args.include_http,
        client_id=args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
    )


def command_journal(args: argparse.Namespace) -> dict[str, Any]:
    return journal_notes_fhir_fallback.fetch_journal_notes(
        patient_identifier=args.patient,
        timestamp=args.timestamp,
        client_id=args.client_id,
        client_secret=args.client_secret,
        scope=args.scope,
        redact=args.redact,
    )


def command_token(args: argparse.Namespace) -> dict[str, Any]:
    client_id, client_secret, scope = effective_auth(args)
    access_token, http = patient_fhir_query.get_token(client_id, client_secret, scope)
    result = {
        "token": http["token_response"]["body"],
        "token_request": http["token_request"],
        "token_response_headers": http["token_response"]["headers"],
    }
    if args.show_token:
        result["token"]["access_token"] = access_token
    return result


def metadata_summary(payload: dict[str, Any], resource_filter: str = "", include_search_params: bool = False) -> dict[str, Any]:
    resources = []
    wanted = resource_filter.strip().lower()
    for rest in payload.get("rest") or []:
        for resource in rest.get("resource") or []:
            resource_type = str(resource.get("type") or "")
            if wanted and resource_type.lower() != wanted:
                continue
            item: dict[str, Any] = {
                "type": resource_type,
                "interaction": [entry.get("code", "") for entry in resource.get("interaction") or []],
            }
            if include_search_params:
                item["searchParams"] = [
                    {"name": sp.get("name", ""), "type": sp.get("type", "")}
                    for sp in resource.get("searchParam") or []
                ]
            resources.append(item)
    return {
        "resourceType": payload.get("resourceType", ""),
        "fhirVersion": payload.get("fhirVersion", ""),
        "software": (payload.get("software") or {}).get("name", ""),
        "resource_count": len(resources),
        "resources": resources,
    }


def command_metadata(args: argparse.Namespace) -> dict[str, Any]:
    client_id, client_secret, scope = effective_auth(args)
    access_token, token_http = patient_fhir_query.get_token(client_id, client_secret, scope)
    url = f"{patient_fhir_query.FHIR_BASE_URL.rstrip('/')}/metadata"
    request_info = {
        "method": "GET",
        "url": url,
        "params": {"_format": "json"},
        "headers": {"Authorization": "Bearer <redacted>", "Accept": "application/fhir+json"},
    }
    response = requests.get(
        url,
        params={"_format": "json"},
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/fhir+json"},
        timeout=60,
        verify=patient_fhir_query.VERIFY_TLS,
    )
    payload = patient_fhir_query.safe_json_or_text(response)
    result: dict[str, Any] = {
        "metadata": metadata_summary(payload, args.resource, args.search_params) if isinstance(payload, dict) else payload
    }
    if args.include_http:
        result["http"] = {
            **token_http,
            "metadata_request": request_info,
            "metadata_response": {
                "http_status": response.status_code,
                "ok": response.ok,
                "final_url": response.url,
                "headers": patient_fhir_query.redacted_headers(response.headers),
            },
        }
    if not response.ok:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode == "patient":
        return command_patient(args)
    if args.mode == "journal":
        return command_journal(args)
    if args.mode == "token":
        return command_token(args)
    if args.mode == "metadata":
        return command_metadata(args)
    raise ValueError(f"Unbekannter Modus: {args.mode}")


def write_or_print(result: dict[str, Any], output_path: str = "") -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    result = run(args)
    write_or_print(result, getattr(args, "out", ""))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        raise SystemExit(1)
