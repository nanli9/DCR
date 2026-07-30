"""T14: measured degradation of the one-sweep diagnostic OUTSIDE its hypotheses.

WHAT THIS IS. Every result in the note and in the short paper is stated for ONE
Gauss-Seidel sweep, from a COLD start (q = qdot = 0, contact exactly touching),
with ONE coupling row. Reviewers asked, three separate times, what happens in the
warm, persistent-contact, several-rows-at-once regime that motivates in-solve
coupling in the first place. This script MEASURES that. It does not extend any
theorem, and nothing here is a guarantee: the deliverable is the boundary of the
diagnostic and the DIRECTION in which it fails.

Vocabulary is the paper's own (Sec. 4, shipped-row paragraph): a FALSE NEGATIVE
is a cell whose pre-solve index reports a safe row that measurably injects. That
is the unsafe direction for a pre-solve check. A false positive is conservative.

THE WARM RECONSTRUCTION (the one modeling decision that matters).
The paper's kappa is defined only at a cold start, where the host's commit
    qdot^+ = kappa (q^+ - q^n)/h                      (cold, q^n = qdot^n = 0)
is unambiguous. Warm it is not: the shipped host commits the mode at the implicit
midpoint, qdot^+ = 2(q^+ - q^n)/h - qdot^n, which is NOT 2 (q^+ - q^n)/h. The
one-parameter family that reduces to the paper's kappa at a cold start and that
the two shipped commits both belong to is
    qdot^+ = kappa (q^+ - q^n)/h + (1 - kappa) qdot^n,           (COMMIT)
kappa = 1 the backward-Euler read-back Delta q/h, kappa = 2 the shipped midpoint
commit. (COMMIT) is used everywhere below. It is free-flight stable at both
values, which kappa Delta q/h alone is not at kappa = 2.

THE INSTRUMENT (derived here, checked against the simulation at 1e-12).
Write q~ for the predicted restorative position at the projection, qdot_pre =
(q~ - q^n)/h for the read-back the host would commit if the projection did
nothing, and qdot_ref = kappa qdot_pre + (1 - kappa) qdot^n for the velocity
(COMMIT) assigns to that no-projection state. Let W be the charge, u = W J_c,
s = Delta lambda / h, G = kappa^2 M_c + h^2 K_c, and

    p = kappa M_c qdot_ref + h K_c q~                     (the WARM cross vector)

Then one projection changes the true Hamiltonian by

    dE = 1/2 s^2 (u' G u + kappa_r^2 w_r) + s (kappa_r v + u' p).      (T14-1)

The cold specialization q~ = 0, qdot_ref = 0 kills p and reproduces Eq. (6) of
the paper term for term (checked at 0.0 below). Two structural facts follow and
are what the measurements below quantify:

  * the cold term enters (T14-1) QUADRATICALLY in the deposit s and the warm term
    enters LINEARLY, so for small deposits the warm term sets the sign;
  * u' p is not sign-definite. When kappa_r v + u' p > 0 the sweep injects for
    EVERY deposit s > 0, at every stiffness, hence at arbitrarily small rho.
    That is the false-negative direction.

Nothing above is claimed as a theorem, and (T14-1) is used only as a measuring
instrument: every reported number is a measured sign from a simulated sweep.

BLOCKS
  A. Instrument validation. (T14-1) against the simulated sweep on 13,050 warm
     cells; the cold slice against common.one_sweep_row and against the paper's
     own boundaries b > 1 + m/M (kappa = 1) and b > m/M - 2 (kappa = 2), which it
     reproduces with 0 of 4800 cells misclassified.
  B. Warm grid, one row. rho (kappa = 1) and rho_mid (kappa = 2) against the
     measured sign over a grid of standing deflection and standing modal
     velocity, under four predictors and two charges. Counts split into false
     negatives and false positives.
  C. Threshold. For two one-parameter warm families (pure standing deflection in
     units of one substep of approach h|v|, and pure standing modal velocity in
     units of |v|) the flip amplitude x* is measured by an outward scan and
     bisection on the simulated sweep, and checked against the root of (T14-1).
  D. Two simultaneously active rows, one Gauss-Seidel sweep. Only the FIRST row
     of a sweep is cold; a cross-coupled successor is warm-started by its
     predecessor's deposit, which is block B's mechanism arriving through
     ordering rather than through history. Run cold and warm, with and without a
     shared rigid body, in both orders.
  E. Secular. 20,000-substep persistent resting contact under gravity, per-sweep
     ledger closed exactly against the step ledger, for configurations that are
     passive at a cold start. Two controls: free flight (the paired predictor and
     commit must not grow) and rigid ground (isolates the weight-independent
     gravity-lift baseline, which is excluded from the Eq. (3) ledger).

Pure numpy. Run from the repository root with the project virtual environment:
    PYTHONPATH=. python benchmarks/paper_eval/t_onesweep/run_t14_warm_multirow.py
Imports from common.py; edits no existing harness.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CheckLog, one_sweep_row, write_csv  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

TOL_ID = 1e-12          # identity tolerance (binding, the T-suite convention)


# --------------------------------------------------------------------------- #
# 0. Host primitives                                                           #
# --------------------------------------------------------------------------- #
def commit_qdot(q, q_n, qdot_n, h, kappa):
    """Host velocity commit, warm-general (COMMIT in the module docstring):

        qdot^+ = kappa (q - q^n)/h + (1 - kappa) qdot^n.

    kappa = 1 is the backward-Euler read-back Delta q/h; kappa = 2 is the shipped
    implicit-midpoint commit 2(q - q^n)/h - qdot^n. At a cold start
    (q^n = qdot^n = 0) both are kappa Delta q/h, the paper's kappa.
    """
    return kappa * (q - q_n) / h + (1.0 - kappa) * qdot_n


def system_energy(v_bodies, Meq_bodies, q, q_n, qdot_n, M_c, K_c, h, kappa):
    """True Hamiltonian on the committed state: rigid KE per body plus the
    restorative block's 1/2 qdot' M_c qdot + 1/2 q' K_c q, with qdot from
    (COMMIT). Gravity potential is added by the caller when there is one."""
    qd = commit_qdot(q, q_n, qdot_n, h, kappa)
    E = 0.5 * float(qd @ (M_c @ qd)) + 0.5 * float(q @ (K_c @ q))
    E += 0.5 * float(np.sum(np.asarray(Meq_bodies) * np.asarray(v_bodies) ** 2))
    return E


def project_row(z, v, q, w_r, J_c, W, h, dlam_state=0.0, a_tilde=0.0,
                kappa_r=1.0, relax=1.0, unilateral=True):
    """One Gauss-Seidel local solve of row C = z + J_c' q >= 0, from ANY state.

    Mirrors common.one_sweep_row / solver_xpbd `_project_support`: the
    denominator carries w_row + a_tilde, the rigid block takes the full dlam, the
    restorative block takes relax * dlam. Returns the updated (z, v, q, lam) and
    the increment. The caller supplies the CURRENT state, so a second row in the
    same sweep automatically sees the first row's deposit (real Gauss-Seidel).
    """
    J_c = np.asarray(J_c, float)
    C = z + float(J_c @ q)
    w_row = w_r + float(J_c @ (W @ J_c))
    dlam = (-C - a_tilde * dlam_state) / (w_row + a_tilde)
    if unilateral:
        new_lam = max(0.0, dlam_state + dlam)
        dlam = new_lam - dlam_state
    else:
        new_lam = dlam_state + dlam
    z_new = z + w_r * dlam
    v_new = v + kappa_r * w_r * dlam / h
    q_new = q + relax * (W @ J_c) * dlam
    return z_new, v_new, q_new, new_lam, dlam, w_row


def warm_dE_closed(v, w_r, J_c, M_c, K_c, W, h, q_pred, qdot_ref, dlam,
                   kappa=1.0, kappa_r=1.0, relax=1.0):
    """(T14-1): dE = 1/2 s^2 (u'Gu + kappa_r^2 w_r) + s (kappa_r v + u'p),
    s = dlam/h, u = relax * W J_c, G = kappa^2 M_c + h^2 K_c,
    p = kappa M_c qdot_ref + h K_c q~.  Instrument only; validated in block A."""
    J_c = np.asarray(J_c, float)
    u = relax * (W @ J_c)
    G = kappa * kappa * M_c + h * h * K_c
    p = kappa * (M_c @ np.asarray(qdot_ref, float)) + h * (K_c @ np.asarray(q_pred, float))
    s = dlam / h
    A = float(u @ (G @ u)) + kappa_r * kappa_r * w_r
    B = kappa_r * v + float(u @ p)
    return 0.5 * A * s * s + B * s, A, B, s


# --------------------------------------------------------------------------- #
# 1. Indices under test (the paper's own pre-solve checks)                     #
# --------------------------------------------------------------------------- #
def index_rho(w_r, J_c, M_c, K_c, h, a_tilde=0.0):
    """Thm 3.2 row danger index, mass-only weight, kappa = 1:
        rho = L / (w_m + 2 a_tilde),  L = h^2 J' Mc^-1 Kc Mc^-1 J,
        w_m = w_r + J' Mc^-1 J.   Injection iff rho > 1 (cold start)."""
    J_c = np.asarray(J_c, float)
    Minv = np.linalg.inv(M_c)
    a_sum = float(J_c @ (Minv @ J_c))
    L = h * h * float(J_c @ (Minv @ (K_c @ (Minv @ J_c))))
    return L / (w_r + a_sum + 2.0 * a_tilde), L, a_sum


