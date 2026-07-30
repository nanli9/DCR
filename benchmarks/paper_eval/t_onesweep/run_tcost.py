#!/usr/bin/env python3
"""T-COST -- what the row index and the matched charge actually cost.

Reviewer ask (Stanford Q1/Q6; internal panel "one sentence on per-row cost"):
  (a) cost of forming the row index rho and the matched charge in a host with
      many contacts and several coupled coordinates per row;
  (b) cost of forming L = h^2 J M^-1 K M^-1 J' and of applying full G^-1 per row;
  (c) whether a cheaper structured charge (block-diagonal, low-rank) keeps
      passivity;
  (d) numerical-stability implications under large mass ratios and stiff modes.

Named by content, not by T-number, to avoid colliding with other harnesses.
No tracked file is edited; run_t4_shipped.py and run_t10_multimode.py are
imported as libraries and run_t10_multimode's output directory is redirected to
a scratch path during the replay so its shipped CSV is never rewritten.

HONESTY NOTE ON ABSOLUTE TIMES. The shipped host is a numpy/Python reference
solver. Its absolute microseconds are NOT production-representative: a compiled
engine would shrink the per-row constant far more than the vector operations.
Only RATIOS measured between two costs on the same host, and the operation
counts, are reported as evidence.

OPERATION COUNTS (per contact row, r carried coordinates, exact, hoisting all
row-independent work to once per substep):
  sweep mobility     w += sum_i U_i^2 * wq_i                    2r flops
  matched charge     wq_i = 1/(kappa^2 m_i + h^2 k_i)           0 extra per row
                                                                r divides / substep
  row index rho      L  = h^2 * sum_i U_i^2 * (k_i wq_i^2)      2r flops + 1 divide
                     (the per-mode vector k_i wq_i^2 is row-independent: r flops
                      per substep)
  full G^-1, K_c coupled   Cholesky of G   r^3/6 flops / substep (shared by rows)
                           per row: two triangular solves        2r^2 flops
  => the dominant per-row term is 2r for a diagonal (modal) G and 2r^2 for a
     coupled G; the index never changes the asymptotic order.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/run_tcost.py
"""
from __future__ import annotations

import csv
import io
import os
import platform
import sys
import tempfile
import time
from contextlib import redirect_stdout

import numpy as np
from scipy.linalg import solve_triangular

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import run_t4_shipped as t4      # noqa: E402
from benchmarks.paper_eval.t_onesweep import run_t10_multimode as t10  # noqa: E402
from benchmarks.paper_eval.t_onesweep.common import write_csv          # noqa: E402
from dcr.avbd._solver.solver_xpbd import _quat_to_R                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
KAPPA = 2.0                       # shipped implicit-midpoint reconstruction


def _best(fn, reps, inner=1):
    """Min-of-reps wall time per call, seconds (min rejects scheduler noise)."""
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        for _ in range(inner):
            fn()
        dt = (time.perf_counter() - t0) / inner
        if dt < best:
            best = dt
    return best


# =========================================================================== #
# (1) SHIPPED HOST: real support rows, real solver code path                  #
# =========================================================================== #
def _active_rows(sol):
    n = 0
    for sc in sol._support:
        R = _quat_to_R(sol._Q[sc.bi])
        r_w = R @ sc.off
        C = sol._X[sc.bi][1] + r_w[1] - (sc.y_rest + float(sc.U_y @ sol._q))
        if not (C >= 0.0 and sc.lam == 0.0):
            n += 1
    return n


