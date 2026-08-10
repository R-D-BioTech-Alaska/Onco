"""Conceptual treatment/cocktail matching for OncoForge.

Recommendations rank simulation cocktails by marker fit, selectivity, healthy
overlap risk, escape coverage, evidence label, and remission suitability. They
are not medical recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Set

from .cancer_profiles import CancerProfile, SCOPE_NOTICE, find_cancer_profile
from .constants import EVIDENCE_LABEL_TO_LEVEL
from .models import BioAgent, Cocktail
from .presets import default_cocktails, load_agents
from .signal_interpreter import SIGNAL_GROUPS, analyze_signals
from .utils import clamp


SURVEILLANCE_ACTIONS = {
    "repair_dna",
    "cell_cycle_arrest",
    "increase_senescence",
    "immune_marking",
    "restore_mhc",
    "block_pd_l1",
    "reduce_proliferation",
}


@dataclass
class CocktailRecommendation:
    cocktail_name: str
    score: float
    rank_type: str
    dominant_signal_coverage: float
    cancer_specific_signal_coverage: float
    escape_signal_coverage: float
    immune_evasion_coverage: float
    apoptosis_resistance_coverage: float
    DNA_repair_defect_coverage: float
    metabolic_stress_coverage: float
    healthy_overlap_penalty: float
    inflammation_risk_penalty: float
    broadness_penalty: float
    evidence_weighting: float
    remission_suitability: float
    predicted_selectivity: float
    reason: str
    matched_signals: List[str]
    agents: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _signal_names(rows: Iterable[Dict[str, Any]], limit: int = 10) -> Set[str]:
    return {str(row.get("signal", "")) for row in list(rows)[:limit] if row.get("signal")}


def _agent_targets(cocktail: Cocktail) -> Set[str]:
    targets: Set[str] = set()
    for agent in cocktail.agents:
        targets.update(agent.targets)
    return targets


def _coverage(targets: Set[str], signals: Set[str]) -> float:
    if not signals:
        return 0.0
    return len(targets & signals) / len(signals)


def _evidence_weight(agents: Iterable[BioAgent]) -> float:
    rows = list(agents)
    if not rows:
        return 0.0
    scores = []
    for agent in rows:
        # Lower evidence level is stronger. Convert to 0-1 with cautious ceiling.
        level = int(agent.evidence_level)
        scores.append(clamp((6 - level) / 5.0))
    return sum(scores) / len(scores)


def _remission_suitability(cocktail: Cocktail) -> float:
    if not cocktail.agents:
        return 0.0
    agent_scores = []
    for agent in cocktail.agents:
        action_set = set(agent.actions)
        safe_action_fit = 1.0 if action_set and action_set <= SURVEILLANCE_ACTIONS else 0.35
        agent_scores.append(clamp(agent.specificity * 0.45 + (1.0 - agent.healthy_cell_risk) * 0.35 + safe_action_fit * 0.20))
    return sum(agent_scores) / len(agent_scores)


def _risk_values(cocktail: Cocktail, interpretation: Dict[str, Any]) -> tuple[float, float, float, float]:
    agent_count = max(1, len(cocktail.agents))
    mean_healthy_risk = sum(agent.healthy_cell_risk for agent in cocktail.agents) / agent_count
    inflammation_actions = {"increase_inflammation", "sting_interferon_signal", "activate_complement", "increase_tcell_kill", "increase_nk_kill"}
    inflammation_risk = sum(0.16 for agent in cocktail.agents if set(agent.actions) & inflammation_actions)
    broadness = clamp((agent_count - 3) / 8.0)
    target_overlap = set()
    for row in interpretation.get("misleading_signals", []):
        target_overlap.add(row.get("signal"))
    overlap = len(_agent_targets(cocktail) & target_overlap) / max(1, len(_agent_targets(cocktail)))
    healthy_overlap_penalty = clamp(mean_healthy_risk * 0.55 + overlap * 0.45)
    return healthy_overlap_penalty, clamp(inflammation_risk), broadness, mean_healthy_risk


def rank_cocktails(
    interpretation: Dict[str, Any],
    *,
    cocktails: Optional[Iterable[Cocktail]] = None,
    preferred_cocktails: Optional[Iterable[str]] = None,
) -> List[CocktailRecommendation]:
    cocktail_list = list(cocktails or default_cocktails())
    preferred = {str(name).lower() for name in (preferred_cocktails or [])}
    dominant = _signal_names(interpretation.get("top_dominant_signals", []), 10)
    specific = _signal_names(interpretation.get("cancer_specific_signals", []), 10)
    escape = _signal_names(interpretation.get("escape_warnings", []), 8)
    immune = _signal_names(interpretation.get("immune_evasion_signals", []), 8)
    apoptosis = _signal_names(interpretation.get("apoptosis_resistance_signals", []), 8)
    repair = _signal_names(interpretation.get("DNA_repair_defect_signals", []), 8)
    metabolic = _signal_names(interpretation.get("metabolic_stress_signals", []), 8)

    rows: List[CocktailRecommendation] = []
    for cocktail in cocktail_list:
        targets = _agent_targets(cocktail)
        dom_cov = _coverage(targets, dominant)
        spec_cov = _coverage(targets, specific)
        escape_cov = _coverage(targets, escape)
        immune_cov = _coverage(targets, immune)
        apoptosis_cov = _coverage(targets, apoptosis)
        repair_cov = _coverage(targets, repair)
        metabolic_cov = _coverage(targets, metabolic)
        healthy_penalty, inflammation_penalty, broad_penalty, mean_healthy_risk = _risk_values(cocktail, interpretation)
        evidence = _evidence_weight(cocktail.agents)
        remission = _remission_suitability(cocktail)
        specificity = sum(agent.specificity for agent in cocktail.agents) / max(1, len(cocktail.agents))
        predicted_selectivity = clamp(specificity * 0.55 + spec_cov * 0.30 + (1.0 - mean_healthy_risk) * 0.15 - healthy_penalty * 0.20)
        preferred_bonus = 0.08 if cocktail.name.lower() in preferred else 0.0
        score = clamp(
            dom_cov * 0.16
            + spec_cov * 0.25
            + escape_cov * 0.10
            + immune_cov * 0.10
            + apoptosis_cov * 0.08
            + repair_cov * 0.08
            + metabolic_cov * 0.06
            + evidence * 0.08
            + remission * 0.07
            + predicted_selectivity * 0.12
            + preferred_bonus
            - healthy_penalty * 0.22
            - inflammation_penalty * 0.18
            - broad_penalty * 0.18
        )
        matched = sorted(targets & (dominant | specific | escape | immune | apoptosis | repair | metabolic))
        reason = (
            f"Matches {len(matched)} current/profile signals ({', '.join(matched[:6]) or 'none'}), "
            f"selectivity {predicted_selectivity:.2f}, remission suitability {remission:.2f}, "
            f"healthy-overlap penalty {healthy_penalty:.2f}."
        )
        rows.append(
            CocktailRecommendation(
                cocktail_name=cocktail.name,
                score=score,
                rank_type="conceptual_match",
                dominant_signal_coverage=dom_cov,
                cancer_specific_signal_coverage=spec_cov,
                escape_signal_coverage=escape_cov,
                immune_evasion_coverage=immune_cov,
                apoptosis_resistance_coverage=apoptosis_cov,
                DNA_repair_defect_coverage=repair_cov,
                metabolic_stress_coverage=metabolic_cov,
                healthy_overlap_penalty=healthy_penalty,
                inflammation_risk_penalty=inflammation_penalty,
                broadness_penalty=broad_penalty,
                evidence_weighting=evidence,
                remission_suitability=remission,
                predicted_selectivity=predicted_selectivity,
                reason=reason,
                matched_signals=matched,
                agents=[agent.name for agent in cocktail.agents],
            )
        )
    rows.sort(key=lambda row: row.score, reverse=True)
    return rows


def _best_by(rows: List[CocktailRecommendation], key: str) -> Optional[CocktailRecommendation]:
    if not rows:
        return None
    return max(rows, key=lambda row: getattr(row, key))


def _agent_gate_recommendations(interpretation: Dict[str, Any]) -> List[Dict[str, Any]]:
    risky = {row.get("signal") for row in interpretation.get("misleading_signals", [])}
    out = []
    for agent in load_agents():
        targets = set(agent.targets)
        if targets & risky or agent.healthy_cell_risk >= 0.14:
            out.append(
                {
                    "agent": agent.name,
                    "reason": "High healthy overlap target or higher healthy-cell risk; use stricter gating in conceptual tests.",
                    "targets": sorted(targets),
                    "healthy_cell_risk": agent.healthy_cell_risk,
                }
            )
    out.sort(key=lambda row: row["healthy_cell_risk"], reverse=True)
    return out[:10]


def recommend_treatments(
    *,
    sim: Optional[Any] = None,
    profile: Optional[CancerProfile | str] = None,
    interpretation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if interpretation is None:
        if sim is None:
            raise ValueError("Either sim or interpretation is required.")
        interpretation = analyze_signals(sim, profile)
    if isinstance(profile, str):
        profile_obj = find_cancer_profile(profile)
        profile_payload = profile_obj.to_dict()
    elif isinstance(profile, CancerProfile):
        profile_obj = profile
        profile_payload = profile.to_dict()
    else:
        profile_obj = None
        profile_payload = {
            "id": interpretation.get("profile_id", ""),
            "display_name": interpretation.get("profile_name", ""),
        }
    preferred_names = set(profile_obj.starter_cocktails if profile_obj else [])
    rows = rank_cocktails(interpretation, preferred_cocktails=preferred_names)
    first_line_candidates = [
        row for row in rows
        if row.broadness_penalty <= 0.25 and row.healthy_overlap_penalty <= 0.20
    ]
    if first_line_candidates:
        best = max(
            first_line_candidates,
            key=lambda row: row.score + (0.12 if row.cocktail_name in preferred_names else 0.0),
        )
    else:
        best = rows[0] if rows else None
    if best:
        rows = [best] + [row for row in rows if row.cocktail_name != best.cocktail_name]
    low_toxicity = min(rows, key=lambda row: (row.healthy_overlap_penalty + row.inflammation_risk_penalty, -row.score)) if rows else None
    anti_escape = _best_by(rows, "escape_signal_coverage")
    remission = _best_by(rows, "remission_suitability")
    emergency = max(rows, key=lambda row: (row.dominant_signal_coverage + row.apoptosis_resistance_coverage + row.metabolic_stress_coverage, row.score)) if rows else None
    avoid = _agent_gate_recommendations(interpretation)
    add_on_candidates = []
    for agent_name in interpretation.get("recommended_addon_agents", [])[:8]:
        add_on_candidates.append({"agent": agent_name, "reason": "Targets one or more top targetable or escape-associated signals."})
    return {
        "scope_notice": SCOPE_NOTICE,
        "profile": profile_payload,
        "best_first_line_conceptual_match": best.to_dict() if best else None,
        "best_low_toxicity_match": low_toxicity.to_dict() if low_toxicity else None,
        "best_anti_escape_addon": anti_escape.to_dict() if anti_escape else None,
        "best_remission_surveillance_option": remission.to_dict() if remission else None,
        "emergency_max_force_option": emergency.to_dict() if emergency else None,
        "ranked_cocktails": [row.to_dict() for row in rows],
        "recommended_addon_agents": add_on_candidates,
        "avoid_or_gate_agents": avoid,
        "plain_english_summary": format_recommendation_summary(rows, low_toxicity, anti_escape, remission, emergency),
        "limitations": [
            SCOPE_NOTICE,
            "Cocktail matching is based on simulator markers and qualitative agent metadata.",
            "Recommendations suggest simulation experiments only, not real treatment choices.",
            "Broad cocktails can rank lower when narrower cocktails cover the same cancer-specific signals with less healthy overlap.",
        ],
    }


def format_recommendation_summary(
    rows: List[CocktailRecommendation],
    low_toxicity: Optional[CocktailRecommendation],
    anti_escape: Optional[CocktailRecommendation],
    remission: Optional[CocktailRecommendation],
    emergency: Optional[CocktailRecommendation],
) -> str:
    if not rows:
        return "No cocktail recommendations are available."
    best = rows[0]
    lines = [
        SCOPE_NOTICE,
        "",
        f"Best match: {best.cocktail_name}",
        "",
        "Why:",
        f"- {best.reason}",
        f"- Cancer-specific coverage: {best.cancer_specific_signal_coverage:.2f}",
        f"- Healthy-overlap penalty: {best.healthy_overlap_penalty:.2f}",
        f"- Inflammation-risk penalty: {best.inflammation_risk_penalty:.2f}",
        "",
        "Other roles:",
    ]
    if low_toxicity:
        lines.append(f"- Best low-toxicity match: {low_toxicity.cocktail_name}")
    if anti_escape:
        lines.append(f"- Best anti-escape add-on candidate: {anti_escape.cocktail_name}")
    if remission:
        lines.append(f"- Best remission-surveillance option: {remission.cocktail_name}")
    if emergency:
        lines.append(f"- Emergency/max-force option: {emergency.cocktail_name}")
    lines.extend(
        [
            "",
            "Avoid/gate logic:",
            "- Prefer the smallest cocktail that covers cancer-specific signals.",
            "- Gate or avoid agents targeting high healthy-overlap signals.",
            "- Reserve broad cocktails for comparison or failure of narrower conceptual matches.",
        ]
    )
    return "\n".join(lines)