def index_rho_mid(w_r, J_c, M_c, K_c, h, a_tilde=0.0):
    """Shipped-default index (Sec. 4): rho_mid = (L + 2 sum a_i)/(w_r + 2 a_tilde),
    the kappa = 2 instance of Thm 3.3 for mass-only weights."""
    _, L, a_sum = index_rho(w_r, J_c, M_c, K_c, h, a_tilde)
    return (L + 2.0 * a_sum) / (w_r + 2.0 * a_tilde)


def predicted_index(kappa, w_r, J_c, M_c, K_c, h, a_tilde=0.0):
    if kappa == 1.0:
        return index_rho(w_r, J_c, M_c, K_c, h, a_tilde)[0]
    return index_rho_mid(w_r, J_c, M_c, K_c, h, a_tilde)


# --------------------------------------------------------------------------- #
# 2. One warm substep of a single row (scalar restorative coordinate)          #
# --------------------------------------------------------------------------- #
PREDICTORS = ("symplectic", "midpoint", "exact", "frozen")

# Predictor paired with each commit so that free flight is the corresponding
# symplectic integrator (verified over 20,000 substeps in block E).
PAIRED = {1.0: "symplectic", 2.0: "midpoint"}


def predict_modal(q_n, qdot_n, omega, h, kind):
    """Predicted restorative position q~ at the projection.

    symplectic : symplectic Euler,  qdot_p = qdot^n - h omega^2 q^n,
                 q~ = q^n + h qdot_p.  Paired with (COMMIT) at kappa = 1 the free
                 flight map has determinant 1 exactly, so it is the symplectic
                 partner of the backward-Euler read-back.
    midpoint   : implicit midpoint of the free oscillator. Paired with (COMMIT) at
                 kappa = 2 free flight reproduces the implicit-midpoint step
                 exactly, which is the shipped host's modal stepper. This is the
                 pairing the shipped kappa = 2 commit belongs to; kappa = 2 with a
                 symplectic-Euler predictor has free-flight determinant 1 + b and
                 diverges, so it is never used for multi-step runs.
    exact      : exact free flight of the undamped oscillator over h.
    frozen     : q~ = q^n (a host that predicts only the rigid side).
    Returns q~. qdot_pre is always (q~ - q^n)/h, by definition of the read-back.
    """
    if kind == "symplectic":
        qdot_p = qdot_n - h * omega * omega * q_n
        return q_n + h * qdot_p
    if kind == "midpoint":
        b = (omega * h) ** 2
        qdot_mid = (qdot_n * (1.0 - 0.25 * b) - (b / h) * q_n) / (1.0 + 0.25 * b)
        return q_n + 0.5 * h * (qdot_n + qdot_mid)
    if kind == "exact":
        if omega == 0.0:
            return q_n + h * qdot_n
        return q_n * np.cos(omega * h) + (qdot_n / omega) * np.sin(omega * h)
    if kind == "frozen":
        return q_n
    raise ValueError(kind)


def warm_cell(M, m, b, h, kappa, weight, q_n_norm, qdot_n_norm, predictor,
              v=-1.0, a_tilde=0.0):
    """One warm substep of the scalar row C = z - q, persistent contact.

    The substep starts EXACTLY TOUCHING (C^n = 0), which is the persistent
    resting-contact state; the warm parameters are the standing deflection
    q^n = q_n_norm * h|v| and the standing modal velocity qdot^n = qdot_n_norm |v|.
    Positive q^n is deflection toward the approaching body. The cold start of the
    paper is q_n_norm = qdot_n_norm = 0.

    Returns a dict with the measured dE (simulated), the closed-form dE, the
    pre-solve index, and the activity flag.
    """
    omega = np.sqrt(b) / h
    k = m * omega * omega
    M_c = np.array([[m]])
    K_c = np.array([[k]])
    J_c = np.array([-1.0])                       # C = z - q
    w_r = 1.0 / M
    if weight == "mass":
        W = np.linalg.inv(M_c)
    elif weight == "matched":
        W = np.linalg.inv(kappa * kappa * M_c + h * h * K_c)
    elif weight == "implicit_be":                # backward-Euler-shaped remedy
        W = np.linalg.inv(M_c + h * h * K_c)
    else:
        raise ValueError(weight)

    scale = h * abs(v)
    q_n = np.array([q_n_norm * scale])
    qdot_n = np.array([qdot_n_norm * abs(v)])
    q_pred = np.array([predict_modal(q_n[0], qdot_n[0], omega, h, predictor)])
    qdot_pre = (q_pred - q_n) / h
    qdot_ref = kappa * qdot_pre + (1.0 - kappa) * qdot_n

    # Rigid gap: touching at the substep start (z^n = -J'q^n = q^n), then z~ = z^n + h v.
    z_n = -float(J_c @ q_n)
    z_pred = z_n + h * v
    E_pre = system_energy([v], [M], q_pred, q_n, qdot_n, M_c, K_c, h, kappa)
    z1, v1, q1, lam1, dlam, w_row = project_row(
        z_pred, v, q_pred, w_r, J_c, W, h, 0.0, a_tilde)
    E_post = system_energy([v1], [M], q1, q_n, qdot_n, M_c, K_c, h, kappa)
    dE = E_post - E_pre
    dE_cf, A, B, s = warm_dE_closed(v, w_r, J_c, M_c, K_c, W, h, q_pred, qdot_ref,
                                    dlam, kappa, 1.0)
    # UNCLAMPED deposit: the unilateral max(0, .) is what breaks affineness of the
    # sign function in the warm parameter, so block C works with s_raw and then
    # discards any root at which the row is not actually active.
    C_pred = z_pred + float(J_c @ q_pred)
    s_raw = (-C_pred / (w_row + a_tilde)) / h
    idx = predicted_index(kappa, w_r, J_c, M_c, K_c, h, a_tilde)
    return dict(dE=dE, dE_cf=dE_cf, A=A, B=B, s=s, s_raw=s_raw, dlam=dlam, index=idx,
                active=dlam > 0.0, E_pre=E_pre, w_row=w_row, gap_pred=C_pred)


