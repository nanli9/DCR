#!/usr/bin/env python3
"""Scene-parameter dump for onesweep_short.tex reproducibility (NEW script).

Reviewer finding addressed: "No scene parameters are reported anywhere, so not one
system-level number in the paper is traceable or reproducible from the PDF."

This script edits NO tracked harness file. It imports run_t4_shipped's helpers and
replays exactly its per-cell setup (build -> configure -> park bystanders -> tilt ->
isolate the single leading impactor support row -> scale modal stiffness by s), then
instead of measuring energy it writes out every parameter the closed forms need:

  scene_params_cells.csv   one row per shipped-row cell (3 scenes x 9 stiffness
                           scales = 27), plus the eight impactor support rows of
                           the Fig. 1 teaser scene: M (row-visible), h,
                           alpha-tilde, w_r, sum a_i, L, rho, rho_mid, omega
                           range, material, budget.
  scene_params_modes.csv   one row per (scene, mode i) at s = 1: m_i, k_i,
                           omega_i, zeta_i, U_i (row shape value), a_i, b_i.
                           omega_i(s) = sqrt(s) omega_i(1); m_i is s-independent
                           and U_i depends only on the row, so 9 stiffness scales
                           need no repeat.

Definitions used (paper Sec. 2/3, all pre-solve):
  w_r      = row-visible rigid mobility 1/M + j_a^T I^-1 j_a  (so M_row := 1/w_r)
  a_i      = U_i^2 / m_i        b_i = (omega_i h)^2
  w_m      = w_r + sum a_i      L   = sum a_i b_i
  a_tilde  = alpha / h^2        (alpha = solver support_compliance)
  rho      = L / (w_m + 2 a_tilde)                        (kappa = 1 index)
  rho_mid  = (L + 2 sum a_i) / (w_r + 2 a_tilde)          (kappa = 2 index)

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/dump_scene_params.py
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import platform
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import run_t4_shipped as T4   # noqa: E402
from dcr.avbd._solver.solver_xpbd import _quat_to_R                 # noqa: E402
from scenes.reduced_shelf import build_reduced_shelf                # noqa: E402
from benchmarks.paper_eval.paper_config import (                    # noqa: E402
    apply_relax, apply_passivity)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# The frozen T4 stiffness grid (run_t4_shipped.py: np.logspace(-7, 0, 9)).
S_GRID = list(np.logspace(-7, 0, 9))

# Material/geometry actually in force for each T4 cell = the builder defaults,
# since run_t4_shipped.BUILD passes only impactor kwargs.
MATERIAL = {
    "shelf":  dict(youngs=0.5e9, density=600.0, poisson=0.30,
                   plate="0.80 x 0.30 x 0.030 m board",
                   impactor_mass=6.0),
    "ledge":  dict(youngs=1.0e10, density=500.0, poisson=0.30,
                   plate="1.20 x 0.80 x 0.080 m slab",
                   impactor_mass=50.0),
    "dinner": dict(youngs=1.1e9, density=770.0, poisson=0.30,
                   plate="2.20 x 1.10 x 0.040 m table",
                   impactor_mass=5.0),
}


# --------------------------------------------------------------------------- #
# row extraction                                                              #
# --------------------------------------------------------------------------- #
def _row_terms(sol, imp, sc, h):
    """Every pre-solve term of the row, per mode and aggregated."""
    X, Q, invm = sol._X, sol._Q, sol._invm
    R = _quat_to_R(Q[imp])
    r_w = R @ sc.off
    j_ang = np.array([-r_w[2], 0.0, r_w[0]])
    inv_Iw = R @ sol._invIl[imp] @ R.T
    w_r = invm[imp] + float(j_ang @ (inv_Iw @ j_ang))
    mq = np.asarray(sol._mq, float)
    kq = np.asarray(sol._kq, float)
    dq = np.asarray(sol._dq, float)
    wq = np.asarray(sol._wq, float)
    U = np.asarray(sc.U_y, float)
    a = U * U * wq                       # a_i = U_i^2 / m_i
    b = h * h * kq * wq                  # b_i = (omega_i h)^2
    omega = np.sqrt(np.maximum(kq * wq, 0.0))
    zeta = np.where(omega > 0, dq * wq / (2.0 * np.maximum(omega, 1e-300)), 0.0)
    sum_a = float(a.sum())
    L = float((a * b).sum())
    a_tilde = sol.support_compliance / (h * h)
    w_m = w_r + sum_a
    rho = L / (w_m + 2.0 * a_tilde)
    rho_mid = (L + 2.0 * sum_a) / (w_r + 2.0 * a_tilde)
    return dict(w_r=w_r, M_row=1.0 / w_r, m_body=1.0 / invm[imp],
                sum_a=sum_a, L=L, a_tilde=a_tilde, alpha=sol.support_compliance,
                w_m=w_m, rho=rho, rho_mid=rho_mid, n_modes=int(mq.shape[0]),
                mq=mq, kq=kq, dq=dq, U=U, a=a, b=b, omega=omega, zeta=zeta)


def _isolated_row(scene, s):
    """Replay run_t4_shipped's cell setup and return (sol, imp, lead_sc, h)."""
    H, sol = T4._build_and_configure(scene, 1)
    T4._preflight_structural(sol, 1)
    h = sol.dt / sol.substeps
    sol.gravity[:] = 0.0
    sol._modal_grav_acc[:] = 0.0
    imp = T4._identify_impactor(H, sol)
    for i in range(sol._X.shape[0]):
        if i == imp:
            continue
        sol._X[i][1] += T4.PARK
        sol._V[i][:] = 0.0
        sol._W[i][:] = 0.0
    if scene == "dinner":
        sol._Q[imp] = T4._aa_xyzw([1, 0, 0], T4.TILT_X)
    sol._Q[imp] = T4._qmul_xyzw(T4._aa_xyzw([0, 0, 1], T4.TILT_Z), sol._Q[imp])
    sol._W[imp][:] = 0.0
    gaps = T4._impactor_gaps(sol, imp)
    lead_si = gaps[0][1]
    sol._support = [sc for k, sc in enumerate(sol._support)
                    if sc.bi != imp or k == lead_si]
    lead_sc = next(sc for sc in sol._support if sc.bi == imp)
    sol._kq = np.asarray(sol._kq, float) * s
    sol._dq = np.asarray(sol._dq, float) * np.sqrt(s)
    R = _quat_to_R(sol._Q[imp])
    r_w = R @ lead_sc.off
    C_min = (sol._X[imp][1] + r_w[1]) - (lead_sc.y_rest
                                         + float(lead_sc.U_y @ sol._q))
    sol._X[imp][1] -= C_min
    sol._V[imp] = np.array([0.0, -1.0, 0.0])
    sol._W[imp][:] = 0.0
    return sol, imp, lead_sc, h


