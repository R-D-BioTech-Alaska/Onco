"""Optional local AI connector for OncoForge.

The connector supports Ollama and OpenAI-compatible local endpoints such as LM
Studio. It is optional: normal simulator operation never depends on a local AI
server being available.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

from .cancer_profiles import SCOPE_NOTICE
from .presets import DATA_DIR


SYSTEM_PROMPT = (
    "You are assisting with OncoForge, a conceptual cancer-systems simulator. "
    "You must not provide medical advice, clinical diagnosis, treatment instructions, or patient-specific recommendations. "
    "Interpret only the simulation data provided. Clearly distinguish established biology, modeled assumptions, and speculative concepts. "
    "Suggest simulation experiments, not real-world treatment decisions."
)


@dataclass
class LocalAIConfig:
    enabled: bool = False
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1"
    temperature: float = 0.2
    max_tokens: int = 1200
    auto_analyze_after_run: bool = True
    allow_continuous_experiments: bool = False
    max_auto_experiments: int = 10
    require_user_confirmation_before_long_runs: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocalAIConfig":
        base = cls()
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        base.enabled = bool(base.enabled)
        base.provider = str(base.provider or "ollama").lower()
        base.base_url = str(base.base_url or "http://localhost:11434").rstrip("/")
        base.model = str(base.model or "llama3.1")
        base.temperature = float(base.temperature)
        base.max_tokens = int(base.max_tokens)
        base.auto_analyze_after_run = bool(base.auto_analyze_after_run)
        base.allow_continuous_experiments = bool(base.allow_continuous_experiments)
        base.max_auto_experiments = max(1, int(base.max_auto_experiments))
        base.require_user_confirmation_before_long_runs = bool(base.require_user_confirmation_before_long_runs)
        return base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_ai_config(path: Optional[str | Path] = None) -> LocalAIConfig:
    target = Path(path or DATA_DIR / "ai_assistant_config.json")
    if not target.exists():
        return LocalAIConfig()
    return LocalAIConfig.from_dict(json.loads(target.read_text(encoding="utf-8")))


def save_ai_config(config: LocalAIConfig, path: Optional[str | Path] = None) -> Path:
    target = Path(path or DATA_DIR / "ai_assistant_config.json")
    target.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return target


def _request_json(url: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 8.0) -> Dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    return json.loads(text) if text else {}


def check_local_ai_available(config: LocalAIConfig) -> Dict[str, Any]:
    try:
        if config.provider == "ollama":
            payload = _request_json(f"{config.base_url}/api/tags", timeout=4.0)
            models = [item.get("name", "") for item in payload.get("models", [])]
            return {"available": True, "provider": config.provider, "models": models, "message": "Ollama responded."}
        payload = _request_json(f"{config.base_url}/v1/models", timeout=4.0)
        models = [item.get("id", "") for item in payload.get("data", [])]
        return {"available": True, "provider": config.provider, "models": models, "message": "OpenAI-compatible endpoint responded."}
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "provider": config.provider,
            "models": [],
            "message": f"Local AI endpoint is not available: {exc}",
        }


def build_simulation_summary(sim: Any, signal_result: Optional[Dict[str, Any]] = None, recommendation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    latest = sim.analytics.latest() if hasattr(sim, "analytics") else None
    return {
        "scope_notice": SCOPE_NOTICE,
        "config": sim.config.to_dict() if hasattr(sim, "config") else {},
        "latest_metrics": latest.to_dict() if latest else {},
        "dosing_state": sim.dosing_state.to_dict() if hasattr(sim, "dosing_state") else {},
        "cancer_profile": getattr(sim, "cancer_profile", {}),
        "signal_interpretation": signal_result or {},
        "cocktail_recommendation": recommendation or {},
    }


def _validate_ai_text(text: str) -> Dict[str, Any]:
    lower = text.lower()
    has_safety = "not medical advice" in lower or "conceptual" in lower
    unsafe_markers = ["you should take", "patient should take", "prescribe", "clinical dose", "cures cancer"]
    unsafe = [marker for marker in unsafe_markers if marker in lower]
    if not has_safety:
        text = SCOPE_NOTICE + "\n\n" + text
    return {"text": text, "has_safety_disclaimer": has_safety, "unsafe_phrases": unsafe}


def ask_local_ai(config: LocalAIConfig, user_payload: Dict[str, Any], task: str = "Analyze this OncoForge simulation.") -> Dict[str, Any]:
    if not config.enabled:
        return {"ok": False, "response": "", "message": "Local AI is disabled in configuration."}
    availability = check_local_ai_available(config)
    if not availability.get("available"):
        return {"ok": False, "response": "", "message": availability.get("message", "Local AI unavailable.")}

    prompt = task + "\n\nSimulation payload:\n" + json.dumps(user_payload, indent=2, sort_keys=True)
    try:
        if config.provider == "ollama":
            payload = {
                "model": config.model,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": config.temperature, "num_predict": config.max_tokens},
            }
            raw = _request_json(f"{config.base_url}/api/generate", payload, timeout=60.0)
            text = str(raw.get("response", ""))
        else:
            payload = {
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            }
            raw = _request_json(f"{config.base_url}/v1/chat/completions", payload, timeout=60.0)
            text = str(raw.get("choices", [{}])[0].get("message", {}).get("content", ""))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
        return {"ok": False, "response": "", "message": f"Local AI request failed gracefully: {exc}"}
    validated = _validate_ai_text(text)
    return {
        "ok": True,
        "response": validated["text"],
        "message": "Local AI response received.",
        "has_safety_disclaimer": validated["has_safety_disclaimer"],
        "unsafe_phrases": validated["unsafe_phrases"],
        "system_prompt": SYSTEM_PROMPT,
    }


def analyze_experiment_with_ai(config: LocalAIConfig, sim: Any, signal_result: Optional[Dict[str, Any]] = None, recommendation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    summary = build_simulation_summary(sim, signal_result, recommendation)
    return ask_local_ai(
        config,
        summary,
        task=(
            "Summarize the OncoForge simulation, identify modeled marker/cocktail lessons, "
            "and suggest safe next simulation experiments only."
        ),
    )


def suggest_next_experiment(config: LocalAIConfig, summary: Dict[str, Any]) -> Dict[str, Any]:
    return ask_local_ai(
        config,
        summary,
        task=(
            "Suggest one bounded next OncoForge simulation. Allowed suggestions: profile, cocktail, steps, seed, "
            "adaptive dosing settings, treatment multiplier, or a parameter sweep. Do not suggest real medical action."
        ),
    )