def shipped(scene, reps=300, inner=20, settle_frames=90):
    """Time the SHIPPED _project_support row under the default charge and under
    the reconstruction-matched charge, plus the index, on settled contacts.

    `_project_support` early-returns on a separated row with zero multiplier, so
    an unsettled scene times the early-return path. We settle under gravity and
    require a nonzero active-row count.
    """
    H, sol = t4._build_and_configure(scene, 1)
    h = sol.dt / sol.substeps
    r = int(sol._r)
    ntot = len(sol._support)
    a_tilde = sol.support_compliance / (h * h)
    for _ in range(settle_frames):
        H.world.step()
    nact = _active_rows(sol)
    if nact == 0:
        raise RuntimeError("%s: no active support rows after settling" % scene)
    active = [sc for sc in sol._support if sc.lam != 0.0] or list(sol._support)
    nact = len(active)

    snap = dict(X=sol._X.copy(), Q=sol._Q.copy(), V=sol._V.copy(),
                W=sol._W.copy(), q=sol._q.copy(), qdot=sol._qdot.copy(),
                lam=[sc.lam for sc in sol._support])

    def restore():
        sol._X[:] = snap["X"]; sol._Q[:] = snap["Q"]; sol._V[:] = snap["V"]
        sol._W[:] = snap["W"]; sol._q[:] = snap["q"]; sol._qdot[:] = snap["qdot"]
        for sc, lv in zip(sol._support, snap["lam"]):
            sc.lam = lv

    def rows_default():
        restore()
        for sc in active:
            sol._project_support(sc, a_tilde)

    mq = np.asarray(sol._mq, float)
    kq = np.asarray(sol._kq, float)
    wq_default = np.asarray(sol._wq, float).copy()

    def install_matched():
        denom = (KAPPA * KAPPA) * mq + (h * h) * kq
        return np.where(mq > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)

    wq_matched = install_matched()

    def rows_matched():
        restore()
        sol._wq_support = wq_matched
        for sc in active:
            sol._project_support(sc, a_tilde)

    # index: one extra length-r weighted dot per row; the per-mode vector is hoisted
    Us = [np.asarray(sc.U_y, float) for sc in active]
    w_rows = []
    for sc, U in zip(active, Us):
        R = _quat_to_R(sol._Q[sc.bi])
        r_w = R @ sc.off
        j_ang = np.array([-r_w[2], 0.0, r_w[0]])
        inv_Iw = R @ sol._invIl[sc.bi] @ R.T
        w_r = sol._invm[sc.bi] + float(j_ang @ (inv_Iw @ j_ang))
        w_rows.append(w_r + float((U * U) @ wq_default))
    w_rows = np.asarray(w_rows)
    kwq2 = (kq * wq_default) * wq_default

    def hoist():
        return (kq * wq_default) * wq_default

    def index_rows():
        acc = 0.0
        for U, wrow in zip(Us, w_rows):
            L = h * h * float((U * U) @ kwq2)
            acc += L / (wrow + 2.0 * a_tilde)
        return acc

    # repeat the whole A/B `trials` times and record the spread, so the CSV
    # supports a stated RANGE rather than a single noisy point
    trials = 5
    rat_m, rat_i = [], []
    for _ in range(trials):
        t_restore = _best(restore, reps, inner)
        t_def = _best(rows_default, reps, inner) - t_restore
        t_mat = _best(rows_matched, reps, inner) - t_restore
        sol._wq_support = None
        restore()
        t_idx = _best(index_rows, reps, inner)
        rat_m.append(t_mat / t_def)
        rat_i.append(t_idx / t_def)
    t_inst = _best(install_matched, reps, inner * 5)
    t_hoist = _best(hoist, reps, inner * 5)

    rec = dict(scene=scene, n_modes=r, n_support_rows=ntot, n_active_rows=nact,
               h_sub=h, a_tilde=a_tilde, trials=trials,
               us_rows_default=t_def * 1e6, us_rows_matched=t_mat * 1e6,
               us_per_row_default=t_def * 1e6 / nact,
               us_index_all_rows=t_idx * 1e6,
               us_index_per_row=t_idx * 1e6 / nact,
               us_install_matched_per_substep=t_inst * 1e6,
               us_index_hoist_per_substep=t_hoist * 1e6,
               us_restore_overhead=t_restore * 1e6,
               ratio_matched_over_default_min=min(rat_m),
               ratio_matched_over_default_max=max(rat_m),
               ratio_index_over_rows_min=min(rat_i),
               ratio_index_over_rows_max=max(rat_i),
               ratio_install_over_rows=t_inst / t_def)
    print("  %-7s r=%2d rows=%3d active=%3d | row solve %7.2f us (%.2f us/row) | "
          "matched/default %.3f..%.3fx | index %.1f%%..%.1f%% of the row solve | "
          "install %.2f us/substep"
          % (scene, r, ntot, nact, t_def * 1e6, t_def * 1e6 / nact,
             min(rat_m), max(rat_m), 100.0 * min(rat_i), 100.0 * max(rat_i),
             t_inst * 1e6))
    return rec