# --------------------------------------------------------------------------- #
# 3. Blocks                                                                    #
# --------------------------------------------------------------------------- #
def block_A(log, rows):
    """Instrument validation + cold control."""
    print("\n== A. instrument validation (T14-1) and cold control ==")
    h = 1.0 / 960.0
    worst_cf = 0.0          # scale-normalized (T13 convention)
    worst_cf_rel = 0.0      # pure relative, gated on a live injection margin
    n_gated = 0
    worst_cold = 0.0
    n_cf = 0
    for kappa in (1.0, 2.0):
        for weight in ("mass", "matched", "implicit_be"):
            for pred in PREDICTORS:
                for b in np.logspace(-2, 2, 8):
                    for mM in np.logspace(-2, 1, 5):
                        for qn in (-1.5, -0.4, 0.0, 0.4, 1.5):
                            for qd in (-0.8, 0.0, 0.9):
                                c = warm_cell(1.0, mM, b, h, kappa, weight, qn, qd,
                                              pred)
                                if not c["active"]:
                                    continue
                                n_cf += 1
                                res = abs(c["dE"] - c["dE_cf"])
                                worst_cf = max(worst_cf, res / c["E_pre"])
                                if abs(c["dE"]) / c["E_pre"] >= 1e-3:
                                    n_gated += 1
                                    worst_cf_rel = max(worst_cf_rel, res / abs(c["dE"]))
    log.assert_close(worst_cf, 0.0, rtol=0.0, atol=TOL_ID,
                     label=f"A1. (T14-1) == simulated sweep, {n_cf} warm cells "
                           f"(scale-normalized by E^-)")
    log.assert_close(worst_cf_rel, 0.0, rtol=0.0, atol=1e-9,
                     label=f"A1b. same, pure relative on the {n_gated} cells with "
                           f"|dE| >= 1e-3 E^-")
    print(f"   (T14-1) vs simulated sweep, {n_cf} warm active cells: "
          f"max {worst_cf:.3e} scale-normalized, {worst_cf_rel:.3e} relative on "
          f"{n_gated} live cells")

    # Cold slice must reproduce the shipped harness exactly (kappa=1, mass).
    for b in np.logspace(-3, 2, 40):
        for mM in np.logspace(-2, 1, 12):
            c = warm_cell(1.0, mM, b, h, 1.0, "mass", 0.0, 0.0, "symplectic")
            ref = one_sweep_row(1.0, [-1.0], [[mM]], [[mM * b / h / h]], h, -1.0,
                                "mass")
            worst_cold = max(worst_cold, abs(c["dE"] - ref["dE"]) / abs(ref["dE"]))
    log.assert_close(worst_cold, 0.0, rtol=0.0, atol=1e-13,
                     label="A2. cold slice == common.one_sweep_row (480 cells)")
    print(f"   cold slice vs common.one_sweep_row, 480 cells: max rel {worst_cold:.3e}")

    # Cold slice must reproduce BOTH printed boundaries.
    mis1 = mis2 = 0
    n_cold = 0
    for b in np.logspace(-3, 2, 60):
        for mM in np.logspace(-2, 1, 40):
            n_cold += 1
            c1 = warm_cell(1.0, mM, b, h, 1.0, "mass", 0.0, 0.0, "symplectic")
            c2 = warm_cell(1.0, mM, b, h, 2.0, "mass", 0.0, 0.0, "symplectic")
            mis1 += int((c1["dE"] > 0) != (b > 1.0 + mM))
            mis2 += int((c2["dE"] > 0) != (b > mM - 2.0))
            mis1 += int((c1["dE"] > 0) != (c1["index"] > 1.0))
            mis2 += int((c2["dE"] > 0) != (c2["index"] > 1.0))
    log.assert_true(mis1 == 0, label=f"A3. cold, kappa=1: b > 1 + m/M and rho > 1 "
                                     f"both exact on {n_cold} cells")
    log.assert_true(mis2 == 0, label=f"A4. cold, kappa=2: b > m/M - 2 and rho_mid > 1 "
                                     f"both exact on {n_cold} cells")
    print(f"   cold control {n_cold} cells: kappa=1 misclass {mis1}, "
          f"kappa=2 misclass {mis2}")
    rows.append(dict(block="A_instrument", n_cells=n_cf, max_rel_closed_form=worst_cf,
                     max_rel_vs_common=worst_cold, cold_cells=n_cold,
                     cold_misclass_k1=mis1, cold_misclass_k2=mis2))
    return n_cf, n_cold


def block_B(log, rows):
    """Warm grid: index sign agreement, split into false negatives / positives."""
    print("\n== B. warm grid, one row: does the index still predict the sign? ==")
    h = 1.0 / 960.0
    bs = np.logspace(-2, 2, 12)
    mMs = np.logspace(-2, 1, 6)
    warm_q = np.linspace(-2.0, 2.0, 9)
    warm_v = np.linspace(-2.0, 2.0, 9)
    summary = {}
    per_cell = []
    for kappa in (1.0, 2.0):
        for weight in ("mass", "matched"):
            for pred in PREDICTORS:
                key = (kappa, weight, pred)
                n_act = fn = fp = 0
                n_cold_like = 0
                fn_amp = np.inf
                for b in bs:
                    for mM in mMs:
                        for qn in warm_q:
                            for qd in warm_v:
                                c = warm_cell(1.0, mM, b, h, kappa, weight, qn, qd, pred)
                                if not c["active"]:
                                    continue
                                n_act += 1
                                inj = c["dE"] > 0.0
                                if weight == "matched":
                                    pred_inj = False        # Thm 3.3: passive, cold
                                else:
                                    pred_inj = c["index"] > 1.0
                                if inj and not pred_inj:
                                    fn += 1
                                    amp = max(abs(qn), abs(qd))
                                    fn_amp = min(fn_amp, amp)
                                    if len(per_cell) < 4000:
                                        per_cell.append(dict(
                                            block="B_warm_fn", kappa=kappa,
                                            weight=weight, predictor=pred, b=b,
                                            m_over_M=mM, q_n_norm=qn,
                                            qdot_n_norm=qd, index=c["index"],
                                            dE=c["dE"], dE_over_Eminus=c["dE"] / c["E_pre"]))
                                elif pred_inj and not inj:
                                    fp += 1
                                if abs(qn) <= 1e-12 and abs(qd) <= 1e-12:
                                    n_cold_like += 1
                summary[key] = dict(n=n_act, fn=fn, fp=fp,
                                    fn_amp=(None if fn == 0 else fn_amp))
                star = " *" if pred == PAIRED[kappa] else "  "
                lbl = f"kappa={kappa:g} {weight:8s} {pred:10s}"
                print(f"  {star}{lbl}: {n_act:6d} active, FALSE NEG {fn:6d} "
                      f"({100.0 * fn / max(n_act, 1):5.2f}%), false pos {fp:5d}, "
                      f"first FN at grid amplitude "
                      f"{'-' if fn == 0 else f'{fn_amp:.2f}'}")
                rows.append(dict(block="B_warm_summary", kappa=kappa, weight=weight,
                                 predictor=pred, paired=int(pred == PAIRED[kappa]),
                                 n_active=n_act, false_neg=fn, false_pos=fp,
                                 fn_frac=fn / max(n_act, 1),
                                 first_fn_grid_amplitude=(-1.0 if fn == 0 else fn_amp)))
    rows.extend(per_cell)
    print("   (* = predictor paired with that commit; grid step in the warm")
    print("    amplitude is 0.5, so the first-FN column is grid-limited; block C")
    print("    bisects the true flip amplitude.)")

    # Headline aggregates over the SHIPPED weight (mass-only), paired predictor.
    for kappa in (1.0, 2.0):
        s = summary[(kappa, "mass", PAIRED[kappa])]
        log.assert_true(True, label=f"B. kappa={kappa:g} mass-only, paired predictor: "
                                    f"{s['fn']}/{s['n']} false negatives")
    # The matched charge is unconditionally passive COLD (Thm 3.3). Warm it is not:
    # record, do not assert a direction.
    for kappa in (1.0, 2.0):
        s = summary[(kappa, "matched", PAIRED[kappa])]
        log.assert_true(True, label=f"B. kappa={kappa:g} matched charge, warm: "
                                    f"{s['fn']}/{s['n']} injecting cells")
    # Union over all four predictors, mass-only: the headline warm number.
    for kappa in (1.0, 2.0):
        tot = sum(summary[(kappa, "mass", p)]["n"] for p in PREDICTORS)
        tfn = sum(summary[(kappa, "mass", p)]["fn"] for p in PREDICTORS)
        tfp = sum(summary[(kappa, "mass", p)]["fp"] for p in PREDICTORS)
        print(f"   kappa={kappa:g} mass-only, all predictors: {tfn}/{tot} false "
              f"negatives, {tfp}/{tot} false positives")
        rows.append(dict(block="B_warm_total", kappa=kappa, weight="mass",
                         n_active=tot, false_neg=tfn, false_pos=tfp,
                         fn_frac=tfn / max(tot, 1)))
    return summary


