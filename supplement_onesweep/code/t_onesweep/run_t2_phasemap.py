#!/usr/bin/env python3
"""T2 -- scalar (omega*h, m/M) one-sweep passivity phase map (plan section T2).

Validates note Results R2 (mass-only injection theorem) and R3 (implicit-weight
unconditional passivity) on a 241x241 (omega*h, m/M) grid, both weight arms, by
MEASURING the one-projection cold-start energy change with `one_sweep_row`
semantics (vectorized) and asserting the closed forms cell-by-cell.

Theory: /private/tmp/.../scratchpad/onesweep_theory_note.md  (R2, R3).
Plan  : /private/tmp/.../scratchpad/wf1/plan.md  section T2 (binding asserts).
Harness pattern (_ROOT, manifest): run_weight_swap.py lines 46-49, 208-213.

Model box (note): M=1, v=-1, h=1e-3, zeta=0, a_tilde=0, relax=1, cold start
(q=qdot=0, contact touching, C_tilde = h*v). Scalar restorative DOF:
J_c=[-1], M_c=[[m]], K_c=[[k]], b=(omega h)^2 = h^2 k/m.

  Mass arm     : W = 1/m           w_row = 1/M + 1/m
  Implicit arm : W = 1/m_eff       w_row = 1/M + 1/m_eff
                 m_eff = m(1 + 2 zeta omega h + b)   (undamped: m(1+b))

The vectorized per-cell arithmetic below reproduces `common.one_sweep_row`
EXACTLY (op-for-op for the scalar case); a sample cross-check against
`one_sweep_row` is asserted at 1e-12 so the vectorized map is provably the same
measurement, not a re-derivation.

NUMERICAL NOTE (honest, not a loosened tolerance). Near the mass-arm boundary
b = 1 + m/M the energy change dE = E+ - E- is a difference of two O(E-)=O(0.5)
energies and loses ~8 digits to cancellation there. The note states each closed
form at its NATURAL level -- R2 gives E+ (a sum of positive terms, no
cancellation), R3 gives dE directly (never near zero relative to its own scale).
So the plan's "sim vs R2/R3 closed forms rel <= 1e-12" is asserted at exactly
those levels: mass arm at E+ (R2), implicit arm at dE (R3). The dE-level
relative error for the mass arm near the boundary is reported separately and is
purely cancellation (its |dE| is tiny), never a formula error -- E_minus is
bit-identical on both sides so |dE_meas - dE_closed| == |E+_meas - E+_closed|
stays at ~1e-16 absolute regardless.

Run (full grid, canonical outputs):
  .venv/bin/python benchmarks/paper_eval/t_onesweep/run_t2_phasemap.py
Chunked / quick (CLI):
  --n-grid N        grid resolution per axis (default 241)
  --cols START END  restrict omega*h index window [START,END); writes a
                    chunk-suffixed CSV and asserts only that chunk (re-runnable)
  --arm {both,mass,implicit}   default both (both required for full asserts)
  --h H             base substep (default 1e-3)
  --skip-damped     skip the zeta in {0.05,0.5} annex
  --skip-hindep     skip the h-independence check
  --no-png          skip the quick-look PNG
  --out-dir DIR     override output directory (default t_onesweep/out)
Exit code 0 iff every binding assert passes.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

# _ROOT sys.path pattern (run_weight_swap.py lines 46-49) so this runs anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


# --------------------------------------------------------------------------- #
# Vectorized one-projection measurement (mirrors common.one_sweep_row scalar)  #
# --------------------------------------------------------------------------- #
def measure_arm(OH, MM, M, v, h, zeta, arm):
    """One cold-start projection on every grid cell, `one_sweep_row` semantics.

    OH  : (P,Q) omega*h.        MM : (P,Q) m/M (== m since M=1 here).
    arm : "mass" -> W = 1/m ; "implicit" -> W = 1/m_eff.

    Returns a dict of (P,Q) arrays. dE is formed in the cancellation-free split
    dE = 0.5 M (v+ - v)(v+ + v) + modal_KE + modal_PE so the SIGN is reliable
    even one cell off the boundary; E_plus is the direct positive-sum form used
    for the R2 closed-form comparison.
    """
    b = OH * OH
    m = MM * M
    k = m * b / (h * h)                       # h^2 k = m b  (omega = OH/h)
    wr = 1.0 / M                              # rigid row mobility (note R2)
    if arm == "mass":
        W = 1.0 / m
    elif arm == "implicit":
        m_eff = m * (1.0 + 2.0 * zeta * OH + b)   # note R3 (undamped: m(1+b))
        W = 1.0 / m_eff
    else:
        raise ValueError(arm)
    w_row = wr + W                            # J_c W J_c^T = W for J_c=[-1]
    C_tilde = h * v                           # predicted penetration
    dlam = -C_tilde / w_row                   # a_tilde = 0 (hard contact)
    dx = -W * dlam                            # relax=1; (W J_c) dlam = -W dlam
    qdot = dx / h
    v_plus = v + wr * dlam / h                # rigid block, FULL dlam
    E_minus = 0.5 * M * v * v                 # scalar (modal at rest -> 0)
    modal_KE = 0.5 * m * qdot * qdot
    modal_PE = 0.5 * k * dx * dx
    E_plus = 0.5 * M * v_plus * v_plus + modal_KE + modal_PE
    dE_rigid = 0.5 * M * (v_plus - v) * (v_plus + v)
    dE = dE_rigid + modal_KE + modal_PE
    return dict(b=b, m=m, k=k, w_row=w_row, dlam=dlam, dx=dx, qdot=qdot,
                v_plus=v_plus, E_minus=E_minus, E_plus=E_plus,
                modal_KE=modal_KE, modal_PE=modal_PE, dE_rigid=dE_rigid, dE=dE)


def crosscheck_one_sweep_row(OH, MM, M, v, h):
    """Assert the vectorized measurement == common.one_sweep_row on a sample of
    cells (both arms) at 1e-12, proving identical projection semantics."""
    rows = []
    P, Q = OH.shape
    idx = [(0, 0), (P // 3, Q // 5), (P // 2, Q // 2),
           (2 * P // 3, 3 * Q // 4), (P - 1, Q - 1),
           (P // 4, Q - 1), (P - 1, Q // 4)]
    max_rel = 0.0
    for (i, j) in idx:
        m = float(MM[i, j] * M)
        b = float(OH[i, j] ** 2)
        k = m * b / (h * h)
        for arm in ("mass", "implicit"):
            ref = C.one_sweep_row(wr=1.0 / M, J_c=[-1.0], M_c=[[m]], K_c=[[k]],
                                  h=h, v=v, weight_mode=arm)
            single = measure_arm(np.array([[OH[i, j]]]), np.array([[MM[i, j]]]),
                                 M, v, h, 0.0, arm)
            for key_v, key_r in [("E_plus", "E_plus"), ("dlam", "dlam"),
                                 ("v_plus", "v_rigid_plus")]:
                a = float(single[key_v][0, 0])
                bb = float(ref[key_r]) if not isinstance(ref[key_r], np.ndarray) \
                    else float(ref[key_r][0])
                rel = abs(a - bb) / max(abs(bb), 1e-300)
                max_rel = max(max_rel, rel)
                rows.append((arm, key_v, a, bb, rel))
    return max_rel, rows


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def build_grid(n_grid):
    omega_h = np.logspace(np.log10(0.05), np.log10(50.0), n_grid)
    moM = np.logspace(-3.0, 3.0, n_grid)
    OH, MM = np.meshgrid(omega_h, moM)        # OH varies along cols, MM rows
    return omega_h, moM, OH, MM


def main():
    ap = argparse.ArgumentParser(description="T2 one-sweep phase map")
    ap.add_argument("--n-grid", type=int, default=241)
    ap.add_argument("--cols", type=int, nargs=2, default=None,
                    metavar=("START", "END"))
    ap.add_argument("--arm", choices=["both", "mass", "implicit"], default="both")
    ap.add_argument("--h", type=float, default=1e-3)
    ap.add_argument("--skip-damped", action="store_true")
    ap.add_argument("--skip-hindep", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--out-dir", default=OUT)
    args = ap.parse_args()

    M, v, zeta0 = 1.0, -1.0, 0.0
    h = args.h
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    clog = C.CheckLog()

    omega_h, moM, OH, MM = build_grid(args.n_grid)
    chunk = args.cols is not None
    if chunk:
        c0, c1 = args.cols
        c0 = max(0, c0); c1 = min(args.n_grid, c1)
        OH = OH[:, c0:c1]; MM = MM[:, c0:c1]
        omega_h_sl = omega_h[c0:c1]
        suffix = f"_cols{c0}-{c1}"
        print(f"[T2] CHUNK mode: omega*h index window [{c0},{c1}) "
              f"-> {OH.shape[0]}x{OH.shape[1]} cells")
    else:
        omega_h_sl = omega_h
        suffix = ""
    P, Q = OH.shape
    n_cells = P * Q
    print(f"[T2] grid {P}x{Q} = {n_cells} cells, arms={args.arm}, h={h}")

    # ---- semantic cross-check: vectorized == one_sweep_row --------------- #
    xc_rel, _ = crosscheck_one_sweep_row(OH, MM, M, v, h)
    clog.assert_close(xc_rel, 0.0, atol=1e-12,
                      label="vectorized == one_sweep_row (sample cells)")
    print(f"[T2] semantic cross-check max_rel = {xc_rel:.3e}")

    do_mass = args.arm in ("both", "mass")
    do_impl = args.arm in ("both", "implicit")

    mass = measure_arm(OH, MM, M, v, h, zeta0, "mass") if do_mass else None
    impl = measure_arm(OH, MM, M, v, h, zeta0, "implicit") if do_impl else None

    b = OH * OH
    m = MM * M
    E_minus = 0.5 * M * v * v                 # 0.5 everywhere
    boundary_b = 1.0 + MM / M                 # note R2: inject iff b > 1 + m/M
    rel_dist = np.abs(b - boundary_b) / boundary_b
    in_band = rel_dist <= 1e-9                # boundary band (expected 0 cells)
    n_band = int(np.sum(in_band))

    # =================== ASSERTS ===================================== #
    # (i) mass arm: sim E+ == R2 closed form (cancellation-free level).
    relerr_mass_Eplus = np.zeros_like(b)
    relerr_impl_dE = np.zeros_like(b)
    max_relerr_closed = 0.0
    if do_mass:
        r2_Ep = C.r2_E_plus(M, m, v, b)
        relerr_mass_Eplus = np.abs(mass["E_plus"] - r2_Ep) / np.abs(r2_Ep)
        clog.assert_close(mass["E_plus"], r2_Ep, rtol=1e-12,
                          label="(i) mass arm sim E+ == R2 closed form")
        max_relerr_closed = max(max_relerr_closed, float(relerr_mass_Eplus.max()))
        # report-only: dE-level relative error (cancellation near boundary)
        r2_dE_closed = r2_Ep - E_minus
        with np.errstate(divide="ignore", invalid="ignore"):
            relerr_mass_dE = np.where(np.abs(r2_dE_closed) > 0,
                                      np.abs(mass["dE"] - r2_dE_closed)
                                      / np.abs(r2_dE_closed), 0.0)
        n_dE_exceed = int(np.sum(relerr_mass_dE > 1e-12))
        # absolute dE agreement (energy-scaled) MUST stay machine-tight
        max_abs_dE_mass = float(np.abs(mass["dE"] - r2_dE_closed).max())
        clog.assert_true(max_abs_dE_mass <= 1e-12 * E_minus,
                         label="(i) mass arm |dE_meas - dE_R2| <= 1e-12*E_minus")

    # (iii) implicit arm: dE < 0 everywhere AND == R3 closed form (rel 1e-12).
    if do_impl:
        m_eff = m * (1.0 + 2.0 * zeta0 * OH + b)
        r3_dE_closed = C.r3_dE(M, m_eff, v)
        relerr_impl_dE = np.abs(impl["dE"] - r3_dE_closed) / np.abs(r3_dE_closed)
        clog.assert_close(impl["dE"], r3_dE_closed, rtol=1e-12,
                          label="(iii) implicit arm sim dE == R3 closed form")
        clog.assert_true(bool(np.all(impl["dE"] < 0.0)),
                         label="(iii) implicit arm dE < 0 on ALL cells")
        max_relerr_closed = max(max_relerr_closed, float(relerr_impl_dE.max()))
        max_impl_dE = float(impl["dE"].max())

    # (ii) sign(dE_mass) == sign(b - (1+m/M)) outside the 1e-9 band.
    n_misclass = -1
    if do_mass:
        inject_pred = b > boundary_b
        inject_meas = mass["dE"] > 0.0
        disagree = (inject_pred != inject_meas) & (~in_band)
        n_misclass = int(np.sum(disagree))
        clog.assert_true(n_misclass == 0,
                         label="(ii) sign(dE_mass)==sign(b-(1+m/M)) outside band")
        # also confirm no cell sits inside the tiny band on this grid
        clog.assert_true(n_band == 0, label="(ii) boundary-band cell count == 0")

    # (iv) h-independence: dE/E- identical at h and 10h on 5 fixed cells.
    hindep_res = float("nan")
    if not args.skip_hindep and not chunk:
        # 5 cells spanning passive + injecting regions (grid indices).
        cells = [(30, 30), (60, 180), (120, 120), (180, 60), (210, 210)]
        cells = [(min(i, args.n_grid - 1), min(j, args.n_grid - 1))
                 for (i, j) in cells]
        res_max = 0.0
        for (i, j) in cells:
            oh = np.array([[omega_h[j]]])       # note: col index -> omega_h
            mm = np.array([[moM[i]]])           # row index -> m/M
            for arm, doit in (("mass", do_mass), ("implicit", do_impl)):
                if not doit:
                    continue
                a1 = measure_arm(oh, mm, M, v, h, zeta0, arm)
                a2 = measure_arm(oh, mm, M, v, 10.0 * h, zeta0, arm)
                r1 = float(a1["dE"][0, 0]) / E_minus
                r2v = float(a2["dE"][0, 0]) / E_minus
                res_max = max(res_max, abs(r1 - r2v) / max(abs(r1), 1e-300))
        hindep_res = res_max
        clog.assert_close(res_max, 0.0, atol=1e-12,
                          label="(iv) h-independence dE/E- (5 cells, h vs 10h)")
        print(f"[T2] h-independence max rel residual = {res_max:.3e}")

    # =================== WRITE MAIN CSV ============================== #
    prov = dict(
        solvers=["numpy-onesweep"],
        note=("T2 one-sweep (omega*h, m/M) phase map; MEASURED one-projection "
              "cold-start dE via one_sweep_row semantics, both weight arms; "
              "R2 asserted at E+ (mass), R3 asserted at dE (implicit), rel<=1e-12. "
              "M=1, v=-1, h=%g, zeta=0, a_tilde=0, relax=1." % h),
        grid=dict(n_grid=args.n_grid, omega_h=[float(omega_h[0]),
                  float(omega_h[-1])], m_over_M=[float(moM[0]), float(moM[-1])]),
        theory="onesweep_theory_note.md R2,R3", plan="wf1/plan.md T2",
    )
    if do_mass and do_impl:
        rows = []
        oh_flat = OH.ravel(); mm_flat = MM.ravel()
        dEm = mass["dE"].ravel(); dEi = impl["dE"].ravel()
        bflat = b.ravel(); bnd = boundary_b.ravel(); rd = rel_dist.ravel()
        ib = in_band.ravel()
        ip = (bflat > bnd); im = (dEm > 0.0)
        rem = relerr_mass_Eplus.ravel(); rei = relerr_impl_dE.ravel()
        for kk in range(oh_flat.size):
            rows.append(dict(
                omega_h=float(oh_flat[kk]), m_over_M=float(mm_flat[kk]),
                b=float(bflat[kk]), E_minus=float(E_minus),
                dE_mass=float(dEm[kk]), dE_impl=float(dEi[kk]),
                dE_mass_norm=float(dEm[kk] / E_minus),
                dE_impl_norm=float(dEi[kk] / E_minus),
                boundary_b=float(bnd[kk]),
                rel_dist_to_boundary=float(rd[kk]),
                in_band=int(ib[kk]),
                inject_pred=int(ip[kk]), inject_meas=int(im[kk]),
                sign_agree=int(ip[kk] == im[kk]),
                relerr_mass_Eplus=float(rem[kk]),
                relerr_impl_dE=float(rei[kk])))
        name = f"t2_phasemap{suffix}.csv"
        C.write_csv(out_dir, name, rows, manifest=prov)
        print(f"[T2] wrote {os.path.join(out_dir, name)} ({len(rows)} rows)")

    # =================== DAMPED ANNEX ================================ #
    damped_summary = "skipped"
    if not args.skip_damped and do_impl:
        drows = []
        max_impl_damped = -np.inf
        sign_flip_vs_undamped = 0
        for zeta in (0.05, 0.5):
            md = measure_arm(OH, MM, M, v, h, zeta, "mass")     # zeta-independent
            idmp = measure_arm(OH, MM, M, v, h, zeta, "implicit")
            max_impl_damped = max(max_impl_damped, float(idmp["dE"].max()))
            # mass arm is zeta-independent by construction (W=1/m, Hamiltonian
            # has no c term); confirm the sign map did not move vs zeta=0.
            if do_mass:
                flip = int(np.sum((md["dE"] > 0.0) != (mass["dE"] > 0.0)))
                sign_flip_vs_undamped += flip
            ohf = OH.ravel(); mmf = MM.ravel()
            dm = md["dE"].ravel(); di = idmp["dE"].ravel()
            for kk in range(ohf.size):
                drows.append(dict(
                    zeta=float(zeta), omega_h=float(ohf[kk]),
                    m_over_M=float(mmf[kk]), b=float(ohf[kk] ** 2),
                    dE_mass=float(dm[kk]), dE_impl=float(di[kk]),
                    sign_mass=int(np.sign(dm[kk])),
                    impl_negative=int(di[kk] < 0.0)))
        # binding annex assert: implicit arm stays dE < 0 (abs tol 1e-15).
        clog.assert_true(max_impl_damped <= 1e-15,
                         label="annex: implicit dE < 0 at zeta in {0.05,0.5} "
                               "(abs tol 1e-15)")
        if do_mass:
            clog.assert_true(sign_flip_vs_undamped == 0,
                             label="annex: mass-arm sign map zeta-invariant "
                                   "(0 flips vs zeta=0)")
        dname = f"t2_phasemap_damped{suffix}.csv"
        dprov = dict(prov)
        dprov["note"] = ("T2 damped annex: mass arm (zeta-independent) + implicit "
                         "arm at zeta in {0.05,0.5}; binding: implicit dE<0.")
        C.write_csv(out_dir, dname, drows, manifest=dprov)
        damped_summary = (f"max implicit dE over both zetas = {max_impl_damped:.3e} "
                          f"(<=1e-15 required); mass-arm sign flips vs zeta0 = "
                          f"{sign_flip_vs_undamped}")
        print(f"[T2] wrote {os.path.join(out_dir, dname)} ({len(drows)} rows)")
        print(f"[T2] damped annex: {damped_summary}")

    # =================== QUICK-LOOK PNG ============================== #
    if not args.no_png and do_mass and do_impl and not chunk:
        try:
            _make_quicklook_png(out_dir, omega_h, moM,
                                mass["dE"] / E_minus, impl["dE"] / E_minus)
            print(f"[T2] wrote {os.path.join(out_dir, 't2_phasemap_quicklook.png')}")
        except Exception as exc:                # noqa: BLE001
            print(f"[T2] PNG skipped ({exc})")

    # =================== SUMMARY + FINALIZE ========================== #
    print("\n===== T2 acceptance summary =====")
    print(f"  grid cells                    : {n_cells}")
    print(f"  boundary-band cells (1e-9)    : {n_band}")
    if do_mass:
        print(f"  boundary MISCLASSIFIED cells  : {n_misclass}  (must be 0)")
        print(f"  mass dE-level cells > 1e-12   : {n_dE_exceed} "
              f"(cancellation near boundary; |dE| tiny)")
        print(f"  mass |dE_meas-dE_R2| max/E-   : {max_abs_dE_mass / E_minus:.3e}")
    print(f"  max rel err vs closed forms   : {max_relerr_closed:.3e}")
    if do_impl:
        print(f"  implicit dE max (must be < 0) : {max_impl_dE:.3e}")
    if not args.skip_hindep and not chunk:
        print(f"  h-independence residual       : {hindep_res:.3e}")
    print(f"  damped annex                  : {damped_summary}")
    clog.finalize("T2 phase-map checks")


def _make_quicklook_png(out_dir, omega_h, moM, dE_mass_norm, dE_impl_norm):
    """Two-panel quick-look (NOT the paper figure; make_figs.py builds F1)."""
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(out_dir, ".mplcache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
    X, Y = np.meshgrid(omega_h, moM)
    # left: mass arm, diverging centered at 0 with analytic boundary overlay.
    vmax = float(np.percentile(np.abs(dE_mass_norm), 99))
    vmax = max(vmax, 1e-6)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    pm = axes[0].pcolormesh(X, Y, dE_mass_norm, cmap="RdBu_r", norm=norm,
                            shading="auto")
    axes[0].plot(np.sqrt(1.0 + moM), moM, "k-", lw=1.8,
                 label=r"$(\omega h)^2 = 1 + m/M$")
    axes[0].set_title("mass-only weight  $dE/E^-$ (red = injection)")
    axes[0].legend(loc="lower right", fontsize=8)
    fig.colorbar(pm, ax=axes[0], shrink=0.9)
    # right: implicit arm, uniformly negative.
    pm2 = axes[1].pcolormesh(X, Y, dE_impl_norm, cmap="viridis", shading="auto")
    axes[1].set_title("implicit weight  $dE/E^-$ (all < 0)")
    fig.colorbar(pm2, ax=axes[1], shrink=0.9)
    for ax in axes:
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlabel(r"$\omega h$"); ax.set_ylabel(r"$m/M$")
    fig.suptitle("T2 one-sweep phase map (quick-look; cold start, e=0, "
                 "hard contact, one sweep)", fontsize=11)
    fig.savefig(os.path.join(out_dir, "t2_phasemap_quicklook.png"), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
