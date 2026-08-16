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
from .core.evidence import EvidenceFabric
from .core.target_forge import TargetForgeConfig, run_target_forge


API_VERSION = "oncoforge.api.v1"
API_PREFIX = "/lab/oncoforge/api"
MISSION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
LOG = logging.getLogger("oncoforge.web_api")


@dataclass(frozen=True)
class PortalAPILimits:
    max_body_bytes: int = 65536
    max_target_forge_body_bytes: int = 2097152
    max_steps: int = 1000
    max_healthy_cells: int = 5000
    max_cancer_cells: int = 2500
    max_total_cells: int = 6000
    max_cell_steps: int = 1500000
    max_auto_experiments: int = 25
    max_qsa_candidates: int = 24
    max_marker_qubits: int = 24
    max_component_states: int = 20000
    max_evidence_entities: int = 5000
    max_evidence_assertions: int = 100000
    max_target_forge_samples: int = 2000
    max_target_forge_input_targets: int = 256
    max_target_forge_targets: int = 24
    max_target_forge_candidates: int = 4000
    max_target_forge_results: int = 100

    def to_dict(self) -> Dict[str, int]:
        return {
            "max_body_bytes": self.max_body_bytes,
            "max_target_forge_body_bytes": self.max_target_forge_body_bytes,
            "max_steps": self.max_steps,
            "max_healthy_cells": self.max_healthy_cells,
            "max_cancer_cells": self.max_cancer_cells,
            "max_total_cells": self.max_total_cells,
            "max_cell_steps": self.max_cell_steps,
            "max_auto_experiments": self.max_auto_experiments,
            "max_qsa_candidates": self.max_qsa_candidates,
            "max_marker_qubits": self.max_marker_qubits,
            "max_component_states": self.max_component_states,
            "max_evidence_entities": self.max_evidence_entities,
            "max_evidence_assertions": self.max_evidence_assertions,
            "max_target_forge_samples": self.max_target_forge_samples,
            "max_target_forge_input_targets": self.max_target_forge_input_targets,
            "max_target_forge_targets": self.max_target_forge_targets,
            "max_target_forge_candidates": self.max_target_forge_candidates,
            "max_target_forge_results": self.max_target_forge_results,
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
        if method == "POST" and path == "/target-forge/runs":
            self._require_auth(environ)
            return self._create_target_forge_run(environ, start_response)
        if method == "GET" and path.startswith("/target-forge/runs/"):
            self._require_auth(environ)
            run_id = path.rsplit("/", 1)[-1]
            return self._get_target_forge_run(run_id, environ, start_response)
        raise PortalRequestError("Endpoint not found", "404 Not Found")

    def _require_auth(self, environ: Dict[str, Any]) -> None:
        if not self.config.api_key:
            raise PortalRequestError("ONCOFORGE_API_KEY is not configured", "503 Service Unavailable")
        authorization = str(environ.get("HTTP_AUTHORIZATION", ""))
        bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        supplied = bearer or str(environ.get("HTTP_X_ONCOFORGE_KEY", ""))
        if not supplied or not hmac.compare_digest(supplied, self.config.api_key):
            raise PortalRequestError("Unauthorized", "401 Unauthorized")

    def _read_json(self, environ: Dict[str, Any], max_bytes: int | None = None) -> Dict[str, Any]:
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
        limit = int(max_bytes or self.config.limits.max_body_bytes)
        if length < 1 or length > limit:
            raise PortalRequestError(
                f"Request body must be between 1 and {limit} bytes",
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

    def _create_target_forge_run(
        self,
        environ: Dict[str, Any],
        start_response: Callable,
    ) -> Iterable[bytes]:
        payload = self._read_json(environ, self.config.limits.max_target_forge_body_bytes)
        unknown = sorted(set(payload) - {"evidence", "config"})
        if unknown:
            raise PortalRequestError("Unknown fields: " + ", ".join(unknown))
        evidence_data = payload.get("evidence")
        config_data = payload.get("config", {})
        if not isinstance(evidence_data, dict):
            raise PortalRequestError("evidence must be an object")
        if not isinstance(config_data, dict):
            raise PortalRequestError("config must be an object")
        allowed_config = set(TargetForgeConfig().__dict__)
        unknown_config = sorted(set(config_data) - allowed_config)
        if unknown_config:
            raise PortalRequestError("Unknown config fields: " + ", ".join(unknown_config))

        entities = evidence_data.get("entities", [])
        assertions = evidence_data.get("assertions", [])
        if not isinstance(entities, list) or not isinstance(assertions, list):
            raise PortalRequestError("evidence entities and assertions must be arrays")
        limits = self.config.limits
        if len(entities) > limits.max_evidence_entities:
            raise PortalRequestError("evidence entity limit exceeded", "422 Unprocessable Entity")
        if len(assertions) > limits.max_evidence_assertions:
            raise PortalRequestError("evidence assertion limit exceeded", "422 Unprocessable Entity")
        sample_count = sum(
            1 for row in entities if isinstance(row, dict) and row.get("kind") == "Sample"
        )
        if sample_count > limits.max_target_forge_samples:
            raise PortalRequestError("target-forge sample limit exceeded", "422 Unprocessable Entity")
        target_count = sum(
            1
            for row in entities
            if isinstance(row, dict)
            and row.get("kind") in {"Gene", "Protein", "ProteinSurfaceTarget", "Receptor"}
        )
        if target_count > limits.max_target_forge_input_targets:
            raise PortalRequestError("target-forge input target limit exceeded", "422 Unprocessable Entity")

        for key in (
            "require_dependency",
            "require_critical_normal_samples",
            "allow_transcript_fallback",
            "include_single_targets",
            "include_and",
            "include_or",
            "include_and_not",
            "use_qsa",
        ):
            if key in config_data and not isinstance(config_data[key], bool):
                raise PortalRequestError(f"config.{key} must be true or false")
        clean_config = dict(config_data)
        clean_config.setdefault("qsa_max_logical_states", limits.max_component_states)
        try:
            config = TargetForgeConfig.from_dict(clean_config)
        except (TypeError, ValueError) as exc:
            raise PortalRequestError(str(exc), "422 Unprocessable Entity") from exc
        bounded = (
            ("max_targets", config.max_targets, limits.max_target_forge_targets),
            ("max_candidates", config.max_candidates, limits.max_target_forge_candidates),
            ("max_results", config.max_results, limits.max_target_forge_results),
            ("qsa_max_logical_states", config.qsa_max_logical_states, limits.max_component_states),
        )
        for name, value, maximum in bounded:
            if value > maximum:
                raise PortalRequestError(
                    f"config.{name} cannot exceed {maximum}",
                    "422 Unprocessable Entity",
                )
        try:
            fabric = EvidenceFabric.from_dict(evidence_data)
            report = run_target_forge(fabric, config)
        except (TypeError, ValueError) as exc:
            raise PortalRequestError(str(exc), "422 Unprocessable Entity") from exc

        run_id = uuid4().hex
        public = {"ok": True, "run_id": run_id, "report": report}
        run_dir = self.config.output_dir / "target_forge" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "response.json").write_text(
            json.dumps(public, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self._json(start_response, "201 Created", public, environ)

    def _get_target_forge_run(
        self,
        run_id: str,
        environ: Dict[str, Any],
        start_response: Callable,
    ) -> Iterable[bytes]:
        if not MISSION_ID_PATTERN.fullmatch(run_id):
            raise PortalRequestError("Invalid target-forge run id", "404 Not Found")
        path = self.config.output_dir / "target_forge" / run_id / "response.json"
        if not path.is_file():
            raise PortalRequestError("Target-forge run not found", "404 Not Found")
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