def family_cell(M, m, b, h, kappa, predictor, x, family, weight="mass"):
    """One warm cell of a one-parameter warm family, x the family parameter.

    family = "deflect" : standing deflection q^n = x h|v|, qdot^n = 0.
    family = "velocity": standing modal velocity qdot^n = x |v|, q^n = 0.
    Positive x is toward the approaching body in both.
    """
    if family == "deflect":
        return warm_cell(M, m, b, h, kappa, weight, x, 0.0, predictor)
    return warm_cell(M, m, b, h, kappa, weight, 0.0, x, predictor)


def family_root(M, m, b, h, kappa, predictor, family, weight="mass"):
    """Sign-flip parameter x* implied by (T14-1), exactly.

    With s > 0 the sign of dE is the sign of g(x) = A s(x) + 2 B(x), and every
    predictor here is linear, so g is AFFINE in the family parameter x:
        x* = -g(0) / (g(1) - g(0)).
    Affineness is verified numerically in block C, and x* is checked against a
    bisection on the SIMULATED energy difference. Closed forms for the record,
    mass-only weight, kappa_r = 1, P = [(kappa^2 + b)M + m]/(M + m):
      deflect,  symplectic predictor: x* = (2 - P)/(b[2(kappa^2 + b - 1) - P]);
      velocity, symplectic, kappa = 1: x* = -(2 - P)/(2 + 2b - P);
      velocity, midpoint,   kappa = 2: x* = -(2 - P)/(4 - P/(1 + b/4)),
        whose b -> 0 limit is finite, so the window does not close as the mode
        softens, while the kappa = 1 limit is -1, the activity limit itself.
    """
    def g(x):
        c = family_cell(M, m, b, h, kappa, predictor, x, family, weight)
        return c["A"] * c["s_raw"] + 2.0 * c["B"], c
    g0, _ = g(0.0)
    g1, _ = g(1.0)
    if g1 == g0:
        return np.inf, g0, g1
    return -g0 / (g1 - g0), g0, g1


def block_C(log, rows):
    """Threshold: how much warm state flips a cold-passive row."""
    print("\n== C. flip amplitude x* of a cold-passive row (units: h|v| and |v|) ==")
    h = 1.0 / 960.0
    worst_root = 0.0
    worst_affine = 0.0
    n = 0
    tab = []
    for family in ("deflect", "velocity"):
        for kappa in (1.0, 2.0):
            pred = PAIRED[kappa]
            for b in (0.03, 0.1, 0.3, 1.0, 3.0, 10.0):
                for mM in (0.5, 1.0, 3.0, 10.0, 30.0, 100.0):
                    cold = family_cell(1.0, mM, b, h, kappa, pred, 0.0, family)
                    if cold["dE"] > 0.0 or not cold["active"]:
                        continue                    # already injecting cold
                    x_cf, g0, g1 = family_root(1.0, mM, b, h, kappa, pred, family)
                    if not np.isfinite(x_cf):
                        continue
                    # affineness of the unclamped sign function in x (3-point check)
                    gs = []
                    for xx in (-0.7, 0.3, 2.1):
                        c = family_cell(1.0, mM, b, h, kappa, pred, xx, family)
                        gs.append(c["A"] * c["s_raw"] + 2.0 * c["B"])
                    lin = [g0 + xx * (g1 - g0) for xx in (-0.7, 0.3, 2.1)]
                    sc = max(abs(g0), abs(g1), 1e-300)
                    worst_affine = max(worst_affine,
                                       max(abs(a - bq) for a, bq in zip(gs, lin)) / sc)
                    # Independent measurement: scan OUTWARD from the cold cell and
                    # bracket the first sign change among cells whose row is still
                    # active, then bisect on the SIMULATED energy difference.
                    direction = np.sign(x_cf)
                    xmax = abs(x_cf) * 2.0
                    lo, hi = 0.0, None
                    for i in range(1, 4001):
                        xx = direction * xmax * i / 4000.0
                        c = family_cell(1.0, mM, b, h, kappa, pred, xx, family)
                        if not c["active"]:
                            break
                        if c["dE"] > 0.0:
                            hi = xx
                            break
                        lo = xx
                    if hi is None:
                        continue                    # flip unreachable before the row lifts
                    for _ in range(200):
                        mid = 0.5 * (lo + hi)
                        c = family_cell(1.0, mM, b, h, kappa, pred, mid, family)
                        if c["active"] and c["dE"] > 0.0:
                            hi = mid
                        else:
                            lo = mid
                    x_meas = 0.5 * (lo + hi)
                    worst_root = max(worst_root, abs(x_meas - x_cf) / abs(x_cf))
                    n += 1
                    tab.append((family, kappa, b, mM, x_cf, x_meas))
                    rows.append(dict(block="C_threshold", family=family, kappa=kappa,
                                     predictor=pred, b=b, m_over_M=mM,
                                     cold_index=cold["index"], x_star_closed=x_cf,
                                     x_star_measured=x_meas))
    log.assert_close(worst_affine, 0.0, rtol=0.0, atol=TOL_ID,
                     label="C0. A s + 2B is affine in the warm family parameter")
    log.assert_close(worst_root, 0.0, rtol=0.0, atol=1e-9,
                     label=f"C1. bisected flip amplitude == (T14-1) root on {n} "
                           f"cold-passive cells")
    print(f"   {n} cold-passive cells, bisected x* vs (T14-1) root: max rel "
          f"{worst_root:.3e}; affineness {worst_affine:.2e}")
    for family in ("deflect", "velocity"):
        for kappa in (1.0, 2.0):
            sub = [t for t in tab if t[0] == family and t[1] == kappa]
            if sub:
                mn = min(abs(t[5]) for t in sub)
                md = float(np.median([abs(t[5]) for t in sub]))
                print(f"   {family:8s} kappa={kappa:g} ({PAIRED[kappa]:10s}): "
                      f"{len(sub):3d} cells, min |x*| {mn:.4f}, median |x*| {md:.4f}")
                rows.append(dict(block="C_summary", family=family, kappa=kappa,
                                 n_cells=len(sub), x_star_absmin=mn,
                                 x_star_absmedian=md))
    # Named operating point and the b -> 0 limit of the velocity family.
    print("   named point m/M = 10, b = 1 (cold index passive at both kappa):")
    for family in ("deflect", "velocity"):
        for kappa in (1.0, 2.0):
            x_cf, _, _ = family_root(1.0, 10.0, 1.0, h, kappa, PAIRED[kappa], family)
            print(f"     {family:8s} kappa={kappa:g}: x* = {x_cf:+.4f}")
            rows.append(dict(block="C_named", family=family, kappa=kappa, b=1.0,
                             m_over_M=10.0, x_star_closed=x_cf))
    print("   velocity-family x* as the mode softens (m/M = 10):")
    for b in (1.0, 1e-1, 1e-2, 1e-3, 1e-4):
        x1, _, _ = family_root(1.0, 10.0, b, h, 1.0, "symplectic", "velocity")
        x2, _, _ = family_root(1.0, 10.0, b, h, 2.0, "midpoint", "velocity")
        print(f"     b = {b:<8g} kappa=1 x* = {x1:+.4f}   kappa=2 x* = {x2:+.4f}")
        rows.append(dict(block="C_softlimit", b=b, m_over_M=10.0,
                         x_star_k1=x1, x_star_k2=x2))
    return tab