def _teaser_rows():
    """Fig. 1's frozen shelf recording: steel board, 6 kg dropped 1.00 m,
    1 iteration x 8 substeps.  Config source: onesweep_scene_record.py --steel,
    as recorded in out/onesweep_scene_data/scene_data_summary.json.

    Unlike a T4 cell this scene is NOT reduced to one isolated row: the impactor
    keeps all of its support rows and the drop is untilted, so every bottom
    corner touches at the same height. All of them are returned, and the paper
    quotes the span rather than one arbitrary member of a tie."""
    H = build_reduced_shelf(device="cpu", iterations=1, avbd_substeps=8,
                            solver="xpbd", youngs=2.00e11, density=7850.0,
                            impactor_mass=6.0, impactor_drop_height=1.0,
                            impactor_v0=0.0)
    sol = H.world._solver
    sol._ensure_arrays()
    apply_relax(sol, "xpbd", 1.0)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=False, eta=1.0)
    sol._psv_monitor_only = False
    h = sol.dt / sol.substeps
    imp = T4._identify_impactor(H, sol)
    rows = [sc for sc in sol._support if sc.bi == imp]
    return sol, imp, rows, h


# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT, exist_ok=True)
    cells, modes = [], []

    for scene in ("shelf", "ledge", "dinner"):
        for si, s in enumerate(S_GRID):
            sol, imp, sc, h = _isolated_row(scene, s)
            t = _row_terms(sol, imp, sc, h)
            mat = MATERIAL[scene]
            cells.append(dict(
                cell=("%s_s%d" % (scene, si + 1)), scene=scene,
                stiffness_scale="%.6e" % s, h_s="%.10g" % h,
                budget="1x1", kappa=2, relax=1.0,
                M_impactor_kg="%.6g" % t["m_body"],
                M_row_kg="%.6g" % t["M_row"], w_r="%.8g" % t["w_r"],
                n_modes=t["n_modes"],
                m_min_kg="%.6g" % float(t["mq"].min()),
                m_max_kg="%.6g" % float(t["mq"].max()),
                omega_min_rad_s="%.6g" % float(t["omega"].min()),
                omega_max_rad_s="%.6g" % float(t["omega"].max()),
                f_max_Hz="%.6g" % float(t["omega"].max() / (2 * np.pi)),
                b_max="%.6g" % float(t["b"].max()),
                alpha_m_per_N="%.6g" % t["alpha"],
                a_tilde="%.6g" % t["a_tilde"],
                sum_a="%.8g" % t["sum_a"], L="%.8g" % t["L"],
                w_m="%.8g" % t["w_m"],
                rho="%.6g" % t["rho"], rho_mid="%.6g" % t["rho_mid"],
                youngs_Pa="%.4g" % mat["youngs"], density_kg_m3=mat["density"],
                poisson=mat["poisson"], plate=mat["plate"],
                source="run_t4_shipped.py cell setup, h = dt/substeps"))
            if si == len(S_GRID) - 1:            # s = 1: the unscaled modes
                for i in range(t["n_modes"]):
                    modes.append(dict(
                        scene=scene, mode=i + 1,
                        m_i_kg="%.8g" % float(t["mq"][i]),
                        k_i_N_per_m="%.8g" % float(t["kq"][i]),
                        omega_i_rad_s="%.8g" % float(t["omega"][i]),
                        f_i_Hz="%.8g" % float(t["omega"][i] / (2 * np.pi)),
                        zeta_i="%.6g" % float(t["zeta"][i]),
                        U_i="%.8g" % float(t["U"][i]),
                        a_i="%.8g" % float(t["a"][i]),
                        h_s="%.10g" % h,
                        b_i_at_cell_h="%.8g" % float(t["b"][i])))
            print("%-7s s=%.3e  rho=%-12.6g rho_mid=%-12.6g w_r=%.6g"
                  % (scene, s, t["rho"], t["rho_mid"], t["w_r"]), flush=True)

    # Fig. 1 teaser: every impactor support row, no isolation, untilted drop
    sol, imp, rows, h = _teaser_rows()
    for k, sc in enumerate(rows):
        t = _row_terms(sol, imp, sc, h)
        cells.append(dict(
            cell="teaser_fig1_row%d" % (k + 1),
            scene="shelf (Fig. 1 teaser, steel board)",
            stiffness_scale="1.000000e+00", h_s="%.10g" % h,
            budget="1x8", kappa=2, relax=1.0,
            M_impactor_kg="%.6g" % t["m_body"],
            M_row_kg="%.6g" % t["M_row"], w_r="%.8g" % t["w_r"],
            n_modes=t["n_modes"],
            m_min_kg="%.6g" % float(t["mq"].min()),
            m_max_kg="%.6g" % float(t["mq"].max()),
            omega_min_rad_s="%.6g" % float(t["omega"].min()),
            omega_max_rad_s="%.6g" % float(t["omega"].max()),
            f_max_Hz="%.6g" % float(t["omega"].max() / (2 * np.pi)),
            b_max="%.6g" % float(t["b"].max()),
            alpha_m_per_N="%.6g" % t["alpha"], a_tilde="%.6g" % t["a_tilde"],
            sum_a="%.8g" % t["sum_a"], L="%.8g" % t["L"],
            w_m="%.8g" % t["w_m"],
            rho="%.6g" % t["rho"], rho_mid="%.6g" % t["rho_mid"],
            youngs_Pa="2.000e+11", density_kg_m3=7850.0, poisson=0.30,
            plate="0.80 x 0.30 x 0.030 m board",
            source=("onesweep_scene_record.py --steel, drop 1.00 m; "
                    "h = dt/8; all impactor support rows, not isolated")))
        if k == 0:
            for i in range(t["n_modes"]):
                modes.append(dict(
                    scene="teaser_fig1_row1", mode=i + 1,
                    m_i_kg="%.8g" % float(t["mq"][i]),
                    k_i_N_per_m="%.8g" % float(t["kq"][i]),
                    omega_i_rad_s="%.8g" % float(t["omega"][i]),
                    f_i_Hz="%.8g" % float(t["omega"][i] / (2 * np.pi)),
                    zeta_i="%.6g" % float(t["zeta"][i]),
                    U_i="%.8g" % float(t["U"][i]),
                    a_i="%.8g" % float(t["a"][i]),
                    h_s="%.10g" % h,
                    b_i_at_cell_h="%.8g" % float(t["b"][i])))
        print("teaser row %d  h=%.6g  rho=%.6g rho_mid=%.6g  w_r=%.6g  "
              "n_modes=%d" % (k + 1, h, t["rho"], t["rho_mid"], t["w_r"],
                              t["n_modes"]), flush=True)

    with open(os.path.join(OUT, "scene_params_cells.csv"), "w",
              newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(cells[0].keys()))
        wr.writeheader()
        wr.writerows(cells)
    with open(os.path.join(OUT, "scene_params_modes.csv"), "w",
              newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(modes[0].keys()))
        wr.writeheader()
        wr.writerows(modes)
    cfg = dict(
        figure="scene_params_cells.csv + scene_params_modes.csv",
        stage="X0", script="dump_scene_params.py",
        generated_utc=datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
        machine=platform.machine(), system=platform.system(),
        python=platform.python_version(),
        what=("per-cell and per-mode scene parameters for every shipped-row "
              "cell of onesweep_short.tex plus the Fig. 1 teaser scene"),
        config=dict(s_grid=[float(s) for s in S_GRID],
                    iterations=1, substeps=1, solver="xpbd",
                    stepper="symplectic", relax=1.0, gravity=0.0,
                    governor="off",
                    teaser=dict(iterations=1, substeps=8, youngs=2.00e11,
                                density=7850.0, impactor_mass=6.0,
                                drop_height_m=1.0)),
        note=("rho = L/(w_m + 2 a_tilde) is the kappa=1 index; rho_mid = "
              "(L + 2 sum a_i)/(w_r + 2 a_tilde) is the kappa=2 index. "
              "omega_i(s) = sqrt(s) omega_i(1); m_i and U_i do not depend on s, "
              "so the modes table is written once at s = 1."))
    with open(os.path.join(OUT, "scene_params.config.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    print("wrote %d cells, %d mode rows" % (len(cells), len(modes)))


if __name__ == "__main__":
    main()