# =========================================================================== #
# (2) VECTORIZED KERNELS: many rows, sweeping the coordinate count            #
# =========================================================================== #
def kernels(r_list=(4, 8, 16, 32, 64), nrows=1000, reps=40):
    rng = np.random.default_rng(20260726)
    out = []
    for r in r_list:
        U = rng.normal(size=(nrows, r))
        U2 = U * U
        mq = rng.uniform(0.5, 2.0, size=r)
        kqv = rng.uniform(1e3, 1e6, size=r)
        h = 1.0 / 960.0
        w_r = rng.uniform(0.1, 2.0, size=nrows)
        wq = 1.0 / mq
        wq_m = 1.0 / (KAPPA * KAPPA * mq + h * h * kqv)
        kwq2 = kqv * wq * wq

        def sweep_diag():
            return w_r + U2 @ wq

        def sweep_matched():
            return w_r + U2 @ wq_m

        def install():
            return 1.0 / (KAPPA * KAPPA * mq + h * h * kqv)

        def index():
            return ((h * h) * (U2 @ kwq2)) / (w_r + 0.0)

        A = rng.normal(size=(r, r))
        Kc = A @ A.T + r * np.eye(r)          # SPD and NOT diagonal
        G = KAPPA * KAPPA * np.diag(mq) + h * h * Kc
        Lc = np.linalg.cholesky(G)

        def factor():
            return np.linalg.cholesky(G)

        def sweep_dense():
            Y = solve_triangular(Lc, U.T, lower=True, check_finite=False)
            return w_r + np.einsum("ij,ij->j", Y, Y)

        # repeat blocks and record the RATIO spread, so a stated band is backed
        blocks = 8
        rm, ri, rn = [], [], []
        for _ in range(blocks):
            a = _best(sweep_diag, reps, 5)
            rm.append(_best(sweep_matched, reps, 5) / a)
            ri.append(_best(index, reps, 5) / a)
            rn.append(_best(sweep_dense, reps, 3) / a)
        t_d = _best(sweep_diag, reps, 5)
        t_m = _best(sweep_matched, reps, 5)
        t_i = _best(index, reps, 5)
        t_in = _best(install, reps, 200)
        t_f = _best(factor, reps, 50)
        t_dn = _best(sweep_dense, reps, 3)
        out.append(dict(n_modes=r, nrows=nrows,
                        us_sweep_diag=t_d * 1e6, us_sweep_matched=t_m * 1e6,
                        us_index=t_i * 1e6, us_install_per_substep=t_in * 1e6,
                        us_cholesky_per_substep=t_f * 1e6,
                        us_sweep_dense_Ginv=t_dn * 1e6,
                        blocks=blocks,
                        ratio_matched_over_diag_min=min(rm),
                        ratio_matched_over_diag_max=max(rm),
                        ratio_index_over_diag_min=min(ri),
                        ratio_index_over_diag_max=max(ri),
                        ratio_denseGinv_over_diag_min=min(rn),
                        ratio_denseGinv_over_diag_max=max(rn)))
        print("  r=%3d | diag %7.2f us | matched %.2f..%.2fx | index %.2f..%.2fx | "
              "install %5.2f us | chol %5.2f us | full G^-1 %8.2f us (%.1f..%.1fx)"
              % (r, t_d * 1e6, min(rm), max(rm), min(ri), max(ri),
                 t_in * 1e6, t_f * 1e6, t_dn * 1e6, min(rn), max(rn)))
    return out


# =========================================================================== #
# (3) STRUCTURED CHARGES on the EXACT 2000 cells of run_t10_multimode block D #
# =========================================================================== #
_CAPTURED = []
_orig_sweep = t10.one_sweep_general