# --------------------------------------------------------------------------- #
# 4. Multi-row                                                                 #
# --------------------------------------------------------------------------- #
def two_row_sweep(M1, M2, M_c, K_c, J1, J2, h, kappa, weight, v1, v2,
                  order=(0, 1), shared_body=False, q_n=None, qdot_n=None,
                  predictor="symplectic"):
    """One Gauss-Seidel sweep over TWO simultaneously active rows.

    Rows C_j = z_j + J_j' q >= 0 on a shared restorative block. `shared_body`
    puts both rows on the same rigid mass (a body resting on two supports), which
    adds a second coupling channel; otherwise each row has its own body. With
    q_n = qdot_n = None the sweep is COLD, in which case only the FIRST row of the
    sweep meets the theorems' hypothesis: its successor is warm-started by its
    predecessor's deposit. Passing q_n/qdot_n makes both rows warm as well, which
    is the combined regime.
    Returns the per-row dE decomposition, the total, and the per-row indices.
    """
    M_c = np.atleast_2d(M_c)
    K_c = np.atleast_2d(K_c)
    n = M_c.shape[0]
    if weight == "mass":
        W = np.linalg.inv(M_c)
    elif weight == "matched":
        W = np.linalg.inv(kappa * kappa * M_c + h * h * K_c)
    else:
        raise ValueError(weight)
    Js = [np.asarray(J1, float), np.asarray(J2, float)]
    if shared_body:
        bodies = [1.0 / M1]
        row_body = [0, 0]
        v = [v1]
    else:
        bodies = [1.0 / M1, 1.0 / M2]
        row_body = [0, 1]
        v = [v1, v2]
    Meq = [1.0 / w for w in bodies]
    q_n = np.zeros(n) if q_n is None else np.asarray(q_n, float)
    qdot_n = np.zeros(n) if qdot_n is None else np.asarray(qdot_n, float)
    # predicted restorative position (per coordinate; M_c, K_c diagonal here)
    om = np.sqrt(np.diag(K_c) / np.diag(M_c))
    q = np.array([predict_modal(q_n[i], qdot_n[i], om[i], h, predictor)
                  for i in range(n)])
    z = [-float(Js[j] @ q_n) + h * v[row_body[j]] for j in range(2)]
    # z is per ROW (each row has its own gap); a shared body moves both.
    E0 = system_energy(v, Meq, q, q_n, qdot_n, M_c, K_c, h, kappa)
    dE_rows = [0.0, 0.0]
    dlams = [0.0, 0.0]
    for j in order:
        bi = row_body[j]
        C = z[j] + float(Js[j] @ q)
        w_row = bodies[bi] + float(Js[j] @ (W @ Js[j]))
        dlam = max(0.0, -C / w_row)
        dz = bodies[bi] * dlam
        for jj in range(2):                          # a shared body moves both gaps
            if row_body[jj] == bi:
                z[jj] += dz
        v[bi] += bodies[bi] * dlam / h               # kappa_r = 1
        q = q + (W @ Js[j]) * dlam
        E1 = system_energy(v, Meq, q, q_n, qdot_n, M_c, K_c, h, kappa)
        dE_rows[j] = E1 - E0
        dlams[j] = dlam
        E0 = E1
    Minv = np.linalg.inv(M_c)
    idx = []
    for j in range(2):
        a_sum = float(Js[j] @ (Minv @ Js[j]))
        L = h * h * float(Js[j] @ (Minv @ (K_c @ (Minv @ Js[j]))))
        wr = bodies[row_body[j]]
        idx.append(L / (wr + a_sum) if kappa == 1.0 else (L + 2.0 * a_sum) / wr)
    Wn = np.linalg.inv(M_c)
    c12 = float(Js[0] @ (Wn @ Js[1]))
    cc = c12 / np.sqrt(float(Js[0] @ (Wn @ Js[0])) * float(Js[1] @ (Wn @ Js[1])))
    return dict(dE_total=sum(dE_rows), dE_rows=dE_rows, idx=idx, dlam=dlams,
                coupling=cc)


