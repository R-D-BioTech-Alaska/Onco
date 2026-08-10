"""Small WSGI API for the OncoForge website portal.

The API keeps web transport separate from the simulation core. Website account
handling stays in the website; authenticated server-side requests call this
application with a private OncoForge API key.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple
from uuid import uuid4
from wsgiref.simple_server import make_server

from .core.cancer_profiles import SCOPE_NOTICE, find_cancer_profile, load_cancer_profiles
from .core.portal_mission import PORTAL_PAYLOAD_VERSION, PortalMissionConfig, build_portal_mission


API_VERSION = "oncoforge.api.v1"
API_PREFIX = "/lab/oncoforge/api"
MISSION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
LOG = logging.getLogger("oncoforge.web_api")


@dataclass(frozen=True)
class PortalAPILimits:
    max_body_bytes: int = 65536
    max_steps: int = 1000
    max_healthy_cells: int = 5000
    max_cancer_cells: int = 2500
    max_total_cells: int = 6000
    max_cell_steps: int = 1500000
    max_auto_experiments: int = 25
    max_qsa_candidates: int = 24
    max_marker_qubits: int = 24
    max_component_states: int = 20000

    def to_dict(self) -> Dict[str, int]:
        return {
            "max_body_bytes": self.max_body_bytes,
            "max_steps": self.max_steps,
            "max_healthy_cells": self.max_healthy_cells,
            "max_cancer_cells": self.max_cancer_cells,
            "max_total_cells": self.max_total_cells,
            "max_cell_steps": self.max_cell_steps,
            "max_auto_experiments": self.max_auto_experiments,
            "max_qsa_candidates": self.max_qsa_candidates,
            "max_marker_qubits": self.max_marker_qubits,
            "max_component_states": self.max_component_states,
        }


@dataclass(frozen=True)
class PortalAPIConfig:
    api_key: str
    output_dir: Path
    allowed_origins: Tuple[str, ...] = ()
    limits: PortalAPILimits = PortalAPILimits()

    @classmethod
    def from_env(cls) -> "PortalAPIConfig":
        origins = tuple(
            item.strip().rstrip("/")
            for item in os.environ.get("ONCOFORGE_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        )
        return cls(
            api_key=os.environ.get("ONCOFORGE_API_KEY", "").strip(),
            output_dir=Path(os.environ.get("ONCOFORGE_OUTPUT_DIR", "outputs/web_api")),
            allowed_origins=origins,
        )


class PortalRequestError(ValueError):
    def __init__(self, message: str, status: str = "400 Bad Request") -> None:
        super().__init__(message)
        self.status = status


def _as_int(payload: Dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise PortalRequestError(f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise PortalRequestError(f"{key} must be an integer") from exc


def _as_float(payload: Dict[str, Any], key: str, default: float | None) -> float | None:
    value = payload.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool):
        raise PortalRequestError(f"{key} must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise PortalRequestError(f"{key} must be a number") from exc


def _as_bool(payload: Dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise PortalRequestError(f"{key} must be true or false")
    return value


def validate_portal_payload(payload: Dict[str, Any], limits: PortalAPILimits) -> Dict[str, Any]:
    allowed = {
        "profile",
        "cocktail",
        "steps",
        "healthy",
        "cancer",
        "seed",
        "profile_strength",
        "profile_heterogeneity",
        "immune_pressure",
        "mutation_rate",
        "run_simulation",
        "auto_select_cocktail",
        "include_qsa",
        "include_research_loop_plan",
        "max_auto_experiments",
        "max_qsa_candidates",
        "max_marker_qubits",
        "max_component_states",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise PortalRequestError("Unknown fields: " + ", ".join(unknown))

    profile = str(payload.get("profile", "")).strip()
    cocktail = str(payload.get("cocktail", "")).strip()
    if not profile or len(profile) > 120:
        raise PortalRequestError("profile is required and must be 120 characters or fewer")
    if len(cocktail) > 200:
        raise PortalRequestError("cocktail must be 200 characters or fewer")

    clean: Dict[str, Any] = {
        "profile": profile,
        "cocktail": cocktail,
        "steps": _as_int(payload, "steps", 120),
        "healthy": _as_int(payload, "healthy", 300),
        "cancer": _as_int(payload, "cancer", 100),
        "seed": _as_int(payload, "seed", 1729),
        "profile_strength": _as_float(payload, "profile_strength", 1.0),
        "profile_heterogeneity": _as_float(payload, "profile_heterogeneity", 0.15),
        "immune_pressure": _as_float(payload, "immune_pressure", None),
        "mutation_rate": _as_float(payload, "mutation_rate", None),
        "run_simulation": _as_bool(payload, "run_simulation", True),
        "auto_select_cocktail": _as_bool(payload, "auto_select_cocktail", True),
        "include_qsa": _as_bool(payload, "include_qsa", True),
        "include_research_loop_plan": _as_bool(payload, "include_research_loop_plan", True),
        "max_auto_experiments": _as_int(payload, "max_auto_experiments", 5),
        "max_qsa_candidates": _as_int(payload, "max_qsa_candidates", 12),
        "max_marker_qubits": _as_int(payload, "max_marker_qubits", 16),
        "max_component_states": _as_int(payload, "max_component_states", 4096),
    }

    bounded = [
        ("steps", clean["steps"], 1, limits.max_steps),
        ("healthy", clean["healthy"], 0, limits.max_healthy_cells),
        ("cancer", clean["cancer"], 0, limits.max_cancer_cells),
        ("max_auto_experiments", clean["max_auto_experiments"], 1, limits.max_auto_experiments),
        ("max_qsa_candidates", clean["max_qsa_candidates"], 1, limits.max_qsa_candidates),
        ("max_marker_qubits", clean["max_marker_qubits"], 1, limits.max_marker_qubits),
        ("max_component_states", clean["max_component_states"], 1, limits.max_component_states),
    ]
    for name, value, minimum, maximum in bounded:
        if not minimum <= value <= maximum:
            raise PortalRequestError(f"{name} must be between {minimum} and {maximum}", "422 Unprocessable Entity")

    total_cells = clean["healthy"] + clean["cancer"]
    if total_cells > limits.max_total_cells:
        raise PortalRequestError(
            f"healthy plus cancer cells cannot exceed {limits.max_total_cells}",
            "422 Unprocessable Entity",
        )
    if total_cells * clean["steps"] > limits.max_cell_steps:
        raise PortalRequestError(
            f"cell-step workload cannot exceed {limits.max_cell_steps}",
            "422 Unprocessable Entity",
        )
    if not -(2**31) <= clean["seed"] < 2**31:
        raise PortalRequestError("seed must fit a signed 32-bit integer", "422 Unprocessable Entity")

    for name in ("profile_strength", "profile_heterogeneity", "immune_pressure"):
        value = clean[name]
        if value is not None and not 0.0 <= value <= 1.0:
            raise PortalRequestError(f"{name} must be between 0 and 1", "422 Unprocessable Entity")
    if clean["mutation_rate"] is not None and not 0.0 <= clean["mutation_rate"] <= 10.0:
        raise PortalRequestError("mutation_rate must be between 0 and 10", "422 Unprocessable Entity")

    try:
        find_cancer_profile(profile)
    except ValueError as exc:
        raise PortalRequestError(str(exc), "422 Unprocessable Entity") from exc
    return clean


def _public_mission(mission: Dict[str, Any], mission_id: str) -> Dict[str, Any]:
    payload = json.loads(json.dumps(mission))
    payload.pop("mission_path", None)
    config = payload.get("config") or {}
    config.pop("output_dir", None)
    payload["config"] = config
    simulation = payload.get("simulation") or {}
    simulation.pop("experiment_path", None)
    payload["simulation"] = simulation
    loop_plan = payload.get("research_loop_plan") or {}
    loop_plan.pop("output_dir", None)
    payload["research_loop_plan"] = loop_plan
    payload["mission_id"] = mission_id
    payload["report_id"] = mission_id
    return payload


class PortalAPI:
    def __init__(self, config: PortalAPIConfig) -> None:
        self.config = config

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        try:
            return self._dispatch(environ, start_response)
        except PortalRequestError as exc:
            return self._json(start_response, exc.status, {"ok": False, "error": str(exc)}, environ)
        except Exception:
            LOG.exception("Unhandled OncoForge API error")
            return self._json(
                start_response,
                "500 Internal Server Error",
                {"ok": False, "error": "The mission could not be completed."},
                environ,
            )

    def _dispatch(self, environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if path.startswith(API_PREFIX):
            path = path[len(API_PREFIX):] or "/"

        if method == "OPTIONS":
            return self._empty(start_response, "204 No Content", environ)
        if method == "GET" and path == "/health":
            return self._json(
                start_response,
                "200 OK",
                {
                    "ok": True,
                    "service": "OncoForge portal API",
                    "api_version": API_VERSION,
                    "payload_version": PORTAL_PAYLOAD_VERSION,
                    "mission_auth_configured": bool(self.config.api_key),
                    "limits": self.config.limits.to_dict(),
                    "scope_notice": SCOPE_NOTICE,
                },
                environ,
            )
        if method == "GET" and path == "/profiles":
            profiles = [
                {
                    "id": profile.id,
                    "display_name": profile.display_name,
                    "category": profile.category,
                    "description": profile.description,
                    "evidence_label": profile.evidence_label,
                    "tags": profile.tags,
                }
                for profile in load_cancer_profiles()
            ]
            return self._json(
                start_response,
                "200 OK",
                {"ok": True, "profiles": profiles, "scope_notice": SCOPE_NOTICE},
                environ,
            )
        if method == "GET" and path.startswith("/profiles/"):
            try:
                profile = find_cancer_profile(path.rsplit("/", 1)[-1])
            except ValueError as exc:
                raise PortalRequestError(str(exc), "404 Not Found") from exc
            return self._json(
                start_response,
                "200 OK",
                {"ok": True, "profile": profile.to_dict()},
                environ,
            )
        if method == "POST" and path == "/portal/missions":
            self._require_auth(environ)
            return self._create_mission(environ, start_response)
        if method == "GET" and path.startswith("/portal/missions/"):
            self._require_auth(environ)
            mission_id = path.rsplit("/", 1)[-1]
            return self._get_mission(mission_id, environ, start_response)
        raise PortalRequestError("Endpoint not found", "404 Not Found")

    def _require_auth(self, environ: Dict[str, Any]) -> None:
        if not self.config.api_key:
            raise PortalRequestError("ONCOFORGE_API_KEY is not configured", "503 Service Unavailable")
        authorization = str(environ.get("HTTP_AUTHORIZATION", ""))
        bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        supplied = bearer or str(environ.get("HTTP_X_ONCOFORGE_KEY", ""))
        if not supplied or not hmac.compare_digest(supplied, self.config.api_key):
            raise PortalRequestError("Unauthorized", "401 Unauthorized")

    def _read_json(self, environ: Dict[str, Any]) -> Dict[str, Any]:
        content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise PortalRequestError("Content-Type must be application/json", "415 Unsupported Media Type")
        raw_length = str(environ.get("CONTENT_LENGTH", "")).strip()
        if not raw_length:
            raise PortalRequestError("Content-Length is required", "411 Length Required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise PortalRequestError("Invalid Content-Length") from exc
        if length < 1 or length > self.config.limits.max_body_bytes:
            raise PortalRequestError(
                f"Request body must be between 1 and {self.config.limits.max_body_bytes} bytes",
                "413 Payload Too Large",
            )
        body = environ["wsgi.input"].read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PortalRequestError("Request body must contain valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise PortalRequestError("Request JSON must be an object")
        return payload

    def _create_mission(self, environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        clean = validate_portal_payload(self._read_json(environ), self.config.limits)
        mission_id = uuid4().hex
        mission_dir = self.config.output_dir / mission_id
        clean["output_dir"] = str(mission_dir)
        mission = build_portal_mission(PortalMissionConfig.from_dict(clean))
        public = _public_mission(mission, mission_id)
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "response.json").write_text(
            json.dumps(public, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self._json(start_response, "201 Created", public, environ)

    def _get_mission(
        self,
        mission_id: str,
        environ: Dict[str, Any],
        start_response: Callable,
    ) -> Iterable[bytes]:
        if not MISSION_ID_PATTERN.fullmatch(mission_id):
            raise PortalRequestError("Invalid mission id", "404 Not Found")
        path = self.config.output_dir / mission_id / "response.json"
        if not path.is_file():
            raise PortalRequestError("Mission not found", "404 Not Found")
        return self._json(start_response, "200 OK", json.loads(path.read_text(encoding="utf-8")), environ)

    def _cors_headers(self, environ: Dict[str, Any]) -> List[Tuple[str, str]]:
        origin = str(environ.get("HTTP_ORIGIN", "")).rstrip("/")
        headers = [
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        if origin and origin in self.config.allowed_origins:
            headers.extend(
                [
                    ("Access-Control-Allow-Origin", origin),
                    ("Access-Control-Allow-Headers", "Authorization, Content-Type, X-OncoForge-Key"),
                    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                    ("Vary", "Origin"),
                ]
            )
        return headers

    def _json(
        self,
        start_response: Callable,
        status: str,
        payload: Dict[str, Any],
        environ: Dict[str, Any],
    ) -> Iterable[bytes]:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            *self._cors_headers(environ),
        ]
        start_response(status, headers)
        return [body]

    def _empty(self, start_response: Callable, status: str, environ: Dict[str, Any]) -> Iterable[bytes]:
        start_response(status, [("Content-Length", "0"), *self._cors_headers(environ)])
        return [b""]


def serve(host: str = "127.0.0.1", port: int = 8765, config: PortalAPIConfig | None = None) -> None:
    app = PortalAPI(config or PortalAPIConfig.from_env())
    with make_server(host, int(port), app) as server:
        print(f"OncoForge API listening on http://{host}:{int(port)}{API_PREFIX}/health")
        if not app.config.api_key:
            print("Mission requests are disabled until ONCOFORGE_API_KEY is set.")
        server.serve_forever()


application = PortalAPI(PortalAPIConfig.from_env())
