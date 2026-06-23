from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Literal

import requests
import urllib3
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
SETTINGS_PATH = ROOT / "settings.json"
LOCAL_SETTINGS_PATH = ROOT / "settings.local.json"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


DEFAULT_SETTINGS: dict[str, Any] = {
    "app_name": "ARIA FHIR Tester",
    "host": "127.0.0.1",
    "port": 8012,
    "token_url": "",
    "fhir_base_url": "",
    "client_id": "",
    "client_id_env": "ARIA_FHIR_CLIENT_ID",
    "client_secret_env": "ARIA_FHIR_CLIENT_SECRET",
    "default_scope": "system/Appointment.cruds system/DocumentReference.cruds system/Patient.rs system/Organization.rs system/ValueSet.rs",
    "resource_scope_presets": {},
    "organization_names": [],
    "document_type_valueset_url": "http://varian.com/fhir/ValueSet/documentreference-type",
    "write_confirmation_phrase": "LIVE",
    "verify_tls": False,
    "request_timeout_seconds": 60,
    "max_response_chars": 500000,
}


def load_settings() -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    for settings_path in (SETTINGS_PATH, LOCAL_SETTINGS_PATH):
        if not settings_path.exists():
            continue
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{settings_path.name} ist kein gueltiges JSON: {exc}") from exc
        settings.update(loaded)
    return settings


def save_settings(settings_update: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    forbidden = {"client_secret", "access_token", "password"}
    for key in list(settings_update):
        if key.lower() in forbidden or "secret" in key.lower() and key != "client_secret_env":
            settings_update.pop(key, None)
    current.update(settings_update)
    LOCAL_SETTINGS_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return current


def public_settings() -> dict[str, Any]:
    settings = load_settings()
    client_id_env = str(settings.get("client_id_env") or "")
    secret_env = str(settings.get("client_secret_env") or "")
    client_id_from_env = os.getenv(client_id_env, "") if client_id_env else ""
    return {
        **settings,
        "client_id_effective": client_id_from_env or settings.get("client_id", ""),
        "client_secret_available_from_env": bool(secret_env and os.getenv(secret_env)),
        "client_secret": "",
    }


def _client_id(settings: dict[str, Any]) -> str:
    env_name = str(settings.get("client_id_env") or "")
    return (os.getenv(env_name, "") if env_name else "") or str(settings.get("client_id") or "")


def _client_secret(settings: dict[str, Any], supplied_secret: str = "") -> str:
    if supplied_secret:
        return supplied_secret
    env_name = str(settings.get("client_secret_env") or "")
    return os.getenv(env_name, "") if env_name else ""


def _verify_tls(settings: dict[str, Any]) -> bool:
    return bool(settings.get("verify_tls", False))


def _timeout(settings: dict[str, Any]) -> int:
    try:
        return int(settings.get("request_timeout_seconds", 60))
    except (TypeError, ValueError):
        return 60


def _required_setting(settings: dict[str, Any], key: str, label: str) -> str:
    value = str(settings.get(key) or "").strip()
    if not value:
        raise HTTPException(
            status_code=400,
            detail=f"{label} fehlt. Setze {key} lokal in settings.local.json, UI oder Umgebung.",
        )
    return value


def _json_or_text(response: requests.Response, max_chars: int) -> dict[str, Any]:
    text = response.text or ""
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    try:
        payload = json.loads(text) if text else None
        return {"json": payload, "text": "", "truncated": truncated}
    except json.JSONDecodeError:
        return {"json": None, "text": text, "truncated": truncated}


def token_response(scope: str, client_secret: str = "") -> tuple[dict[str, Any], str]:
    settings = load_settings()
    client_id = _client_id(settings)
    secret = _client_secret(settings, client_secret)
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="Client ID fehlt. Setze sie in settings.json oder ueber ARIA_FHIR_CLIENT_ID.",
        )
    if not secret:
        raise HTTPException(
            status_code=400,
            detail=(
                "Client Secret fehlt. Gib es im Tester ein oder setze die Umgebungsvariable "
                f"{settings.get('client_secret_env', 'ARIA_FHIR_CLIENT_SECRET')}."
            ),
        )

    requested_scope = scope.strip() or str(settings.get("default_scope") or "").strip()
    token_url = _required_setting(settings, "token_url", "Token-URL")
    started = time.perf_counter()
    response = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
            "scope": requested_scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=_timeout(settings),
        verify=_verify_tls(settings),
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    body = _json_or_text(response, int(settings.get("max_response_chars", 500000)))
    public = {
        "ok": response.ok,
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "requested_scope": requested_scope,
        "token_type": "",
        "expires_in": "",
        "returned_scope": "",
        "error": "",
    }
    access_token = ""
    if response.ok and isinstance(body.get("json"), dict):
        payload = body["json"]
        access_token = str(payload.get("access_token") or "")
        public.update(
            {
                "token_type": payload.get("token_type", ""),
                "expires_in": payload.get("expires_in", ""),
                "returned_scope": payload.get("scope", ""),
            }
        )
    elif isinstance(body.get("json"), dict):
        public["error"] = body["json"]
    else:
        public["error"] = body.get("text", "")
    return public, access_token