def block_D(log, rows):
    """Two simultaneously active rows, one sweep."""
    print("\n== D. two simultaneously active rows, one Gauss-Seidel sweep ==")
    h = 1.0 / 960.0
    agg = {}
    rng = np.random.default_rng(20260728)
    for warm in (False, True):
      for shared in (False, True):
        for kappa in (1.0, 2.0):
            for weight in ("mass", "matched"):
                rng = np.random.default_rng(20260728)   # same draws in every arm
                n_cells = fn = fp = 0
                fn_r2 = 0                        # row-2-only false negatives
                order_flip = 0
                worst_fn_cc = 0.0
                for _ in range(1500):
                    n = 2
                    m1 = 10.0 ** rng.uniform(-1.5, 1.0)
                    m2 = 10.0 ** rng.uniform(-1.5, 1.0)
                    M_c = np.diag([m1, m2])
                    b1 = 10.0 ** rng.uniform(-2, 1.2)
                    b2 = 10.0 ** rng.uniform(-2, 1.2)
                    K_c = np.diag([m1 * b1 / h / h, m2 * b2 / h / h])
                    t1 = rng.uniform(0.0, np.pi)
                    t2 = rng.uniform(0.0, np.pi)
                    J1 = -np.array([np.cos(t1), np.sin(t1)])
                    J2 = -np.array([np.cos(t2), np.sin(t2)])
                    M1 = 10.0 ** rng.uniform(-1, 1)
                    M2 = 10.0 ** rng.uniform(-1, 1)
                    v1 = -10.0 ** rng.uniform(-1, 0.5)
                    v2 = -10.0 ** rng.uniform(-1, 0.5)
                    vs = abs(v1) if shared else 0.5 * (abs(v1) + abs(v2))
                    if warm:
                        # standing deflection and standing modal velocity, drawn in
                        # the same units as block B: h|v| and |v|.
                        qn0 = rng.uniform(-1.0, 1.0, 2) * h * vs
                        qdn0 = rng.uniform(-1.0, 1.0, 2) * vs
                    else:
                        qn0 = qdn0 = None
                    kw = dict(q_n=qn0, qdot_n=qdn0, predictor=PAIRED[kappa])
                    r = two_row_sweep(M1, M2, M_c, K_c, J1, J2, h, kappa, weight,
                                      v1, v2, (0, 1), shared, **kw)
                    if min(r["dlam"]) <= 0.0:
                        continue                 # not simultaneously active
                    n_cells += 1
                    inj = r["dE_total"] > 0.0
                    if weight == "matched":
                        pred_inj = False
                    else:
                        pred_inj = max(r["idx"]) > 1.0
                    if inj and not pred_inj:
                        fn += 1
                        worst_fn_cc = max(worst_fn_cc, r["coupling"])
                    elif pred_inj and not inj:
                        fp += 1
                    # row 2 alone: its own index against its own measured change
                    if weight == "mass":
                        if r["dE_rows"][1] > 0.0 and r["idx"][1] <= 1.0:
                            fn_r2 += 1
                    rB = two_row_sweep(M1, M2, M_c, K_c, J1, J2, h, kappa, weight,
                                       v1, v2, (1, 0), shared, **kw)
                    if (rB["dE_total"] > 0.0) != inj:
                        order_flip += 1
                tag = ("warm " if warm else "cold ") + \
                      ("shared body   " if shared else "separate bodies")
                print(f"   {tag}, kappa={kappa:g}, {weight:8s}: {n_cells:5d} both-active, "
                      f"FALSE NEG {fn:4d}, false pos {fp:4d}, order flips sign {order_flip:4d}"
                      + (f", row-2-only FN {fn_r2:4d}" if weight == "mass" else ""))
                rows.append(dict(block="D_multirow", warm=int(warm),
                                 shared_body=int(shared),
                                 kappa=kappa, weight=weight, n_both_active=n_cells,
                                 false_neg=fn, false_pos=fp,
                                 row2_only_false_neg=fn_r2,
                                 order_sign_flips=order_flip,
                                 max_fn_coupling=worst_fn_cc))
                log.assert_true(True, label=f"D. {tag} kappa={kappa:g} {weight}: "
                                            f"{fn}/{n_cells} false negatives, "
                                            f"{order_flip} order-dependent signs")
                key = (warm, weight)
                a = agg.setdefault(key, dict(n=0, fn=0, fp=0, flip=0, r2=0))
                a["n"] += n_cells
                a["fn"] += fn
                a["fp"] += fp
                a["flip"] += order_flip
                a["r2"] += fn_r2
    print("   aggregates over the four (shared/separate) x (kappa 1/2) arms:")
    for (warm, weight), a in sorted(agg.items()):
        wl = "warm" if warm else "cold"
        print(f"     {wl} {weight:8s}: {a['n']:5d} both-active, FALSE NEG {a['fn']:4d}"
              f" ({100.0 * a['fn'] / max(a['n'], 1):5.2f}%), false pos {a['fp']:4d}, "
              f"order-dependent signs {a['flip']:4d} "
              f"({100.0 * a['flip'] / max(a['n'], 1):5.2f}%)"
              + (f", row-2-only FN {a['r2']:4d} "
                 f"({100.0 * a['r2'] / max(a['n'], 1):5.2f}%)" if weight == "mass" else ""))
        rows.append(dict(block="D_total", warm=int(warm), weight=weight,
                         n_both_active=a["n"], false_neg=a["fn"], false_pos=a["fp"],
                         order_sign_flips=a["flip"], row2_only_false_neg=a["r2"]))
        log.assert_true(True, label=f"D-total. {wl} {weight}: {a['fn']}/{a['n']} "
                                    f"false negatives, {a['flip']} order-dependent "
                                    f"signs, {a['r2']} row-2-only false negatives")
    return agg


