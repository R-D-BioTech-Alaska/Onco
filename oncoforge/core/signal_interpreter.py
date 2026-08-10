"""Cancer-vs-healthy signal interpretation for OncoForge.

The interpreter is deliberately transparent. It computes simple signal means,
prevalence, cancer/healthy separation, and a targetability score:

targetability_score =
    cancer_mean * 0.40
  + max(cancer_mean - healthy_mean, 0) * 0.35
  + cancer_prevalence * 0.15
  - healthy_prevalence * 0.10
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

from .cancer_profiles import CancerProfile, SCOPE_NOTICE, find_cancer_profile
from .constants import SIGNALS
from .presets import default_cocktails, load_agents
from .utils import clamp

if TYPE_CHECKING:
    from .models import Cell
    from .simulation import Simulation


SIGNAL_GROUPS = {
    "escape_signals": {"MHC_LOW", "PD_L1_HIGH", "CD47_DONT_EAT_ME"},
    "immune_evasion_signals": {"MHC_LOW", "PD_L1_HIGH", "CD47_DONT_EAT_ME", "INFLAMMATION_HIGH"},
    "apoptosis_resistance_signals": {"CASPASE_BLOCKED", "P53_INACTIVE"},
    "DNA_repair_defect_signals": {"MMR_DEFECT", "BRCA_DEFECT", "PARP_DEPENDENCE", "DNA_DAMAGE_HIGH", "STING_DNA_SENSING"},
    "metabolic_stress_signals": {"HYPOXIA_HIGH", "LACTATE_HIGH", "AUTOPHAGY_DEPENDENCE", "FERROPTOSIS_SUSCEPTIBLE", "PROTEASOME_STRESS", "UNFOLDED_PROTEIN_RESPONSE"},
    "microenvironment_signals": {"HYPOXIA_HIGH", "LACTATE_HIGH", "ECM_INVASION_HIGH", "ANGIOGENESIS_SIGNAL", "INFLAMMATION_HIGH"},
}


def _mean(cells: Iterable["Cell"], signal: str) -> float:
    rows = list(cells)
    return sum(cell.signals.get(signal, 0.0) for cell in rows) / max(1, len(rows))


def _prevalence(cells: Iterable["Cell"], signal: str, threshold: float = 0.35) -> float:
    rows = list(cells)
    if not rows:
        return 0.0
    return sum(1 for cell in rows if cell.signals.get(signal, 0.0) >= threshold) / len(rows)


def _ratio(cancer_mean: float, healthy_mean: float) -> Optional[float]:
    if healthy_mean <= 1e-6:
        return None
    return cancer_mean / healthy_mean


def _profile_payload(profile: Optional[CancerProfile | Dict[str, Any] | str], sim: "Simulation") -> Dict[str, str]:
    if isinstance(profile, str):
        p = find_cancer_profile(profile)
        return {"profile_id": p.id, "profile_name": p.display_name}
    if isinstance(profile, CancerProfile):
        return {"profile_id": profile.id, "profile_name": profile.display_name}
    if isinstance(profile, dict) and profile:
        return {
            "profile_id": str(profile.get("id", "")),
            "profile_name": str(profile.get("display_name", profile.get("name", ""))),
        }
    sim_profile = getattr(sim, "cancer_profile", {}) or {}
    return {
        "profile_id": str(sim_profile.get("id", "")),
        "profile_name": str(sim_profile.get("display_name", sim.config.cancer_preset_name or "")),
    }


def _agent_recommendations(top_signal_names: List[str]) -> List[str]:
    signal_set = set(top_signal_names)
    ranked = []
    for agent in load_agents():
        targets = set(agent.targets)
        overlap = len(targets & signal_set)
        if overlap:
            ranked.append((overlap, agent.specificity, -agent.healthy_cell_risk, agent.name))
    ranked.sort(reverse=True)
    return [name for *_rest, name in ranked[:8]]


def _cocktail_recommendations(top_signal_names: List[str]) -> List[str]:
    signal_set = set(top_signal_names)
    rows = []
    for cocktail in default_cocktails():
        targets = set()
        healthy_risk = 0.0
        specificity = 0.0
        for agent in cocktail.agents:
            targets.update(agent.targets)
            healthy_risk += agent.healthy_cell_risk
            specificity += agent.specificity
        coverage = len(targets & signal_set)
        rows.append((coverage, specificity / max(1, len(cocktail.agents)), -healthy_risk / max(1, len(cocktail.agents)), cocktail.name))
    rows.sort(reverse=True)
    return [name for *_rest, name in rows[:5]]


def analyze_signals(sim: "Simulation", profile: Optional[CancerProfile | Dict[str, Any] | str] = None) -> Dict[str, Any]:
    living = [cell for cell in sim.cells if cell.alive]
    cancer = [cell for cell in living if cell.cell_kind in {"cancer", "precancerous"}]
    healthy = [cell for cell in living if cell.cell_kind == "healthy"]
    profile_info = _profile_payload(profile, sim)

    used_snapshot = False
    no_cancer_message = ""
    snapshot = {}
    if not cancer:
        snapshot = dict(getattr(sim, "marker_snapshots", {}).get("last_living_cancer", {}))
        if snapshot.get("mean_signals"):
            used_snapshot = True
        else:
            no_cancer_message = "No living cancer cells are present and no prior cancer-signal snapshot is available."

    signal_rows: List[Dict[str, Any]] = []
    for signal in SIGNALS:
        if cancer:
            cancer_mean = _mean(cancer, signal)
            cancer_prev = _prevalence(cancer, signal)
        elif used_snapshot:
            cancer_mean = float(snapshot.get("mean_signals", {}).get(signal, 0.0))
            cancer_prev = 1.0 if cancer_mean >= 0.35 else 0.0
        else:
            cancer_mean = 0.0
            cancer_prev = 0.0
        healthy_mean = _mean(healthy, signal)
        healthy_prev = _prevalence(healthy, signal)
        difference = cancer_mean - healthy_mean
        targetability = clamp(cancer_mean * 0.40 + max(difference, 0.0) * 0.35 + cancer_prev * 0.15 - healthy_prev * 0.10)
        overlap = clamp((healthy_mean * 0.65) + (healthy_prev * 0.35))
        confidence = clamp((cancer_prev * 0.40) + (max(difference, 0.0) * 0.40) + (cancer_mean * 0.20))
        signal_rows.append(
            {
                "signal": signal,
                "cancer_mean": cancer_mean,
                "healthy_mean": healthy_mean,
                "difference": difference,
                "ratio": _ratio(cancer_mean, healthy_mean),
                "cancer_prevalence": cancer_prev,
                "healthy_prevalence": healthy_prev,
                "targetability_score": targetability,
                "healthy_overlap_risk": overlap,
                "marker_confidence": confidence,
            }
        )

    dominant = sorted(signal_rows, key=lambda row: row["cancer_mean"], reverse=True)
    targetable = sorted(signal_rows, key=lambda row: row["targetability_score"], reverse=True)
    cancer_specific = [row for row in targetable if row["difference"] >= 0.20 and row["healthy_overlap_risk"] <= 0.45]
    misleading = [row for row in dominant if row["healthy_overlap_risk"] >= 0.50 and row["difference"] <= 0.15]
    overlap_warnings = [
        f"{row['signal']} also appears in healthy cells (healthy mean {row['healthy_mean']:.2f}, prevalence {row['healthy_prevalence']:.2f})."
        for row in misleading[:8]
    ]

    grouped = {}
    for group_name, names in SIGNAL_GROUPS.items():
        grouped[group_name] = [row for row in targetable if row["signal"] in names][:8]

    top_names = [row["signal"] for row in targetable[:10]]
    recommended_cocktails = _cocktail_recommendations(top_names)
    recommended_agents = _agent_recommendations(top_names)
    avoid = [
        row["signal"]
        for row in misleading[:8]
    ]

    if no_cancer_message:
        summary = no_cancer_message
    else:
        origin = "last saved cancer-signal snapshot" if used_snapshot else "living cancer cells"
        summary = (
            f"Interpreted {len(cancer)} living cancer/precancerous cells and {len(healthy)} healthy cells "
            f"using {origin}. Top targetable signals: {', '.join(top_names[:5]) or 'none'}."
        )

    return {
        **profile_info,
        "scope_notice": SCOPE_NOTICE,
        "formula": "targetability_score = cancer_mean*0.40 + max(cancer_mean-healthy_mean,0)*0.35 + cancer_prevalence*0.15 - healthy_prevalence*0.10",
        "cancer_count": len(cancer),
        "healthy_count": len(healthy),
        "used_fallback_snapshot": used_snapshot,
        "snapshot_step": snapshot.get("step") if used_snapshot else None,
        "signal_scores": signal_rows,
        "top_dominant_signals": dominant[:10],
        "top_targetable_signals": targetable[:10],
        "cancer_specific_signals": cancer_specific[:10],
        "misleading_signals": misleading[:10],
        "healthy_overlap_warnings": overlap_warnings,
        "escape_warnings": [row for row in grouped["escape_signals"] if row["cancer_mean"] >= 0.35],
        "immune_evasion_signals": grouped["immune_evasion_signals"],
        "apoptosis_resistance_signals": grouped["apoptosis_resistance_signals"],
        "DNA_repair_defect_signals": grouped["DNA_repair_defect_signals"],
        "metabolic_stress_signals": grouped["metabolic_stress_signals"],
        "microenvironment_signals": grouped["microenvironment_signals"],
        "recommended_cocktails": recommended_cocktails,
        "recommended_addon_agents": recommended_agents,
        "agents_to_avoid_or_gate": avoid,
        "plain_english_summary": summary,
        "limitations": [
            SCOPE_NOTICE,
            "Signal scores are qualitative simulator measurements, not biomarkers from a patient sample.",
            "Healthy overlap means a signal may be less selective in this simulation and should be gated or avoided conceptually.",
            "A zero living cancer count uses prior snapshots only when the simulator has stored them.",
        ],
    }


def analyze_marker_evolution(sim: "Simulation", interpretation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    snapshots = getattr(sim, "marker_snapshots", {}) or {}
    initial = snapshots.get("initial_profile") or snapshots.get("initial") or {}
    latest = snapshots.get("last_living_cancer") or {}
    result = interpretation or analyze_signals(sim)
    initial_means = initial.get("mean_signals", {})
    latest_means = latest.get("mean_signals", {})
    enriched = []
    reduced = []
    untreated = []
    for signal in SIGNALS:
        start = float(initial_means.get(signal, 0.0))
        end = float(latest_means.get(signal, 0.0))
        if end - start >= 0.15:
            enriched.append({"signal": signal, "initial": start, "latest": end, "change": end - start})
        elif start - end >= 0.15:
            reduced.append({"signal": signal, "initial": start, "latest": end, "change": end - start})
        if end >= 0.45 and signal not in {row["signal"] for row in result.get("top_targetable_signals", [])[:8]}:
            untreated.append({"signal": signal, "latest": end})
    living_cancer = result.get("cancer_count", 0)
    if living_cancer <= 0:
        summary = "No living cancer cells remain. Remission surveillance should be based on last pre-clearance signal profile and escape-risk history."
    else:
        summary = f"{living_cancer} cancer/precancerous cells remain; survivor markers should guide the next conceptual cocktail adjustment."
    return {
        "initial_dominant_markers": initial.get("dominant_signals", [])[:10],
        "markers_enriched_in_survivors": sorted(enriched, key=lambda row: row["change"], reverse=True)[:10],
        "markers_reduced_by_treatment": sorted(reduced, key=lambda row: row["change"])[:10],
        "potential_escape_markers": [row["signal"] for row in result.get("escape_warnings", [])[:8]],
        "markers_that_remained_untreated": untreated[:10],
        "suggested_next_cocktail_adjustment": result.get("recommended_cocktails", [])[:3],
        "plain_english_summary": summary,
    }