def _spy(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde=0.0, cond=False):
    o = _orig_sweep(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde=a_tilde, cond=cond)
    _CAPTURED.append(dict(w_r=w_r, J_c=np.atleast_1d(np.asarray(J_c, float)).copy(),
                          M_c=np.atleast_2d(np.asarray(M_c, float)).copy(),
                          K_c=np.atleast_2d(np.asarray(K_c, float)).copy(),
                          h=h, v=v, kappa=kappa, a_tilde=a_tilde, dE=o["dE"]))
    return o


def structured_charges(G):
    n = G.shape[0]
    ch = {"full": np.linalg.inv(G), "diag": np.diag(1.0 / np.diag(G))}
    Wb = np.zeros_like(G)
    for s in range(0, n, 2):                       # 2x2 block-diagonal of G
        e = min(s + 2, n)
        Wb[s:e, s:e] = np.linalg.inv(G[s:e, s:e])
    ch["block2"] = Wb
    Off = G - np.diag(np.diag(G))                  # diag + dominant rank-1
    Dinv = np.diag(1.0 / np.diag(G))
    if n >= 2 and np.any(Off):
        wv, Vv = np.linalg.eigh(Off)
        k = int(np.argmax(np.abs(wv)))
        s1, u1 = float(wv[k]), Vv[:, k]
        Du = Dinv @ u1
        den = 1.0 + s1 * float(u1 @ Du)
        ch["rank1"] = (Dinv - np.outer(Du, Du) * (s1 / den) if abs(den) > 1e-12
                       else Dinv)
    else:
        ch["rank1"] = Dinv
    return ch


def charges_same_cells():
    scratch = tempfile.mkdtemp(prefix="tcost_replay_")
    saved_out, saved_fn = t10.OUT, t10.one_sweep_general
    t10.OUT = scratch                      # shipped t10_multimode.csv untouched
    t10.one_sweep_general = _spy
    try:
        with redirect_stdout(io.StringIO()):
            t10.main()
    finally:
        t10.OUT, t10.one_sweep_general = saved_out, saved_fn

    shipped_rows = [r for r in csv.DictReader(
        open(os.path.join(OUT, "t10_multimode.csv")))
        if r["block"] == "D_diag_on_coupled"]
    tgt = np.array([float(r["dE"]) for r in shipped_rows])
    cap = np.array([c["dE"] for c in _CAPTURED])
    start = None
    for i in range(len(cap) - len(tgt) + 1):
        if np.allclose(cap[i:i + len(tgt)], tgt, rtol=1e-12, atol=0.0):
            start = i
            break
    if start is None:
        raise SystemExit("could not align the replay to shipped block D")
    cells = _CAPTURED[start:start + len(tgt)]
    print("  aligned to shipped block D at replay index %d "
          "(exact dE match on all %d cells; shipped file injecting %d)"
          % (start, len(tgt), int((tgt > 0).sum())))

    names = ("full", "diag", "block2", "rank1")
    counts = {k: 0 for k in names}
    worst = {k: -np.inf for k in names}
    rows = []
    for idx, c in enumerate(cells):
        G = c["kappa"] ** 2 * c["M_c"] + c["h"] ** 2 * c["K_c"]
        rec = dict(cell=idx, n_modes=int(c["J_c"].size), kappa=c["kappa"],
                   h=c["h"], v=c["v"], w_r=c["w_r"])
        for name, W in structured_charges(G).items():
            r0 = _orig_sweep(c["w_r"], c["J_c"], c["M_c"], c["K_c"], c["h"],
                             c["v"], W, c["kappa"], a_tilde=c["a_tilde"])
            rec["dE_" + name] = r0["dE"]
            rec["inject_" + name] = int(r0["dE"] > 0.0)
            counts[name] += int(r0["dE"] > 0.0)
            worst[name] = max(worst[name], r0["dE"])
        rows.append(rec)
    for k in names:
        print("  %-7s injecting %4d / %d   worst dE %+.6e"
              % (k, counts[k], len(cells), worst[k]))
    return rows, counts, worst


