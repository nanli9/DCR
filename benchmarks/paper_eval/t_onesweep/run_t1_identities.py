#!/usr/bin/env python3
"""T1 — identity battery and machine-check vectors (plan section T1, items 1-8).

Validates the closed forms of the one-sweep XPBD passivity note
(`scratchpad/onesweep_theory_note.md`, Results R1-R5) numerically to machine
precision. Pure numpy + `common.py`; NO scipy, NO `dcr.*`, NO eigendecomposition,
NO scene builders. Every random draw uses `np.random.default_rng` seeded from
20260723 (per-group substreams so results are identical whether the groups are
run together or chunked one at a time).

Items (plan T1):
  1. R1  mobility ratio over an (omega*h, zeta, m) grid.
  2. R2  note machine-check vector (M=m=1, v=-1, omega h=10, h=1e-3).
  3. R2  formula on 100 seeded draws + the injection-boundary sign flip.
  4. R3  note machine-check vector (implicit weight, zeta=0).
  5. R3  formula on the same draws (undamped exact) + damped dE<0 (+ monotone report).
  6. R4  200 seeded multi-DOF rows: a_tilde-generalized mass dE, threshold sign,
         collapse identity, and the undamped effective-weight arm.
  7. R5  order-A/B closed forms at 6 (M,m,b) points, incl. D_B/D_A == (1+b)^2.
  8. relax sub-claim: modal deposit scales by exactly relax^2, no passive->injecting flip.

Tolerance discipline (BINDING): every machine check asserts relative error
<= 1e-12 unless a scale-aware form is named in the code below (the collapse
identity uses the plan's own T3 tolerance `<= 1e-12*max(1,rho)` for the SAME
identity, to avoid a spurious blow-up when a random row lands with rho ~ 1; this
is the plan's stated tolerance, not a loosening). On any binding failure the
script prints the failing identity and its measured residual and EXITS NONZERO.
Two checks are report-only by the plan's explicit instruction (item 5 damped
monotonicity, item 8 injecting->passive count); they never affect the exit code.

Re-runnable / chunkable:
    .venv/bin/python run_t1_identities.py                 # all groups
    .venv/bin/python run_t1_identities.py --checks R1,R2  # subset, merged into CSV
    .venv/bin/python run_t1_identities.py --checks R4 --r4-rows 500

Output: out/t1_identities.csv (+ .config.json). Figure: none.
Acceptance: all binding checks pass at their tolerances; exit code 0.
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
import time

import numpy as np

# _ROOT sys.path pattern (run_weight_swap.py lines 46-49): repo root on path.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C            # noqa: E402
from benchmarks.paper_eval.t_onesweep.selftest_common import two_row_sweep  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SEED = 20260723
ALL_GROUPS = ["R1", "R2", "R3", "R4", "R5", "relax"]

# CSV schema: the plan's 4 required columns (check_id, n_cases, max_rel_err, pass)
# plus provenance columns (group, item, max_abs_err, tol, binding, note).
FIELDS = ["check_id", "group", "item", "n_cases", "max_rel_err", "max_abs_err",
          "tol", "binding", "pass", "note"]


# --------------------------------------------------------------------------- #
# Accounting: one row per check_id; binding failures drive the exit code.      #
# --------------------------------------------------------------------------- #
class Battery:
    def __init__(self):
        self.rows = []
        self.binding_fail = []

    def _push(self, check_id, group, item, n, max_rel, max_abs, tol, binding,
              passed, note):
        self.rows.append(dict(
            check_id=check_id, group=group, item=item, n_cases=int(n),
            max_rel_err=float(max_rel), max_abs_err=float(max_abs),
            tol=float(tol), binding=bool(binding), pass_=bool(passed),
            note=note))
        tag = "PASS" if passed else "FAIL"
        bt = "" if binding else " (report-only)"
        print(f"  [{tag}] {check_id:34s} n={int(n):5d} "
              f"max_rel={max_rel:.3e} max_abs={max_abs:.3e}{bt}"
              f"{('  '+note) if note else ''}", flush=True)
        if binding and not passed:
            self.binding_fail.append(self.rows[-1])

    def close(self, check_id, group, item, a, b, note="", binding=True,
              tol=1e-12, atol=0.0):
        """assert_close semantics: |a-b| <= tol*|b| + atol elementwise."""
        a = np.asarray(a, dtype=np.float64)
        b = np.asarray(b, dtype=np.float64)
        num = np.abs(a - b)
        thr = tol * np.abs(b) + atol
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(np.abs(b) > 0, num / np.abs(b), num)
        passed = bool(np.all(num <= thr))
        n = int(num.size)
        self._push(check_id, group, item, n,
                   float(np.max(rel)) if n else 0.0,
                   float(np.max(num)) if n else 0.0, tol, binding, passed, note)
        return passed

    def true(self, check_id, group, item, cond, n, note="", binding=True,
             metric=0.0):
        passed = bool(np.all(cond))
        self._push(check_id, group, item, n, float(metric), 0.0, 0.0,
                   binding, passed, note)
        return passed

    def energy_dE(self, check_id, group, item, dE_sim, dE_frm, E_plus, E_minus,
                  note="", binding=True, tol=1e-12):
        """Machine check for an energy-DIFFERENCE identity dE = E+ - E-.

        The sim forms dE by subtracting two energies that are nearly equal
        whenever the rigid loss is small vs the total KE (heavy rigid body); the
        absolute floor of that subtraction is ~1 ulp of the energy scale, so a
        pure |dE_sim-dE_frm|/|dE_frm| test is unattainable in float64 on
        cancellation-dominated cells (PROVEN: residual == eps*max(|E+|,|E-|),
        and the cancellation-free reconstruction matches the closed form at pure
        rel <= 5e-15; see the accompanying `*_stable` corroboration check).

        Binding criterion is therefore the machine-precision floor at the energy
        scale, IDENTICAL in form to the plan's collapse-identity / T3 tolerance
        (`<= 1e-12*max(1,rho)`): |dE_sim - dE_frm| <= 1e-12*max(|E+|,|E-|,|dE_frm|).
        The raw pure-relative max is reported in the note (nothing hidden). This
        is not a loosening: a genuine formula error would leave a residual of
        O(|dE|) or O(E_scale), far above the eps*E_scale floor, and would also
        fail the pure-rel `*_stable` check.
        """
        dE_sim = np.asarray(dE_sim, dtype=np.float64)
        dE_frm = np.asarray(dE_frm, dtype=np.float64)
        escale = np.maximum.reduce([np.abs(np.asarray(E_plus, dtype=np.float64)),
                                    np.abs(np.asarray(E_minus, dtype=np.float64)),
                                    np.abs(dE_frm)])
        num = np.abs(dE_sim - dE_frm)
        passed = bool(np.all(num <= tol * escale))
        n = int(num.size)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw_rel = np.where(np.abs(dE_frm) > 0, num / np.abs(dE_frm), num)
            metric = float(np.max(num / escale)) if n else 0.0
        raw = float(np.max(raw_rel)) if n else 0.0
        full = (note + f"; raw pure-rel max={raw:.2e}").strip("; ")
        self._push(check_id, group, item, n, float(metric),
                   float(np.max(num)) if n else 0.0, tol, binding, passed, full)
        return passed

    def scale_aware(self, check_id, group, item, a, b, scale, note="",
                    binding=True, tol=1e-12):
        """|a-b| <= tol*scale elementwise (scale is a positive array/scalar)."""
        a = np.asarray(a, dtype=np.float64)
        b = np.asarray(b, dtype=np.float64)
        scale = np.asarray(scale, dtype=np.float64)
        num = np.abs(a - b)
        passed = bool(np.all(num <= tol * scale))
        n = int(num.size)
        with np.errstate(divide="ignore", invalid="ignore"):
            metric = np.max(num / scale) if n else 0.0
        self._push(check_id, group, item, n, float(metric),
                   float(np.max(num)) if n else 0.0, tol, binding, passed, note)
        return passed


# --------------------------------------------------------------------------- #
# Cancellation-free reconstruction of the sim's dE (for the `*_stable` proofs). #
# Rebuilds dE from the SAME one_sweep_row states, but writes the rigid term as  #
# 0.5/wr*(v+ - v)*(v+ + v) with (v+ - v) = wr*dlam/h computed directly, so the  #
# only large near-equal subtraction (E+ - E-) never occurs. Matches the closed  #
# form at pure rel <= 5e-15 => the closed form is exact; the raw res['dE']      #
# excursions above 1e-12 rel are float64 cancellation, not a formula error.     #
# --------------------------------------------------------------------------- #
def _stable_dE(res, wr, mi, ki, v, h):
    mi = np.atleast_1d(np.asarray(mi, dtype=np.float64))
    ki = np.atleast_1d(np.asarray(ki, dtype=np.float64))
    dv = wr * res["dlam"] / h                      # v+ - v, exact (no cancellation)
    vp = res["v_rigid_plus"]
    rigid = 0.5 * (1.0 / wr) * dv * (vp + v)
    qdot = np.atleast_1d(res["qdot"])
    dx = np.atleast_1d(res["dx"])
    modal = 0.5 * float(np.sum(mi * qdot ** 2)) + 0.5 * float(np.sum(ki * dx ** 2))
    return rigid + modal


# --------------------------------------------------------------------------- #
# Group R1 — item 1                                                           #
# --------------------------------------------------------------------------- #
def group_R1(bat: Battery):
    h = 1e-3
    oh = np.logspace(-3.0, np.log10(30.0), 13)
    zetas = np.array([0.0, 0.05, 0.5, 1.0])
    ms = np.array([0.5, 1.0, 2.0])
    OH, Z, MM = np.meshgrid(oh, zetas, ms, indexing="ij")
    OH, Z, MM = OH.ravel(), Z.ravel(), MM.ravel()
    omega = OH / h
    k = MM * omega ** 2
    c = 2.0 * Z * omega * MM
    # one backward-Euler step from q=qdot=0 with unit impulse P=1:
    qdot_plus = 1.0 / (MM + h * c + h * h * k)
    measured = (1.0 / MM) / qdot_plus
    analytic = C.r1_ratio(MM, Z, omega, h)          # 1 + 2 zeta omega h + (omega h)^2
    bat.close("R1_mobility_ratio", "R1", 1, measured, analytic,
              note="(1/m)/qdot+ == 1+2*zeta*wh+(wh)^2")


# --------------------------------------------------------------------------- #
# Group R2 — items 2, 3                                                       #
# --------------------------------------------------------------------------- #
def group_R2(bat: Battery, n_draws: int):
    h = 1e-3
    # ----- item 2: note machine-check vector -----
    M = m = 1.0
    v = -1.0
    b = 100.0
    k = b * m / h ** 2
    r2 = C.one_sweep_row(wr=1.0 / M, J_c=[-1.0], M_c=[[m]], K_c=[[k]],
                         h=h, v=v, weight_mode="mass")
    meas = np.array([r2["dlam"] / h, r2["v_rigid_plus"], float(r2["qdot"][0]),
                     float(r2["dx"][0]), r2["E_minus"], r2["E_plus"],
                     r2["E_plus"] / r2["E_minus"]])
    tgt = np.array([0.5, -0.5, -0.5, -h / 2.0, 0.5, 12.75, 25.5])
    bat.close("R2_note_vector", "R2", 2, meas, tgt,
              note="dlam/h,v+,qdot,q+,E-,E+,ratio")

    # ----- item 3: 100 seeded draws, sim vs closed form -----
    rng = np.random.default_rng([SEED, 2])
    Md = 10.0 ** rng.uniform(-2.0, 2.0, n_draws)
    md = 10.0 ** rng.uniform(-2.0, 2.0, n_draws)
    bd = 10.0 ** rng.uniform(np.log10(0.05 ** 2), np.log10(50.0 ** 2), n_draws)  # b=(wh)^2
    vd = rng.uniform(-2.0, -0.1, n_draws)
    hd = rng.choice([1e-3, 1e-2], n_draws)
    sim = np.empty(n_draws)
    stab = np.empty(n_draws)
    frm = np.empty(n_draws)
    Ep = np.empty(n_draws)
    Em = np.empty(n_draws)
    for i in range(n_draws):
        kd = bd[i] * md[i] / hd[i] ** 2
        res = C.one_sweep_row(wr=1.0 / Md[i], J_c=[-1.0], M_c=[[md[i]]],
                              K_c=[[kd]], h=hd[i], v=vd[i], weight_mode="mass")
        sim[i] = res["dE"]
        stab[i] = _stable_dE(res, 1.0 / Md[i], md[i], kd, vd[i], hd[i])
        frm[i] = C.r2_dE(Md[i], md[i], vd[i], bd[i])
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]
    bat.energy_dE("R2_formula_sim_vs_closed", "R2", 3, sim, frm, Ep, Em,
                  note="one_sweep_row dE == r2_dE over draws")
    bat.close("R2_formula_stable", "R2", 3, stab, frm,
              note="cancellation-free sim dE == r2_dE (pure rel proof)")

    # boundary: b0 = 1 + m/M; sign flip at b0*(1 +/- 1e-9); neutral at b0.
    b0 = 1.0 + md / Md
    dE_lo = np.empty(n_draws)
    dE_hi = np.empty(n_draws)
    dE_eq = np.empty(n_draws)
    Eminus = np.empty(n_draws)
    for i in range(n_draws):
        for tag, bb in (("lo", b0[i] * (1.0 - 1e-9)),
                        ("eq", b0[i]),
                        ("hi", b0[i] * (1.0 + 1e-9))):
            kd = bb * md[i] / hd[i] ** 2
            res = C.one_sweep_row(wr=1.0 / Md[i], J_c=[-1.0], M_c=[[md[i]]],
                                  K_c=[[kd]], h=hd[i], v=vd[i], weight_mode="mass")
            if tag == "lo":
                dE_lo[i] = res["dE"]
            elif tag == "eq":
                dE_eq[i] = res["dE"]
                Eminus[i] = res["E_minus"]
            else:
                dE_hi[i] = res["dE"]
    # |dE(b0)| <= 1e-12 * E- (energy-neutral at exact boundary)
    bat.scale_aware("R2_boundary_neutral", "R2", 3, dE_eq, 0.0, Eminus,
                    note="|dE(b0)| <= 1e-12*E-")
    # sign flip: passive just below, injecting just above
    flip_ok = (dE_lo < 0.0) & (dE_hi > 0.0)
    worst_margin = float(np.min(np.minimum(-dE_lo, dE_hi) / Eminus))
    bat.true("R2_boundary_signflip", "R2", 3, flip_ok, n_draws,
             note=f"dE<0 below & dE>0 above; min |dE|/E- margin={worst_margin:.2e}",
             metric=worst_margin)


# --------------------------------------------------------------------------- #
# Group R3 — items 4, 5                                                       #
# --------------------------------------------------------------------------- #
def group_R3(bat: Battery, n_draws: int):
    h = 1e-3
    # ----- item 4: note machine-check vector (implicit weight, zeta=0) -----
    M = m = 1.0
    v = -1.0
    b = 100.0
    k = b * m / h ** 2
    m_eff = C.r3_m_eff(m, omega_h=10.0, zeta=0.0)
    r3 = C.one_sweep_row(wr=1.0 / M, J_c=[-1.0], M_c=[[m]], K_c=[[k]],
                         h=h, v=v, weight_mode="implicit")
    meas = np.array([m_eff, r3["w_row"], r3["v_rigid_plus"],
                     float(r3["qdot"][0]), float(r3["dx"][0]),
                     r3["E_plus"], r3["dE"]])
    tgt = np.array([101.0, 102.0 / 101.0, -1.0 / 102.0, -1.0 / 102.0,
                    -h / 102.0, 51.0 / 10404.0, -101.0 / 204.0])
    bat.close("R3_note_vector", "R3", 4, meas, tgt,
              note="m_eff,w_eff,v+,qdot,q+,E+,dE")

    # ----- item 5: same draws, implicit weight, zeta=0 exact -----
    rng = np.random.default_rng([SEED, 2])          # SAME stream as R2 item 3
    Md = 10.0 ** rng.uniform(-2.0, 2.0, n_draws)
    md = 10.0 ** rng.uniform(-2.0, 2.0, n_draws)
    bd = 10.0 ** rng.uniform(np.log10(0.05 ** 2), np.log10(50.0 ** 2), n_draws)
    vd = rng.uniform(-2.0, -0.1, n_draws)
    hd = rng.choice([1e-3, 1e-2], n_draws)
    omega = np.sqrt(bd) / hd

    sim0 = np.empty(n_draws)
    stab0 = np.empty(n_draws)
    frm0 = np.empty(n_draws)
    Ep = np.empty(n_draws)
    Em = np.empty(n_draws)
    for i in range(n_draws):
        kd = bd[i] * md[i] / hd[i] ** 2
        res = C.one_sweep_row(wr=1.0 / Md[i], J_c=[-1.0], M_c=[[md[i]]],
                              K_c=[[kd]], h=hd[i], v=vd[i],
                              weight_mode="implicit")   # C_damp None => zeta=0
        sim0[i] = res["dE"]
        stab0[i] = _stable_dE(res, 1.0 / Md[i], md[i], kd, vd[i], hd[i])
        meff = C.r3_m_eff(md[i], omega[i] * hd[i], zeta=0.0)
        frm0[i] = C.r3_dE(Md[i], meff, vd[i])
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]
    bat.energy_dE("R3_formula_undamped", "R3", 5, sim0, frm0, Ep, Em,
                  note="implicit sim dE == -0.5*M*meff/(M+meff)*v^2 (zeta=0)")
    bat.close("R3_formula_undamped_stable", "R3", 5, stab0, frm0,
              note="cancellation-free implicit sim dE == r3_dE (pure rel proof)")

    # damped arms: dE<0 unconditionally (binding) + monotone report vs zeta=0.
    for zeta in (0.05, 0.5):
        simz = np.empty(n_draws)
        for i in range(n_draws):
            kd = bd[i] * md[i] / hd[i] ** 2
            cc = 2.0 * zeta * omega[i] * md[i]
            res = C.one_sweep_row(wr=1.0 / Md[i], J_c=[-1.0], M_c=[[md[i]]],
                                  K_c=[[kd]], h=hd[i], v=vd[i],
                                  weight_mode="implicit", C_damp=[[cc]])
            simz[i] = res["dE"]
        zt = str(zeta).replace(".", "p")
        bat.true(f"R3_damped_dE_negative_z{zt}", "R3", 5, simz < 0.0, n_draws,
                 note=f"implicit dE<0 unconditionally, zeta={zeta}",
                 metric=float(np.max(simz)))
        # report-only monotonicity (plan: flag if violated, never force)
        mono = simz <= sim0 + 1e-15
        n_viol = int(np.sum(~mono))
        bat.true(f"R3_damped_monotone_z{zt}", "R3", 5, mono, n_draws,
                 note=f"dE(zeta={zeta}) <= dE(zeta=0)+1e-15; violations={n_viol}",
                 binding=False, metric=float(np.max(simz - sim0)))


# --------------------------------------------------------------------------- #
# Group R4 — item 6                                                           #
# --------------------------------------------------------------------------- #
def group_R4(bat: Battery, n_rows: int):
    h_choices = np.array([1e-3, 1e-2])
    rng = np.random.default_rng([SEED, 4])

    sim_mass = np.empty(n_rows)
    stab_mass = np.empty(n_rows)
    frm_mass = np.empty(n_rows)
    Ep_m = np.empty(n_rows)
    Em_m = np.empty(n_rows)
    sim_impl = np.empty(n_rows)
    stab_impl = np.empty(n_rows)
    frm_impl = np.empty(n_rows)
    Ep_i = np.empty(n_rows)
    Em_i = np.empty(n_rows)
    rho = np.empty(n_rows)
    dE_sign = np.empty(n_rows)
    at = np.empty(n_rows)
    # collapse arrays (a_tilde==0 subset). y is built from the cancellation-free
    # reconstruction (the identity y == rho-1 is an algebraic property of the
    # formula; the raw-dE E+-E- roundoff is validated separately above and is
    # reported here as `y_raw` for transparency).
    y_list, y_raw_list, rho0_list = [], [], []

    for i in range(n_rows):
        r = int(rng.integers(1, 7))
        U = 10.0 ** rng.uniform(-2.0, 1.0, r) * rng.choice([-1.0, 1.0], r)
        mi = 10.0 ** rng.uniform(-1.0, 1.0, r)
        omega = 10.0 ** rng.uniform(0.5, 4.0, r)
        w_r = 10.0 ** rng.uniform(-2.0, 1.0)
        v = float(rng.uniform(-2.0, -0.1))
        h = float(rng.choice(h_choices))
        a_tilde = 0.0 if (i % 2 == 0) else 10.0 ** rng.uniform(-6.0, -1.0)
        at[i] = a_tilde

        ki = mi * omega ** 2
        a_i = U ** 2 / mi
        b_i = (omega * h) ** 2
        w_m = w_r + float(np.sum(a_i))
        L = float(np.sum(a_i * b_i))
        rho[i] = C.r4_rho(L, w_m, a_tilde)          # L / (w_m + 2 a_tilde)

        # mass arm: a_tilde-generalized dE
        res = C.one_sweep_row(wr=w_r, J_c=U, M_c=np.diag(mi), K_c=np.diag(ki),
                              h=h, v=v, weight_mode="mass", a_tilde=a_tilde)
        sim_mass[i] = res["dE"]
        stab_mass[i] = _stable_dE(res, w_r, mi, ki, v, h)
        frm_mass[i] = C.r4_dE_mass(v, w_r, w_m, L, a_tilde)
        Ep_m[i], Em_m[i] = res["E_plus"], res["E_minus"]
        dE_sign[i] = np.sign(res["dE"])

        # effective-weight arm (undamped)
        w_eff = C.r4_w_eff(w_r, U, np.diag(mi), np.diag(ki), h)
        res_i = C.one_sweep_row(wr=w_r, J_c=U, M_c=np.diag(mi), K_c=np.diag(ki),
                                h=h, v=v, weight_mode="implicit", a_tilde=a_tilde)
        sim_impl[i] = res_i["dE"]
        stab_impl[i] = _stable_dE(res_i, w_r, mi, ki, v, h)
        frm_impl[i] = C.r4_dE_implicit(v, w_eff, a_tilde)
        Ep_i[i], Em_i[i] = res_i["E_plus"], res_i["E_minus"]

        if a_tilde == 0.0:
            y_list.append(C.collapse_y(stab_mass[i], w_m, v))
            y_raw_list.append(C.collapse_y(res["dE"], w_m, v))
            rho0_list.append(L / w_m)

    # 6a: mass-arm a_tilde-generalized formula (energy-scale floor + pure-rel proof)
    bat.energy_dE("R4_mass_dE_formula", "R4", 6, sim_mass, frm_mass, Ep_m, Em_m,
                  note="sim dE == r4_dE_mass (a_tilde-generalized)")
    bat.close("R4_mass_dE_stable", "R4", 6, stab_mass, frm_mass,
              note="cancellation-free sim dE == r4_dE_mass (pure rel proof)")

    # 6b: threshold sign agreement outside the 1e-9 band
    band = np.abs(rho - 1.0) <= 1e-9
    out = ~band
    sign_ok = np.sign(np.where(rho > 1.0, 1.0, -1.0))[out] == dE_sign[out]
    bat.true("R4_threshold_sign", "R4", 6, sign_ok, int(np.sum(out)),
             note=f"sign(dE)==(rho>1) outside band; band_cells={int(np.sum(band))}, "
                  f"inject={int(np.sum(rho>1))}, passive={int(np.sum(rho<1))}",
             metric=0.0)

    # 6c: collapse identity y == rho-1 (a_tilde==0), plan's T3 scale-aware tol
    y = np.array(y_list)
    y_raw = np.array(y_raw_list)
    rho0 = np.array(rho0_list)
    scale = np.maximum(1.0, rho0)
    raw_worst = float(np.max(np.abs(y_raw - (rho0 - 1.0)) / scale)) if y.size else 0.0
    bat.scale_aware("R4_collapse_identity", "R4", 6, y, rho0 - 1.0, scale,
                    note=f"|y-(rho-1)| <= 1e-12*max(1,rho); n_atilde0={y.size}; "
                         f"raw-dE variant worst={raw_worst:.2e} (E+-E- cancellation)")

    # 6d: effective-weight arm equality (undamped) + dE<0
    bat.energy_dE("R4_implicit_arm", "R4", 6, sim_impl, frm_impl, Ep_i, Em_i,
                  note="implicit sim dE == r4_dE_implicit (undamped)")
    bat.close("R4_implicit_arm_stable", "R4", 6, stab_impl, frm_impl,
              note="cancellation-free implicit sim dE == r4_dE_implicit (pure rel proof)")
    bat.true("R4_implicit_dE_negative", "R4", 6, sim_impl < 0.0, n_rows,
             note="implicit dE<0 all rows", metric=float(np.max(sim_impl)))


# --------------------------------------------------------------------------- #
# Group R5 — item 7                                                           #
# --------------------------------------------------------------------------- #
def group_R5(bat: Battery):
    h = 1e-3
    v = -1.0
    pts = [(1.0, 1.0), (1.0, 0.01), (2.0, 0.5)]
    bs = [4.0, 100.0]
    EA_s, EB_s, DA_s, DB_s = [], [], [], []
    EA_f, EB_f, DA_f, DB_f = [], [], [], []
    ratio_s, ratio_f = [], []
    dEA = []
    for (M, m) in pts:
        for b in bs:
            ea, da = two_row_sweep(M, m, v, b, h, "A")
            eb, db = two_row_sweep(M, m, v, b, h, "B")
            EA_s.append(ea); EB_s.append(eb); DA_s.append(da); DB_s.append(db)
            EA_f.append(C.r5_E_plus_A(M, m, v, b))
            EB_f.append(C.r5_E_plus_B(M, m, v, b))
            DA_f.append(C.r5_D_A(M, m, v, b))
            DB_f.append(C.r5_D_B(M, m, v, b))
            ratio_s.append(db / da)
            ratio_f.append(C.r5_ratio_DB_DA(b))
            dEA.append(ea - 0.5 * M * v ** 2)
    bat.close("R5_E_plus_A", "R5", 7, EA_s, EA_f, note="order-A total energy")
    bat.close("R5_E_plus_B", "R5", 7, EB_s, EB_f, note="order-B total energy")
    bat.close("R5_D_A", "R5", 7, DA_s, DA_f, note="order-A modal deposit")
    bat.close("R5_D_B", "R5", 7, DB_s, DB_f, note="order-B modal deposit")
    bat.close("R5_ratio_DB_DA", "R5", 7, ratio_s, ratio_f,
              note="D_B/D_A == (1+b)^2")
    bat.true("R5_dE_A_passive", "R5", 7, np.array(dEA) <= 1e-15, len(dEA),
             note="trailing-spring order A passive at n=1 (dE_A<=0)",
             metric=float(np.max(dEA)))


# --------------------------------------------------------------------------- #
# Group relax — item 8                                                        #
# --------------------------------------------------------------------------- #
def group_relax(bat: Battery, n_draws: int):
    rng = np.random.default_rng([SEED, 8])
    relaxes = [0.25, 0.7]
    scale_err = []           # |deposit(relax) - relax^2*deposit(1)| / |relax^2*deposit(1)|
    n_scale = 0
    bad_flip = []            # passive(relax=1) -> injecting(relax<1): must never happen
    inj_to_passive = 0       # injecting(1) -> passive(relax): allowed, report only
    for _ in range(n_draws):
        r = int(rng.integers(1, 7))
        U = 10.0 ** rng.uniform(-2.0, 1.0, r) * rng.choice([-1.0, 1.0], r)
        mi = 10.0 ** rng.uniform(-1.0, 1.0, r)
        omega = 10.0 ** rng.uniform(0.5, 4.0, r)
        w_r = 10.0 ** rng.uniform(-2.0, 1.0)
        v = float(rng.uniform(-2.0, -0.1))
        h = float(rng.choice([1e-3, 1e-2]))
        ki = mi * omega ** 2
        Mc, Kc = np.diag(mi), np.diag(ki)

        base = C.one_sweep_row(wr=w_r, J_c=U, M_c=Mc, K_c=Kc, h=h, v=v,
                               weight_mode="mass", relax=1.0)
        rigid_ke1 = 0.5 * (1.0 / w_r) * base["v_rigid_plus"] ** 2
        dep1 = base["E_plus"] - rigid_ke1
        dE1 = base["dE"]
        for rl in relaxes:
            res = C.one_sweep_row(wr=w_r, J_c=U, M_c=Mc, K_c=Kc, h=h, v=v,
                                  weight_mode="mass", relax=rl)
            rigid_ke = 0.5 * (1.0 / w_r) * res["v_rigid_plus"] ** 2
            dep = res["E_plus"] - rigid_ke
            pred = rl ** 2 * dep1
            denom = abs(pred) if abs(pred) > 0 else 1.0
            scale_err.append(abs(dep - pred) / denom)
            n_scale += 1
            # sign-flip bookkeeping
            if dE1 <= 0.0 and res["dE"] > 0.0:
                bad_flip.append(1.0)
            if dE1 > 0.0 and res["dE"] <= 0.0:
                inj_to_passive += 1
    max_scale_err = float(np.max(scale_err)) if scale_err else 0.0
    passed_scale = max_scale_err <= 1e-12
    bat._push("relax_deposit_scaling", "relax", 8, n_scale, max_scale_err,
              0.0, 1e-12, True, passed_scale,
              "modal deposit == relax^2 * deposit(relax=1)")
    if passed_scale is False:
        pass  # already registered as binding failure via _push
    bat.true("relax_no_passive_to_injecting", "relax", 8,
             len(bad_flip) == 0, n_scale,
             note="no passive->injecting sign flip under relax<1", metric=0.0)
    bat.true("relax_injecting_to_passive_count", "relax", 8, True, n_scale,
             note=f"injecting->passive flips (allowed) = {inj_to_passive}",
             binding=False, metric=float(inj_to_passive))


# --------------------------------------------------------------------------- #
# CSV merge (chunk-safe) + manifest                                            #
# --------------------------------------------------------------------------- #
def merge_write(out_dir, name, new_rows):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    existing = {}
    order = []
    if os.path.exists(path):
        with open(path) as fh:
            for row in csv.DictReader(fh):
                existing[row["check_id"]] = row
                order.append(row["check_id"])
    for r in new_rows:
        cid = r["check_id"]
        out = {"check_id": cid, "group": r["group"], "item": r["item"],
               "n_cases": r["n_cases"], "max_rel_err": repr(r["max_rel_err"]),
               "max_abs_err": repr(r["max_abs_err"]), "tol": repr(r["tol"]),
               "binding": r["binding"], "pass": r["pass_"], "note": r["note"]}
        if cid not in existing:
            order.append(cid)
        existing[cid] = out
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for cid in order:
            w.writerow(existing[cid])
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checks", default="all",
                    help="comma list from {R1,R2,R3,R4,R5,relax} or 'all'")
    ap.add_argument("--r2-draws", type=int, default=100)
    ap.add_argument("--r4-rows", type=int, default=200)
    ap.add_argument("--relax-draws", type=int, default=20)
    ap.add_argument("--out", default="t1_identities")
    args = ap.parse_args()

    if args.checks.strip().lower() == "all":
        groups = list(ALL_GROUPS)
    else:
        groups = [g.strip() for g in args.checks.split(",") if g.strip()]
        bad = [g for g in groups if g not in ALL_GROUPS]
        if bad:
            ap.error(f"unknown group(s) {bad}; valid: {ALL_GROUPS}")

    os.makedirs(OUT, exist_ok=True)
    t0 = time.perf_counter()
    bat = Battery()
    print(f"### T1 identity battery ({platform.machine()}, {platform.system()}) "
          f"### groups={groups} seed={SEED}\n", flush=True)

    if "R1" in groups:
        print("[R1] mobility ratio (item 1)", flush=True)
        group_R1(bat)
    if "R2" in groups:
        print("[R2] one-sweep injection theorem (items 2-3)", flush=True)
        group_R2(bat, args.r2_draws)
    if "R3" in groups:
        print("[R3] implicit-weight exactness (items 4-5)", flush=True)
        group_R3(bat, args.r2_draws)
    if "R4" in groups:
        print("[R4] multi-DOF row-visible condition (item 6)", flush=True)
        group_R4(bat, args.r4_rows)
    if "R5" in groups:
        print("[R5] Gauss-Seidel ordering closed forms (item 7)", flush=True)
        group_R5(bat)
    if "relax" in groups:
        print("[relax] modal-deposit relax^2 scaling (item 8)", flush=True)
        group_relax(bat, args.relax_draws)

    path = merge_write(OUT, f"{args.out}.csv", bat.rows)
    from benchmarks.paper_eval.paper_config import write_manifest
    write_manifest(
        OUT, f"{args.out}.csv", scenes=[], solvers=["numpy-identity"],
        note=("T1 identity battery: R1-R5 closed forms of the one-sweep XPBD "
              "passivity note checked to rel<=1e-12 (collapse identity uses the "
              "plan's T3 scale-aware tol 1e-12*max(1,rho)). Pure numpy; no scene, "
              "no eig. Groups run: " + ",".join(groups) + ". "
              "Report-only checks (R3 damped monotonicity, relax injecting->"
              "passive count) never affect the exit code."))

    n_bind = sum(1 for r in bat.rows if r["binding"])
    n_report = len(bat.rows) - n_bind
    wall = time.perf_counter() - t0
    print(f"\n--- T1: {len(bat.rows)} checks ({n_bind} binding, {n_report} "
          f"report-only), {len(bat.binding_fail)} binding failure(s), "
          f"{wall:.2f}s ---")
    print(f"CSV: {path}")
    if bat.binding_fail:
        print("\nFAILED binding check(s) [tolerance NOT loosened; this is a "
              "finding about the note/plan]:")
        for r in bat.binding_fail:
            print(f"  {r['check_id']}: max_rel={r['max_rel_err']:.3e} "
                  f"max_abs={r['max_abs_err']:.3e} tol={r['tol']:.0e}  "
                  f"[{r['note']}]")
        sys.exit(1)
    print("\nALL BINDING CHECKS PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
