"""Tkinter GUI for OncoForge."""

from __future__ import annotations

import csv
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from oncoforge.core.models import BioAgent, Cocktail, Microenvironment, SimulationConfig
from oncoforge.core.simulation import Simulation
from oncoforge.core.presets import load_agents, load_cancer_presets, default_cocktails
from oncoforge.core.exporter import export_html_report, export_json_report, export_report_by_suffix
from oncoforge.core.knowledge import validate_agent, validate_cocktail, cocktail_coverage, pathway_map_text
from oncoforge.core.experiment_runner import compare_cocktails, export_results_csv, format_results_table
from oncoforge.core.sweep import export_sweep_csv, export_sweep_json, format_sweep_table, run_parameter_sweep
from oncoforge.core.automation import automation_profile_options, automation_profiles, run_automated_protocol
from oncoforge.core.interpretation import assess_cure_pathway, interpret_latest
from oncoforge.core.cancer_profiles import (
    SCOPE_NOTICE,
    apply_profile_to_simulation,
    create_profile_simulation,
    duplicate_profile_as_custom,
    filter_cancer_profiles,
    load_cancer_profiles,
    profile_summary_text,
)
from oncoforge.core.local_ai import (
    LocalAIConfig,
    analyze_experiment_with_ai,
    check_local_ai_available,
    load_ai_config,
    suggest_next_experiment,
)
from oncoforge.core.research_loop import ResearchLoopConfig, run_research_loop
from oncoforge.core.signal_interpreter import analyze_marker_evolution, analyze_signals
from oncoforge.core.treatment_matcher import recommend_treatments
from oncoforge.core.constants import EVIDENCE_LEVELS, SIGNALS, ACTIONS, MICROENVIRONMENT_TARGETS


DARK = {
    "bg": "#0b1020",
    "panel": "#111827",
    "panel_alt": "#162033",
    "surface": "#1f2937",
    "surface_hi": "#26344a",
    "text": "#e5e7eb",
    "muted": "#aab4c3",
    "accent": "#38bdf8",
    "accent_hi": "#0ea5e9",
    "danger": "#ef4444",
    "healthy": "#22c55e",
    "cancer": "#f43f5e",
    "warning": "#f59e0b",
    "dead": "#94a3b8",
    "grid": "#334155",
}


class OncoForgeApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OncoForge - Cancer / Protein Systems Simulator")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.configure(bg=DARK["bg"])

        self.agents: List[BioAgent] = load_agents()
        self.agent_map: Dict[str, BioAgent] = {a.name: a for a in self.agents}
        self.presets = load_cancer_presets()
        self.default_cocktails = default_cocktails()
        self.automation_profiles = automation_profiles()
        self.cancer_profiles = load_cancer_profiles()
        self.ai_config = load_ai_config()
        self.last_batch_results = []
        self.last_sweep_results = []
        self.sim = Simulation()
        self.sim.reset()
        self.running = False
        self.worker: Optional[threading.Thread] = None
        self.ui_lock = threading.Lock()
        self._apply_dark_theme()

        self._build_menu()
        self._build_layout()
        self._apply_default_cocktail()
        self._style_tk_widgets(self)
        self.refresh_all()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _apply_dark_theme(self) -> None:
        self.option_add("*Font", "{Segoe UI} 10")
        self.option_add("*TCombobox*Listbox.background", DARK["surface"])
        self.option_add("*TCombobox*Listbox.foreground", DARK["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", DARK["accent_hi"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=DARK["bg"], foreground=DARK["text"], fieldbackground=DARK["surface"])
        style.configure("TFrame", background=DARK["bg"])
        style.configure("TLabel", background=DARK["bg"], foreground=DARK["text"])
        style.configure("TLabelFrame", background=DARK["panel"], foreground=DARK["text"], bordercolor=DARK["grid"], relief="solid")
        style.configure("TLabelFrame.Label", background=DARK["panel"], foreground=DARK["accent"])
        style.configure("TNotebook", background=DARK["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=DARK["panel"], foreground=DARK["muted"], padding=(12, 7))
        style.map("TNotebook.Tab", background=[("selected", DARK["surface_hi"])], foreground=[("selected", DARK["text"])])
        style.configure("TButton", background=DARK["surface"], foreground=DARK["text"], borderwidth=1, focusthickness=2, focuscolor=DARK["accent"], padding=(10, 6))
        style.map("TButton", background=[("active", DARK["surface_hi"]), ("pressed", DARK["accent_hi"])], foreground=[("pressed", "#ffffff")])
        style.configure("Accent.TButton", background=DARK["accent_hi"], foreground="#ffffff", padding=(12, 8))
        style.map("Accent.TButton", background=[("active", DARK["accent"]), ("pressed", DARK["accent_hi"])])
        style.configure("TEntry", fieldbackground=DARK["surface"], foreground=DARK["text"], bordercolor=DARK["grid"], insertcolor=DARK["text"])
        style.configure("TCombobox", fieldbackground=DARK["surface"], foreground=DARK["text"], background=DARK["surface"], arrowcolor=DARK["text"])
        style.map("TCombobox", fieldbackground=[("readonly", DARK["surface"])], foreground=[("readonly", DARK["text"])])
        style.configure("TCheckbutton", background=DARK["bg"], foreground=DARK["text"])
        style.map("TCheckbutton", background=[("active", DARK["bg"])], foreground=[("active", DARK["text"])])
        style.configure("Treeview", background=DARK["surface"], foreground=DARK["text"], fieldbackground=DARK["surface"], rowheight=26, bordercolor=DARK["grid"])
        style.configure("Treeview.Heading", background=DARK["panel_alt"], foreground=DARK["accent"], padding=(6, 5))
        style.map("Treeview", background=[("selected", DARK["accent_hi"])], foreground=[("selected", "#ffffff")])

    def _menu_options(self) -> Dict[str, str]:
        return {
            "bg": DARK["panel"],
            "fg": DARK["text"],
            "activebackground": DARK["accent_hi"],
            "activeforeground": "#ffffff",
            "selectcolor": DARK["accent"],
            "relief": "flat",
        }

    def _style_tk_widgets(self, widget: tk.Widget) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(
                    bg=DARK["surface"],
                    fg=DARK["text"],
                    insertbackground=DARK["text"],
                    selectbackground=DARK["accent_hi"],
                    selectforeground="#ffffff",
                    relief="flat",
                    borderwidth=1,
                    highlightthickness=1,
                    highlightbackground=DARK["grid"],
                )
            elif isinstance(child, tk.Canvas):
                child.configure(bg=DARK["panel"], highlightthickness=1, highlightbackground=DARK["grid"])
            self._style_tk_widgets(child)

    def _build_menu(self) -> None:
        menu = tk.Menu(self, **self._menu_options())
        file_menu = tk.Menu(menu, tearoff=0, **self._menu_options())
        file_menu.add_command(label="New / Reset", command=self.reset_simulation)
        file_menu.add_command(label="Save experiment JSON", command=self.save_experiment)
        file_menu.add_command(label="Load experiment JSON", command=self.load_experiment)
        file_menu.add_separator()
        file_menu.add_command(label="Export metrics CSV", command=self.export_metrics_csv)
        file_menu.add_command(label="Export HTML report", command=self.export_report)
        file_menu.add_command(label="Export JSON report", command=self.export_json_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=0, **self._menu_options())
        help_menu.add_command(label="Scope / Safety Notice", command=self.show_scope_notice)
        help_menu.add_command(label="Evidence Levels", command=self.show_evidence_levels)
        help_menu.add_command(label="How to Read a Run", command=self.show_how_to_read_run)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, sticky="nsew")

        self.dashboard = ttk.Frame(self.nb)
        self.automation_tab = ttk.Frame(self.nb)
        self.dosing_tab = ttk.Frame(self.nb)
        self.profile_tab = ttk.Frame(self.nb)
        self.ai_tab = ttk.Frame(self.nb)
        self.population_tab = ttk.Frame(self.nb)
        self.agents_tab = ttk.Frame(self.nb)
        self.cocktail_tab = ttk.Frame(self.nb)
        self.agent_designer_tab = ttk.Frame(self.nb)
        self.pathway_tab = ttk.Frame(self.nb)
        self.batch_tab = ttk.Frame(self.nb)
        self.sweep_tab = ttk.Frame(self.nb)
        self.viewer_tab = ttk.Frame(self.nb)
        self.signals_tab = ttk.Frame(self.nb)
        self.results_tab = ttk.Frame(self.nb)
        self.notebook_tab = ttk.Frame(self.nb)

        self.nb.add(self.dashboard, text="Dashboard")
        self.nb.add(self.automation_tab, text="Automated Run")
        self.nb.add(self.dosing_tab, text="Dosing & Cure Test")
        self.nb.add(self.profile_tab, text="Cancer Profiles")
        self.nb.add(self.ai_tab, text="Local AI Assistant")
        self.nb.add(self.population_tab, text="Cell Population")
        self.nb.add(self.agents_tab, text="Protein / Enzyme Library")
        self.nb.add(self.cocktail_tab, text="Cocktail Builder")
        self.nb.add(self.agent_designer_tab, text="Agent Designer")
        self.nb.add(self.pathway_tab, text="Pathway Map")
        self.nb.add(self.batch_tab, text="Batch Compare")
        self.nb.add(self.sweep_tab, text="Parameter Sweep")
        self.nb.add(self.viewer_tab, text="Simulation Viewer")
        self.nb.add(self.signals_tab, text="Signal Matrix")
        self.nb.add(self.results_tab, text="Results")
        self.nb.add(self.notebook_tab, text="Experiment Notebook")

        self._build_dashboard()
        self._build_automation_tab()
        self._build_dosing_tab()
        self._build_profile_tab()
        self._build_ai_tab()
        self._build_population_tab()
        self._build_agents_tab()
        self._build_cocktail_tab()
        self._build_agent_designer_tab()
        self._build_pathway_tab()
        self._build_batch_tab()
        self._build_sweep_tab()
        self._build_viewer_tab()
        self._build_signals_tab()
        self._build_results_tab()
        self._build_notebook_tab()

    def _build_dashboard(self) -> None:
        self.dashboard.columnconfigure(0, weight=0)
        self.dashboard.columnconfigure(1, weight=1)
        self.dashboard.rowconfigure(3, weight=1)

        control = ttk.LabelFrame(self.dashboard, text="Simulation Controls")
        control.grid(row=0, column=0, sticky="new", padx=8, pady=8)

        ttk.Button(control, text="Reset", command=self.reset_simulation).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(control, text="Step 1", command=lambda: self.run_steps(1)).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(control, text="Run 25", command=lambda: self.run_steps(25)).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(control, text="Run 100", command=lambda: self.run_steps(100)).grid(row=0, column=3, padx=4, pady=4)
        self.run_live_btn = ttk.Button(control, text="Live Run", command=self.toggle_live_run)
        self.run_live_btn.grid(row=1, column=0, padx=4, pady=4)
        ttk.Button(control, text="Stop", command=self.stop_live_run).grid(row=1, column=1, padx=4, pady=4)
        ttk.Button(control, text="Export Report", command=self.export_report).grid(row=1, column=2, padx=4, pady=4)
        ttk.Button(control, text="Save", command=self.save_experiment).grid(row=1, column=3, padx=4, pady=4)

        quick = ttk.LabelFrame(self.dashboard, text="One-Click Workflows")
        quick.grid(row=2, column=0, sticky="new", padx=8, pady=8)
        ttk.Button(quick, text="Automated run + exports", style="Accent.TButton", command=self.run_automation_from_dashboard).grid(row=0, column=0, sticky="ew", padx=6, pady=5)
        ttk.Button(quick, text="Compare cocktails now", command=self.run_dashboard_compare).grid(row=1, column=0, sticky="ew", padx=6, pady=5)
        ttk.Button(quick, text="Open automation options", command=lambda: self.nb.select(self.automation_tab)).grid(row=2, column=0, sticky="ew", padx=6, pady=5)

        config_box = ttk.LabelFrame(self.dashboard, text="Configuration")
        config_box.grid(row=3, column=0, sticky="nsew", padx=8, pady=8)

        self.config_vars: Dict[str, tk.StringVar] = {}
        fields = [
            ("name", "Name"),
            ("initial_healthy_cells", "Healthy cells"),
            ("initial_cancer_cells", "Cancer cells"),
            ("steps", "Default steps"),
            ("random_seed", "Random seed"),
            ("mutation_rate_multiplier", "Mutation multiplier"),
            ("immune_strength_multiplier", "Immune multiplier"),
            ("treatment_strength_multiplier", "Treatment multiplier"),
        ]
        for i, (key, label) in enumerate(fields):
            ttk.Label(config_box, text=label).grid(row=i, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value=str(getattr(self.sim.config, key)))
            self.config_vars[key] = var
            ttk.Entry(config_box, textvariable=var, width=24).grid(row=i, column=1, sticky="ew", padx=4, pady=2)
        self.allow_evolution_var = tk.BooleanVar(value=self.sim.config.allow_evolution)
        self.allow_proliferation_var = tk.BooleanVar(value=self.sim.config.allow_proliferation)
        ttk.Checkbutton(config_box, text="Allow evolution / escape", variable=self.allow_evolution_var).grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(config_box, text="Allow proliferation", variable=self.allow_proliferation_var).grid(row=len(fields)+1, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Button(config_box, text="Apply Settings", command=self.apply_config).grid(row=len(fields)+2, column=0, columnspan=2, sticky="ew", padx=4, pady=6)

        status = ttk.LabelFrame(self.dashboard, text="Live System State")
        status.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=8, pady=8)
        status.columnconfigure(0, weight=1)
        status.rowconfigure(0, weight=1)
        self.status_text = tk.Text(status, height=20, wrap="word")
        self.status_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_automation_tab(self) -> None:
        self.automation_tab.columnconfigure(0, weight=0)
        self.automation_tab.columnconfigure(1, weight=1)
        self.automation_tab.rowconfigure(0, weight=1)

        options = ttk.LabelFrame(self.automation_tab, text="Automated Experiment Options")
        options.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)
        options.columnconfigure(1, weight=1)

        default_profile = self.automation_profiles[1].label if len(self.automation_profiles) > 1 else (self.automation_profiles[0].label if self.automation_profiles else "")
        self.auto_vars: Dict[str, tk.StringVar] = {
            "profile": tk.StringVar(value=default_profile),
            "name": tk.StringVar(value="Automated OncoForge experiment"),
            "preset": tk.StringVar(value=self.presets[0]["name"] if self.presets else ""),
            "cocktail": tk.StringVar(value=self.default_cocktails[-1].name if self.default_cocktails else ""),
            "healthy": tk.StringVar(value="250"),
            "cancer": tk.StringVar(value="100"),
            "steps": tk.StringVar(value="100"),
            "seed": tk.StringVar(value="1729"),
            "compare_seeds": tk.StringVar(value="1729,1730,1731"),
            "output_dir": tk.StringVar(value=str(Path("outputs") / "automated")),
        }
        self.auto_compare_var = tk.BooleanVar(value=True)
        self.auto_select_var = tk.BooleanVar(value=False)
        fields = [
            ("name", "Experiment name"),
            ("healthy", "Healthy cells"),
            ("cancer", "Cancer cells"),
            ("steps", "Steps to run"),
            ("seed", "Primary seed"),
            ("compare_seeds", "Comparison seeds"),
            ("output_dir", "Output folder"),
        ]
        row = 0
        ttk.Label(options, text="Workflow profile").grid(row=row, column=0, sticky="w", padx=6, pady=5)
        profile_combo = ttk.Combobox(options, textvariable=self.auto_vars["profile"], values=[p.label for p in self.automation_profiles], state="readonly", width=34)
        profile_combo.grid(row=row, column=1, sticky="ew", padx=6, pady=5)
        profile_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_automation_profile())
        row += 1
        ttk.Button(options, text="Apply profile", command=self.apply_automation_profile).grid(row=row, column=0, sticky="nsew", padx=6, pady=5)
        self.profile_summary = tk.Text(options, height=4, width=34, wrap="word")
        self.profile_summary.grid(row=row, column=1, sticky="ew", padx=6, pady=5)
        row += 1
        ttk.Label(options, text="Cancer preset").grid(row=row, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(options, textvariable=self.auto_vars["preset"], values=[p["name"] for p in self.presets], state="readonly", width=34).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
        row += 1
        ttk.Label(options, text="Cocktail").grid(row=row, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(options, textvariable=self.auto_vars["cocktail"], values=[c.name for c in self.default_cocktails], state="readonly", width=34).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
        row += 1
        for key, label in fields:
            ttk.Label(options, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=5)
            ttk.Entry(options, textvariable=self.auto_vars[key], width=34).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
            row += 1
        ttk.Checkbutton(options, text="Also compare all bundled cocktails", variable=self.auto_compare_var).grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=8)
        row += 1
        ttk.Checkbutton(options, text="Auto-select best cocktail before run", variable=self.auto_select_var).grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=8)
        row += 1
        ttk.Button(options, text="Use current dashboard settings", command=self.fill_automation_from_current).grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        row += 1
        ttk.Button(options, text="Choose output folder", command=self.choose_automation_output_dir).grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        row += 1
        self.auto_run_btn = ttk.Button(options, text="Run automated workflow", style="Accent.TButton", command=self.run_automated_workflow)
        self.auto_run_btn.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=10)
        row += 1
        ttk.Button(options, text="Open output folder", command=self.open_automation_output_dir).grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=5)

        result_box = ttk.LabelFrame(self.automation_tab, text="Automation Output")
        result_box.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        result_box.columnconfigure(0, weight=1)
        result_box.rowconfigure(0, weight=1)
        self.automation_output = tk.Text(result_box, wrap="word")
        self.automation_output.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.automation_output.insert(
            "1.0",
            "Choose a preset and cocktail, then run the automated workflow. "
            "It will reset, run the simulation, export HTML/JSON/CSV reports, save the experiment, "
            "and optionally rank bundled cocktails across seeds.\n",
        )
        if default_profile:
            self.apply_automation_profile()

    def _build_dosing_tab(self) -> None:
        self.dosing_tab.columnconfigure(0, weight=0)
        self.dosing_tab.columnconfigure(1, weight=1)
        self.dosing_tab.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(self.dosing_tab, text="Adaptive dosing controller")
        controls.grid(row=0, column=0, sticky="new", padx=8, pady=8)

        self.adaptive_dosing_var = tk.BooleanVar(value=self.sim.config.adaptive_dosing_enabled)
        self.auto_shutoff_var = tk.BooleanVar(value=self.sim.config.auto_shutoff_enabled)
        self.remission_surveillance_var = tk.BooleanVar(value=self.sim.config.remission_surveillance_enabled)
        ttk.Checkbutton(controls, text="Enable adaptive dosing", variable=self.adaptive_dosing_var).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        ttk.Checkbutton(controls, text="Auto-shutoff after confirmed zero cancer", variable=self.auto_shutoff_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        ttk.Checkbutton(controls, text="Leave low-intensity surveillance after clearance", variable=self.remission_surveillance_var).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=3)

        self.dosing_vars: Dict[str, tk.StringVar] = {}
        dosing_fields = [
            ("taper_start_cancer_count", "Taper starts at cancer count <="),
            ("surveillance_start_cancer_count", "Surveillance starts at cancer count <="),
            ("adaptive_minimum_intensity", "Minimum intensity while cancer remains"),
            ("remission_surveillance_intensity", "Post-clearance surveillance intensity"),
            ("zero_cancer_confirmation_steps", "Zero-cancer confirmation steps"),
            ("inflammation_toxicity_threshold", "Inflammation toxicity threshold"),
            ("healthy_damage_toxicity_threshold", "Healthy damage-rate threshold"),
            ("recovery_rate", "Recovery rate after clearance"),
        ]
        for idx, (key, label) in enumerate(dosing_fields, start=3):
            ttk.Label(controls, text=label).grid(row=idx, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value=str(getattr(self.sim.config, key)))
            self.dosing_vars[key] = var
            ttk.Entry(controls, textvariable=var, width=16).grid(row=idx, column=1, sticky="ew", padx=4, pady=2)

        status_start = len(dosing_fields) + 3
        self.dosing_status_vars: Dict[str, tk.StringVar] = {}
        status_fields = [
            ("phase", "Current remission phase"),
            ("zero_steps", "Steps cancer remained zero"),
            ("rebound", "Rebound detected"),
            ("max_after_clearance", "Max cancer after clearance"),
        ]
        for offset, (key, label) in enumerate(status_fields):
            ttk.Label(controls, text=label).grid(row=status_start + offset, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value="")
            self.dosing_status_vars[key] = var
            ttk.Label(controls, textvariable=var).grid(row=status_start + offset, column=1, sticky="w", padx=4, pady=2)

        button_start = status_start + len(status_fields)
        ttk.Button(controls, text="Apply dosing settings", style="Accent.TButton", command=self.apply_config).grid(row=button_start, column=0, columnspan=2, sticky="ew", padx=4, pady=8)
        ttk.Button(controls, text="Run 250-step cure/remission test", command=lambda: self.run_steps(250)).grid(row=button_start + 1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(controls, text="Refresh interpretation", command=self.refresh_dosing_interpretation).grid(row=button_start + 2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)

        guide = ttk.LabelFrame(self.dosing_tab, text="How to use this tab")
        guide.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        guide.rowconfigure(0, weight=1)
        guide.columnconfigure(0, weight=1)
        self.dosing_guide_text = tk.Text(guide, wrap="word", width=52, height=14)
        self.dosing_guide_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.dosing_guide_text.insert("1.0", (
            "Adaptive dosing solves a common problem: a broad cocktail may clear cancer but continue damaging healthy cells.\n\n"
            "Recommended workflow:\n"
            "1. Start with a cancer preset and cocktail.\n"
            "2. Enable adaptive dosing and, if desired, auto-shutoff.\n"
            "3. Run until cancer reaches zero.\n"
            "4. Keep running through the zero-cancer confirmation window.\n"
            "5. Look for no rebound, falling inflammation, preserved healthy cells, and low healthy damage.\n\n"
            "A strong cure-like simulation is not just Cancer = 0. It also needs confirmed remission, watch time, and recovery."
        ))

        output = ttk.LabelFrame(self.dosing_tab, text="Plain-English interpretation")
        output.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=8, pady=8)
        output.rowconfigure(0, weight=1)
        output.columnconfigure(0, weight=1)
        self.dosing_interpretation_text = tk.Text(output, wrap="word")
        self.dosing_interpretation_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_profile_tab(self) -> None:
        self.profile_tab.columnconfigure(1, weight=1)
        self.profile_tab.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(self.profile_tab, text="Cancer Profile Library")
        left.grid(row=0, column=0, sticky="nsw", padx=8, pady=8)
        left.columnconfigure(0, weight=1)
        self.profile_search_var = tk.StringVar()
        self.profile_category_var = tk.StringVar(value="")
        ttk.Label(left, text="Search").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(left, textvariable=self.profile_search_var, width=30).grid(row=1, column=0, sticky="ew", padx=4, pady=2)
        ttk.Label(left, text="Category/tag").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Combobox(
            left,
            textvariable=self.profile_category_var,
            values=[
                "",
                "solid tumor",
                "blood cancer",
                "immune-visible",
                "immune-evasive",
                "DNA-repair-defective",
                "hypoxic/metabolic",
                "stromal-barrier-heavy",
                "custom profile",
            ],
            width=28,
        ).grid(row=3, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(left, text="Filter profiles", command=self.refresh_profile_list).grid(row=4, column=0, sticky="ew", padx=4, pady=4)
        self.profile_list = tk.Listbox(left, height=18, width=36, bg=DARK["surface"], fg=DARK["text"], selectbackground=DARK["accent_hi"])
        self.profile_list.grid(row=5, column=0, sticky="nsew", padx=4, pady=4)
        self.profile_list.bind("<<ListboxSelect>>", lambda _e: self.show_selected_profile())

        run_box = ttk.LabelFrame(left, text="Profile Simulation")
        run_box.grid(row=6, column=0, sticky="ew", padx=4, pady=4)
        self.profile_run_vars: Dict[str, tk.StringVar] = {
            "healthy": tk.StringVar(value="250"),
            "cancer": tk.StringVar(value="100"),
            "steps": tk.StringVar(value="100"),
            "seed": tk.StringVar(value="1729"),
            "heterogeneity": tk.StringVar(value="0.15"),
        }
        for idx, (key, label) in enumerate([
            ("healthy", "Healthy"),
            ("cancer", "Cancer"),
            ("steps", "Steps"),
            ("seed", "Seed"),
            ("heterogeneity", "Heterogeneity"),
        ]):
            ttk.Label(run_box, text=label).grid(row=idx, column=0, sticky="w", padx=3, pady=2)
            ttk.Entry(run_box, textvariable=self.profile_run_vars[key], width=12).grid(row=idx, column=1, sticky="ew", padx=3, pady=2)

        main = ttk.LabelFrame(self.profile_tab, text="Profile, Markers, and Recommendations")
        main.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)
        self.profile_output = tk.Text(main, wrap="word")
        self.profile_output.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        buttons = ttk.Frame(main)
        buttons.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        for col in range(4):
            buttons.columnconfigure(col, weight=1)
        profile_buttons = [
            ("Load profile into simulation", self.load_selected_profile_into_simulation),
            ("Create cells from profile", self.create_cells_from_selected_profile),
            ("Analyze current profile signals", self.analyze_current_profile_signals),
            ("Recommend cocktail from profile", self.recommend_profile_cocktail),
            ("Run profile simulation", self.run_selected_profile_simulation),
            ("Run profile comparison", self.run_profile_comparison),
            ("Export profile report", self.export_profile_report),
            ("Duplicate as custom profile", self.duplicate_selected_profile),
        ]
        for idx, (label, command) in enumerate(profile_buttons):
            ttk.Button(buttons, text=label, command=command).grid(row=idx // 4, column=idx % 4, sticky="ew", padx=3, pady=3)
        self.refresh_profile_list()

    def _build_ai_tab(self) -> None:
        self.ai_tab.columnconfigure(1, weight=1)
        self.ai_tab.rowconfigure(0, weight=1)
        controls = ttk.LabelFrame(self.ai_tab, text="Local AI Configuration")
        controls.grid(row=0, column=0, sticky="nsw", padx=8, pady=8)
        self.ai_enabled_var = tk.BooleanVar(value=self.ai_config.enabled)
        self.ai_provider_var = tk.StringVar(value=self.ai_config.provider)
        self.ai_base_url_var = tk.StringVar(value=self.ai_config.base_url)
        self.ai_model_var = tk.StringVar(value=self.ai_config.model)
        ttk.Checkbutton(controls, text="Enable local AI", variable=self.ai_enabled_var).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        ttk.Label(controls, text="Provider").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(controls, textvariable=self.ai_provider_var, values=["ollama", "lmstudio", "openai_compatible"], width=22).grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        ttk.Label(controls, text="Base URL").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(controls, textvariable=self.ai_base_url_var, width=30).grid(row=2, column=1, sticky="ew", padx=4, pady=3)
        ttk.Label(controls, text="Model").grid(row=3, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(controls, textvariable=self.ai_model_var, width=30).grid(row=3, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(controls, text="Test connection", command=self.ai_test_connection).grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(controls, text="Analyze current experiment", command=self.ai_analyze_current_experiment).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(controls, text="Suggest next simulation", command=self.ai_suggest_next_simulation).grid(row=6, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(controls, text="Run bounded auto-experiment loop", command=self.ai_run_research_loop).grid(row=7, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(controls, text="Stop auto-experiment loop", command=self.ai_stop_research_loop).grid(row=8, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        safety = tk.Text(controls, height=12, width=38, wrap="word")
        safety.grid(row=9, column=0, columnspan=2, sticky="ew", padx=4, pady=8)
        safety.insert("1.0", SCOPE_NOTICE + "\n\nLocal AI is optional. It may suggest simulation experiments only. It must not be treated as clinical truth.")
        self.ai_output = tk.Text(self.ai_tab, wrap="word")
        self.ai_output.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

    def _build_population_tab(self) -> None:
        self.population_tab.columnconfigure(1, weight=1)
        self.population_tab.rowconfigure(2, weight=1)
        ttk.Label(self.population_tab, text="Cancer preset").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.preset_var = tk.StringVar(value=self.presets[0]["name"] if self.presets else "")
        preset_combo = ttk.Combobox(self.population_tab, textvariable=self.preset_var, values=[p["name"] for p in self.presets], state="readonly", width=40)
        preset_combo.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        ttk.Button(self.population_tab, text="Apply preset to cancer cells", command=self.apply_preset).grid(row=0, column=2, padx=8, pady=8)

        self.micro_vars: Dict[str, tk.StringVar] = {}
        micro_box = ttk.LabelFrame(self.population_tab, text="Microenvironment")
        micro_box.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        micro_fields = ["oxygen", "glucose", "acidity", "inflammation", "immune_pressure", "stromal_barrier", "vascular_support"]
        for i, field in enumerate(micro_fields):
            ttk.Label(micro_box, text=field).grid(row=i // 4, column=(i % 4) * 2, padx=4, pady=4, sticky="w")
            var = tk.StringVar(value=f"{getattr(self.sim.microenvironment, field):.3f}")
            self.micro_vars[field] = var
            ttk.Entry(micro_box, textvariable=var, width=10).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=4, pady=4)
        ttk.Button(micro_box, text="Apply microenvironment", command=self.apply_microenvironment).grid(row=2, column=0, columnspan=2, padx=4, pady=6, sticky="ew")

        self.preset_details = tk.Text(self.population_tab, wrap="word")
        self.preset_details.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)
        self._update_preset_details()
        preset_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_preset_details())

    def _build_agents_tab(self) -> None:
        self.agents_tab.columnconfigure(0, weight=1)
        self.agents_tab.columnconfigure(1, weight=1)
        self.agents_tab.rowconfigure(1, weight=1)
        ttk.Label(self.agents_tab, text="Search").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.agent_search_var = tk.StringVar()
        self.agent_search_var.trace_add("write", lambda *_: self.refresh_agent_list())
        ttk.Entry(self.agents_tab, textvariable=self.agent_search_var).grid(row=0, column=0, sticky="ew", padx=70, pady=4)

        self.agent_tree = ttk.Treeview(self.agents_tab, columns=("category", "evidence", "targets", "actions"), show="headings", height=20)
        for col, width in [("category", 170), ("evidence", 70), ("targets", 260), ("actions", 260)]:
            self.agent_tree.heading(col, text=col.title())
            self.agent_tree.column(col, width=width, anchor="w")
        self.agent_tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.agent_tree.bind("<<TreeviewSelect>>", lambda _e: self.show_selected_agent())
        ttk.Button(self.agents_tab, text="Add selected agent to cocktail", command=self.add_selected_agent_to_cocktail).grid(row=2, column=0, sticky="ew", padx=8, pady=4)

        detail_box = ttk.LabelFrame(self.agents_tab, text="Agent Detail")
        detail_box.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=8, pady=8)
        detail_box.columnconfigure(0, weight=1)
        detail_box.rowconfigure(0, weight=1)
        self.agent_detail = tk.Text(detail_box, wrap="word")
        self.agent_detail.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_cocktail_tab(self) -> None:
        self.cocktail_tab.columnconfigure(0, weight=1)
        self.cocktail_tab.columnconfigure(1, weight=1)
        self.cocktail_tab.rowconfigure(1, weight=1)

        preset_box = ttk.LabelFrame(self.cocktail_tab, text="Default Cocktails")
        preset_box.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.cocktail_var = tk.StringVar(value=self.default_cocktails[-1].name if self.default_cocktails else "")
        ttk.Combobox(preset_box, textvariable=self.cocktail_var, values=[c.name for c in self.default_cocktails], state="readonly", width=40).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(preset_box, text="Load cocktail", command=self.load_default_cocktail).grid(row=0, column=1, padx=4, pady=4)

        self.cocktail_tree = ttk.Treeview(self.cocktail_tab, columns=("name", "category", "evidence", "potency", "risk"), show="headings", height=18)
        for col, width in [("name", 240), ("category", 190), ("evidence", 70), ("potency", 80), ("risk", 80)]:
            self.cocktail_tree.heading(col, text=col.title())
            self.cocktail_tree.column(col, width=width, anchor="w")
        self.cocktail_tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        ttk.Button(self.cocktail_tab, text="Remove selected", command=self.remove_selected_cocktail_agent).grid(row=2, column=0, sticky="ew", padx=8, pady=4)

        edit_box = ttk.LabelFrame(self.cocktail_tab, text="Cocktail Notes")
        edit_box.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=8, pady=8)
        edit_box.columnconfigure(0, weight=1)
        edit_box.rowconfigure(1, weight=1)
        ttk.Label(edit_box, text="Name").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.cocktail_name_var = tk.StringVar(value=self.sim.cocktail.name)
        ttk.Entry(edit_box, textvariable=self.cocktail_name_var).grid(row=0, column=0, sticky="ew", padx=60, pady=4)
        self.cocktail_notes = tk.Text(edit_box, wrap="word", height=16)
        self.cocktail_notes.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        ttk.Button(edit_box, text="Apply name/notes", command=self.apply_cocktail_metadata).grid(row=2, column=0, sticky="ew", padx=4, pady=4)

    def _build_agent_designer_tab(self) -> None:
        self.agent_designer_tab.columnconfigure(0, weight=1)
        self.agent_designer_tab.columnconfigure(1, weight=1)
        self.agent_designer_tab.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(self.agent_designer_tab, text="Create Custom Protein / Enzyme Agent")
        form.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        form.columnconfigure(1, weight=1)

        self.design_vars: Dict[str, tk.StringVar] = {
            "name": tk.StringVar(value="Custom multi-signal gate"),
            "category": tk.StringVar(value="user_designed_agent"),
            "logic": tk.StringVar(value="WEIGHTED"),
            "threshold": tk.StringVar(value="0.50"),
            "specificity": tk.StringVar(value="0.75"),
            "potency": tk.StringVar(value="0.55"),
            "risk": tk.StringVar(value="0.10"),
            "evidence": tk.StringVar(value="5"),
        }
        fields = [("name", "Name"), ("category", "Category"), ("threshold", "Activation threshold"), ("specificity", "Specificity"), ("potency", "Potency"), ("risk", "Healthy-cell risk"), ("evidence", "Evidence level")]
        for i, (key, label) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            ttk.Entry(form, textvariable=self.design_vars[key]).grid(row=i, column=1, sticky="ew", padx=6, pady=3)
        ttk.Label(form, text="Activation logic").grid(row=len(fields), column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(form, textvariable=self.design_vars["logic"], values=["WEIGHTED", "AND", "OR", "THRESHOLD"], state="readonly").grid(row=len(fields), column=1, sticky="ew", padx=6, pady=3)

        target_box = ttk.LabelFrame(form, text="Targets / signals")
        target_box.grid(row=len(fields)+1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        target_box.columnconfigure(0, weight=1)
        target_box.columnconfigure(1, weight=0)
        self.design_target_vars: Dict[str, tk.BooleanVar] = {}
        self.design_target_weight_vars: Dict[str, tk.StringVar] = {}
        target_names = SIGNALS + MICROENVIRONMENT_TARGETS
        for i, target in enumerate(target_names):
            var = tk.BooleanVar(value=target in {"DNA_DAMAGE_HIGH", "P53_INACTIVE", "STRESS_LIGAND_HIGH"})
            wvar = tk.StringVar(value="0.35")
            self.design_target_vars[target] = var
            self.design_target_weight_vars[target] = wvar
            ttk.Checkbutton(target_box, text=target, variable=var).grid(row=i, column=0, sticky="w", padx=4, pady=1)
            ttk.Entry(target_box, textvariable=wvar, width=7).grid(row=i, column=1, sticky="e", padx=4, pady=1)

        action_box = ttk.LabelFrame(form, text="Actions")
        action_box.grid(row=0, column=2, rowspan=len(fields)+2, sticky="nsew", padx=6, pady=6)
        self.design_action_vars: Dict[str, tk.BooleanVar] = {}
        self.design_action_weight_vars: Dict[str, tk.StringVar] = {}
        for i, action in enumerate(ACTIONS):
            var = tk.BooleanVar(value=action in {"immune_marking", "increase_apoptosis"})
            wvar = tk.StringVar(value="0.45")
            self.design_action_vars[action] = var
            self.design_action_weight_vars[action] = wvar
            ttk.Checkbutton(action_box, text=action, variable=var).grid(row=i, column=0, sticky="w", padx=4, pady=1)
            ttk.Entry(action_box, textvariable=wvar, width=7).grid(row=i, column=1, sticky="e", padx=4, pady=1)

        self.design_description = tk.Text(form, height=6, wrap="word")
        self.design_description.grid(row=len(fields)+2, column=0, columnspan=3, sticky="ew", padx=6, pady=6)
        self.design_description.insert("1.0", "User-designed conceptual agent. Use evidence level 5 until a rule is tied to a stronger source.")
        ttk.Button(form, text="Validate", command=self.validate_designed_agent).grid(row=len(fields)+3, column=0, sticky="ew", padx=6, pady=6)
        ttk.Button(form, text="Add to library + cocktail", command=self.add_designed_agent).grid(row=len(fields)+3, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(form, text="Clear", command=self.clear_designer).grid(row=len(fields)+3, column=2, sticky="ew", padx=6, pady=6)

        detail = ttk.LabelFrame(self.agent_designer_tab, text="Validation / JSON Preview")
        detail.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(0, weight=1)
        self.design_preview = tk.Text(detail, wrap="word")
        self.design_preview.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_pathway_tab(self) -> None:
        self.pathway_tab.columnconfigure(0, weight=1)
        self.pathway_tab.rowconfigure(0, weight=1)
        self.pathway_text = tk.Text(self.pathway_tab, wrap="word")
        self.pathway_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.pathway_text.insert("1.0", pathway_map_text())
        ttk.Button(self.pathway_tab, text="Refresh pathway map", command=lambda: self._replace_text(self.pathway_text, pathway_map_text())).grid(row=1, column=0, sticky="ew", padx=8, pady=4)

    def _build_batch_tab(self) -> None:
        self.batch_tab.columnconfigure(0, weight=1)
        self.batch_tab.rowconfigure(1, weight=1)
        controls = ttk.LabelFrame(self.batch_tab, text="Headless cocktail comparison")
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.batch_steps_var = tk.StringVar(value="80")
        self.batch_seeds_var = tk.StringVar(value="1729,1730,1731")
        self.batch_preset_var = tk.StringVar(value="")
        ttk.Label(controls, text="Steps").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Entry(controls, textvariable=self.batch_steps_var, width=10).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(controls, text="Seeds").grid(row=0, column=2, padx=4, pady=4, sticky="w")
        ttk.Entry(controls, textvariable=self.batch_seeds_var, width=24).grid(row=0, column=3, padx=4, pady=4)
        ttk.Label(controls, text="Preset").grid(row=0, column=4, padx=4, pady=4, sticky="w")
        ttk.Combobox(controls, textvariable=self.batch_preset_var, values=[""] + [p["name"] for p in self.presets], state="readonly", width=34).grid(row=0, column=5, padx=4, pady=4)
        ttk.Button(controls, text="Compare bundled cocktails", command=self.run_batch_compare).grid(row=0, column=6, padx=4, pady=4)
        ttk.Button(controls, text="Export batch CSV", command=self.export_batch_csv).grid(row=0, column=7, padx=4, pady=4)

        self.batch_text = tk.Text(self.batch_tab, wrap="none")
        self.batch_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.batch_text.insert("1.0", "Run a batch comparison to rank cocktails across seeds.\n")

    def _build_sweep_tab(self) -> None:
        self.sweep_tab.columnconfigure(0, weight=0)
        self.sweep_tab.columnconfigure(1, weight=1)
        self.sweep_tab.rowconfigure(0, weight=1)

        controls = ttk.LabelFrame(self.sweep_tab, text="Parameter sweep")
        controls.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.sweep_parameter_var = tk.StringVar(value="treatment")
        self.sweep_values_var = tk.StringVar(value="0.5,0.75,1.0,1.25")
        self.sweep_steps_var = tk.StringVar(value="100")
        ttk.Label(controls, text="Parameter").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Combobox(
            controls,
            textvariable=self.sweep_parameter_var,
            values=[
                "treatment",
                "immune",
                "mutation",
                "recovery",
                "surveillance_intensity",
                "oxygen",
                "acidity",
                "inflammation",
                "immune_pressure",
                "stromal_barrier",
                "vascular_support",
            ],
            width=28,
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(controls, text="Values").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(controls, textvariable=self.sweep_values_var, width=30).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(controls, text="Steps per value").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(controls, textvariable=self.sweep_steps_var, width=12).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        ttk.Button(controls, text="Run sweep", style="Accent.TButton", command=self.run_parameter_sweep_gui).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=8)
        ttk.Button(controls, text="Export sweep CSV", command=self.export_sweep_csv_gui).grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(controls, text="Export sweep JSON", command=self.export_sweep_json_gui).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        help_text = tk.Text(controls, wrap="word", height=12, width=42)
        help_text.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=4, pady=8)
        help_text.insert("1.0", (
            "Sweeps show how sensitive a result is to one parameter. Try treatment, immune, oxygen, acidity, inflammation, or recovery.\n\n"
            "Use adaptive dosing settings from the Dosing & Cure Test tab before running a sweep. Results are ranked by cure-pathway score, final cancer burden, and healthy preservation."
        ))
        controls.rowconfigure(6, weight=1)

        output = ttk.LabelFrame(self.sweep_tab, text="Sweep results")
        output.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        output.rowconfigure(0, weight=1)
        output.columnconfigure(0, weight=1)
        self.sweep_text = tk.Text(output, wrap="none")
        self.sweep_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_viewer_tab(self) -> None:
        self.viewer_tab.columnconfigure(0, weight=1)
        self.viewer_tab.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.viewer_tab, background="white")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        legend = ttk.Frame(self.viewer_tab)
        legend.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        ttk.Label(legend, text="Legend: green=healthy, red=cancer, orange=precancerous, black=dead, blue-ish=immune/stromal").pack(side="left")

    def _build_signals_tab(self) -> None:
        self.signals_tab.columnconfigure(0, weight=1)
        self.signals_tab.rowconfigure(0, weight=1)
        cols = ["clone", "kind", "count"] + SIGNALS[:12]
        self.signal_tree = ttk.Treeview(self.signals_tab, columns=cols, show="headings")
        for col in cols:
            self.signal_tree.heading(col, text=col)
            self.signal_tree.column(col, width=120 if col not in {"clone", "kind"} else 150, anchor="w")
        self.signal_tree.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        ttk.Button(self.signals_tab, text="Refresh Signal Matrix", command=self.refresh_signal_matrix).grid(row=1, column=0, sticky="ew", padx=8, pady=4)

    def _build_results_tab(self) -> None:
        self.results_tab.columnconfigure(0, weight=1)
        self.results_tab.rowconfigure(0, weight=1)
        paned = ttk.Panedwindow(self.results_tab, orient="vertical")
        paned.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.results_canvas = tk.Canvas(paned, background="white", height=280)
        text_frame = ttk.Frame(paned)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.results_text = tk.Text(text_frame, wrap="word")
        self.results_text.grid(row=0, column=0, sticky="nsew")
        paned.add(self.results_canvas, weight=1)
        paned.add(text_frame, weight=1)
        btns = ttk.Frame(self.results_tab)
        btns.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        ttk.Button(btns, text="Export CSV", command=self.export_metrics_csv).pack(side="left", padx=4)
        ttk.Button(btns, text="Export HTML", command=self.export_report).pack(side="left", padx=4)
        ttk.Button(btns, text="Export JSON", command=self.export_json_report).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=self.refresh_results).pack(side="left", padx=4)

    def _build_notebook_tab(self) -> None:
        self.notebook_tab.columnconfigure(0, weight=1)
        self.notebook_tab.rowconfigure(0, weight=1)
        self.notebook_text = tk.Text(self.notebook_tab, wrap="word")
        self.notebook_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        starter = (
            "Experiment notebook\n\n"
            "Use this panel to record hypotheses, cocktail rationale, observed outputs, and next changes.\n\n"
            "Suggested pattern:\n"
            "1. Cancer preset / clone state:\n"
            "2. Selected agents and why:\n"
            "3. Expected outcome:\n"
            "4. Actual result after simulation:\n"
            "5. Next modification:\n"
        )
        self.notebook_text.insert("1.0", starter)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _replace_text(self, widget: tk.Text, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _selected_cancer_profile(self):
        if not hasattr(self, "profile_list"):
            return self.cancer_profiles[0] if self.cancer_profiles else None
        selection = self.profile_list.curselection()
        if not selection:
            return self.cancer_profiles[0] if self.cancer_profiles else None
        idx = selection[0]
        visible = getattr(self, "_visible_profiles", self.cancer_profiles)
        return visible[idx] if 0 <= idx < len(visible) else None

    def refresh_profile_list(self) -> None:
        search = self.profile_search_var.get() if hasattr(self, "profile_search_var") else ""
        category = self.profile_category_var.get() if hasattr(self, "profile_category_var") else ""
        self._visible_profiles = filter_cancer_profiles(search, category)
        self.profile_list.delete(0, "end")
        for profile in self._visible_profiles:
            self.profile_list.insert("end", f"{profile.display_name} [{profile.category}]")
        if self._visible_profiles:
            self.profile_list.selection_set(0)
            self.show_selected_profile()

    def show_selected_profile(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            return
        self._replace_text(self.profile_output, profile_summary_text(profile))

    def _profile_run_numbers(self) -> Dict[str, object]:
        return {
            "healthy": int(float(self.profile_run_vars["healthy"].get())),
            "cancer": int(float(self.profile_run_vars["cancer"].get())),
            "steps": int(float(self.profile_run_vars["steps"].get())),
            "seed": int(float(self.profile_run_vars["seed"].get())),
            "profile_heterogeneity": float(self.profile_run_vars["heterogeneity"].get()),
        }

    def load_selected_profile_into_simulation(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            return
        apply_profile_to_simulation(self.sim, profile, profile_heterogeneity=float(self.profile_run_vars["heterogeneity"].get()))
        self.refresh_all()
        self.nb.select(self.profile_tab)
        self._replace_text(self.profile_output, profile_summary_text(profile) + "\n\nLoaded profile biases into current living cancer cells and microenvironment.")

    def create_cells_from_selected_profile(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            return
        try:
            values = self._profile_run_numbers()
            self.sim = create_profile_simulation(profile, cocktail=Cocktail.from_dict(self.sim.cocktail.to_dict()), **values)
            self._sync_ui_from_sim()
            self.refresh_all()
            self._replace_text(self.profile_output, profile_summary_text(profile) + "\n\nCreated a new profile-biased cell population.")
        except Exception as exc:
            messagebox.showerror("Profile population failed", str(exc))

    def analyze_current_profile_signals(self) -> None:
        profile = self._selected_cancer_profile()
        result = analyze_signals(self.sim, profile)
        evolution = analyze_marker_evolution(self.sim, result)
        self._replace_text(
            self.profile_output,
            result["plain_english_summary"] + "\n\nTop targetable signals:\n"
            + "\n".join(f"- {row['signal']}: {row['targetability_score']:.3f}" for row in result.get("top_targetable_signals", [])[:10])
            + "\n\nMarker evolution:\n"
            + json.dumps(evolution, indent=2, sort_keys=True),
        )

    def recommend_profile_cocktail(self) -> None:
        profile = self._selected_cancer_profile()
        result = recommend_treatments(sim=self.sim, profile=profile)
        self._replace_text(self.profile_output, result["plain_english_summary"])

    def run_selected_profile_simulation(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            return
        try:
            values = self._profile_run_numbers()
            steps = int(values.pop("steps"))
            self.sim = create_profile_simulation(profile, cocktail=Cocktail.from_dict(self.sim.cocktail.to_dict()), steps=steps, **values)
            self.sim.run(steps)
            self._sync_ui_from_sim()
            self.refresh_all()
            signal_result = analyze_signals(self.sim, profile)
            recommendation = recommend_treatments(sim=self.sim, profile=profile, interpretation=signal_result)
            self._replace_text(self.profile_output, signal_result["plain_english_summary"] + "\n\n" + recommendation["plain_english_summary"])
        except Exception as exc:
            messagebox.showerror("Profile run failed", str(exc))

    def run_profile_comparison(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            return
        rows = []
        try:
            values = self._profile_run_numbers()
            steps = int(values.pop("steps"))
            for cocktail in self.default_cocktails:
                sim = create_profile_simulation(profile, cocktail=Cocktail.from_dict(cocktail.to_dict()), steps=steps, **values)
                sim.run(steps)
                rec = recommend_treatments(sim=sim, profile=profile)
                best = rec.get("best_first_line_conceptual_match") or {}
                latest = sim.analytics.latest()
                rows.append((cocktail.name, latest.cancer_alive if latest else 0, latest.healthy_alive if latest else 0, best.get("score", 0.0)))
            rows.sort(key=lambda row: (row[1], -row[2], -row[3]))
            text = "Profile comparison\n\n" + "\n".join(f"{name}: cancer={cancer}, healthy={healthy}, match_score={score:.3f}" for name, cancer, healthy, score in rows)
            self._replace_text(self.profile_output, text)
        except Exception as exc:
            messagebox.showerror("Profile comparison failed", str(exc))

    def export_profile_report(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML", "*.html"), ("JSON", "*.json")], initialfile="oncoforge_profile_report.html")
        if not path:
            return
        export_report_by_suffix(self.sim, path)
        messagebox.showinfo("Exported", f"Profile report exported to:\n{path}")

    def duplicate_selected_profile(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            return
        try:
            path = duplicate_profile_as_custom(profile, f"{profile.id}_custom")
            messagebox.showinfo("Custom profile", f"Custom profile copy written to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Could not duplicate profile", str(exc))

    def _current_ai_config_from_form(self) -> LocalAIConfig:
        cfg = LocalAIConfig.from_dict(self.ai_config.to_dict())
        cfg.enabled = bool(self.ai_enabled_var.get())
        cfg.provider = self.ai_provider_var.get().strip() or "ollama"
        cfg.base_url = self.ai_base_url_var.get().strip().rstrip("/") or "http://localhost:11434"
        cfg.model = self.ai_model_var.get().strip() or "llama3.1"
        self.ai_config = cfg
        return cfg

    def ai_test_connection(self) -> None:
        cfg = self._current_ai_config_from_form()
        result = check_local_ai_available(cfg)
        self._replace_text(self.ai_output, json.dumps(result, indent=2, sort_keys=True))

    def ai_analyze_current_experiment(self) -> None:
        cfg = self._current_ai_config_from_form()
        cfg.enabled = True
        signal_result = analyze_signals(self.sim)
        recommendation = recommend_treatments(sim=self.sim, interpretation=signal_result)
        result = analyze_experiment_with_ai(cfg, self.sim, signal_result, recommendation)
        self._replace_text(self.ai_output, result.get("response") or result.get("message", "No response."))

    def ai_suggest_next_simulation(self) -> None:
        cfg = self._current_ai_config_from_form()
        cfg.enabled = True
        summary = {"signals": analyze_signals(self.sim), "recommendation": recommend_treatments(sim=self.sim)}
        result = suggest_next_experiment(cfg, summary)
        self._replace_text(self.ai_output, result.get("response") or result.get("message", "No response."))

    def ai_run_research_loop(self) -> None:
        profile = self._selected_cancer_profile()
        if not profile:
            messagebox.showinfo("No profile", "Select a cancer profile first.")
            return
        if not messagebox.askyesno("Start bounded loop", "Run up to 5 bounded local simulation experiments?"):
            return
        cfg = ResearchLoopConfig(profile=profile.id, max_auto_experiments=5, max_steps_per_experiment=100, output_dir=str(Path("outputs") / "research_loop"))
        result = run_research_loop(cfg, self._current_ai_config_from_form(), confirmed=True)
        self._replace_text(self.ai_output, json.dumps(result, indent=2, sort_keys=True))

    def ai_stop_research_loop(self) -> None:
        self._replace_text(self.ai_output, "No background research loop is currently running. Loops are bounded and run synchronously in this build.")

    def apply_automation_profile(self) -> None:
        try:
            options = automation_profile_options(self.auto_vars["profile"].get())
        except Exception as exc:
            messagebox.showerror("Automation profile", str(exc))
            return

        self.auto_vars["name"].set(str(options.get("name", "Automated OncoForge experiment")))
        self.auto_vars["preset"].set(str(options.get("preset_name", "")))
        self.auto_vars["cocktail"].set(str(options.get("cocktail_name", "Full conceptual swarm")))
        self.auto_vars["healthy"].set(str(options.get("healthy", 250)))
        self.auto_vars["cancer"].set(str(options.get("cancer", 100)))
        self.auto_vars["steps"].set(str(options.get("steps", 100)))
        self.auto_vars["seed"].set(str(options.get("seed", 1729)))
        self.auto_vars["output_dir"].set(str(options.get("output_dir", str(Path("outputs") / "automated"))))
        seeds = options.get("compare_seeds", [1729, 1730, 1731])
        self.auto_vars["compare_seeds"].set(",".join(str(seed) for seed in seeds))
        self.auto_compare_var.set(bool(options.get("compare", True)))
        self.auto_select_var.set(bool(options.get("auto_select_cocktail", False)))

        if hasattr(self, "profile_summary"):
            summary = [
                str(options.get("label", "")),
                str(options.get("description", "")),
                f"Preset: {options.get('preset_name', '')}",
                f"Cocktail: {options.get('cocktail_name', '')}",
            ]
            self._replace_text(self.profile_summary, "\n".join(line for line in summary if line))

    def fill_automation_from_current(self) -> None:
        self.apply_config()
        self.auto_vars["name"].set(self.sim.config.name or "Automated OncoForge experiment")
        self.auto_vars["healthy"].set(str(self.sim.config.initial_healthy_cells))
        self.auto_vars["cancer"].set(str(self.sim.config.initial_cancer_cells))
        self.auto_vars["steps"].set(str(self.sim.config.steps))
        self.auto_vars["seed"].set(str(self.sim.config.random_seed))
        if self.preset_var.get():
            self.auto_vars["preset"].set(self.preset_var.get())
        if self.sim.cocktail.name:
            self.auto_vars["cocktail"].set(self.sim.cocktail.name)

    def choose_automation_output_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=str(Path.cwd() / "outputs"))
        if path:
            self.auto_vars["output_dir"].set(path)

    def open_automation_output_dir(self) -> None:
        path = Path(self.auto_vars["output_dir"].get()).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("Could not open folder", str(exc))

    def run_automation_from_dashboard(self) -> None:
        self.fill_automation_from_current()
        self.nb.select(self.automation_tab)
        self.run_automated_workflow()

    def run_dashboard_compare(self) -> None:
        self.nb.select(self.batch_tab)
        self.run_batch_compare()

    def _automation_args_from_form(self) -> Dict[str, object]:
        seeds = [int(x.strip()) for x in self.auto_vars["compare_seeds"].get().split(",") if x.strip()]
        return {
            "name": self.auto_vars["name"].get().strip() or "Automated OncoForge experiment",
            "preset_name": self.auto_vars["preset"].get().strip() or None,
            "cocktail_name": self.auto_vars["cocktail"].get().strip() or "Full conceptual swarm",
            "steps": int(float(self.auto_vars["steps"].get())),
            "healthy": int(float(self.auto_vars["healthy"].get())),
            "cancer": int(float(self.auto_vars["cancer"].get())),
            "seed": int(float(self.auto_vars["seed"].get())),
            "output_dir": self.auto_vars["output_dir"].get().strip() or str(Path("outputs") / "automated"),
            "compare": bool(self.auto_compare_var.get()),
            "compare_seeds": seeds,
            "compare_limit": 12,
            "auto_select_cocktail": bool(self.auto_select_var.get()),
        }

    def run_automated_workflow(self) -> None:
        try:
            kwargs = self._automation_args_from_form()
        except ValueError as exc:
            messagebox.showerror("Invalid automation settings", str(exc))
            return
        self.auto_run_btn.config(state="disabled")
        self._replace_text(self.automation_output, "Running automated workflow...\n")
        worker = threading.Thread(target=self._automation_worker, args=(kwargs,), daemon=True)
        worker.start()

    def _automation_worker(self, kwargs: Dict[str, object]) -> None:
        try:
            result = run_automated_protocol(**kwargs)
        except Exception as exc:
            self.after(0, self._automation_failed, exc)
            return
        self.after(0, self._automation_finished, result)

    def _automation_failed(self, exc: Exception) -> None:
        self.auto_run_btn.config(state="normal")
        self._replace_text(self.automation_output, f"Automation failed:\n{exc}")
        messagebox.showerror("Automation failed", str(exc))

    def _automation_finished(self, result: Dict[str, object]) -> None:
        self.auto_run_btn.config(state="normal")
        lines = [
            "Automation complete",
            "",
            str(result.get("summary", "")),
        ]
        if result.get("auto_select_cocktail"):
            lines.extend(["", f"Auto-selected cocktail: {result.get('selected_cocktail', 'not recorded')}"])
            summary = result.get("selection_summary", [])
            if isinstance(summary, list) and summary:
                lines.append("Top cocktail means:")
                for item in summary[:3]:
                    if isinstance(item, dict):
                        lines.append(
                            f"  {item.get('cocktail_name', '')}: score {float(item.get('mean_score', 0.0)):.3f}, "
                            f"cancer suppression {float(item.get('mean_cancer_suppression_fraction', 0.0)):.3f}"
                        )
        lines.extend(["", "Exports:"])
        paths = result.get("paths", {})
        if isinstance(paths, dict):
            for key, path in paths.items():
                lines.append(f"  {key}: {path}")
        comparison = str(result.get("comparison_table", "") or "")
        if comparison:
            lines.extend(["", comparison])
        self._replace_text(self.automation_output, "\n".join(lines))
        experiment_path = paths.get("experiment") if isinstance(paths, dict) else None
        if experiment_path:
            try:
                self.sim = Simulation.load_experiment(str(experiment_path))
                self._sync_ui_from_sim()
                self.refresh_all()
            except Exception as exc:
                messagebox.showwarning("Loaded reports, not session", f"Reports were exported, but the session could not be loaded:\n{exc}")

    def _designed_agent_from_form(self) -> BioAgent:
        targets = {}
        for target, var in self.design_target_vars.items():
            if var.get():
                targets[target] = float(self.design_target_weight_vars[target].get())
        actions = {}
        for action, var in self.design_action_vars.items():
            if var.get():
                actions[action] = float(self.design_action_weight_vars[action].get())
        return BioAgent(
            name=self.design_vars["name"].get().strip(),
            category=self.design_vars["category"].get().strip() or "user_designed_agent",
            targets=targets,
            activation_logic=self.design_vars["logic"].get().strip().upper(),
            activation_threshold=float(self.design_vars["threshold"].get()),
            actions=actions,
            specificity=float(self.design_vars["specificity"].get()),
            potency=float(self.design_vars["potency"].get()),
            healthy_cell_risk=float(self.design_vars["risk"].get()),
            evidence_level=int(float(self.design_vars["evidence"].get())),
            description=self.design_description.get("1.0", "end").strip(),
        )

    def validate_designed_agent(self) -> None:
        try:
            agent = self._designed_agent_from_form()
            issues = validate_agent(agent)
            lines = ["Validation result", ""]
            if not issues:
                lines.append("No validation issues detected.")
            else:
                for issue in issues:
                    lines.append(f"{issue.severity.upper()} | {issue.location}: {issue.message}")
            lines.extend(["", "Agent JSON", json.dumps(agent.to_dict(), indent=2)])
            self._replace_text(self.design_preview, "\n".join(lines))
        except Exception as exc:
            self._replace_text(self.design_preview, f"Could not build agent: {exc}")

    def add_designed_agent(self) -> None:
        try:
            agent = self._designed_agent_from_form()
        except Exception as exc:
            messagebox.showerror("Invalid custom agent", str(exc))
            return
        issues = validate_agent(agent)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            self.validate_designed_agent()
            messagebox.showerror("Invalid custom agent", "Fix validation errors before adding the agent.")
            return
        # Replace same-name library entry; append to cocktail as a fresh copy.
        self.agent_map[agent.name] = agent
        self.agents = [a for a in self.agents if a.name != agent.name] + [agent]
        self.sim.cocktail.agents.append(BioAgent.from_dict(agent.to_dict()))
        self.refresh_agent_list()
        self.refresh_cocktail()
        self.validate_designed_agent()
        self.nb.select(self.cocktail_tab)

    def clear_designer(self) -> None:
        for var in self.design_target_vars.values():
            var.set(False)
        for var in self.design_action_vars.values():
            var.set(False)
        self._replace_text(self.design_preview, "")

    def run_batch_compare(self) -> None:
        try:
            self.apply_config()
            steps = int(float(self.batch_steps_var.get()))
            seeds = [int(x.strip()) for x in self.batch_seeds_var.get().split(",") if x.strip()]
            preset = self.batch_preset_var.get().strip() or None
            self.last_batch_results = compare_cocktails(config=self.sim.config, microenvironment=self.sim.microenvironment, cancer_preset_name=preset, steps=steps, seeds=seeds)
            text = format_results_table(self.last_batch_results, limit=30)
            self._replace_text(self.batch_text, text)
        except Exception as exc:
            messagebox.showerror("Batch comparison failed", str(exc))

    def export_batch_csv(self) -> None:
        if not self.last_batch_results:
            messagebox.showinfo("No batch results", "Run batch comparison first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="oncoforge_batch_compare.csv")
        if not path:
            return
        export_results_csv(self.last_batch_results, path)
        messagebox.showinfo("Exported", f"Batch comparison exported to:\n{path}")

    def run_parameter_sweep_gui(self) -> None:
        try:
            self.apply_config()
            values = [float(x.strip()) for x in self.sweep_values_var.get().split(",") if x.strip()]
            steps = int(float(self.sweep_steps_var.get()))
            preset = self._selected_preset()
            preset_name = preset.get("name") if preset else None
            self.last_sweep_results = run_parameter_sweep(
                parameter=self.sweep_parameter_var.get(),
                values=values,
                config=self.sim.config,
                microenvironment=self.sim.microenvironment,
                cocktail=self.sim.cocktail,
                cancer_preset_name=preset_name,
                steps=steps,
                seed=self.sim.config.random_seed,
            )
            self._replace_text(self.sweep_text, format_sweep_table(self.last_sweep_results, limit=40))
        except Exception as exc:
            messagebox.showerror("Parameter sweep failed", str(exc))

    def export_sweep_csv_gui(self) -> None:
        if not self.last_sweep_results:
            messagebox.showwarning("No sweep results", "Run a parameter sweep first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="oncoforge_sweep.csv")
        if path:
            export_sweep_csv(self.last_sweep_results, path)
            messagebox.showinfo("Exported", f"Sweep CSV exported to:\n{path}")

    def export_sweep_json_gui(self) -> None:
        if not self.last_sweep_results:
            messagebox.showwarning("No sweep results", "Run a parameter sweep first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")], initialfile="oncoforge_sweep.json")
        if path:
            export_sweep_json(self.last_sweep_results, path)
            messagebox.showinfo("Exported", f"Sweep JSON exported to:\n{path}")

    def _apply_default_cocktail(self) -> None:
        if self.default_cocktails:
            self.sim.cocktail = Cocktail.from_dict(self.default_cocktails[-1].to_dict())

    def apply_config(self) -> None:
        try:
            cfg = self.sim.config
            cfg.name = self.config_vars["name"].get()
            cfg.initial_healthy_cells = int(float(self.config_vars["initial_healthy_cells"].get()))
            cfg.initial_cancer_cells = int(float(self.config_vars["initial_cancer_cells"].get()))
            cfg.steps = int(float(self.config_vars["steps"].get()))
            cfg.random_seed = int(float(self.config_vars["random_seed"].get()))
            cfg.mutation_rate_multiplier = float(self.config_vars["mutation_rate_multiplier"].get())
            cfg.immune_strength_multiplier = float(self.config_vars["immune_strength_multiplier"].get())
            cfg.treatment_strength_multiplier = float(self.config_vars["treatment_strength_multiplier"].get())
            if hasattr(self, "adaptive_dosing_var"):
                cfg.adaptive_dosing_enabled = bool(self.adaptive_dosing_var.get())
                cfg.auto_shutoff_enabled = bool(self.auto_shutoff_var.get())
                cfg.remission_surveillance_enabled = bool(self.remission_surveillance_var.get())
                for key, var in self.dosing_vars.items():
                    if key.endswith("count") or key.endswith("steps"):
                        setattr(cfg, key, int(float(var.get())))
                    else:
                        setattr(cfg, key, float(var.get()))
            cfg.allow_evolution = bool(self.allow_evolution_var.get())
            cfg.allow_proliferation = bool(self.allow_proliferation_var.get())
            self.refresh_status()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", f"Could not apply settings: {exc}")

    def apply_microenvironment(self) -> None:
        try:
            for key, var in self.micro_vars.items():
                setattr(self.sim.microenvironment, key, max(0.0, min(1.0, float(var.get()))))
            self.refresh_all()
        except ValueError as exc:
            messagebox.showerror("Invalid microenvironment", f"Could not apply microenvironment: {exc}")

    def apply_preset(self) -> None:
        preset = self._selected_preset()
        if not preset:
            return
        self.sim.set_cancer_preset(preset)
        self.refresh_all()

    def reset_simulation(self) -> None:
        self.stop_live_run()
        self.apply_config()
        self.apply_microenvironment()
        self.sim.reset()
        preset = self._selected_preset()
        if preset:
            self.sim.set_cancer_preset(preset)
        self.refresh_all()

    def run_steps(self, steps: int) -> None:
        self.apply_config()
        if not self.sim.cells:
            self.sim.reset()
        for _ in range(int(steps)):
            self.sim.step()
        self.refresh_all()

    def toggle_live_run(self) -> None:
        if self.running:
            self.stop_live_run()
            return
        self.running = True
        self.run_live_btn.config(text="Pause Live")
        self.worker = threading.Thread(target=self._live_worker, daemon=True)
        self.worker.start()

    def stop_live_run(self) -> None:
        self.running = False
        if hasattr(self, "run_live_btn"):
            self.run_live_btn.config(text="Live Run")

    def _live_worker(self) -> None:
        while self.running:
            with self.ui_lock:
                self.sim.step()
            self.after(0, self.refresh_all)
            time.sleep(0.15)

    def _selected_preset(self) -> Optional[Dict]:
        name = self.preset_var.get()
        for preset in self.presets:
            if preset.get("name") == name:
                return preset
        return None

    def _update_preset_details(self) -> None:
        preset = self._selected_preset()
        self.preset_details.delete("1.0", "end")
        if preset:
            self.preset_details.insert("1.0", json.dumps(preset, indent=2))

    def refresh_agent_list(self) -> None:
        query = self.agent_search_var.get().lower().strip()
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)
        for agent in self.agents:
            hay = f"{agent.name} {agent.category} {agent.description} {' '.join(agent.targets)} {' '.join(agent.actions)}".lower()
            if query and query not in hay:
                continue
            self.agent_tree.insert("", "end", iid=agent.name, values=(agent.category, agent.evidence_level, ", ".join(agent.targets), ", ".join(agent.actions)))

    def show_selected_agent(self) -> None:
        sel = self.agent_tree.selection()
        self.agent_detail.delete("1.0", "end")
        if not sel:
            return
        agent = self.agent_map.get(sel[0])
        if not agent:
            return
        text = (
            f"Name: {agent.name}\n"
            f"Category: {agent.category}\n"
            f"Evidence level: {agent.evidence_level} - {EVIDENCE_LEVELS.get(agent.evidence_level, 'Unknown')}\n"
            f"Specificity: {agent.specificity:.3f}\n"
            f"Potency: {agent.potency:.3f}\n"
            f"Healthy-cell risk: {agent.healthy_cell_risk:.3f}\n"
            f"Activation logic: {agent.activation_logic}\n\n"
            f"Targets:\n{json.dumps(agent.targets, indent=2)}\n\n"
            f"Actions:\n{json.dumps(agent.actions, indent=2)}\n\n"
            f"Description:\n{agent.description}\n\n"
            f"Full object:\n{json.dumps(agent.to_dict(), indent=2)}"
        )
        self.agent_detail.insert("1.0", text)

    def add_selected_agent_to_cocktail(self) -> None:
        sel = self.agent_tree.selection()
        if not sel:
            return
        agent = self.agent_map.get(sel[0])
        if agent:
            self.sim.cocktail.agents.append(BioAgent.from_dict(agent.to_dict()))
            self.refresh_cocktail()

    def load_default_cocktail(self) -> None:
        name = self.cocktail_var.get()
        for cocktail in self.default_cocktails:
            if cocktail.name == name:
                self.sim.cocktail = Cocktail.from_dict(cocktail.to_dict())
                self.refresh_cocktail()
                self.refresh_status()
                return

    def remove_selected_cocktail_agent(self) -> None:
        sel = self.cocktail_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("__")[-1])
        if 0 <= idx < len(self.sim.cocktail.agents):
            del self.sim.cocktail.agents[idx]
        self.refresh_cocktail()

    def apply_cocktail_metadata(self) -> None:
        self.sim.cocktail.name = self.cocktail_name_var.get().strip() or "Unnamed cocktail"
        self.sim.cocktail.notes = self.cocktail_notes.get("1.0", "end").strip()
        self.refresh_status()

    def save_experiment(self) -> None:
        self.apply_cocktail_metadata()
        self.sim.config.notes = self.notebook_text.get("1.0", "end").strip()
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")], initialfile="oncoforge_experiment.json")
        if not path:
            return
        self.sim.save_experiment(path)
        messagebox.showinfo("Saved", f"Experiment saved to:\n{path}")

    def load_experiment(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self.stop_live_run()
        self.sim = Simulation.load_experiment(path)
        self._sync_ui_from_sim()
        self.refresh_all()

    def export_metrics_csv(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="oncoforge_metrics.csv")
        if not path:
            return
        self.sim.analytics.export_csv(path)
        messagebox.showinfo("Exported", f"Metrics exported to:\n{path}")

    def export_report(self) -> None:
        self.apply_cocktail_metadata()
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML files", "*.html")], initialfile="oncoforge_report.html")
        if not path:
            return
        export_html_report(self.sim, path)
        messagebox.showinfo("Exported", f"Report exported to:\n{path}")

    def export_json_report(self) -> None:
        self.apply_cocktail_metadata()
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")], initialfile="oncoforge_report.json")
        if not path:
            return
        export_json_report(self.sim, path)
        messagebox.showinfo("Exported", f"JSON report exported to:\n{path}")

    def show_scope_notice(self) -> None:
        messagebox.showinfo(
            "Scope / Safety Notice",
            "OncoForge is a conceptual research simulator for hypothesis generation.\n\n"
            "It is not medical advice, not a treatment recommendation, and not a clinical prediction tool. "
            "Use it to reason about mechanisms, combinations, and assumptions."
        )

    def show_evidence_levels(self) -> None:
        text = "\n".join(f"{level}: {name}" for level, name in EVIDENCE_LEVELS.items())
        messagebox.showinfo("Evidence Levels", text)

    def show_how_to_read_run(self) -> None:
        messagebox.showinfo(
            "How to Read a Run",
            "Read outputs in this order:\n\n"
            "1. Cancer count: did the cancer clear or only shrink?\n"
            "2. Healthy count and dead count: what did it cost?\n"
            "3. Inflammation and immune pressure: is the system overactivated?\n"
            "4. Healthy damage events: is treatment still harming healthy cells?\n"
            "5. Dosing phase/intensity: did the controller taper or shut off?\n"
            "6. Cure-pathway assessment: did clearance stay durable after more steps?"
        )

    # ------------------------------------------------------------------
    # Refresh / rendering
    # ------------------------------------------------------------------
    def _sync_ui_from_sim(self) -> None:
        for key, var in self.config_vars.items():
            var.set(str(getattr(self.sim.config, key)))
        self.allow_evolution_var.set(self.sim.config.allow_evolution)
        self.allow_proliferation_var.set(self.sim.config.allow_proliferation)
        if hasattr(self, "adaptive_dosing_var"):
            self.adaptive_dosing_var.set(self.sim.config.adaptive_dosing_enabled)
            self.auto_shutoff_var.set(self.sim.config.auto_shutoff_enabled)
            self.remission_surveillance_var.set(self.sim.config.remission_surveillance_enabled)
            for key, var in self.dosing_vars.items():
                var.set(str(getattr(self.sim.config, key)))
        for key, var in self.micro_vars.items():
            var.set(f"{getattr(self.sim.microenvironment, key):.3f}")
        self.cocktail_name_var.set(self.sim.cocktail.name)
        self.cocktail_notes.delete("1.0", "end")
        self.cocktail_notes.insert("1.0", self.sim.cocktail.notes)
        if self.sim.config.notes:
            self.notebook_text.delete("1.0", "end")
            self.notebook_text.insert("1.0", self.sim.config.notes)

    def refresh_all(self) -> None:
        self.refresh_status()
        self.refresh_agent_list()
        self.refresh_cocktail()
        self.render_cells()
        self.refresh_signal_matrix()
        self.refresh_results()
        self.refresh_dosing_interpretation()

    def refresh_status(self) -> None:
        self.status_text.delete("1.0", "end")
        counts = self.sim.live_cell_counts()
        latest = self.sim.analytics.latest()
        micro = self.sim.microenvironment
        dosing = self.sim.dosing_state
        if hasattr(self, "dosing_status_vars"):
            self.dosing_status_vars["phase"].set(dosing.phase)
            self.dosing_status_vars["zero_steps"].set(f"{dosing.zero_cancer_steps}/{self.sim.config.zero_cancer_confirmation_steps}")
            self.dosing_status_vars["rebound"].set("yes" if dosing.recurrence_after_clearance else "no")
            self.dosing_status_vars["max_after_clearance"].set(str(dosing.max_cancer_after_clearance))
        lines = [
            f"Experiment: {self.sim.config.name}",
            f"Step: {self.sim.step_index}",
            "",
            "Cell counts:",
            f"  Healthy: {counts.get('healthy', 0)}",
            f"  Precancerous: {counts.get('precancerous', 0)}",
            f"  Cancer: {counts.get('cancer', 0)}",
            f"  Dead: {counts.get('dead', 0)}",
            "",
            "Microenvironment:",
            f"  Oxygen: {micro.oxygen:.3f}",
            f"  Glucose: {micro.glucose:.3f}",
            f"  Acidity: {micro.acidity:.3f}",
            f"  Inflammation: {micro.inflammation:.3f}",
            f"  Immune pressure: {micro.immune_pressure:.3f}",
            f"  Stromal barrier: {micro.stromal_barrier:.3f}",
            f"  Vascular support: {micro.vascular_support:.3f}",
            "",
            f"Active cocktail: {self.sim.cocktail.name}",
            f"Agents: {len(self.sim.cocktail.agents)}",
            "",
            "Dosing controller:",
            f"  Adaptive dosing: {self.sim.config.adaptive_dosing_enabled}",
            f"  Phase: {dosing.phase}",
            f"  Intensity: {dosing.intensity:.3f}",
            f"  Clearance step: {dosing.clearance_step if dosing.clearance_step >= 0 else 'not reached'}",
            f"  Zero-cancer steps: {dosing.zero_cancer_steps}/{self.sim.config.zero_cancer_confirmation_steps}",
            f"  Rebound detected: {dosing.recurrence_after_clearance}",
            f"  Max cancer after clearance: {dosing.max_cancer_after_clearance}",
            f"  Rebound step: {dosing.rebound_step if dosing.rebound_step >= 0 else 'not observed'}",
            f"  Reason: {dosing.reason}",
            "",
        ]
        if latest:
            lines.extend([
                "Latest metrics:",
                f"  Mean malignancy: {latest.mean_malignancy:.3f}",
                f"  Mean DNA damage: {latest.mean_dna_damage:.3f}",
                f"  Mean immune visibility: {latest.mean_immune_visibility:.3f}",
                f"  Treatment hits last step: {latest.treatment_hits}",
                f"  Immune kills last step: {latest.immune_kills}",
                f"  Apoptosis events last step: {latest.apoptosis_events}",
                f"  Escape clone events last step: {latest.escape_clone_events}",
                f"  Healthy damage events last step: {latest.healthy_damage_events}",
            ])
        self.status_text.insert("1.0", "\n".join(lines))

    def refresh_cocktail(self) -> None:
        for item in self.cocktail_tree.get_children():
            self.cocktail_tree.delete(item)
        for idx, agent in enumerate(self.sim.cocktail.agents):
            self.cocktail_tree.insert("", "end", iid=f"agent__{idx}", values=(agent.name, agent.category, agent.evidence_level, f"{agent.potency:.2f}", f"{agent.healthy_cell_risk:.2f}"))
        self.cocktail_name_var.set(self.sim.cocktail.name)
        self.cocktail_notes.delete("1.0", "end")
        self.cocktail_notes.insert("1.0", self.sim.cocktail.notes)

    def render_cells(self) -> None:
        self.canvas.delete("all")
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        margin = 12
        self.canvas.create_rectangle(margin, margin, w - margin, h - margin, outline="#999999")
        max_draw = 2500
        cells = self.sim.cells
        if len(cells) > max_draw:
            step = max(1, len(cells) // max_draw)
            cells = cells[::step]
        for cell in cells:
            x = margin + (cell.position[0] / max(1, self.sim.config.width)) * (w - 2 * margin)
            y = margin + (cell.position[1] / max(1, self.sim.config.height)) * (h - 2 * margin)
            r = 2.2 if cell.alive else 1.6
            if not cell.alive or cell.cell_kind == "dead":
                color = "#111111"
            elif cell.cell_kind == "healthy":
                color = "#3a9f47"
            elif cell.cell_kind == "cancer":
                color = "#cc3030"
                r = 2.7 + cell.malignancy_score() * 1.8
            elif cell.cell_kind == "precancerous":
                color = "#de8b26"
            else:
                color = "#3d6fb6"
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
        self.canvas.create_text(16, 16, anchor="nw", text=f"step {self.sim.step_index} | cells drawn {len(cells)} / total {len(self.sim.cells)}", fill="#333333")

    def refresh_signal_matrix(self) -> None:
        for item in self.signal_tree.get_children():
            self.signal_tree.delete(item)
        groups: Dict[tuple, List] = {}
        for c in self.sim.cells:
            if not c.alive:
                continue
            c.generate_signals(self.sim.microenvironment.oxygen)
            key = (c.clone_id, c.cell_kind)
            groups.setdefault(key, []).append(c)
        for (clone, kind), cells in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0]))[:80]:
            averages = []
            for signal in SIGNALS[:12]:
                averages.append(sum(c.signals.get(signal, 0.0) for c in cells) / len(cells))
            values = [clone, kind, len(cells)] + [f"{x:.2f}" for x in averages]
            self.signal_tree.insert("", "end", values=values)

    def refresh_dosing_interpretation(self) -> None:
        if not hasattr(self, "dosing_interpretation_text"):
            return
        assessment = assess_cure_pathway(self.sim)
        text = interpret_latest(self.sim) + "\n\nAssessment object:\n" + json.dumps(assessment.to_dict(), indent=2, sort_keys=True)
        self._replace_text(self.dosing_interpretation_text, text)

    def refresh_results(self) -> None:
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", self.sim.analytics.summary_text() + "\n\n" + interpret_latest(self.sim))
        self._render_results_chart()

    def _render_results_chart(self) -> None:
        c = self.results_canvas
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        hist = self.sim.analytics.history
        margin = 32
        c.create_rectangle(margin, margin, w - margin, h - margin, outline="#999999")
        if len(hist) < 2:
            c.create_text(w / 2, h / 2, text="Run simulation to plot metrics", fill="#555555")
            return
        max_count = max(max(s.healthy_alive, s.cancer_alive, s.dead_cells) for s in hist) or 1
        max_step = max(s.step for s in hist) or 1

        def xy(step: int, value: float) -> tuple[float, float]:
            x = margin + (step / max_step) * (w - 2 * margin)
            y = h - margin - (value / max_count) * (h - 2 * margin)
            return x, y

        series = [
            ("Healthy", [s.healthy_alive for s in hist], "#3a9f47"),
            ("Cancer", [s.cancer_alive for s in hist], "#cc3030"),
            ("Dead", [s.dead_cells for s in hist], "#111111"),
        ]
        for label, values, color in series:
            pts = []
            for snap, value in zip(hist, values):
                pts.extend(xy(snap.step, value))
            if len(pts) >= 4:
                c.create_line(*pts, fill=color, width=2)
        c.create_text(margin + 4, margin + 4, anchor="nw", text="Healthy / Cancer / Dead over time", fill="#333333")
        c.create_text(w - margin - 4, margin + 4, anchor="ne", text=f"max count {max_count}", fill="#333333")


def main() -> None:
    app = OncoForgeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