# =========================================================================== #
# (4) STABILITY: mass ratio and stiffness                                     #
# =========================================================================== #
def stability():
    """Matched index rho = M/(2M + mu_c) with mu_c = m(kappa^2 + b), against the
    mass-only weight's index, over mass ratio and (omega h)^2."""
    rows = []
    for mr in (1e-6, 1e-3, 1.0, 1e3, 1e6):
        for b in (1e-6, 1.0, 1e3, 1e6, 1e12):
            M, m = 1.0, mr
            mu = m * (KAPPA * KAPPA + b)
            rows.append(dict(mass_ratio_m_over_M=mr, b_omega_h_sq=b,
                             mu_matched=mu,
                             rho_matched=M / (2.0 * M + mu),
                             rho_massonly=(m * (KAPPA * KAPPA + b)) / (M + m),
                             cond_G_single_mode=(KAPPA ** 2 + b) / KAPPA ** 2))
    rm = [r["rho_matched"] for r in rows]
    r0 = [r["rho_massonly"] for r in rows]
    print("  matched index over m/M in [1e-6,1e6] x b in [1e-6,1e12]: "
          "%.3e .. %.6f  (bound 1/2)" % (min(rm), max(rm)))
    print("  mass-only index over the same box:                       "
          "%.3e .. %.3e" % (min(r0), max(r0)))
    # measured counterpart from the shipped-row sweep
    p = os.path.join(OUT, "t4_matched.csv")
    if os.path.exists(p):
        v = [r for r in csv.DictReader(open(p)) if r["valid"] == "True"]
        rmv = [float(r["rho_matched"]) for r in v]
        rhv = [float(r["rho_host"]) for r in v]
        sv = [float(r["s"]) for r in v]
        print("  MEASURED on the shipped rows (t4_matched.csv, %d cells, "
              "stiffness scale %.0e..%.0e): matched index %.4f..%.4f, "
              "mass-only index %.3e..%.3e"
              % (len(v), min(sv), max(sv), min(rmv), max(rmv),
                 min(rhv), max(rhv)))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    print("=" * 78)
    print("(1) SHIPPED HOST (numpy/Python reference; only RATIOS are evidence)")
    print("=" * 78)
    srows = []
    for sc in ("shelf", "ledge", "dinner"):
        srows.append(shipped(sc))
    for r in srows:
        r["host"] = platform.platform()
        r["machine"] = platform.machine()

    print()
    print("=" * 78)
    print("(2) VECTORIZED KERNELS, nrows = 1000 coupling contacts")
    print("=" * 78)
    krows = kernels()

    print()
    print("=" * 78)
    print("(3) STRUCTURED CHARGES on the exact 2000 cells of T10 block D")
    print("=" * 78)
    crows, counts, worst = charges_same_cells()

    print()
    print("=" * 78)
    print("(4) STABILITY")
    print("=" * 78)
    strows = stability()

    write_csv(OUT, "tcost_shipped", srows, manifest=dict(
        script="run_tcost.py",
        what="shipped support-row cost: default vs reconstruction-matched charge, "
             "and the danger index, on settled active contacts",
        note="numpy/Python reference host; absolute us are not production "
             "representative, ratios and operation counts are the evidence"))
    write_csv(OUT, "tcost_kernels", krows, manifest=dict(
        script="run_tcost.py",
        what="vectorized per-row kernels over 1000 coupling rows, r = 4..64: "
             "diagonal sweep, matched sweep, index, install, Cholesky, full G^-1"))
    write_csv(OUT, "tcost_charges", crows, manifest=dict(
        script="run_tcost.py",
        what="full G^-1 vs diagonal-of-G vs 2x2 block-diagonal vs diag+rank1 on "
             "the EXACT 2000 coupled-K_c cells of run_t10_multimode.py block D",
        counts=str(counts)))
    write_csv(OUT, "tcost_stability", strows, manifest=dict(
        script="run_tcost.py",
        what="matched index M/(2M+mu_c) vs mass-only index over mass ratio and "
             "(omega h)^2"))
    print("\nwrote tcost_shipped.csv tcost_kernels.csv tcost_charges.csv "
          "tcost_stability.csv in %s" % OUT)


if __name__ == "__main__":
    main()