def fhir_session(scope: str, client_secret: str = "") -> tuple[requests.Session, dict[str, Any]]:
    token_public, access_token = token_response(scope, client_secret)
    if not access_token:
        raise HTTPException(status_code=401, detail={"message": "Token konnte nicht geholt werden.", "token": token_public})
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}", "Accept": "application/fhir+json"})
    return session, token_public


def relative_fhir_path(path: str) -> str:
    cleaned = (path or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="FHIR-Pfad fehlt.")
    if cleaned.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Bitte nur relative FHIR-Pfade verwenden, z.B. DocumentReference?patient=...")
    return cleaned.lstrip("/")


def require_write_confirmation(req: "FhirRequest") -> None:
    if req.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    settings = load_settings()
    phrase = str(settings.get("write_confirmation_phrase") or "LIVE")
    if not req.confirm_write or req.confirmation_phrase != phrase:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Schreib-/Loeschoperation blockiert. Aktiviere Live-Bestaetigung und gib '{phrase}' ein. "
                "Pruefe vorher Patient, Ressource, Methode und Payload."
            ),
        )


class SettingsUpdate(BaseModel):
    token_url: str | None = None
    fhir_base_url: str | None = None
    client_id: str | None = None
    default_scope: str | None = None
    verify_tls: bool | None = None
    request_timeout_seconds: int | None = None


class TokenRequest(BaseModel):
    scope: str = ""
    client_secret: str = ""