# --------------------------------------------------------------------------- #
# 5. Secular                                                                   #
# --------------------------------------------------------------------------- #
def secular_run(M, m, b, h, kappa, weight, n_steps, g=9.81, v0=-0.5, zeta=0.0,
                z0=0.0, predictor=None, q0=0.0, qdot0=0.0, coupled=True):
    """Persistent resting contact under gravity: rigid mass M on one restorative
    coordinate, one Gauss-Seidel projection per substep, host commit (COMMIT).

    Per substep the ledger is closed EXACTLY as
        dE_step = dE_predictor + dE_sweep,
    with dE_sweep the quantity every theorem in the paper bounds and dE_predictor
    carrying gravity, the free modal flight and the host's own velocity commit.
    The predictor is PAIRED with the commit (symplectic Euler with kappa = 1,
    implicit midpoint with kappa = 2), so with the contact switched off the modal
    free flight is exactly the symplectic integrator that commit belongs to; the
    z0 argument runs that control. Returns cumulative sweep-attributed energy
    (whole run and first half), the injecting-substep count, and the energy trace.
    """
    if predictor is None:
        predictor = PAIRED[kappa]
    omega = np.sqrt(b) / h
    k = m * omega * omega
    c_damp = 2.0 * zeta * omega * m
    M_c = np.array([[m]])
    K_c = np.array([[k]])
    # coupled=False is the RIGID-GROUND CONTROL: the same host, the same gravity,
    # the same one-sweep penetration correction, but the row does not see the
    # restorative coordinate. It measures the weight-independent baseline that a
    # position-level host accrues by lifting a penetrating body against gravity,
    # which is a rigid-side artifact and not the modal question.
    J_c = np.array([-1.0]) if coupled else np.array([0.0])
    w_r = 1.0 / M
    if weight == "mass":
        W = np.linalg.inv(M_c)
    elif weight == "matched":
        W = np.linalg.inv(kappa * kappa * M_c + h * h * K_c)
    elif weight == "implicit_be":
        W = np.linalg.inv(M_c + h * h * K_c)
    else:
        raise ValueError(weight)
    idx = predicted_index(kappa, w_r, J_c, M_c, K_c, h)

    z = z0                        # body height; the surface point sits at q
    v = v0
    q = np.array([q0])
    qdot = np.array([qdot0])
    cum_sweep = cum_sweep_half = 0.0
    cum_pred = 0.0
    cum_sweep_rigid = cum_sweep_modal = 0.0
    n_inj = 0
    n_active = 0
    worst_ledger = 0.0
    E_tr = np.zeros(n_steps)
    Em_tr = np.zeros(n_steps)
    peak_inj = 0.0
    cum_lift = 0.0
    Etot_tr = np.zeros(n_steps)
    for it in range(n_steps):
        q_n = q.copy()
        qdot_n = qdot.copy()
        # LEDGER. The paper's Hamiltonian, Eq. (3): 1/2 M v^2 + 1/2 m qdot^2 +
        # 1/2 k q^2, with NO gravity potential. Gravity is an external force and
        # enters only the predictor. This matters: a one-sweep position-level host
        # lifts a penetrating body against gravity every substep, and if M g z is
        # folded into the sweep's ledger that weight-independent rigid artifact
        # (+0.919 J here, measured by the rigid-ground control) swamps the modal
        # transfer the theorems are about. It is reported separately as cum_lift.
        E_start = system_energy([v], [M], q_n, q_n, qdot_n, M_c, K_c, h, kappa)
        # gravity + rigid predictor
        v = v - h * g
        z_pred = z + h * v
        # modal predictor, paired with the commit
        if c_damp == 0.0:
            q_pred = np.array([predict_modal(q_n[0], qdot_n[0], omega, h, predictor)])
        else:
            qdot_p = qdot_n - h * (k * q_n + c_damp * qdot_n) / m
            q_pred = q_n + h * qdot_p
        E_pred = system_energy([v], [M], q_pred, q_n, qdot_n, M_c, K_c, h, kappa)
        Em_pred = E_pred - 0.5 * M * v * v
        z1, v1, q1, _, dlam, _ = project_row(z_pred, v, q_pred, w_r, J_c, W, h)
        E_post = system_energy([v1], [M], q1, q_n, qdot_n, M_c, K_c, h, kappa)
        Em_post = E_post - 0.5 * M * v1 * v1
        dE_sweep = E_post - E_pred
        cum_sweep += dE_sweep
        if it < n_steps // 2:
            cum_sweep_half += dE_sweep
        cum_sweep_modal += Em_post - Em_pred
        cum_sweep_rigid += 0.5 * M * (v1 * v1 - v * v)
        cum_lift += M * g * (z1 - z_pred)
        cum_pred += E_pred - E_start
        worst_ledger = max(worst_ledger,
                           abs((E_post - E_start) - ((E_pred - E_start) + dE_sweep)))
        if dlam > 0.0:
            n_active += 1
            if dE_sweep > 0.0:
                n_inj += 1
                peak_inj = max(peak_inj, dE_sweep)
        z, v = z1, v1
        q = q1
        qdot = commit_qdot(q1, q_n, qdot_n, h, kappa)
        E_tr[it] = E_post
        Em_tr[it] = Em_post
        Etot_tr[it] = E_post + M * g * z1
    half = n_steps // 2
    return dict(index=idx, cum_sweep=cum_sweep, cum_sweep_half=cum_sweep_half,
                cum_lift=cum_lift, Etot0=Etot_tr[0], Etotfin=Etot_tr[-1],
                Etot_max_h1=float(Etot_tr[:half].max()),
                Etot_max_h2=float(Etot_tr[half:].max()),
                cum_sweep_rigid=cum_sweep_rigid, cum_sweep_modal=cum_sweep_modal,
                cum_pred=cum_pred, n_inj=n_inj,
                n_active=n_active, E_trace=E_tr, worst_ledger=worst_ledger,
                peak_inj=peak_inj, E0=E_tr[0], Efin=E_tr[-1], Emax=float(E_tr.max()),
                Emin=float(E_tr.min()),
                Emodal_max=float(Em_tr.max()), Emodal_final=float(Em_tr[-1]),
                Emodal_max_h1=float(Em_tr[:half].max()),
                Emodal_max_h2=float(Em_tr[half:].max()),
                Emax_h1=float(E_tr[:half].max()), Emax_h2=float(E_tr[half:].max()))


def block_E(log, rows, n_steps=20000):
    """Secular behaviour of configurations that are passive at a cold start."""
    print(f"\n== E. secular: {n_steps} substeps of persistent resting contact ==")
    h = 1.0 / 960.0
    configs = [
        # (label, M, m, b, kappa, weight)
        ("k1 mass, cold-passive",        1.0, 10.0, 1.0, 1.0, "mass"),
        ("k2 mass, cold-passive",        1.0, 10.0, 1.0, 2.0, "mass"),
        ("k1 mass, cold-injecting",      1.0,  1.0, 3.0, 1.0, "mass"),
        ("k2 mass, cold-injecting",      1.0,  1.0, 1.0, 2.0, "mass"),
        ("k1 matched m(1+b)",            1.0, 10.0, 1.0, 1.0, "matched"),
        ("k2 matched m(4+b)",            1.0, 10.0, 1.0, 2.0, "matched"),
        ("k2 backward-Euler-shaped",     1.0, 10.0, 1.0, 2.0, "implicit_be"),
    ]
    worst_ledger = 0.0
    # Control 1: free flight. The paired predictor/commit pair must not grow.
    print("   free-flight control (contact never active):")
    for kappa in (1.0, 2.0):
        rc = secular_run(1.0, 10.0, 1.0, h, kappa, "mass", n_steps, g=0.0, v0=0.0,
                         z0=1.0, q0=1e-3, qdot0=0.0)
        band = abs(rc["Emax"] - rc["Emin"]) / max(abs(rc["E0"]), 1e-30)
        growth = abs(rc["Emax_h2"] / rc["Emax_h1"] - 1.0)
        print(f"     kappa={kappa:g} ({PAIRED[kappa]:10s}): {rc['n_active']} active "
              f"substeps, cum sweep {rc['cum_sweep']:+.1e} J, free-flight energy "
              f"band {band:.2e} of E_0, second-half peak / first-half peak "
              f"- 1 = {growth:.2e}")
        log.assert_true(rc["n_active"] == 0 and rc["cum_sweep"] == 0.0
                        and growth < 1e-12,
                        label=f"E1. free-flight control kappa={kappa:g} "
                              f"({PAIRED[kappa]}): row never active, cumulative "
                              f"sweep energy exactly 0, no secular growth "
                              f"(half-peak ratio - 1 = {growth:.1e})")
        rows.append(dict(block="E_control_freeflight", kappa=kappa,
                         predictor=PAIRED[kappa], n_active=rc["n_active"],
                         cum_sweep_dE=rc["cum_sweep"], energy_band=band,
                         half_peak_growth=growth))
    # Control 2: rigid ground. Isolates the gravity-lift baseline of a one-sweep
    # position-level host, which is weight-independent and NOT the modal question.
    ground = {}
    print("   rigid-ground control (same host and gravity, row does not see the mode):")
    for kappa in (1.0, 2.0):
        rg = secular_run(1.0, 10.0, 1.0, h, kappa, "mass", n_steps, coupled=False)
        ground[kappa] = rg["cum_sweep"]
        print(f"     kappa={kappa:g}: cum sweep {rg['cum_sweep']:+.4e} J over "
              f"{rg['n_active']} active substeps, {rg['n_inj']} of them injecting; "
              f"gravity lift excluded from the ledger is {rg['cum_lift']:+.4f} J")
        log.assert_true(rg["n_inj"] == 0,
                        label=f"E2. rigid-ground control kappa={kappa:g}: "
                              f"{rg['n_inj']}/{rg['n_active']} injecting substeps "
                              f"under Eq. (3) (the excluded gravity lift is "
                              f"{rg['cum_lift']:+.3f} J)")
        rows.append(dict(block="E_control_ground", kappa=kappa,
                         cum_sweep_dE=rg["cum_sweep"],
                         cum_sweep_rigid=rg["cum_sweep_rigid"],
                         cum_sweep_modal=rg["cum_sweep_modal"],
                         cum_gravity_lift=rg["cum_lift"],
                         n_active=rg["n_active"], n_injecting=rg["n_inj"]))
    print("   coupled runs (cum sweep split; E_mod is the peak modal energy over the")
    print("   run in units of the impact energy 1/2 M v0^2 = 0.125 J):")
    for lbl, M, m, b, kappa, weight in configs:
        r = secular_run(M, m, b, h, kappa, weight, n_steps)
        worst_ledger = max(worst_ledger, r["worst_ledger"])
        frac = r["n_inj"] / max(r["n_active"], 1)
        E_imp = 0.5 * M * 0.5 ** 2
        print(f"   {lbl:26s} idx {r['index']:6.3f}  inject {r['n_inj']:6d}/"
              f"{r['n_active']:6d} ({100 * frac:5.1f}%)  cum sweep "
              f"{r['cum_sweep']:+.3e} = rigid {r['cum_sweep_rigid']:+.3e} + modal "
              f"{r['cum_sweep_modal']:+.3e} J   E_mod peak "
              f"{r['Emodal_max'] / E_imp:8.3f} (h2/h1 "
              f"{r['Emodal_max_h2'] / max(r['Emodal_max_h1'], 1e-300):.3f})")
        rows.append(dict(block="E_secular", label=lbl, M=M, m=m, b=b, kappa=kappa,
                         weight=weight, predictor=PAIRED[kappa], n_steps=n_steps,
                         index=r["index"],
                         n_active=r["n_active"], n_injecting=r["n_inj"],
                         inject_frac=frac, cum_sweep_dE=r["cum_sweep"],
                         cum_sweep_first_half=r["cum_sweep_half"],
                         cum_sweep_rigid=r["cum_sweep_rigid"],
                         cum_sweep_modal=r["cum_sweep_modal"],
                         cum_sweep_minus_ground=r["cum_sweep"] - ground[kappa],
                         cum_gravity_lift_excluded=r["cum_lift"],
                         cum_predictor_dE=r["cum_pred"], peak_step_inj=r["peak_inj"],
                         E_impact=E_imp, Emodal_peak=r["Emodal_max"],
                         Emodal_peak_over_impact=r["Emodal_max"] / E_imp,
                         Emodal_peak_h1=r["Emodal_max_h1"],
                         Emodal_peak_h2=r["Emodal_max_h2"],
                         E0=r["E0"], E_final=r["Efin"], E_max=r["Emax"]))
        log.assert_true(True, label=f"E. {lbl}: cold index {r['index']:.3f}, "
                                    f"{r['n_inj']}/{r['n_active']} injecting substeps, "
                                    f"modal part of the cumulative sweep "
                                    f"{r['cum_sweep_modal']:+.3e} J, peak modal energy "
                                    f"{r['Emodal_max'] / E_imp:.3f} E_impact")
    log.assert_close(worst_ledger, 0.0, rtol=0.0, atol=1e-12,
                     label="E0. per-substep ledger dE_step == dE_pred + dE_sweep")
    print(f"   ledger closure |dE_step - (dE_pred + dE_sweep)| <= {worst_ledger:.2e} J")


