"""Single source of truth for the paper's pinned configuration (Stage X0).

ISOLATED benchmark support code. Imports scenes / probes READ-ONLY and sets all
solver knobs at RUNTIME — it never modifies solver source or the original
`benchmarks/material_sweeps/` outputs.

Why this file exists
--------------------
The pre-X0 headline evidence was generated at TWO different configurations and a
paper cannot mix them:

  * the material/scene sweeps (`benchmarks/material_sweeps/`) ran at modal
    relaxation **0.7** + the **symplectic** modal step (via `sweep_common`);
  * the energy-loop verification (`scripts/probe_native_energy_loop.py`) took a
    `symplectic=` flag but **no** relaxation knob, so it ran at the solver-SOURCE
    default relax (AVBD `_modal_relax=0.1`, XPBD `modal_relax=0.25`), which
    under-relaxes the modal block and changes the two-way ratio.

`PAPER_CONFIG` below is the ONE configuration every paper figure must use. Its
values are taken from the documented safe operating point of the robustness
matrix (`benchmarks/material_sweeps/out/robustness_matrix.csv`): relax 0.7 with
budget >= (16 iterations, 4 substeps) is the only region that is simultaneously
ring-accurate and (for the current, un-clamped solvers) energy-safe on 5/6
scene-solver combos. Stage X1 adds the enforced passivity clamp; until then this
config is the empirical safe region, not a guarantee.

Determinism protocol
--------------------
Frame counts are fixed here (no separate "quick"/"full" values that silently
change the answer — the ledge/XPBD 246x-vs-208x wrinkle in the old numbers was a
220-frame pass vs a 170-frame pass of the *same* nominal config). Pick the LONGER
of each previously-used pair so the post-impact ring is fully captured.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone


# --------------------------------------------------------------------------- #
# THE pinned configuration                                                    #
# --------------------------------------------------------------------------- #
PAPER_CONFIG: dict = dict(
    # solver knobs
    relax=0.7,              # modal relaxation, BOTH solvers (source defaults 0.1/0.25)
    iterations=16,          # >= robustness-matrix safe budget
    substeps=4,             # >= robustness-matrix safe budget
    stepper="symplectic",   # implicit-midpoint modal step (CPU host, non-cargo)
    h=1.0 / 120.0,          # rigid timestep [s]
    gravity=9.81,
    # probe protocol — fixed frame counts (longer of each previously-used pair)
    settle_frames=8,        # energy-loop settle before logging (probe default)
    settle_s=0.30,          # ring-measurement settle window [s]
    ring_window_s=0.6,      # ring-measurement FFT window [s]
    n_frames_energy=220,    # energy-loop detail run (was 220 full / 140 quick)
    n_frames_coupling=200,  # coupling_metrics run    (was 200 full / 140 quick)
    seed=0,                 # reserved; the native CPU path is deterministic (no RNG)
)

# how much run-to-run variation the determinism gate tolerates on the two-way ratio
DETERMINISM_TOL = 0.05  # +/- 5 %


# --------------------------------------------------------------------------- #
# Runtime application helpers (never touch solver source)                     #
# --------------------------------------------------------------------------- #
def apply_relax(sol, solver: str, relax: float = None) -> None:
    """Set the modal relaxation on a freshly-built solver, per-solver knob names.

    Mirrors the (private) `sweep_common._set_relax` so paper_eval stays the
    single source of truth. AVBD (`Solver6DOF`): `sol._modal_relax`. XPBD
    (`SolverXPBD`): `sol.modal_relax` and its mirror `sol._support_block_relax`.
    """
    if relax is None:
        relax = PAPER_CONFIG["relax"]
    if solver == "avbd":
        sol._modal_relax = float(relax)
    else:
        sol.modal_relax = float(relax)
        sol._support_block_relax = float(relax)


def apply_passivity(sol, solver: str, enable: bool = True, eta: float = 1.0) -> None:
    """Turn the Stage X1 passive-energy clamp on/off at runtime (foundation §15).

    XPBD gets the ACTIVE γ-clamp (it can inject at low budget); AVBD is empirically
    passive, so it runs the ledger MONITOR-only (records + asserts, no perturbation).
    """
    sol._enforce_modal_passivity = bool(enable)
    sol._modal_eta = float(eta)
    # XPBD builds its ledger at set_modal_support (before this runs), so sync η.
    if getattr(sol, "_psv_ledger", None) is not None:
        sol._psv_ledger.eta = float(eta)
    if solver == "avbd":
        sol._psv_monitor_only = True


def passivity_builder(build_fn, solver: str, relax: float = None,
                      enable: bool = True, eta: float = 1.0):
    """Wrap a builder to pin BOTH relax and the passive-energy clamp post-build."""
    if relax is None:
        relax = PAPER_CONFIG["relax"]

    def _wrapped(**kw):
        H = build_fn(**kw)
        sol = H.world._solver
        apply_relax(sol, solver, relax)
        apply_passivity(sol, solver, enable=enable, eta=eta)
        return H

    _wrapped.__name__ = getattr(build_fn, "__name__", "build") + "_passive"
    return _wrapped


def relaxed_builder(build_fn, solver: str, relax: float = None):
    """Wrap a scene builder so the modal relaxation is pinned right after build.

    Lets us reuse `scripts.probe_native_energy_loop.run()` unchanged: `run()`
    calls `build_fn(**kw)` and only sets `_modal_symplectic`/freeze AFTERWARDS, so
    a relax set inside the wrapped builder survives. The energy-loop probe has no
    `relax=` argument of its own — this is how X0 pins it to 0.7 without editing
    the probe.
    """
    if relax is None:
        relax = PAPER_CONFIG["relax"]

    def _wrapped(**kw):
        H = build_fn(**kw)
        apply_relax(H.world._solver, solver, relax)
        return H

    _wrapped.__name__ = getattr(build_fn, "__name__", "build") + "_relaxed"
    return _wrapped


# --------------------------------------------------------------------------- #
# Provenance / manifests                                                       #
# --------------------------------------------------------------------------- #
def git_sha() -> str:
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return subprocess.check_output(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def manifest(figure: str, scenes=None, solvers=None, **extra) -> dict:
    """Assemble a provenance manifest for one figure/CSV artifact."""
    m = dict(
        figure=figure,
        stage="X0",
        git_sha=git_sha(),
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        config=dict(PAPER_CONFIG),
    )
    if scenes is not None:
        m["scenes"] = list(scenes)
    if solvers is not None:
        m["solvers"] = list(solvers)
    m.update(extra)
    return m


def write_manifest(out_dir: str, figure: str, **kw) -> str:
    """Write `<figure>.config.json` next to an artifact; return its path."""
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(figure)[0]
    path = os.path.join(out_dir, stem + ".config.json")
    with open(path, "w") as fh:
        json.dump(manifest(figure, **kw), fh, indent=2)
    return path