class FhirRequest(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    params: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    scope: str = ""
    client_secret: str = ""
    confirm_write: bool = False
    confirmation_phrase: str = ""


class PatientResolveRequest(BaseModel):
    patient_identifier: str = ""
    patient_fhir_id: str = ""
    scope: str = ""
    client_secret: str = ""


class DocumentTypesRequest(BaseModel):
    publisher: str = ""
    scope: str = ""
    client_secret: str = ""


app = FastAPI(title="ARIA FHIR Tester", version="0.1")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return public_settings()


@app.post("/api/settings")
def update_settings(req: SettingsUpdate) -> dict[str, Any]:
    update = {key: value for key, value in req.model_dump().items() if value is not None}
    return {**save_settings(update), "client_secret": ""}


@app.post("/api/token/test")
def test_token(req: TokenRequest) -> dict[str, Any]:
    token_public, _ = token_response(req.scope, req.client_secret)
    return token_public


@app.post("/api/fhir")
def execute_fhir(req: FhirRequest) -> dict[str, Any]:
    require_write_confirmation(req)
    settings = load_settings()
    session, token_public = fhir_session(req.scope, req.client_secret)
    method = req.method.upper()
    path = relative_fhir_path(req.path)
    base_url = _required_setting(settings, "fhir_base_url", "FHIR-Base-URL")
    url = f"{base_url.rstrip('/')}/{path}"
    headers: dict[str, str] = {}
    if method == "PATCH":
        headers["Content-Type"] = "application/json-patch+json" if isinstance(req.body, list) else "application/fhir+json"
    elif method in {"POST", "PUT"}:
        headers["Content-Type"] = "application/fhir+json"

    started = time.perf_counter()
    try:
        response = session.request(
            method,
            url,
            params={key: value for key, value in req.params.items() if value not in ("", None)},
            json=req.body if method in {"POST", "PUT", "PATCH"} else None,
            headers=headers,
            timeout=_timeout(settings),
            verify=_verify_tls(settings),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"FHIR-Aufruf fehlgeschlagen: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    body = _json_or_text(response, int(settings.get("max_response_chars", 500000)))
    return {
        "ok": response.ok,
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "method": method,
        "url": response.url,
        "token": token_public,
        "response": body,
        "headers": dict(response.headers),
    }


@app.post("/api/patient/resolve")
def resolve_patient(req: PatientResolveRequest) -> dict[str, Any]:
    if not req.patient_identifier.strip() and not req.patient_fhir_id.strip():
        raise HTTPException(status_code=400, detail="Gib sichtbare ARIA-PatID oder Patient-FHIR-ID an.")
    if req.patient_fhir_id.strip():
        path = f"Patient/{req.patient_fhir_id.strip().removeprefix('Patient/')}"
        return execute_fhir(
            FhirRequest(method="GET", path=path, scope=req.scope, client_secret=req.client_secret)
        )
    return execute_fhir(
        FhirRequest(
            method="GET",
            path="Patient",
            params={"identifier": req.patient_identifier.strip(), "_count": "5"},
            scope=req.scope,
            client_secret=req.client_secret,
        )
    )


@app.post("/api/documentreference/types")
def document_types(req: DocumentTypesRequest) -> dict[str, Any]:
    settings = load_settings()
    publisher = req.publisher.strip()
    session, token_public = fhir_session(req.scope, req.client_secret)
    base_url = _required_setting(settings, "fhir_base_url", "FHIR-Base-URL")
    if not publisher:
        org_response = session.get(
            f"{base_url.rstrip('/')}/Organization",
            params={"type": "prov", "active": "true", "_count": "10"},
            timeout=_timeout(settings),
            verify=_verify_tls(settings),
        )
        if org_response.ok:
            payload = org_response.json()
            entries = payload.get("entry") or []
            for entry in entries:
                resource = entry.get("resource") or {}
                if resource.get("id"):
                    publisher = str(resource["id"])
                    break

    params = {"url": str(settings.get("document_type_valueset_url"))}
    if publisher:
        params["publisher"] = publisher
    response = session.get(
        f"{base_url.rstrip('/')}/ValueSet/$expand",
        params=params,
        timeout=_timeout(settings),
        verify=_verify_tls(settings),
    )
    body = _json_or_text(response, int(settings.get("max_response_chars", 500000)))
    doc_types: list[dict[str, str]] = []
    payload = body.get("json")
    resources = [payload] if isinstance(payload, dict) else []
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        resources = [(entry.get("resource") or {}) for entry in payload.get("entry") or []]
    for resource in resources:
        for item in (resource.get("expansion") or {}).get("contains") or []:
            code = str(item.get("code") or "")
            display = str(item.get("display") or "")
            system = str(item.get("system") or "")
            if code and display:
                doc_types.append({"code": code, "display": display, "system": system})
    return {
        "ok": response.ok,
        "status_code": response.status_code,
        "publisher": publisher,
        "count": len(doc_types),
        "document_types": doc_types,
        "token": token_public,
        "raw": body,
    }


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "server:app",
        host=str(settings.get("host") or "127.0.0.1"),
        port=int(settings.get("port") or 8012),
        reload=False,
        access_log=False,
    )
