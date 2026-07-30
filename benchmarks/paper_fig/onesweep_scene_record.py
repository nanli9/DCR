#!/usr/bin/env python3
"""Record a FULL scene twice -- unfixed vs reconstruction-matched row weight --
as a per-substep pose trace for the real-cubes one-sweep video.

Two scenes are supported (`--scene`), both recorded through the same code path
and written with the SAME npz schema:

  shelf   (act 1) 5 standing books on a soft modal cantilever shelf + a 6 kg
                  dropped weight            -> onesweep_scene_traj.npz
  dinner  (act 2) the DCR-style dinner table: 2.2 x 1.1 m modal table, six
                  place settings (plate + fork + knife), four teacups, two
                  candlesticks, and a 5 kg pot dropped from above
                                            -> onesweep_dinner_traj.npz

Both arms are independent builds of the SAME scene, stepped through the actual
shipped XPBD solver with the shipped symplectic (implicit-midpoint) modal
reconstruction. Nothing is parked, nothing is isolated: this is the whole scene,
so what the video shows is the system-level consequence of the row weight.

  arm "unfixed"  sol._wq_support = None
                 -> the shipped stiffness-blind contact-row modal weight 1/M_q.
  arm "fixed"    sol._wq_support = 1/(kappa^2*M_q + h^2*K_q), kappa = 2
                 -> the reconstruction-matched charge mass mu = m(kappa^2 + b)
                    for the shipped midpoint reconstruction (the working fix;
                    same install point as run_t9_matched._install_matched_weight
                    and run_weight_swap._install_weight_swap: the opt-in
                    sol._wq_support knob, which defaults to None).

Only RUNTIME knobs are set (sol._wq_support, sol._modal_symplectic, modal
relaxation, the passivity governor OFF); no tracked file is edited and no solver
math is touched. The passivity governor is OFF in BOTH arms: the video is about
the row weight, not about the clamp.

Capture is PER SUBSTEP (h_sub = 1/120/S), which is what makes an honest
slow-motion clip possible: every displayed pose is a state the solver actually
produced, never an interpolation.

Modes
  --probe    sweep budgets / relaxations / stiffness scales / drop points and
             print the contrast metrics for both arms (no files written)
  (default)  record the chosen operating point and write
             out/onesweep_scene_data/<scene>_traj.npz +
             out/onesweep_scene_data/<scene>_data_summary.json

Run:
  .venv/bin/python benchmarks/paper_fig/onesweep_scene_record.py --probe
  .venv/bin/python benchmarks/paper_fig/onesweep_scene_record.py
  .venv/bin/python benchmarks/paper_fig/onesweep_scene_record.py --scene dinner
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

# writable matplotlib cache before ANY import that might pull matplotlib in
os.environ.setdefault("MPLCONFIGDIR",
                      tempfile.mkdtemp(prefix="mplcache_onesweep_scene_"))

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf                  # noqa: E402
from scenes.reduced_dinner_table import build_reduced_dinner_table    # noqa: E402
from dcr.avbd._solver.passivity import rigid_mechanical_energy        # noqa: E402
from benchmarks.paper_eval.paper_config import (                      # noqa: E402
    apply_relax, apply_passivity)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "onesweep_scene_data")
KAPPA = 2.0                 # shipped implicit-midpoint modal reconstruction
N_GRID_X, N_GRID_Z = 21, 11   # render grid (both builders use the same one)
SUPPORT_THICKNESS = 0.03      # shelf board (kept as the module-level default)
ARMS = ("unfixed", "fixed")

# --------------------------------------------------------------------------- #
# scene registry                                                              #
# --------------------------------------------------------------------------- #
# Each entry maps the recorder's scene-neutral cfg keys onto one builder's own
# argument names, so both acts run through ONE run_arm/record path and land in
# one npz schema. `bystander` is only the noun used in printed/summary prose;
# the npz keys stay `book_*` in both scenes so the schema is literally shared.
SCENES = {
    "shelf": dict(
        builder=build_reduced_shelf,
        title=("reduced_shelf (5 standing books + 6 kg dropped weight on a "
               "soft modal cantilever shelf)"),
        builder_path="scenes/reduced_shelf.build_reduced_shelf",
        bystander="book", bystanders="books", impactor="dropped weight",
        support="board", support_thickness=0.03,
        argmap={"drop_height": "impactor_drop_height",
                "v0": "impactor_v0",
                "impactor_mass": "impactor_mass",
                "youngs": "youngs",
                "density": "density",
                "impactor_dx": "impactor_dx",
                "impactor_dz": "impactor_dz",
                "impactor_tilt": "impactor_tilt"},
        defaults=dict(youngs=0.5e9, density=600.0, impactor_mass=6.0),
        traj="onesweep_scene_traj.npz", summary="scene_data_summary.json"),
    "dinner": dict(
        builder=build_reduced_dinner_table,
        title=("reduced_dinner_table (2.2 x 1.1 m modal table, six place "
               "settings of plate+fork+knife, four teacups, two candlesticks, "
               "and a 5 kg pot dropped from above)"),
        builder_path="scenes/reduced_dinner_table.build_reduced_dinner_table",
        bystander="crockery item", bystanders="crockery", impactor="pot",
        support="table", support_thickness=0.04,
        argmap={"drop_height": "pot_drop_height",
                "v0": "pot_v0_y",
                "impactor_mass": "pot_mass",
                "youngs": "youngs",
                "density": "density",
                "drop_xz": "pot_drop_xz"},
        # DCR §5.1 duplicate: paper Table 2 table material, 5 kg pot.
        defaults=dict(youngs=1.1e9, density=770.0, impactor_mass=5.0),
        traj="onesweep_dinner_traj.npz",
        summary="dinner_data_summary.json"),
}


def scene_of(cfg) -> dict:
    return SCENES[str(cfg.get("scene", "shelf"))]


# --------------------------------------------------------------------------- #
# runtime hooks (reused, not reimplemented)                                   #
# --------------------------------------------------------------------------- #
def matched_weight(sol, kappa: float = KAPPA) -> np.ndarray:
    """Reconstruction-matched contact-row modal weight (foundation note T7-4):

        mu* = m(kappa^2 + b) = kappa^2 * M_q + h^2 * K_q ,   w = 1/mu*

    kappa = 2 is the shipped midpoint commit qdot+ = 2(q-qn)/h - qdotn.
    Damping-independent by construction (T7 case i). Identical to
    run_t9_matched._install_matched_weight; recomputed here so this module can
    also be pointed at a kq-scaled solver.
    """
    mq = np.asarray(sol._mq, dtype=np.float64)
    kq = np.asarray(sol._kq, dtype=np.float64)
    h = float(sol.dt) / int(sol.substeps)
    denom = (kappa * kappa) * mq + (h * h) * kq
    return np.where(mq > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)


def be_implicit_weight(sol) -> np.ndarray:
    """Backward-Euler-shaped implicit weight (M_q + h D_q + h^2 K_q)^-1 -- the
    E-WS weight-swap arm. Matched to kappa = 1, NOT to the shipped kappa = 2;
    kept here only for the disclosed fallback contrast."""
    mq = np.asarray(sol._mq, dtype=np.float64)
    kq = np.asarray(sol._kq, dtype=np.float64)
    dq = np.asarray(sol._dq, dtype=np.float64)
    h = float(sol.dt) / int(sol.substeps)
    denom = mq + h * dq + (h * h) * kq
    return np.where(mq > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)


# --------------------------------------------------------------------------- #
# energy accounting                                                           #
# --------------------------------------------------------------------------- #
def _modal_grav_force(sol) -> np.ndarray:
    """Generalized modal gravity load f_q = M_q * (M_q^-1 f_q) (solver stores the
    acceleration form in _modal_grav_acc)."""
    g = getattr(sol, "_modal_grav_acc", None)
    if g is None:
        return np.zeros(int(np.asarray(sol._mq).size))
    return np.asarray(g, dtype=np.float64) * np.asarray(sol._mq, dtype=np.float64)


def total_energy(sol, fq_grav) -> tuple[float, float, float]:
    """(E_total, E_rigid_mech, E_modal) in joules.

    E_rigid_mech = sum_b [1/2 m|v|^2 + 1/2 w^T I w - m g.x]  (gravity PE included,
    so free fall is flat). E_modal = 1/2 qdot^T M_q qdot + 1/2 q^T K_q q - f_q.q,
    the last term being the modal gravity potential the solver loads through
    _modal_grav_acc (without it the shelf's static sag would read as a free
    energy gain). Contact compliance stores no energy here: support_compliance is
    the XPBD alpha-tilde regularizer, not a physical spring, and the shipped row
    keeps no compliant state between substeps.
    """
    e_rig = rigid_mechanical_energy(sol._V, sol._W, sol._psv_quats_wxyz(),
                                    sol._mass, sol._invIl, X=sol._X,
                                    gravity=sol.gravity)
    q = np.asarray(sol._q, dtype=np.float64)
    qd = np.asarray(sol._qdot, dtype=np.float64)
    mq = np.asarray(sol._mq, dtype=np.float64)
    kq = np.asarray(sol._kq, dtype=np.float64)
    e_mod = (0.5 * float(qd @ (mq * qd)) + 0.5 * float(q @ (kq * q))
             - float(fq_grav @ q))
    return e_rig + e_mod, e_rig, e_mod


# --------------------------------------------------------------------------- #
# one arm                                                                     #
# --------------------------------------------------------------------------- #
def build_scene(cfg):
    sc = scene_of(cfg)
    kw = dict(device="cpu", iterations=int(cfg["K"]), avbd_substeps=int(cfg["S"]),
              solver="xpbd")
    for k_src, k_dst in sc["argmap"].items():
        if cfg.get(k_src) is not None:
            kw[k_dst] = cfg[k_src]
    if str(cfg.get("scene", "shelf")) == "dinner":
        # the dinner builder has no impactor_dx/dz knob: the drop point IS the
        # knob (pot_drop_xz), so the ensemble offsets are folded into it.
        x, z = (float(v) for v in cfg.get("drop_xz", (0.0, 0.0)))
        kw["pot_drop_xz"] = (x + float(cfg.get("impactor_dx", 0.0) or 0.0),
                             z + float(cfg.get("impactor_dz", 0.0) or 0.0))
    H = sc["builder"](**kw)
    sol = H.world._solver
    sol._ensure_arrays()
    apply_relax(sol, "xpbd", float(cfg["relax"]))
    sol._modal_symplectic = bool(cfg.get("symplectic", True))
    apply_passivity(sol, "xpbd", enable=False, eta=1.0)   # governor OFF
    sol._psv_monitor_only = False
    s = float(cfg.get("stiff_scale", 1.0))
    if s != 1.0:
        # zeta-preserving stiffness sweep, exactly the T4/T9 convention
        sol._kq = np.asarray(sol._kq, dtype=np.float64) * s
        sol._dq = np.asarray(sol._dq, dtype=np.float64) * np.sqrt(s)
    return H, sol


def scene_meta(H) -> dict:
    world = H.world
    bodies = []
    for b in H.bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is None:
            continue
        bodies.append(dict(
            name=str(b.name), avbd_idx=int(desc.avbd_body.index),
            half=[float(v) for v in b.half_extents],
            color=[float(v) for v in b.color],
            kind=str(b.render_kind),
            is_impactor=bool(b.dcr_idx == H.impactor_idx)))
    rs = H.rs
    return dict(bodies=bodies,
                support_rest=np.asarray(rs.point_positions_rest, dtype=np.float64),
                support_Uy=np.asarray(rs.U_points[:, 1, :], dtype=np.float64),
                grid=(N_GRID_X, N_GRID_Z))


def run_arm(cfg, arm, *, capture=True, weight_kind=None):
    """One independent run of the full scene. Returns a dict of per-substep
    arrays plus scalar metrics. Never raises on blow-up (reports finite=False)."""
    t0 = time.perf_counter()
    H, sol = build_scene(cfg)
    meta = scene_meta(H)
    idxs = np.array([b["avbd_idx"] for b in meta["bodies"]], dtype=int)
    is_imp = np.array([b["is_impactor"] for b in meta["bodies"]], dtype=bool)
    half = np.array([b["half"] for b in meta["bodies"]], dtype=np.float64)
    nb = len(idxs)
    S = int(sol.substeps)
    h_sub = float(sol.dt) / S

    kind = weight_kind or ("matched" if arm == "fixed" else "shipped")
    if kind == "matched":
        sol._wq_support = matched_weight(sol, float(cfg.get("kappa", KAPPA)))
    elif kind == "be_implicit":
        sol._wq_support = be_implicit_weight(sol)
    elif kind == "shipped":
        sol._wq_support = None
    else:
        raise ValueError("unknown weight kind %r" % kind)
    w_shipped = np.asarray(sol._wq, dtype=np.float64)
    w_used = w_shipped if sol._wq_support is None else np.asarray(sol._wq_support)
    with np.errstate(divide="ignore", invalid="ignore"):
        wratio = np.where(w_shipped > 0, w_used / w_shipped, np.nan)

    fq_grav = _modal_grav_force(sol)
    imp_bi = int(idxs[np.argmax(is_imp)])
    mass = np.asarray(sol._mass, dtype=np.float64)[idxs]
    r = int(np.asarray(sol._q).size)
    F = int(cfg["settle"]) + int(cfg["nframes"])
    N = F * S

    pos = np.zeros((N, nb, 3)); quat = np.zeros((N, nb, 4))
    vel = np.zeros((N, nb, 3)); omg = np.zeros((N, nb, 3))
    qs = np.zeros((N, r))
    e_tot = np.zeros(N); e_rig = np.zeros(N); e_mod = np.zeros(N)
    imp_touch = np.zeros(N, dtype=bool)
    n_active = np.zeros(N, dtype=np.int32)
    box = dict(k=0, finite=True)

    orig_sub = sol._substep_cpu

    def sub_wrapper(hh):
        orig_sub(hh)
        k = box["k"]
        if k >= N or not box["finite"]:
            box["k"] = k + 1
            return
        pos[k] = sol._X[idxs]
        quat[k] = sol._Q[idxs]
        vel[k] = sol._V[idxs]
        omg[k] = sol._W[idxs]
        qs[k] = sol._q
        et, er, em = total_energy(sol, fq_grav)
        e_tot[k], e_rig[k], e_mod[k] = et, er, em
        act = [sc for sc in sol._support if sc.lam > 0.0]
        n_active[k] = len(act)
        imp_touch[k] = any(sc.bi == imp_bi for sc in act)
        if not (np.isfinite(et) and np.all(np.isfinite(pos[k]))):
            box["finite"] = False
        box["k"] = k + 1

    sol._substep_cpu = sub_wrapper
    try:
        for _ in range(F):
            H.world.step()
            if not box["finite"]:
                break
    finally:
        sol._substep_cpu = orig_sub

    n_ok = min(box["k"], N)
    if not box["finite"]:
        n_ok = max(0, n_ok - 1)
    sl = slice(0, n_ok)
    pos, quat, vel, omg, qs = pos[sl], quat[sl], vel[sl], omg[sl], qs[sl]
    e_tot, e_rig, e_mod = e_tot[sl], e_rig[sl], e_mod[sl]
    imp_touch, n_active = imp_touch[sl], n_active[sl]

    # ---- reference state: the last substep before the weight first touches ----
    touch = np.flatnonzero(imp_touch)
    impact = int(touch[0]) if touch.size else -1
    ref = max(0, impact - 1) if impact > 0 else max(0, n_ok - 1)
    book = ~is_imp
    rest_y = pos[ref, :, 1].copy()
    rise = pos[:, :, 1] - rest_y[None, :]
    speed = np.linalg.norm(vel, axis=2)
    book_rise = rise[:, book]
    book_speed = speed[:, book]
    # post-impact window only: before the touch the books are still settling
    post = slice(ref, n_ok)

    # book topple: angle of each book's own +y axis away from world +y
    tilt = np.zeros((n_ok, nb))
    if n_ok:
        x_, y_, z_, w_ = (quat[:, :, 0], quat[:, :, 1], quat[:, :, 2],
                          quat[:, :, 3])
        uy_y = 1.0 - 2.0 * (x_ * x_ + z_ * z_)          # R[1,1] = body +y . world +y
        tilt = np.degrees(np.arccos(np.clip(uy_y, -1.0, 1.0)))
    book_tilt = tilt[:, book]

    # body translational kinetic energy (D2: what fraction of the headline
    # joules is actually MOVING CROCKERY, as opposed to board/table modal
    # energy). Rotational KE is excluded on purpose: this number exists to be
    # compared with "the objects' own motion energy", so it is the translational
    # part only, and it is reported as such.
    ke_tr = 0.5 * (mass[None, :] * np.sum(vel * vel, axis=2))   # (N, nb)
    ke_trans_tot = np.sum(ke_tr, axis=1)
    ke_trans_by = np.sum(ke_tr[:, book], axis=1)

    # support surface deflection U_y q (what the contact row and the render see)
    S_rest = meta["support_rest"]; S_Uy = meta["support_Uy"]
    defl = qs @ S_Uy.T if n_ok else np.zeros((0, S_rest.shape[0]))   # (N, npts)

    # renderability: how far the lowest bystander corner sits under the
    # DEFLECTED support surface (the painter's-algorithm draw order needs this
    # >= -5 mm). Conservative AABB-base proxy, kept for the probe sweep; the
    # recorded arms additionally get the REAL render3d.assert_layering_valid
    # check on sampled frames (rotated box corners, every body) below.
    slack_min = np.inf
    if n_ok:
        step_k = max(1, n_ok // 220)
        for k in range(ref, n_ok, step_k):
            top_y = S_rest[:, 1] + defl[k]
            for i in range(nb):
                if is_imp[i]:
                    continue
                lo = pos[k, i, 1] - float(half[i, 1])   # conservative (AABB base)
                d2 = ((S_rest[:, 0] - pos[k, i, 0]) ** 2
                      + (S_rest[:, 2] - pos[k, i, 2]) ** 2)
                slack_min = min(slack_min, lo - float(top_y[int(np.argmin(d2))]))

    e0 = float(e_tot[ref]) if n_ok else float("nan")
    # ---- M3: the D2 split has to be read at a POST-CONTACT substep ----------
    # `post` starts at `ref`, which is the last substep BEFORE the impactor
    # touches. Any arm whose total energy merely decays after impact (both
    # bounded arms do: the contact is dissipative) therefore had its argmax land
    # on `ref` itself, and its "energy split at peak" described the scene while
    # the impactor was still in the air -- E_modal ~ 0, E_rigid ~ everything,
    # which is true of the state but says nothing about the contact. The peak
    # substep is now the total-energy maximum over [impact, end] whenever a
    # contact was seen; for the injecting arm that is the same substep as
    # before (its maximum is post-contact anyway), so its numbers do not move.
    if n_ok and impact > 0:
        kpk = int(np.argmax(e_tot[impact:n_ok])) + impact
    else:
        kpk = int(np.argmax(e_tot[post])) + ref if n_ok else 0
    return dict(
        arm=arm, weight_kind=kind, meta=meta, pos=pos, quat=quat, vel=vel,
        omega=omg, q=qs, e_tot=e_tot, e_rig=e_rig, e_mod=e_mod,
        imp_touch=imp_touch, n_active=n_active, h_sub=h_sub, S=S,
        n_substeps=int(n_ok), impact_idx=impact, ref_idx=int(ref),
        rest_y=rest_y, is_impactor=is_imp, half=half,
        book_rise_max_mm=float(np.max(book_rise[post]) * 1e3) if n_ok else float("nan"),
        book_rise_per_body_mm=(np.max(book_rise[post], axis=0) * 1e3
                               if n_ok else np.zeros(int(book.sum()))),
        book_speed_max=float(np.max(book_speed[post])) if n_ok else float("nan"),
        book_speed_p99=float(np.percentile(book_speed[post], 99)) if n_ok else float("nan"),
        e_ref=e0,
        e_init=float(e_tot[0]) if n_ok else float("nan"),
        e_peak=float(np.max(e_tot[post])) if n_ok else float("nan"),
        e_end=float(e_tot[n_ok - 1]) if n_ok else float("nan"),
        e_peak_at_ms=(float((int(np.argmax(e_tot[post])) + ref - impact) * h_sub
                            * 1e3) if n_ok else float("nan")),
        n_substeps_over_ref=int(np.sum(e_tot[post] > e0 + 1e-9)) if n_ok else 0,
        impactor_rebound_mm=(float((np.max(pos[impact:, is_imp, 1])
                                    - rest_y[is_imp][0]) * 1e3)
                             if (n_ok and impact > 0) else float("nan")),
        e_max_gain=float(np.max(e_tot[post]) - e0) if n_ok else float("nan"),
        e_end_gain=float(e_tot[n_ok - 1] - e0) if n_ok else float("nan"),
        e_mod_peak=float(np.max(e_mod[post])) if n_ok else float("nan"),
        # ---- D2 split, evaluated AT the total-energy peak substep ----------
        ke_trans=ke_trans_tot, ke_trans_bystander=ke_trans_by, mass=mass,
        peak_idx=int(kpk),
        peak_is_post_contact=bool(n_ok and impact > 0 and kpk >= impact),
        e_tot_at_peak=float(e_tot[kpk]) if n_ok else float("nan"),
        e_mod_at_peak=float(e_mod[kpk]) if n_ok else float("nan"),
        e_rig_at_peak=float(e_rig[kpk]) if n_ok else float("nan"),
        ke_trans_at_peak=float(ke_trans_tot[kpk]) if n_ok else float("nan"),
        ke_trans_bystander_at_peak=(float(ke_trans_by[kpk]) if n_ok
                                    else float("nan")),
        ke_trans_bystander_max=(float(np.max(ke_trans_by[post])) if n_ok
                                else float("nan")),
        ke_trans_max=float(np.max(ke_trans_tot[post])) if n_ok else float("nan"),
        book_tilt=book_tilt, tilt=tilt, defl=defl,
        book_tilt_max_deg=float(np.max(book_tilt[post])) if n_ok else float("nan"),
        book_tilt_end_deg=(float(np.max(book_tilt[n_ok - 1])) if n_ok
                           else float("nan")),
        slab_defl_absmax_mm=(float(np.max(np.abs(defl[post]))) * 1e3 if n_ok
                             else float("nan")),
        w_ratio_min=float(np.nanmin(wratio)), w_ratio_max=float(np.nanmax(wratio)),
        slack_min_mm=float(slack_min * 1e3) if np.isfinite(slack_min) else float("nan"),
        finite=bool(box["finite"]), wall_s=time.perf_counter() - t0)


# --------------------------------------------------------------------------- #
# renderability: the REAL check the video's draw order relies on              #
# --------------------------------------------------------------------------- #
def layering_report(a, *, n_samples=240, tol=5e-3) -> dict:
    """Run render3d.assert_layering_valid on sampled frames of one arm.

    The video draws the support slab in a layer BEHIND every body; that is only
    exact if no body ever sits under the DEFLECTED support surface. Same call
    the frame builder makes (rotated box corners, all bodies, deflected slab),
    evaluated here so an operating point that cannot be depth-ordered honestly
    is rejected at record time rather than discovered at render time.
    """
    from benchmarks.paper_fig.render3d import (assert_layering_valid,
                                               box_corners, slab_top)
    n = int(a["n_substeps"])
    if n <= 0:
        return dict(checked=0, ok=False, worst_slack_mm=float("nan"),
                    error="empty trajectory")
    lo = int(a["ref_idx"])
    ks = np.unique(np.linspace(lo, n - 1, min(n_samples, n - lo)).astype(int))
    worst, err = np.inf, None
    for k in ks:
        top = slab_top(a["meta"]["support_rest"], a["meta"]["support_Uy"],
                       a["q"][k])
        bottoms = []
        for i in range(a["pos"].shape[1]):
            V = box_corners(a["half"][i], a["pos"][k, i], a["quat"][k, i])
            bottoms.append(V[int(np.argmin(V[:, 1]))])
        B = np.asarray(bottoms)
        d2 = ((B[:, None, 0] - top[None, :, 0]) ** 2
              + (B[:, None, 2] - top[None, :, 2]) ** 2)
        worst = min(worst, float(np.min(B[:, 1] - top[np.argmin(d2, axis=1), 1])))
        try:
            assert_layering_valid(B, top, tol=tol)
        except ValueError as exc:
            err = "substep %d: %s" % (k, exc)
            break
    return dict(checked=int(ks.size), ok=bool(err is None),
                worst_slack_mm=worst * 1e3, tol_mm=tol * 1e3, error=err)


# --------------------------------------------------------------------------- #
# probe                                                                       #
# --------------------------------------------------------------------------- #
def probe(cfgs, arms=ARMS, weight_kinds=None):
    print("%-30s %-8s | %8s %7s %7s %7s %10s %9s %8s %5s"
          % ("config", "arm", "rise_mm", "spd", "tilt", "slab_mm", "dE_max",
             "Emod_pk", "slack_mm", "ok"), flush=True)
    out = []
    for cfg in cfgs:
        xz = cfg.get("drop_xz")
        label = ("%dx%d r%.2g s%.4g h%.3g%s"
                 % (cfg["K"], cfg["S"], cfg["relax"],
                    cfg.get("stiff_scale", 1.0), cfg.get("drop_height", 0.5),
                    "" if xz is None else " @%+.2f,%+.2f" % tuple(xz)))
        row = dict(cfg=cfg, label=label)
        todo = [(a, cfg, (weight_kinds or {}).get(a)) for a in arms]
        if cfg.get("ref_budget"):
            rk, rs = cfg["ref_budget"]
            cref = dict(cfg); cref.update(K=rk, S=rs)
            todo.append(("ref%dx%d" % (rk, rs), cref, "shipped"))
        for arm, ccfg, kind in todo:
            a = run_arm(ccfg, arm, weight_kind=kind)
            row[arm] = a
            print("%-30s %-8s | %8.2f %7.3f %7.1f %7.2f %+10.3g %9.4g %8.2f %5s"
                  % (label, arm, a["book_rise_max_mm"], a["book_speed_max"],
                     a["book_tilt_max_deg"], a["slab_defl_absmax_mm"],
                     a["e_max_gain"], a["e_mod_peak"], a["slack_min_mm"],
                     a["finite"]), flush=True)
        out.append(row)
    return out


# --------------------------------------------------------------------------- #
# record                                                                      #
# --------------------------------------------------------------------------- #
def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def _reference_spread_sentence(ref_arm, xref) -> str:
    """D3: say what the two converged self-references actually do.

    Act 1 (steel shelf) they disagree by two orders of magnitude; on a soft
    table they agree. Writing either outcome as a fixed sentence is how a stale
    claim gets shipped, so the wording is derived from the measured spread.
    """
    a = float(ref_arm["book_rise_max_mm"])
    b = float(xref["book_rise_max_mm"]) if xref else float("nan")
    lo, hi = (min(a, b), max(a, b)) if np.isfinite(b) else (a, a)
    if not np.isfinite(b):
        return ("Only one converged self-reference was run (%.2f mm peak "
                "bystander rise); the legitimate scale is quoted from it "
                "alone." % a)
    rel = (hi - lo) / max(hi, 1e-12)
    verdict = ("DISAGREE (%.0fx apart)" % (hi / max(lo, 1e-12)) if rel > 0.2
               else "AGREE to within %.1f%%" % (100.0 * rel))
    return ("The two converged self-references %s on the legitimate bystander "
            "scale (%.2f mm at the recorded substep grid vs %.2f mm at one "
            "substep per frame), so 'the true motion' is quoted as the range "
            "%.2f-%.2f mm, never as a single number."
            % (verdict, a, b, lo, hi))


def budget_grading(cfg, ks=(2, 4, 8), weight_kind="shipped"):
    """D1 evidence: the effect is BUDGET-GRADED, measured on the same substep
    grid as the recorded arms. An undisclosed budget reads as rigging, so the
    artifact carries the grading rather than asserting it."""
    out = []
    for K in ks:
        c = dict(cfg); c["K"] = int(K)
        a = run_arm(c, "grade%d" % K, weight_kind=weight_kind)
        out.append(dict(budget="%dx%d" % (K, cfg["S"]), iterations=int(K),
                        substeps=int(cfg["S"]),
                        e_max_gain_J=a["e_max_gain"],
                        e_modal_peak_J=a["e_mod_peak"],
                        bystander_rise_max_mm=a["book_rise_max_mm"],
                        bystander_tilt_max_deg=a["book_tilt_max_deg"]))
        print("  grading %-6s dE %+10.4g J  rise %7.2f mm  tilt %6.1f deg"
              % (out[-1]["budget"], a["e_max_gain"], a["book_rise_max_mm"],
                 a["book_tilt_max_deg"]), flush=True)
    return out


def _split_at(a, k: int, definition: str) -> dict:
    """The D2 energy split of one arm AT one substep (M3).

    Every field is read at the same index k, so the block cannot mix a total
    taken at one substep with a modal part taken at another.
    """
    k = int(min(max(k, 0), max(int(a["n_substeps"]) - 1, 0)))
    et = float(a["e_tot"][k])
    return dict(
        substep=k, peak_definition=definition,
        ms_after_impact=float((k - int(a["impact_idx"])) * float(a["h_sub"])
                              * 1e3),
        is_post_contact=bool(int(a["impact_idx"]) > 0
                             and k >= int(a["impact_idx"])),
        e_total_J=et,
        e_modal_J=float(a["e_mod"][k]),
        e_rigid_mech_J=float(a["e_rig"][k]),
        body_translational_KE_J=float(a["ke_trans"][k]),
        bystander_translational_KE_J=float(a["ke_trans_bystander"][k]),
        modal_fraction_of_total=float(a["e_mod"][k]) / max(abs(et), 1e-30))


def record(cfg, out_dir=OUT, perturb=(), weight_kinds=None, note="",
           ref_budget=(32, 8), extra_ref=(500, 1), grade_ks=(2, 4, 8)):
    os.makedirs(out_dir, exist_ok=True)
    SC = scene_of(cfg)
    arms = {}
    plan = [(arm, cfg, (weight_kinds or {}).get(arm)) for arm in ARMS]
    if ref_budget:
        cref = dict(cfg); cref.update(K=ref_budget[0], S=ref_budget[1])
        plan.append(("ref", cref, "shipped"))
    for arm, ccfg, kind in plan:
        arms[arm] = run_arm(ccfg, arm, weight_kind=kind)
        a = arms[arm]
        print("  %-8s (%s, %dx%d): rise %.2f mm  spd %.3f m/s  tilt %.1f deg  "
              "dE_max %+.4g J  Emod_pk %.4g J  slack %.2f mm  N=%d  [%.1f s]"
              % (arm, a["weight_kind"], ccfg["K"], ccfg["S"],
                 a["book_rise_max_mm"], a["book_speed_max"],
                 a["book_tilt_max_deg"], a["e_max_gain"], a["e_mod_peak"],
                 a["slack_min_mm"], a["n_substeps"], a["wall_s"]), flush=True)
    rec_arms = tuple(arms)

    # second, substep-1 converged self-reference: scalars only (its h_sub does
    # not match the recorded arms, so it is reported, not rendered)
    xref = None
    if extra_ref:
        c2 = dict(cfg); c2.update(K=extra_ref[0], S=extra_ref[1])
        e = run_arm(c2, "xref", weight_kind="shipped")
        xref = dict(budget="%dx%d" % extra_ref, book_rise_max_mm=e["book_rise_max_mm"],
                    book_speed_max_mps=e["book_speed_max"],
                    book_tilt_max_deg=e["book_tilt_max_deg"],
                    e_max_gain_J=e["e_max_gain"], e_modal_peak_J=e["e_mod_peak"],
                    h_substep_s=e["h_sub"])
        print("  xref     (shipped, %dx%d): rise %.2f mm  tilt %.1f deg  "
              "dE_max %+.4g J" % (extra_ref[0], extra_ref[1],
                                  e["book_rise_max_mm"], e["book_tilt_max_deg"],
                                  e["e_max_gain"]), flush=True)

    A, B = arms["unfixed"], arms["fixed"]
    n = min(a["n_substeps"] for a in arms.values())
    meta = A["meta"]
    flat = {}
    for arm, a in arms.items():
        flat[f"{arm}/pos"] = a["pos"].astype(np.float64)
        flat[f"{arm}/quat"] = a["quat"].astype(np.float64)
        flat[f"{arm}/vel"] = a["vel"].astype(np.float64)
        flat[f"{arm}/omega"] = a["omega"].astype(np.float64)
        flat[f"{arm}/q"] = a["q"].astype(np.float64)
        flat[f"{arm}/e_total"] = a["e_tot"]
        flat[f"{arm}/e_rigid"] = a["e_rig"]
        flat[f"{arm}/e_modal"] = a["e_mod"]
        flat[f"{arm}/book_rise_mm"] = ((a["pos"][:, ~a["is_impactor"], 1]
                                        - a["rest_y"][None, ~a["is_impactor"]])
                                       * 1e3)
        flat[f"{arm}/book_speed"] = np.linalg.norm(
            a["vel"][:, ~a["is_impactor"], :], axis=2)
        flat[f"{arm}/book_tilt_deg"] = a["book_tilt"]
        flat[f"{arm}/slab_defl_absmax_mm"] = (
            np.max(np.abs(a["defl"]), axis=1) * 1e3 if a["defl"].size
            else np.zeros(0))
        flat[f"{arm}/h_sub"] = np.float64(a["h_sub"])
        flat[f"{arm}/imp_touch"] = a["imp_touch"]
        flat[f"{arm}/n_active_support"] = a["n_active"]
        flat[f"{arm}/impact_idx"] = np.int64(a["impact_idx"])
        flat[f"{arm}/ref_idx"] = np.int64(a["ref_idx"])
        flat[f"{arm}/rest_y"] = a["rest_y"]
        flat[f"{arm}/n_substeps"] = np.int64(a["n_substeps"])
        flat[f"{arm}/e_ref"] = np.float64(a["e_ref"])
        flat[f"{arm}/weight_kind"] = np.str_(a["weight_kind"])
        # D2 split: modal/board energy vs the bodies' own translational KE
        flat[f"{arm}/ke_trans"] = a["ke_trans"]
        flat[f"{arm}/ke_trans_bystander"] = a["ke_trans_bystander"]
    flat["support_rest"] = meta["support_rest"]
    flat["support_Uy"] = meta["support_Uy"]
    flat["grid"] = np.array(meta["grid"], dtype=np.int64)
    flat["half"] = A["half"]
    flat["color"] = np.array([b["color"] for b in meta["bodies"]],
                             dtype=np.float64)
    flat["body_names"] = np.array([b["name"] for b in meta["bodies"]])
    flat["is_impactor"] = A["is_impactor"]
    flat["body_kinds"] = np.array([b["kind"] for b in meta["bodies"]])
    flat["mass"] = A["mass"]
    flat["scene"] = np.str_(str(cfg.get("scene", "shelf")))
    flat["support_thickness"] = np.float64(SC["support_thickness"])
    flat["h_sub"] = np.float64(A["h_sub"])
    flat["h_frame"] = np.float64(cfg.get("h", 1.0 / 120.0))
    flat["substeps"] = np.int64(A["S"])
    flat["arm_labels"] = np.array([
        "unfixed: shipped stiffness-blind contact-row modal weight 1/M_q",
        "fixed: reconstruction-matched charge mass 1/(4 M_q + h^2 K_q)",
        "converged reference: shipped weight at %dx%d, same substep grid"
        % (ref_budget or (0, 0))][:len(rec_arms)])
    flat["arm_names"] = np.array(list(rec_arms))
    flat["n_common"] = np.int64(n)

    # D1: the same shipped weight at richer budgets, same substep grid
    grading = budget_grading(cfg, ks=grade_ks) if grade_ks else []

    # deterministic neighbourhood ensemble: is the contrast knife-edge?
    ens = []
    for p in perturb:
        c2 = dict(cfg); c2.update(p)
        row = dict(perturb=p)
        for arm in ARMS:
            a = run_arm(c2, arm, weight_kind=(weight_kinds or {}).get(arm))
            row[arm] = dict(book_rise_max_mm=a["book_rise_max_mm"],
                            book_speed_max=a["book_speed_max"],
                            book_tilt_max_deg=a["book_tilt_max_deg"],
                            e_max_gain_J=a["e_max_gain"],
                            e_mod_peak_J=a["e_mod_peak"],
                            finite=a["finite"])
        ens.append(row)
        print("  perturb %-28s unfixed rise %8.2f mm / fixed %6.2f mm"
              % (json.dumps(p), row["unfixed"]["book_rise_max_mm"],
                 row["fixed"]["book_rise_max_mm"]), flush=True)

    npz = os.path.join(out_dir, SC["traj"])
    np.savez_compressed(npz, **flat)

    # the real render-order guard, on every recorded arm
    layering = {arm: layering_report(arms[arm]) for arm in rec_arms}
    for arm, L in layering.items():
        print("  layering %-6s: %s (%d frames checked, worst slack %+.3f mm)%s"
              % (arm, "OK" if L["ok"] else "FAIL", L["checked"],
                 L["worst_slack_mm"], "" if L["ok"] else "  " + str(L["error"])),
              flush=True)

    summary = dict(
        generated_by="benchmarks/paper_fig/onesweep_scene_record.py",
        commit=_git_commit(), machine=platform.machine(),
        system=platform.system(), python=platform.python_version(),
        note=note,
        scene=dict(
            key=str(cfg.get("scene", "shelf")),
            name=SC["title"],
            builder=SC["builder_path"],
            youngs_Pa=cfg.get("youngs", SC["defaults"]["youngs"]),
            density=cfg.get("density", SC["defaults"]["density"]),
            impactor_mass_kg=cfg.get("impactor_mass",
                                     SC["defaults"]["impactor_mass"]),
            drop_height_m=cfg.get("drop_height", 0.5),
            drop_xz_m=list(cfg.get("drop_xz", (0.0, 0.0))),
            impactor_v0=cfg.get("v0", 0.0),
            n_bodies=len(meta["bodies"]),
            n_bystanders=int(np.sum(~A["is_impactor"])),
            bystander_noun=SC["bystanders"],
            n_modes=int(A["q"].shape[1]),
            support_grid=list(meta["grid"]),
            support_thickness_m=SC["support_thickness"]),
        operating_point=dict(
            solver="xpbd (shipped SolverXPBD)",
            iterations=int(cfg["K"]), substeps=int(cfg["S"]),
            budget="%dx%d" % (cfg["K"], cfg["S"]),
            modal_relax=float(cfg["relax"]),
            reconstruction=("symplectic implicit-midpoint (shipped, kappa=2)"
                            if cfg.get("symplectic", True)
                            else "backward Euler (kappa=1)"),
            stiffness_scale=float(cfg.get("stiff_scale", 1.0)),
            passivity_governor="OFF (both arms)",
            h_frame_s=float(cfg.get("h", 1.0 / 120.0)),
            h_substep_s=float(A["h_sub"]),
            settle_frames=int(cfg["settle"]), logged_frames=int(cfg["nframes"])),
        arms={arm: dict(
            weight_kind=arms[arm]["weight_kind"],
            budget=("%dx%d" % (ref_budget if arm == "ref"
                               else (cfg["K"], cfg["S"]))),
            weight_ratio_to_shipped=[arms[arm]["w_ratio_min"],
                                     arms[arm]["w_ratio_max"]],
            n_substeps=arms[arm]["n_substeps"],
            h_substep_s=arms[arm]["h_sub"],
            impact_substep=arms[arm]["impact_idx"],
            ref_substep=arms[arm]["ref_idx"],
            finite=arms[arm]["finite"],
            book_rise_max_mm=arms[arm]["book_rise_max_mm"],
            book_rise_per_book_mm=[float(v) for v in
                                   arms[arm]["book_rise_per_body_mm"]],
            book_speed_max_mps=arms[arm]["book_speed_max"],
            book_speed_p99_mps=arms[arm]["book_speed_p99"],
            book_tilt_max_deg=arms[arm]["book_tilt_max_deg"],
            slab_defl_absmax_mm=arms[arm]["slab_defl_absmax_mm"],
            impactor_rebound_mm=arms[arm]["impactor_rebound_mm"],
            e_init_J=arms[arm]["e_init"],
            e_ref_J=arms[arm]["e_ref"],
            e_peak_J=arms[arm]["e_peak"],
            e_peak_at_ms_after_impact=arms[arm]["e_peak_at_ms"],
            e_end_J=arms[arm]["e_end"],
            n_substeps_above_pre_impact=arms[arm]["n_substeps_over_ref"],
            e_max_gain_J=arms[arm]["e_max_gain"],
            e_end_gain_J=arms[arm]["e_end_gain"],
            e_modal_peak_J=arms[arm]["e_mod_peak"],
            # ---- D2: what the headline joules actually ARE ----------------
            # Read at the arm's own POST-CONTACT total-energy maximum (M3), not
            # at the maximum over a window that starts one substep before the
            # impactor lands. `e_total_J` here is the total AT that substep, so
            # the block is internally consistent; the window maximum is still
            # reported separately as e_peak_J above.
            energy_split_at_peak=_split_at(arms[arm], arms[arm]["peak_idx"],
                                           "post-contact total-energy maximum "
                                           "of this arm"),
            # the same split for every arm at ONE substep -- the injecting
            # arm's peak -- so the three arms can be compared at one instant
            energy_split_at_unfixed_peak_substep=_split_at(
                arms[arm], arms["unfixed"]["peak_idx"],
                "the unfixed arm's post-contact total-energy peak substep"),
            bystander_translational_KE_max_J=arms[arm]["ke_trans_bystander_max"],
            body_translational_KE_max_J=arms[arm]["ke_trans_max"],
            render_slack_min_mm=arms[arm]["slack_min_mm"],
            render_layering=layering[arm],
            wall_s=arms[arm]["wall_s"]) for arm in rec_arms},
        second_reference=xref,
        budget_grading=grading,
        contrast=dict(
            book_rise_ratio=(A["book_rise_max_mm"]
                             / max(abs(B["book_rise_max_mm"]), 1e-9)),
            book_speed_ratio=(A["book_speed_max"]
                              / max(abs(B["book_speed_max"]), 1e-9)),
            book_tilt_ratio=(A["book_tilt_max_deg"]
                             / max(abs(B["book_tilt_max_deg"]), 1e-9)),
            energy_gain_ratio=(A["e_max_gain"] / max(abs(B["e_max_gain"]), 1e-9)),
            modal_peak_ratio=(A["e_mod_peak"] / max(abs(B["e_mod_peak"]), 1e-9)),
            bystander_KE_ratio=(A["ke_trans_bystander_max"]
                                / max(abs(B["ke_trans_bystander_max"]), 1e-12)),
            impact_energy_budget_J=(
                float(cfg.get("impactor_mass", SC["defaults"]["impactor_mass"]))
                * 9.81 * float(cfg.get("drop_height", 0.5))),
            unfixed_injects=bool(A["e_max_gain"] > 0.0),
            fixed_bounded=bool(B["e_max_gain"] <= max(0.02 * abs(A["e_max_gain"]),
                                                      1e-3)),
            fixed_strictly_passive=bool(B["e_max_gain"] <= 0.0),
            # REJECTION GATE: if the unfixed arm does not out-move the
            # converged reference, the motion is not attributable to injection.
            unfixed_outmoves_reference=bool(
                A["book_rise_max_mm"]
                > arms.get("ref", A)["book_rise_max_mm"]),
            unfixed_over_reference_x=(
                A["book_rise_max_mm"]
                / max(arms.get("ref", A)["book_rise_max_mm"], 1e-9)),
            render_layering_ok_all_arms=bool(
                all(layering[a]["ok"] for a in rec_arms))),
        ensemble=ens,
        disclosures=[
            "The injection PHENOMENON (a finite-budget contact sweep depositing "
            "energy) is known prior art and is conceded, not claimed. What the "
            "two arms differ in is the contact-row modal weight.",
            "Both arms are independent runs from identical build states; nothing "
            "is toggled mid-trajectory and no body is parked or isolated.",
            "The passivity governor / clamp is OFF in both arms. The fixed arm's "
            "boundedness comes from the row weight alone.",
            "The boundary is an energy-SIGN effect, not a stability threshold: "
            "the unfixed arm never goes non-finite over this clip.",
            "The unfixed arm is already %+0.1f J from the fixed arm at the "
            "instant the %s lands: the RESTING objects' own support rows inject "
            "during the fall."
            % (arms["unfixed"]["e_ref"] - arms["fixed"]["e_ref"],
               SC["impactor"]),
            "D2: the headline joules are almost entirely %s-MODE (modal) "
            "energy, not the objects' own motion. At the unfixed peak: "
            "E_total = %.4g J, of which E_modal = %.4g J (%.3f%%), while the "
            "bodies' translational KE is %.4g J (bystanders alone %.4g J)."
            % (SC["support"], arms["unfixed"]["e_peak"],
               arms["unfixed"]["e_mod_at_peak"],
               100.0 * arms["unfixed"]["e_mod_at_peak"]
               / max(abs(arms["unfixed"]["e_peak"]), 1e-30),
               arms["unfixed"]["ke_trans_at_peak"],
               arms["unfixed"]["ke_trans_bystander_at_peak"]),
            "Fidelity caveat: the matched weight is CONSERVATIVE here. Against "
            "the substep-matched converged reference the fixed arm under-moves "
            "the bystanders (%.1f mm vs %.1f mm peak rise, %.1f deg vs %.1f deg "
            "peak tilt) while the unfixed arm over-moves them by %.1fx."
            % (arms["fixed"]["book_rise_max_mm"],
               arms.get("ref", arms["fixed"])["book_rise_max_mm"],
               arms["fixed"]["book_tilt_max_deg"],
               arms.get("ref", arms["fixed"])["book_tilt_max_deg"],
               arms["unfixed"]["book_rise_max_mm"]
               / max(arms.get("ref", arms["fixed"])["book_rise_max_mm"], 1e-9)),
            _reference_spread_sentence(arms.get("ref", arms["fixed"]), xref),
            "Both arms still show a spurious impactor rebound (%.1f mm unfixed, "
            "%.1f mm fixed, %.1f mm converged): the matched weight fixes the "
            "modal contact row, not every fixed-budget error."
            % (arms["unfixed"]["impactor_rebound_mm"],
               arms["fixed"]["impactor_rebound_mm"],
               arms.get("ref", arms["fixed"])["impactor_rebound_mm"]),
            "The render draw order (support behind bodies) was checked with the "
            "video's own render3d.assert_layering_valid on sampled frames of "
            "every recorded arm: %s."
            % "; ".join("%s %s (worst slack %+.3f mm)"
                        % (a, "OK" if layering[a]["ok"] else "FAIL",
                           layering[a]["worst_slack_mm"]) for a in rec_arms),
            "D1: the effect is BUDGET-GRADED, not a property of the scene. "
            "Holding the substep grid fixed and raising only the iteration "
            "count, the same shipped weight gives %s. The recorded operating "
            "point (%d iteration(s) x %d substeps) must therefore be stated "
            "wherever these numbers are shown."
            % ("; ".join("%s -> %+.4g J" % (g["budget"], g["e_max_gain_J"])
                         for g in ([dict(budget="%dx%d" % (cfg["K"], cfg["S"]),
                                         e_max_gain_J=A["e_max_gain"])]
                                   + list(grading))) or "no grading run",
               int(cfg["K"]), int(cfg["S"])),
            "No real-time claim is supported by this recording: it is an offline "
            "CPU float64 run.",
        ],
        npz=os.path.abspath(npz))
    js = os.path.join(out_dir, SC["summary"])
    with open(js, "w") as fh:
        json.dump(summary, fh, indent=2, default=float)
    print("wrote %s" % npz)
    print("wrote %s" % js)
    return summary


# --------------------------------------------------------------------------- #
CFG = dict(scene="shelf", K=8, S=2, relax=1.0, stiff_scale=1.0,
           drop_height=0.5, drop_xz=(0.0, 0.0), v0=0.0,
           settle=8, nframes=100, symplectic=True, kappa=KAPPA, h=1.0 / 120.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--scene", default="shelf", choices=sorted(SCENES))
    ap.add_argument("--drop-xz", default="",
                    help="dinner only: comma-separated x:z drop points, e.g. "
                         "'0:0,-0.72:0.34' (pot_drop_xz)")
    ap.add_argument("--budgets", default="8x2")
    ap.add_argument("--relaxes", default="1.0")
    ap.add_argument("--stiff", default="1.0")
    ap.add_argument("--drops", default="0.5")
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--settle", type=int, default=8)
    ap.add_argument("--be", action="store_true",
                    help="backward-Euler reconstruction (fallback contrast)")
    ap.add_argument("--fixed-kind", default=None,
                    help="matched | be_implicit | shipped")
    ap.add_argument("--unfixed-kind", default=None)
    ap.add_argument("--youngs", type=float, default=None)
    ap.add_argument("--density", type=float, default=None)
    ap.add_argument("--impactor-mass", type=float, default=None)
    ap.add_argument("--steel", action="store_true",
                    help="steel board (E=200 GPa, rho=7850): the legitimate "
                         "bystander response is ~0, so any book motion is spurious")
    ap.add_argument("--ref-budget", default="",
                    help="also run a converged shipped-weight reference, e.g. 64x4")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    wk = {}
    if args.fixed_kind:
        wk["fixed"] = args.fixed_kind
    if args.unfixed_kind:
        wk["unfixed"] = args.unfixed_kind

    budgets = [tuple(int(v) for v in b.lower().split("x"))
               for b in args.budgets.split(",") if b.strip()]
    relaxes = [float(v) for v in args.relaxes.split(",") if v.strip()]
    stiffs = [float(v) for v in args.stiff.split(",") if v.strip()]
    drops = [float(v) for v in args.drops.split(",") if v.strip()]
    xzs = [tuple(float(v) for v in p.split(":"))
           for p in args.drop_xz.split(",") if p.strip()] or [(0.0, 0.0)]

    cfgs = []
    for (K, S) in budgets:
        for r in relaxes:
            for s in stiffs:
                for d in drops:
                    for xz in xzs:
                        c = dict(CFG)
                        c.update(scene=args.scene, K=K, S=S, relax=r,
                                 stiff_scale=s, drop_height=d, drop_xz=xz,
                                 nframes=args.nframes, settle=args.settle,
                                 symplectic=not args.be)
                        c.update(SCENES[args.scene]["defaults"])
                        if args.steel:
                            c.update(youngs=2.00e11, density=7850.0)
                        if args.youngs is not None:
                            c["youngs"] = args.youngs
                        if args.density is not None:
                            c["density"] = args.density
                        if args.impactor_mass is not None:
                            c["impactor_mass"] = args.impactor_mass
                        if args.ref_budget:
                            c["ref_budget"] = tuple(
                                int(v) for v in args.ref_budget.lower().split("x"))
                        cfgs.append(c)
    if args.probe:
        probe(cfgs, weight_kinds=wk)
    else:
        rb = (tuple(int(v) for v in args.ref_budget.lower().split("x"))
              if args.ref_budget else (32, 8))
        c = dict(cfgs[0])
        c.pop("ref_budget", None)
        # deterministic neighbourhood: the dinner builder has no tilt knob, so
        # its fourth perturbation is a 1 % drop-height change instead.
        pert = (dict(impactor_dx=+0.004), dict(impactor_dx=-0.004),
                dict(impactor_dz=+0.004),
                dict(impactor_tilt=0.02) if args.scene == "shelf"
                else dict(drop_height=float(c["drop_height"]) * 1.01))
        record(c, out_dir=args.out, weight_kinds=wk, note=args.note,
               ref_budget=rb, perturb=pert)


if __name__ == "__main__":
    main()