# --------------------------------------------------------------------------- #
def main():
    log = CheckLog()
    rows = []
    print("T14: warm-start and multi-row degradation of the one-sweep diagnostic")
    print("     MEASUREMENT ONLY. No theorem below is extended; the deliverable is")
    print("     the boundary of the diagnostic and the direction in which it fails.")
    nA, n_cold = block_A(log, rows)
    sB = block_B(log, rows)
    block_C(log, rows)
    aggD = block_D(log, rows)
    block_E(log, rows)

    # ------------------------------------------------------------------ #
    # Composite totals the paper quotes. Every one traces to a block above. #
    # ------------------------------------------------------------------ #
    print("\n== HEADLINE (the numbers the paper quotes) ==")
    nB = sum(sB[(k, "mass", p)]["n"] for k in (1.0, 2.0) for p in PREDICTORS)
    fB = sum(sB[(k, "mass", p)]["fn"] for k in (1.0, 2.0) for p in PREDICTORS)
    pB = sum(sB[(k, "mass", p)]["fp"] for k in (1.0, 2.0) for p in PREDICTORS)
    nBm = sum(sB[(k, "matched", p)]["n"] for k in (1.0, 2.0) for p in PREDICTORS)
    fBm = sum(sB[(k, "matched", p)]["fn"] for k in (1.0, 2.0) for p in PREDICTORS)
    nD = aggD[(False, "mass")]["n"] + aggD[(True, "mass")]["n"]
    fD = aggD[(False, "mass")]["fn"] + aggD[(True, "mass")]["fn"]
    nDm = aggD[(False, "matched")]["n"] + aggD[(True, "matched")]["n"]
    fDm = aggD[(False, "matched")]["fn"] + aggD[(True, "matched")]["fn"]
    pD = aggD[(False, "mass")]["fp"] + aggD[(True, "mass")]["fp"]
    flip = aggD[(False, "mass")]["flip"] + aggD[(True, "mass")]["flip"]
    print(f"   cold control cells, 0 misclassified          : {2 * n_cold}")
    print(f"   warm one-row cells, mass-only weight         : {nB}, "
          f"{fB} false negatives, {pB} false positives")
    print(f"   two-row cells, mass-only weight              : {nD}, "
          f"{fD} false negatives, {pD} false positives, "
          f"{flip} order-dependent signs")
    print(f"   COMBINED warm + multi-row, mass-only         : {nB + nD}, "
          f"{fB + fD} false negatives ({100.0 * (fB + fD) / (nB + nD):.2f}%), "
          f"{pB + pD} false positives ({100.0 * (pB + pD) / (nB + nD):.2f}%)")
    print(f"   same cells, reconstruction-matched charge    : {nBm + nDm}, "
          f"{fBm + fDm} injecting")
    print(f"   instrument cells checked against the sweep   : {nA}")
    rows.append(dict(block="HEADLINE", cold_control_cells=2 * n_cold,
                     cold_misclassified=0,
                     warm_onerow_cells_mass=nB, warm_onerow_false_neg=fB,
                     warm_onerow_false_pos=pB,
                     tworow_cells_mass=nD, tworow_false_neg=fD,
                     tworow_false_pos=pD,
                     tworow_order_sign_flips=flip,
                     combined_cells_mass=nB + nD, combined_false_neg=fB + fD,
                     combined_false_pos=pB + pD,
                     combined_cells_matched=nBm + nDm,
                     combined_injecting_matched=fBm + fDm,
                     instrument_cells=nA))
    log.assert_true(True,
                    label=f"HEADLINE. {2 * n_cold} cold cells 0 misclassified; "
                          f"{nB + nD} warm/two-row mass-only cells {fB + fD} false "
                          f"negatives; same cells matched charge {fBm + fDm} injecting")

    field_union = []
    for r in rows:
        for kk in r:
            if kk not in field_union:
                field_union.append(kk)
    rows = [{kk: r.get(kk, "") for kk in field_union} for r in rows]
    write_csv(OUT, "t14_warm_multirow", rows, fieldnames=field_union,
              manifest=dict(script="run_t14_warm_multirow.py",
                            what="measured degradation of the one-sweep diagnostic "
                                 "outside its hypotheses: warm start, two "
                                 "simultaneously active rows, secular multi-step",
                            metrics="index-vs-measured-sign agreement split into "
                                    "false negatives (unsafe) and false positives, "
                                    "flip amplitude x* in units of h|v| and |v|, "
                                    "order-dependent signs, cumulative "
                                    "sweep-attributed energy over 20,000 substeps",
                            tol="1e-12 on the instrument identity, 1e-9 on the "
                                "bisected threshold and the ledger, sign elsewhere"))

    print("\n" + "\n".join(log.summary_lines()))
    fails = log.failures
    print(f"\nT14: {len(log.rows) - len(fails)}/{len(log.rows)} checks pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
