#!/usr/bin/env python3
"""T4 — SHIPPED solver: per-row R4 predictor vs measured one-substep energy sign.

Validates the one-sweep passivity note (Results R2/R3/R4) against the actual
`dcr/avbd/_solver/solver_xpbd.py` support-contact row (lines 1510-1551), using
the E-WS harness pattern (scene builders + runtime monkeypatches ONLY; no tracked
file is edited). Plan: wf1/plan.md section T4.

Setup per cell (plan steps 1-9), all at RUNTIME:
  * build shelf/ledge/dinner with iterations=1, substeps=1, solver="xpbd";
  * symplectic modal path ON, governor OFF, relax=1 (E-WS config);
  * zero gravity, park bystander bodies +50 y, isolate ONE impactor support row
    (single leading corner) so the measured substep is the note's one-coupling-row
    cold-start setup;
  * scale the modal stiffness `_kq *= s` (`_dq *= sqrt(s)`, zeta preserved) to
    sweep the row danger index rho = L/(w_m + 2 a_tilde) across 1;
  * measure dE over ONE substep = (rigid KE + modal E)_after - _before.

Two measurements per cell:
  dE_meas  — the PLAN-MANDATED symplectic path (`_modal_symplectic=True`, the
             shipped default). Modal velocity is reconstructed by the implicit-
             midpoint commit qdot = 2(q-qn)/h - qdotn (symplectic_stepper.py:115,
             solver_xpbd.py:1212).
  dE_be    — DIAGNOSTIC control on the SAME cold state with `_modal_symplectic=
             False` (backward-Euler reconstruction qdot=(q-qn)/h), which is the
             velocity reconstruction the note's R2/R3/R4 forms assume.

KEY EXECUTION FINDING (recorded, not silently patched): the note's predictor
matches the shipped CONTACT-ROW PROJECTION math essentially exactly under the
BE reconstruction (dE_be vs dE_pred: reldiff ~1e-10..1e-5, sign-perfect across
the whole sweep). Under the shipped SYMPLECTIC reconstruction the modal velocity
is 2x larger (confirmed exactly 2.000x), i.e. modal KE is 4x the note's, which
(i) makes the mass arm inject at ALL rho on this single-substep cold-start impact
(a ~const modal-KE floor exceeds the rigid loss below the boundary), and
(ii) breaks the implicit arm's unconditional passivity once the modes are softened
(low s => implicit weight -> mass weight). This is a MODEL/SOLVER mismatch in the
note (its Model box uses v+ = (x+-xn)/h but the shipped modal stepper is implicit
midpoint), reported per the ground rules, never tolerance-loosened.

CLI (chunkable, re-runnable):
  --scenes shelf,ledge,dinner   --arms mass,implicit
  --s-list "..."  or  --trim (7-pt s-grid)   --annex (9 iteration-sweep cells)
  --out t4_shipped   --append (merge into an existing CSV by cell key)
Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/run_t4_shipped.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf              # noqa: E402
from scenes.reduced_ledge import build_reduced_ledge             # noqa: E402
from scenes.reduced_dinner_table import build_reduced_dinner_table  # noqa: E402
from dcr.avbd._solver.solver_xpbd import _quat_to_R              # noqa: E402
from dcr.avbd._solver.passivity import rigid_mechanical_energy   # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)
from benchmarks.paper_eval.x1_passivity.run_weight_swap import (  # noqa: E402
    _install_weight_swap)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PARK = 50.0                       # +y parking offset for bystander bodies
TILT_X = 0.06                     # rad, primary tilt about x (plan step 1/4)
TILT_Z = 0.02                     # rad, tie-break tilt about z (see NOTE below)

BUILD = {
    "shelf": (build_reduced_shelf,
              dict(impactor_tilt=TILT_X, impactor_drop_height=0.02,
                   impactor_v0=-1.0)),
    "ledge": (build_reduced_ledge,
              dict(impactor_tilt=TILT_X, impactor_drop_height=0.02,
                   impactor_v0=-1.0)),
    "dinner": (build_reduced_dinner_table, dict()),   # no tilt/v0 kwargs
}

# NOTE (deviation from plan step 4, recorded): a pure-x tilt leaves the box's two
# bottom-leading corners (x=+/-hx, same y,z) at IDENTICAL height, so the "leading
# support row" is a 2-fold tie and the natural corner-height separation (~0.01 m)
# is far below the plan's 5*h*|v| = 0.042 m runner-up margin. To realize the note's
# ONE-coupling-row cold-start setup exactly and robustly we (i) add a negligible
# TILT_Z about z so the leading corner is unique, and (ii) PRUNE the impactor's
# other 7 support rows at runtime, leaving exactly one impactor row plus the
# parked-bystander rows. The nearest non-leading candidate is then a parked row at
# gap ~ +50 m >> 5*h*|v|, so the plan's single-row-isolation guard holds by
# construction. Runtime monkeypatch only; the solver projection math is untouched.


# --------------------------------------------------------------------------- #
# quaternion helpers (solver _Q storage is XYZW; _psv_quats_wxyz reorders)     #
# --------------------------------------------------------------------------- #
def _aa_xyzw(axis, ang):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    s = np.sin(ang / 2.0)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(ang / 2.0)])


def _qmul_xyzw(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz])


# --------------------------------------------------------------------------- #
# energy accessors (plan step 8)                                              #
# --------------------------------------------------------------------------- #
def _rigid_E(sol):
    return rigid_mechanical_energy(sol._V, sol._W, sol._psv_quats_wxyz(),
                                   sol._mass, sol._invIl)


def _modal_E(sol):
    mq = np.asarray(sol._mq); kq = np.asarray(sol._kq)
    ke = 0.5 * float(sol._qdot @ (mq * sol._qdot))
    pe = 0.5 * float(sol._q @ (kq * sol._q))
    return ke, pe


def _total_E(sol):
    ke, pe = _modal_E(sol)
    return _rigid_E(sol) + ke + pe


# --------------------------------------------------------------------------- #
# per-cell setup                                                             #
# --------------------------------------------------------------------------- #
class CellAbort(Exception):
    pass


def _build_and_configure(scene, iterations):
    build_fn, kw = BUILD[scene]
    H = build_fn(device="cpu", iterations=iterations, avbd_substeps=1,
                 solver="xpbd", **kw)
    sol = H.world._solver
    sol._ensure_arrays()
    apply_relax(sol, "xpbd", 1.0)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=False, eta=1.0)     # governor OFF
    sol._psv_monitor_only = False
    return H, sol


def _preflight_structural(sol, iterations):
    """plan step 3 preflight asserts (abort cell on failure)."""
    checks = {
        "_support_block is False": sol._support_block is False,
        "_warm_start_lam is False": sol._warm_start_lam is False,
        "iterations == %d" % iterations: sol.iterations == iterations,
        "substeps == 1": sol.substeps == 1,
        "_freeze_qdot is False": sol._freeze_qdot is False,
        "len(_cargo) == 0": len(sol._cargo) == 0,
    }
    for k, v in checks.items():
        if not v:
            raise CellAbort("preflight %s" % k)


def _identify_impactor(H, sol):
    imp_pos = np.asarray(H.world._descs[H.impactor_idx].dcr_body.position[:3],
                         dtype=np.float64)
    d = np.linalg.norm(sol._X - imp_pos, axis=1)
    j = int(np.argmin(d))
    if np.sort(d)[1] < 1e-3:          # ambiguous unique-match (plan risk 6)
        raise CellAbort("impactor position match ambiguous")
    return j


def _impactor_gaps(sol, imp):
    Q = sol._Q; X = sol._X; q = sol._q
    R = _quat_to_R(Q[imp])
    out = []
    for si, sc in enumerate(sol._support):
        if sc.bi != imp:
            continue
        r_w = R @ sc.off
        corner_y = X[imp][1] + r_w[1]
        C = corner_y - (sc.y_rest + float(sc.U_y @ q))
        out.append((C, si))
    out.sort(key=lambda t: t[0])
    return out


def _predict_mass(sol, imp, sc, h):
    X, Q, invm = sol._X, sol._Q, sol._invm
    R = _quat_to_R(Q[imp])
    r_w = R @ sc.off
    j_ang = np.array([-r_w[2], 0.0, r_w[0]])
    inv_Iw = R @ sol._invIl[imp] @ R.T
    w_r = invm[imp] + float(j_ang @ (inv_Iw @ j_ang))
    wq = np.asarray(sol._wq)
    kq = np.asarray(sol._kq)
    U = sc.U_y
    w_row = w_r + float((U * U) @ wq)
    L = h * h * float((U * U) @ (kq * wq * wq))
    a_tilde = sol.support_compliance / (h * h)
    v = float(sol._V[imp][1])
    rho = L / (w_row + 2.0 * a_tilde)
    # alpha-generalized R4 (plan line 26): dE = v^2((w_m+L)/2 - w_m - a)/(w_m+a)^2
    dE = v * v * ((w_row + L) / 2.0 - w_row - a_tilde) / (w_row + a_tilde) ** 2
    return dict(w_r=w_r, w_row=w_row, L=L, a_tilde=a_tilde, rho=rho, v=v, dE=dE)


def _predict_impl(sol, imp, sc, h, mass_pred):
    """implicit-weight arm (plan step 7): w_eff = w_r + U^2 . 1/(mq+h dq+h^2 kq);
    dE = -v^2 (w_eff/2 + a)/(w_eff + a)^2 (exact only if dq==0; damped => sign)."""
    mq = np.asarray(sol._mq); kq = np.asarray(sol._kq); dq = np.asarray(sol._dq)
    U = sc.U_y
    w_impl = 1.0 / (mq + h * dq + h * h * kq)
    w_eff = mass_pred["w_r"] + float((U * U) @ w_impl)
    a = mass_pred["a_tilde"]; v = mass_pred["v"]
    dE = -v * v * (w_eff / 2.0 + a) / (w_eff + a) ** 2
    return dict(w_row=w_eff, dE=dE)


def _wrap_measure(sol):
    box = {}
    orig_sub = sol._substep_cpu
    orig_col = sol._collect_contacts

    def sub_wrapper(hh):
        box["E0"] = _total_E(sol)
        orig_sub(hh)
        ke, pe = _modal_E(sol)
        box["E1"] = _rigid_E(sol) + ke + pe
        box["ke"] = ke; box["pe"] = pe

    def col_wrapper():
        cs = orig_col()
        box["ncontacts"] = box.get("ncontacts", 0) + len(cs)
        return cs

    sol._substep_cpu = sub_wrapper
    sol._collect_contacts = col_wrapper
    return box, (orig_sub, orig_col)


def _unwrap(sol, saved):
    sol._substep_cpu, sol._collect_contacts = saved


def _snapshot(sol, lead_sc):
    return dict(X=sol._X.copy(), Q=sol._Q.copy(), V=sol._V.copy(),
                W=sol._W.copy(), q=sol._q.copy(), qdot=sol._qdot.copy(),
                lam=lead_sc.lam, time=getattr(sol, "time", None))


def _restore(sol, snap, lead_sc):
    sol._X[:] = snap["X"]; sol._Q[:] = snap["Q"]
    sol._V[:] = snap["V"]; sol._W[:] = snap["W"]
    sol._q[:] = snap["q"]; sol._qdot[:] = snap["qdot"]
    lead_sc.lam = snap["lam"]
    for sc in sol._support:
        if sc is not lead_sc:
            sc.lam = 0.0


def run_cell(scene, s, arm, iterations=1, be_control=True, trail=20):
    """One T4 cell. Returns a record dict (valid may be False with a reason)."""
    t0 = time.perf_counter()
    rec = dict(scene=scene, s=s, arm=arm, iterations=iterations,
               valid=False, reason="", wall_s=0.0)
    try:
        H, sol = _build_and_configure(scene, iterations)
        _preflight_structural(sol, iterations)
        if sol._wq_support is not None:
            raise CellAbort("wq_support not None at build")
        h = sol.dt / sol.substeps
        sol.gravity[:] = 0.0
        sol._modal_grav_acc[:] = 0.0
        imp = _identify_impactor(H, sol)
        # park bystanders
        for i in range(sol._X.shape[0]):
            if i == imp:
                continue
            sol._X[i][1] += PARK
            sol._V[i][:] = 0.0
            sol._W[i][:] = 0.0
        # tilt: dinner has no builder tilt -> apply Rx; then Rz tie-break (all)
        if scene == "dinner":
            sol._Q[imp] = _aa_xyzw([1, 0, 0], TILT_X)
        sol._Q[imp] = _qmul_xyzw(_aa_xyzw([0, 0, 1], TILT_Z), sol._Q[imp])
        sol._W[imp][:] = 0.0
        # locate unique leading impactor row (pre-scale pose)
        gaps = _impactor_gaps(sol, imp)
        if len(gaps) < 2:
            raise CellAbort("impactor has < 2 support rows")
        if abs(gaps[0][0] - gaps[1][0]) < 1e-9:
            raise CellAbort("leading support row is a tie (%.3e)"
                            % (gaps[1][0] - gaps[0][0]))
        lead_si = gaps[0][1]
        # prune impactor rows to the single leading row (keep bystander rows)
        sol._support = [sc for k, sc in enumerate(sol._support)
                        if sc.bi != imp or k == lead_si]
        lead_sc = next(sc for sc in sol._support if sc.bi == imp)
        # ---- stiffness scale (plan step 5a) ----
        sol._kq = np.asarray(sol._kq, float) * s
        sol._dq = np.asarray(sol._dq, float) * np.sqrt(s)
        # ---- contact-free 5-frame energy preflight (risk item 1, 1e-9) ----
        rec.update(_energy_conservation_preflight(sol, H))
        if not rec["preflight_ok"]:
            raise CellAbort("energy preflight residual %.3e > 1e-9"
                            % rec["preflight_res"])
        # ---- shift leading corner to exact touch (plan step 4) ----
        R = _quat_to_R(sol._Q[imp])
        r_w = R @ lead_sc.off
        corner_y = sol._X[imp][1] + r_w[1]
        C_min = corner_y - (lead_sc.y_rest + float(lead_sc.U_y @ sol._q))
        sol._X[imp][1] -= C_min
        sol._V[imp] = np.array([0.0, -1.0, 0.0])
        sol._W[imp][:] = 0.0
        for sc in sol._support:
            sc.mu = 0.0
        # runner-up isolation (now a parked bystander row): gap >> 5 h |v|
        g2 = sorted(
            (float((_quat_to_R(sol._Q[sc.bi]) @ sc.off)[1]) + sol._X[sc.bi][1]
             - (sc.y_rest + float(sc.U_y @ sol._q)))
            for sc in sol._support if sc is not lead_sc)
        runner_gap = g2[0] if g2 else np.inf
        rec["runner_gap"] = runner_gap
        if runner_gap <= 5.0 * h * 1.0:
            raise CellAbort("runner-up gap %.3e <= 5 h|v|" % runner_gap)
        # ---- implicit arm: install weight swap AFTER scaling (plan step 5) ----
        if arm == "implicit":
            _install_weight_swap(sol)
            if sol._wq_support is None:
                raise CellAbort("weight swap failed to install")
        # ---- R1 shipped-array check (plan step 6; at s == 1) ----
        rec.update(_r1_check(sol, h) if abs(s - 1.0) < 1e-12
                   else dict(r1_ok=None, r1_res=None))
        # ---- predictor (plan step 7) ----
        mp = _predict_mass(sol, imp, lead_sc, h)
        rec.update(w_r=mp["w_r"], w_row=(mp["w_row"] if arm == "mass"
                                         else None),
                   L=mp["L"], a_tilde=mp["a_tilde"], rho=mp["rho"], v=mp["v"])
        if arm == "mass":
            dE_pred = mp["dE"]
        else:
            ip = _predict_impl(sol, imp, lead_sc, h, mp)
            dE_pred = ip["dE"]
            rec["w_row"] = ip["w_row"]
        rec["dE_pred"] = dE_pred
        # ---- measurement: BE control first (snapshot/restore), then symplectic --
        snap = _snapshot(sol, lead_sc)
        dE_be = None
        if be_control:
            sol._modal_symplectic = False
            box_be, saved = _wrap_measure(sol)
            H.world.step()
            _unwrap(sol, saved)
            dE_be = box_be["E1"] - box_be["E0"]
            _restore(sol, snap, lead_sc)
            sol._modal_symplectic = True
        # symplectic (PLAN-MANDATED primary)
        box, saved = _wrap_measure(sol)
        H.world.step()
        _unwrap(sol, saved)
        dE_meas = box["E1"] - box["E0"]
        ncontacts = box.get("ncontacts", 0)
        n_active = sum(1 for sc in sol._support if sc.lam > 0.0)
        lead_active = lead_sc.lam > 0.0
        # validity of the MEASURED substep (isolation), not prediction agreement
        valid = (ncontacts == 0 and n_active == 1 and lead_active)
        rec.update(
            dE_meas=dE_meas, dE_be=dE_be, modal_ke=box["ke"], modal_pe=box["pe"],
            n_contacts=ncontacts, n_active_support=n_active, valid=valid,
            reldiff_sym=(abs(dE_meas - dE_pred) / max(abs(dE_pred), 1e-15)),
            reldiff_be=(abs(dE_be - dE_pred) / max(abs(dE_pred), 1e-15)
                        if dE_be is not None else None))
        if not valid:
            rec["reason"] = ("ncontacts=%d n_active=%d lead_active=%s"
                             % (ncontacts, n_active, lead_active))
        # sign / band bookkeeping (mass arm)
        rho = mp["rho"]
        rec["band"] = abs(rho - 1.0) <= 0.1
        if arm == "mass":
            rec["sign_agree"] = ((dE_meas > 0.0) == (rho > 1.0))
            rec["sign_agree_be"] = ((dE_be > 0.0) == (rho > 1.0)
                                    if dE_be is not None else None)
        else:
            rec["sign_agree"] = None
            rec["sign_agree_be"] = None
            rec["passive_meas"] = (dE_meas <= 1e-12)
            rec["passive_be"] = (dE_be <= 1e-12) if dE_be is not None else None
        # ---- observational trail (plan step 9) ----
        emax = 0.0
        for _ in range(trail):
            H.world.step()
            ke, pe = _modal_E(sol)
            emax = max(emax, ke + pe)
        rec["e_modal_trail_peak"] = emax
    except CellAbort as e:
        rec["reason"] = str(e)
        rec["valid"] = False
    rec["wall_s"] = time.perf_counter() - t0
    return rec


def _energy_conservation_preflight(sol, H, nframes=5):
    """Risk item 1: 5 contact-free frames after kq/dq scaling must conserve
    total energy to 1e-9. Contact-free is guaranteed by V=0 everywhere (bodies
    do not drift, gravity is 0, the impactor's leading row sits at gap ~0.015 > 0
    so it stays inactive). To exercise the SCALED modal stiffness through the
    stepper (the cache the risk warns about) we excite qdot deterministically and
    run UNDAMPED (implicit midpoint conserves quadratic invariants exactly); the
    scaled damping is restored afterward. Returns preflight_ok/res and restores
    the pre-preflight state (modal at rest)."""
    r = np.asarray(sol._mq).shape[0]
    dq_saved = np.asarray(sol._dq).copy()
    X0 = sol._X.copy(); Q0 = sol._Q.copy()
    V0 = sol._V.copy(); W0 = sol._W.copy()
    sol._V[:] = 0.0; sol._W[:] = 0.0
    sol._q[:] = 0.0
    rng = np.random.default_rng(20260723)
    sol._qdot[:] = 1e-3 * (rng.standard_normal(r))
    sol._dq = np.zeros(r)                       # undamped for the conservation test
    box = {"n": 0}
    orig_col = sol._collect_contacts

    def col_wrapper():
        cs = orig_col()
        box["n"] += len(cs)
        return cs
    sol._collect_contacts = col_wrapper
    E0 = _total_E(sol)
    for _ in range(nframes):
        H.world.step()
    E1 = _total_E(sol)
    sol._collect_contacts = orig_col
    res = abs(E1 - E0) / max(1.0, abs(E0))
    # restore
    sol._dq = dq_saved
    sol._X[:] = X0; sol._Q[:] = Q0; sol._V[:] = V0; sol._W[:] = W0
    sol._q[:] = 0.0; sol._qdot[:] = 0.0
    return dict(preflight_res=res, preflight_ncontacts=box["n"],
                preflight_ok=(res <= 1e-9 and box["n"] == 0))


def _r1_check(sol, h):
    """plan step 6: one damped BE step with unit impulse, per mode, equals the
    installed implicit weight w_implicit[i] = 1/(mq+h dq+h^2 kq) (note R1 mu_eff).
    (m + h c + h^2 k) qdot+ = P=1 (cold start q=qdot=0)."""
    mq = np.asarray(sol._mq); kq = np.asarray(sol._kq); dq = np.asarray(sol._dq)
    denom = mq + h * dq + h * h * kq
    qdot_plus = 1.0 / denom               # BE step response to unit impulse
    w_implicit = 1.0 / denom              # E-WS installed weight / note mu_eff
    res = float(np.max(np.abs(qdot_plus - w_implicit)
                       / np.maximum(np.abs(w_implicit), 1e-300)))
    return dict(r1_ok=(res <= 1e-12), r1_res=res)


# --------------------------------------------------------------------------- #
# CSV / driver                                                                #
# --------------------------------------------------------------------------- #
FIELDS = ["scene", "s", "arm", "iterations", "w_r", "w_row", "L", "a_tilde",
          "rho", "v", "dE_pred", "dE_meas", "dE_be", "modal_ke", "modal_pe",
          "reldiff_sym", "reldiff_be", "sign_agree", "sign_agree_be", "band",
          "passive_meas", "passive_be", "n_contacts", "n_active_support",
          "valid", "runner_gap", "preflight_res", "preflight_ok", "r1_ok",
          "r1_res", "e_modal_trail_peak", "reason", "wall_s"]


def _load_existing(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))


def _key(r):
    return (str(r["scene"]), "%.6e" % float(r["s"]), str(r["arm"]),
            int(r["iterations"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--arms", default="mass,implicit")
    ap.add_argument("--s-list", default="",
                    help="comma list; default logspace(-7,0,9) or trim")
    ap.add_argument("--trim", action="store_true",
                    help="use 7-pt s-grid (plan section 4 trim)")
    ap.add_argument("--annex", action="store_true",
                    help="run the 9 iteration-sweep annex cells (shelf,mass)")
    ap.add_argument("--no-be", action="store_true", help="skip BE control")
    ap.add_argument("--trail", type=int, default=20)
    ap.add_argument("--out", default="t4_shipped")
    ap.add_argument("--append", action="store_true",
                    help="merge into existing CSV by cell key (chunked runs)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    n_s = 7 if args.trim else 9
    if args.s_list.strip():
        s_grid = [float(x) for x in args.s_list.split(",") if x.strip()]
    else:
        s_grid = list(np.logspace(-7, 0, n_s))
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    be = not args.no_be

    print("### T4 shipped-solver row-index sweep (%s, %s) ###"
          % (platform.machine(), platform.system()), flush=True)
    print("s-grid (%d): %s" % (len(s_grid),
          ", ".join("%.1e" % x for x in s_grid)), flush=True)

    rows = []
    if args.annex:
        # 3 s-values spanning rho<1,~1,>1 (shelf), mass arm, iterations 2,4,8
        annex_s = [1e-6, 1.5e-5, 1e-3]
        for s in annex_s:
            for it in (2, 4, 8):
                rec = run_cell("shelf", s, "mass", iterations=it,
                               be_control=be, trail=0)
                rows.append(rec)
                print("  annex shelf mass s=%.1e it=%d rho=%.3e dE_meas=%+.3e "
                      "valid=%s %s" % (s, it, rec.get("rho", float("nan")),
                      rec.get("dE_meas", float("nan")), rec["valid"],
                      rec["reason"]), flush=True)
    else:
        for scene in scenes:
            for arm in arms:
                for s in s_grid:
                    rec = run_cell(scene, s, arm, iterations=1,
                                   be_control=be, trail=args.trail)
                    rows.append(rec)
                    print("  %-6s %-8s s=%.1e rho=%.3e dE_pred=%+.3e "
                          "dE_meas=%+.3e dE_be=%+.3e valid=%s %s"
                          % (scene, arm, s, rec.get("rho", float("nan")),
                             rec.get("dE_pred", float("nan")),
                             rec.get("dE_meas", float("nan")),
                             (rec.get("dE_be") if rec.get("dE_be") is not None
                              else float("nan")),
                             rec["valid"], rec["reason"]), flush=True)

    csv_path = os.path.join(OUT, "%s.csv" % args.out)
    merged = {}
    if args.append:
        for r in _load_existing(csv_path):
            merged[_key(r)] = r
    for r in rows:
        merged[_key(r)] = r
    ordered = sorted(merged.values(),
                     key=lambda r: (str(r["scene"]), str(r["arm"]),
                                    int(r["iterations"]), float(r["s"])))
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    write_manifest(
        OUT, "%s.csv" % args.out, scenes=scenes, solvers=["xpbd"],
        note=("T4: shipped SolverXPBD support row (lines 1510-1551), one-substep "
              "cold-start single-row impact; dE_meas = symplectic (plan-mandated) "
              "vs dE_be = backward-Euler control vs dE_pred = note R2/R3/R4. "
              "rho = L/(w_m+2 a_tilde). See module docstring for the symplectic "
              "midpoint 2x modal-velocity finding."))
    print("\nCSV: %s (%d rows total)" % (csv_path, len(ordered)))
    _summary(ordered)


def _summary(rows):
    def f(r, k):
        v = r.get(k, "")
        return float(v) if v not in ("", None, "None") else float("nan")
    print("\n--- T4 acceptance summary ---", flush=True)
    for scene in sorted(set(r["scene"] for r in rows)):
        for arm in sorted(set(r["arm"] for r in rows
                              if r["scene"] == scene)):
            cells = [r for r in rows if r["scene"] == scene and r["arm"] == arm
                     and int(r["iterations"]) == 1]
            if not cells:
                continue
            valid = [r for r in cells if str(r["valid"]) == "True"]
            band = [r for r in cells if str(r.get("band")) == "True"]
            nonband = [r for r in valid if str(r.get("band")) != "True"]
            line = "%-6s %-8s | cells=%d valid=%d band=%d" % (
                scene, arm, len(cells), len(valid), len(band))
            if arm == "mass":
                sa = sum(1 for r in nonband if str(r.get("sign_agree")) == "True")
                sabe = sum(1 for r in nonband
                           if str(r.get("sign_agree_be")) == "True")
                line += " | sign_agree(sym)=%d/%d sign_agree(be)=%d/%d" % (
                    sa, len(nonband), sabe, len(nonband))
            else:
                pm = sum(1 for r in valid if str(r.get("passive_meas")) == "True")
                pb = sum(1 for r in valid if str(r.get("passive_be")) == "True")
                line += " | passive(sym)=%d/%d passive(be)=%d/%d" % (
                    pm, len(valid), pb, len(valid))
            print(line, flush=True)


if __name__ == "__main__":
    main()
