#!/usr/bin/env python3
"""Record the teaser / supplementary-video arms as frozen pose traces.

Each arm is an INDEPENDENT build stepped from its own reset state, so the
OFF/ON/reference comparison is three separate runs of the same scene rather
than one trajectory with a mid-run toggle (which would compare a diverged
state against itself).

Sim setup mirrors `x1_passivity/run_governed_accuracy.run_arm` exactly --
same builder defaults, same `settle` frames, same `_modal_symplectic`, same
`apply_relax` / `apply_passivity` -- so a frame recorded here is the same
frame the paper's numbers come from.

Ungoverned arms run the reservoir accounting LIVE with `passivity_gamma`
forced to 1.0 (paper 3.1: every state write in the enforcement path is
guarded by gamma < 1, so the trajectory is bit-identical to an un-governed
run). That is what lets the figure draw the supply curve of
(eq:invariant)'s right-hand side on an arm that is not being governed.
`--verify-unperturbed` asserts that equivalence rather than assuming it.

Run:
  .venv/bin/python benchmarks/paper_fig/record_teaser.py --case canonical
  .venv/bin/python benchmarks/paper_fig/record_teaser.py --case steel
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                      # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy                  # noqa: E402
from scenes.reduced_shelf import build_reduced_shelf               # noqa: E402
from benchmarks.paper_eval.paper_config import (                   # noqa: E402
    apply_relax, apply_passivity)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Support-slab render grid + physical thickness (both = the shelf builder's
# own defaults; the slab bends as a solid unit of this thickness).
N_GRID_X, N_GRID_Z = 21, 11
SETTLE = 8           # settle frames before the logged window (paper harness)
NFRAMES = 100        # logged frames                          (paper harness)

# Steel, for the hero arm only: the stiff board that turns the truncation
# injection into a visible bystander launch. Textbook (E, rho).
STEEL = dict(youngs=2.00e11, density=7850.0)

# Budget vocabulary, fixed here so no figure or caption can drift from it.
# K = constraint iterations per substep, S = substeps per 1/120 s frame; a
# cell costs K*S row evaluations per frame, but S also repeats contact
# generation, so equal-sweep cells are NOT equal-cost.
#
# 1xS is the one-iteration small-step regime of Macklin et al. (Small Steps
# in Physics Simulation), which advocates one sweep per substep and reports
# up to ~100 substeps. It is a legitimate schedule, NOT a universal engine
# default -- nothing here may be labelled "what XPBD ships".
BUDGET_LABEL = {
    (1, 4): "very tight interactive budget",
    (2, 2): "very tight interactive budget",
    (1, 8): "production-like interactive budget",
    (2, 4): "production-like interactive budget",
    (1, 16): "small-step stress budget",
    (8, 2): "iteration-heavier cell of comparable work",
    (16, 4): "quality-leaning budget",
    (32, 8): "convergence budget, not production",
    (500, 1): "converged reference, not production",
}

CASES = {
    # The paper's canonical injecting cell (sec. Accuracy): default builder
    # material (E = 0.5 GPa board), 8x2, relaxation 0.7.
    "canonical": dict(
        budget=(8, 2), relax=0.7, material=None, converged=(500, 1),
        note="paper canonical shelf cell: 8x2, relax 0.7"),
    # The deployed budget the paper measures in its 18 further cells.
    "deployed": dict(
        budget=(1, 8), relax=0.7, material=None, converged=(500, 1),
        note="production-like interactive budget 1x8, relax 0.7"),
    # Hero arm for the video: same production-like budget, steel board. The
    # stiffness -- not a starved-beyond-production budget -- is what makes
    # the injection visible as bystander launch.
    "steel": dict(
        budget=(1, 8), relax=0.7, material=STEEL, converged=(500, 1),
        note="steel board at the production-like 1x8 interactive budget"),
}


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def _build(K, S, relax, material):
    kw = dict(device="cpu", iterations=int(K), avbd_substeps=int(S),
              solver="xpbd")
    if material:
        kw.update(material)
    H = build_reduced_shelf(**kw)
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True          # PAPER_CONFIG stepper
    return H, sol


def _scene_meta(H) -> dict:
    """Static per-body render data + the support rest geometry."""
    world = H.world
    bodies = []
    for b in H.bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is None:
            continue
        bodies.append(dict(
            name=b.name, avbd_idx=int(desc.avbd_body.index),
            half=[float(v) for v in b.half_extents],
            color=[float(v) for v in b.color],
            kind=str(b.render_kind),
            is_impactor=bool(b.dcr_idx == H.impactor_idx)))
    rs = H.rs
    return dict(bodies=bodies,
                support_rest=rs.point_positions_rest.astype(np.float64),
                support_Uy=rs.U_points[:, 1, :].astype(np.float64),
                grid=(N_GRID_X, N_GRID_Z))


def run_arm(K, S, relax, material, *, governed, nframes, settle=SETTLE,
            ledger_live=True, gap_preserving=False):
    """One arm, recorded frame by frame.

    governed=False + ledger_live=True is the paper 3.1 un-governed
    measurement: accounting runs, gamma is pinned to 1.0, physics unperturbed.

    gap_preserving selects the shipped projection (eq. 5) over the superseded
    whole-state scale. It is applied ONLY on the governed arm: the gap path
    computes its own scale internally, so the gamma pin below would not
    neutralize it, and the un-governed arm must stay unperturbed.
    """
    t0 = time.perf_counter()
    H, sol = _build(K, S, relax, material)
    apply_passivity(sol, "xpbd", enable=bool(governed or ledger_live), eta=1.0)
    if governed:
        sol._psv_monitor_only = False     # ACTIVE projection (matrix ON column)
        sol._psv_gap_preserving = bool(gap_preserving)

    orig_gamma = _psv_mod.passivity_gamma
    if not governed:
        # pin gamma == 1: the enforcement path observes but never writes state
        _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0

    meta = _scene_meta(H)
    n_bodies = len(meta["bodies"])
    idxs = np.array([b["avbd_idx"] for b in meta["bodies"]], dtype=int)
    F = settle + nframes
    pos = np.zeros((F, n_bodies, 3))
    quat = np.zeros((F, n_bodies, 4))          # xyzw, as the solver stores it
    r = H.rs.q.shape[0]
    qs = np.zeros((F, r))
    e_mod = np.zeros(F)
    supply = np.zeros(F)                       # eta * cum rigid loss  [J]
    reservoir = np.zeros(F)
    clamped = np.zeros(F, dtype=int)
    e_imp = np.zeros(F)

    world = H.world
    ib = world._descs[H.impactor_idx].dcr_body
    try:
        for f in range(F):
            world.step()
            world._sync_avbd_to_dcr()
            pos[f] = sol.positions()[idxs]
            quat[f] = sol.orientations()[idxs]
            mq = sol.modal_q
            if mq is not None:
                qs[f] = mq
            e_mod[f] = float(sol.last_modal_KE) + float(sol.last_modal_PE)
            e_imp[f] = float(rigid_kinetic_energy([ib]))
            L = getattr(sol, "_psv_ledger", None)
            if L is not None:
                supply[f] = float(L.eta) * float(L.cum_rigid_loss)
                reservoir[f] = float(L.reservoir)
                clamped[f] = int(L.n_clamped)
    finally:
        _psv_mod.passivity_gamma = orig_gamma

    # Bystander launch: how far the RESTING books rise above the height they
    # settled to. Measured against each book's own post-settle height, so a
    # legitimate sag is not scored as a launch. This is the visible
    # consequence the figure and video are about, so it is measured, not
    # eyeballed.
    rest_y = pos[settle - 1, :, 1] if settle > 0 else pos[0, :, 1]
    rise = pos[settle:, :, 1] - rest_y[None, :]
    bystander = np.array([not b["is_impactor"] for b in meta["bodies"]])
    launch = (np.max(rise[:, bystander], axis=0) if bystander.any()
              else np.zeros(0))

    L = getattr(sol, "_psv_ledger", None)
    return dict(
        meta=meta, pos=pos, quat=quat, q=qs, e_mod=e_mod, e_imp=e_imp,
        supply=supply, reservoir=reservoir, clamped=clamped,
        settle=settle, nframes=nframes, h=1.0 / 120.0,
        K=int(K), S=int(S), relax=float(relax), governed=bool(governed),
        # peak over the LOGGED window only, exactly as the paper reports it
        e_mod_peak=float(np.max(e_mod[settle:])),
        e_imp_peak=float(np.max(e_imp[settle:])),
        launch_mm=launch * 1e3,
        launch_max_mm=float(np.max(launch) * 1e3) if launch.size else 0.0,
        n_clamped=int(0 if L is None else L.n_clamped),
        n_steps=int(0 if L is None else L.n_steps),
        wall_s=time.perf_counter() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="canonical", choices=tuple(CASES))
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--budget", default=None,
                    help="override the case budget, e.g. 1x8 / 2x4")
    ap.add_argument("--relax", type=float, default=None,
                    help="override the case modal relaxation")
    ap.add_argument("--gap-preserving", action="store_true",
                    help="governed arm uses the shipped gap-preserving "
                         "projection (eq. 5) instead of the whole-state scale")
    ap.add_argument("--verify-unperturbed", action="store_true",
                    help="assert the live-ledger OFF arm is bit-identical to a "
                         "ledger-free OFF arm (paper 3.1 non-perturbation)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    case = CASES[args.case]
    K, S = case["budget"]
    if args.budget:
        K, S = (int(v) for v in args.budget.lower().split("x"))
    CK, CS = case["converged"]
    relax = case["relax"] if args.relax is None else float(args.relax)
    material = case["material"]

    print(f"### teaser record: case={args.case} {K}x{S} "
          f"({BUDGET_LABEL.get((K, S), 'unlabelled budget')}) relax={relax} "
          f"material={'steel' if material else 'builder default'} ###",
          flush=True)

    arms = {}
    for name, (k, s, gov) in {
            "off": (K, S, False),
            "on":  (K, S, True),
            "ref": (CK, CS, False)}.items():
        a = run_arm(k, s, relax, material, governed=gov, nframes=args.nframes,
                    gap_preserving=args.gap_preserving)
        arms[name] = a
        lm = " ".join(f"{v:.1f}" for v in a["launch_mm"])
        print(f"  {name:4s} xpbd {k}x{s} gov={int(gov)}: "
              f"E_mod_peak={a['e_mod_peak']:12.5g} J  "
              f"E_imp_peak={a['e_imp_peak']:8.4g} J  "
              f"clamps={a['n_clamped']}/{a['n_steps']}  "
              f"bystander rise [mm]: {lm}  [{a['wall_s']:.1f}s]",
              flush=True)

    if args.verify_unperturbed:
        # The OFF arm above ran with the ledger live and gamma pinned to 1.
        # Re-run it with no ledger at all; the trajectories must agree bitwise.
        plain = run_arm(K, S, relax, material, governed=False,
                        nframes=args.nframes, ledger_live=False)
        dp = float(np.max(np.abs(plain["pos"] - arms["off"]["pos"])))
        dq = float(np.max(np.abs(plain["q"] - arms["off"]["q"])))
        ok = (dp == 0.0 and dq == 0.0)
        print(f"  non-perturbation check: max|dpos|={dp:.3e} "
              f"max|dq|={dq:.3e}  {'BITWISE IDENTICAL' if ok else 'DIFFERS'}")
        if not ok:
            raise SystemExit("ungoverned ledger perturbed the trajectory")

    name = args.out or f"teaser_{args.case}"
    npz = os.path.join(OUT, f"{name}.npz")
    flat = {}
    for arm, a in arms.items():
        for k_, v in a.items():
            if k_ == "meta":
                continue
            flat[f"{arm}/{k_}"] = np.asarray(v)
    m = arms["off"]["meta"]
    flat["support_rest"] = m["support_rest"]
    flat["support_Uy"] = m["support_Uy"]
    np.savez_compressed(npz, **flat)

    manifest = dict(
        case=args.case, note=case["note"], commit=_git_commit(),
        scene="shelf", solver="xpbd", budget=f"{K}x{S}",
        budget_label=BUDGET_LABEL.get((K, S), "unlabelled budget"),
        budget_semantics="KxS = K constraint iterations per substep, "
                         "S substeps per 1/120 s frame",
        converged=f"{CK}x{CS}", relax=relax,
        material=("steel" if material else "builder default (E=0.5 GPa)"),
        material_params=material or {},
        settle=SETTLE, nframes=args.nframes, h=1.0 / 120.0,
        stepper="symplectic", eta=1.0,
        projection=("gap-preserving (eq. 5)" if args.gap_preserving
                    else "whole-state scale"),
        bodies=m["bodies"], grid=list(m["grid"]),
        support_thickness=0.03,
        peaks={a: dict(e_mod_peak_J=arms[a]["e_mod_peak"],
                       e_imp_peak_J=arms[a]["e_imp_peak"],
                       bystander_rise_mm=[float(v) for v in arms[a]["launch_mm"]],
                       clamps=arms[a]["n_clamped"],
                       steps=arms[a]["n_steps"]) for a in arms},
        generated_by="benchmarks/paper_fig/record_teaser.py")
    with open(os.path.join(OUT, f"{name}.manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"wrote {npz}")
    print(f"wrote {os.path.join(OUT, f'{name}.manifest.json')}")


if __name__ == "__main__":
    main()
