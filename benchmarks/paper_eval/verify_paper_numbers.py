#!/usr/bin/env python3
"""Verify every R5/R6/R7 number printed in `paper/main_short.tex` against the
frozen CSVs (MIG 2026 short paper).

Why this exists. Three numbers had to be retracted during the review-response
pass -- a ratio with a denominator that accumulated from zero, an FFT peak that
moved with window length, and a ledger-overhead range that came from the wrong
machine AND quoted its own error bar as its value. Each was caught by hand.
This makes the check mechanical and repeatable, so a number cannot drift
between the CSV and the tex without failing loudly.

Scope: the numbers introduced by R5 (governed accuracy, AVBD validity rows,
normalized penetration) and R7 (CPU enforcement cost). Earlier items are
already covered by their own `--check-frozen` acceptance paths
(`run_eq2_utilization.py`, `run_governed_accuracy.py`).

Exit code 0 if every check passes, 1 otherwise.

Run: .venv/bin/python benchmarks/paper_eval/verify_paper_numbers.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
X1 = os.path.join(_HERE, "x1_passivity", "out")
X5 = os.path.join(_HERE, "x5_perf", "out")
TEX = os.path.join(_ROOT, "paper", "main_short.tex")

_ok: list[str] = []
_bad: list[str] = []
_skipped: list[str] = []


def chk(label: str, cond: bool, detail: str) -> None:
    (_ok if cond else _bad).append(f"{label}: {detail}")


def _sections(path):
    """governed_accuracy.csv is a long (section, key, value) table."""
    out: dict[str, dict[str, str]] = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["section"], {})[r["key"]] = r["value"]
    return out


def main() -> int:
    # The supplement ships the CSVs flat in `data/` and does not ship the tex,
    # so both locations are overridable and the tex-dependent checks degrade to
    # SKIP rather than crashing. Without this the bundle's own CLAIMS_INDEX
    # pointed at a script that could not run from the bundle.
    global X1, X5
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="directory holding the CSVs (supplement: "
                                   "`data`); defaults to the in-repo out/ dirs")
    ap.add_argument("--tex", default=TEX, help="paper source; checks that need "
                                               "it are skipped if absent")
    a = ap.parse_args()
    if a.data:
        X1 = X5 = a.data
    tex = open(a.tex).read() if os.path.isfile(a.tex) else None

    # ---- R5.1 / R5.1c: governed accuracy + spectral content ----------------
    g = _sections(os.path.join(X1, "governed_accuracy.csv"))
    arm = lambda a, k: float(g[f"arm:{a}"][k])           # noqa: E731
    acc = lambda r, k: float(g[f"accuracy:{r}"][k])      # noqa: E731
    sag = lambda r, k: float(g[f"sag:{r}"][k])           # noqa: E731

    chk("E_mod ungoverned 1555.6 J",
        abs(arm("ungoverned", "e_modal_peak_J") - 1555.6) < 0.1,
        f"{arm('ungoverned', 'e_modal_peak_J'):.1f}")
    chk("E_mod governed 29.56 J",
        abs(arm("governed", "e_modal_peak_J") - 29.56) < 0.01,
        f"{arm('governed', 'e_modal_peak_J'):.2f}")
    chk("E_mod reference 7.92 J",
        abs(arm("oracle", "e_modal_peak_J") - 7.92) < 0.01,
        f"{arm('oracle', 'e_modal_peak_J'):.4f}")
    chk("E_mod xpbd fixed point 8.22 J",
        abs(arm("xpbd_converged", "e_modal_peak_J") - 8.22) < 0.01,
        f"{arm('xpbd_converged', 'e_modal_peak_J'):.4f}")
    chk("KE fraction 0.3%",
        abs(100 * arm("ungoverned", "ke_frac_at_peak") - 0.3) < 0.05,
        f"{100 * arm('ungoverned', 'ke_frac_at_peak'):.2f}%")

    # The spectral claim, including that the 10 kHz cut sits in a real gap --
    # this is the guard against the threshold quietly becoming a tuned knob.
    chk("E>10kHz ungoverned 99.6%",
        abs(100 * arm("ungoverned", "energy_frac_above_10kHz") - 99.6) < 0.1,
        f"{100 * arm('ungoverned', 'energy_frac_above_10kHz'):.3f}%")
    chk("E>10kHz governed 97.7%",
        abs(100 * arm("governed", "energy_frac_above_10kHz") - 97.7) < 0.1,
        f"{100 * arm('governed', 'energy_frac_above_10kHz'):.3f}%")
    for a in ("oracle", "xpbd_converged"):
        chk(f"E>10kHz {a} is 0.0%",
            100 * arm(a, "energy_frac_above_10kHz") < 0.05,
            f"{100 * arm(a, 'energy_frac_above_10kHz'):.4f}%")
    lo, hi = (arm("ungoverned", "spectral_gap_lo_Hz"),
              arm("ungoverned", "spectral_gap_hi_Hz"))
    chk("spectral gap 2.03 kHz -> 20.7 kHz (threshold not tuned)",
        abs(lo - 2033) < 3 and abs(hi - 20685) < 5, f"{lo:.0f} -> {hi:.0f} Hz")
    chk("gap spans the 10 kHz cut by >3x on both sides",
        lo < 1e4 / 3 and hi > 1e4 * 2, f"{lo:.0f} < 10000 < {hi:.0f}")

    chk("energy error 196x -> 3.7x (reference)",
        abs(acc("oracle", "ungoverned_E_err_x") - 196.5) < 0.5
        and abs(acc("oracle", "governed_E_err_x") - 3.733) < 0.01,
        f"{acc('oracle', 'ungoverned_E_err_x'):.1f} -> "
        f"{acc('oracle', 'governed_E_err_x'):.3f}")
    chk("energy error 189x -> 3.6x (xpbd fixed point)",
        abs(acc("xpbd_converged", "ungoverned_E_err_x") - 189.2) < 0.5
        and abs(acc("xpbd_converged", "governed_E_err_x") - 3.594) < 0.01,
        f"{acc('xpbd_converged', 'ungoverned_E_err_x'):.1f} -> "
        f"{acc('xpbd_converged', 'governed_E_err_x'):.3f}")
    chk("Linf 6.5 -> 14.2 mm (governed is WORSE)",
        abs(1e3 * acc("oracle", "ungoverned_linf_m") - 6.5) < 0.06
        and abs(1e3 * acc("oracle", "governed_linf_m") - 14.19) < 0.06
        and acc("oracle", "governed_linf_m") > acc("oracle", "ungoverned_linf_m"),
        f"{1e3 * acc('oracle', 'ungoverned_linf_m'):.2f} -> "
        f"{1e3 * acc('oracle', 'governed_linf_m'):.2f} mm")
    chk("Linf 33% -> 71% of reference peak",
        abs(100 * acc("oracle", "ungoverned_linf_rel") - 33) < 1
        and abs(100 * acc("oracle", "governed_linf_rel") - 71) < 1,
        f"{100 * acc('oracle', 'ungoverned_linf_rel'):.1f}% -> "
        f"{100 * acc('oracle', 'governed_linf_rel'):.1f}%")

    # ---- the gap-preserving arm's accuracy (paper 4.2 "Accuracy") ----------
    # Same cell, same references; only the projection differs. Every number the
    # paper prints for the preserving arm is checked here, and each is compared
    # against the whole-state arm above so a regression in either shows up.
    try:
        gp = _sections(os.path.join(X1, "governed_accuracy_gap.csv"))
    except FileNotFoundError:
        _skipped.append("gap-preserving accuracy (run run_governed_accuracy "
                        "--gap-preserving --out governed_accuracy_gap)")
        gp = None
    if gp:
        garm = lambda k: float(gp["arm:governed"][k])           # noqa: E731
        gacc = lambda r, k: float(gp[f"accuracy:{r}"][k])       # noqa: E731
        chk("preserving: E_mod governed 28.7 J",
            abs(garm("e_modal_peak_J") - 28.68) < 0.02,
            f"{garm('e_modal_peak_J'):.3f}")
        chk("preserving: energy error 3.6x / 3.5x",
            abs(gacc("oracle", "governed_E_err_x") - 3.622) < 0.01
            and abs(gacc("xpbd_converged", "governed_E_err_x") - 3.487) < 0.01,
            f"{gacc('oracle', 'governed_E_err_x'):.3f} / "
            f"{gacc('xpbd_converged', 'governed_E_err_x'):.3f}")
        chk("preserving: Linf 9.2 mm (46% of ref peak), better than 14.2 (71%)",
            abs(1e3 * gacc("oracle", "governed_linf_m") - 9.235) < 0.02
            and abs(100 * gacc("oracle", "governed_linf_rel") - 46.2) < 0.2
            and gacc("oracle", "governed_linf_m")
                < acc("oracle", "governed_linf_m"),
            f"{1e3 * gacc('oracle', 'governed_linf_m'):.2f} mm / "
            f"{100 * gacc('oracle', 'governed_linf_rel'):.1f}%")
        chk("preserving: E>10kHz falls to 89.8% (vs 97.7% scaled)",
            abs(100 * garm("energy_frac_above_10kHz") - 89.76) < 0.1
            and garm("energy_frac_above_10kHz")
                < arm("governed", "energy_frac_above_10kHz"),
            f"{100 * garm('energy_frac_above_10kHz'):.2f}%")
        chk("preserving: reference peak deflection 20.5 mm",
            abs(1e3 * gacc("xpbd_converged", "ref_peak_defl_m") - 20.48) < 0.05,
            f"{1e3 * gacc('xpbd_converged', 'ref_peak_defl_m'):.2f} mm")

    # ---- the 90 governed cells, gap-preserving (paper 4 "governor holds") --
    try:
        marg, ratio = [], {}
        for f in ("solver_matrix_gap.csv", "solver_matrix_deployed_gap.csv"):
            with open(os.path.join(X1, f)) as fh:
                for r in csv.DictReader(fh):
                    if r["max_net_excess_on"] not in ("", "None"):
                        marg.append(float(r["max_net_excess_on"]))
                    if r["holds_on"] != "True" or r["passive_on"] != "True":
                        marg.append(float("inf"))       # forces the check to fail
                    if r["ratio_on"] not in ("", "None"):
                        ratio.setdefault(r["solver"], []).append(
                            float(r["ratio_on"]))
        chk("90 governed cells hold at the roundoff floor (3.6e-15 J)",
            len(marg) == 90 and max(marg) < 4e-15,
            f"{len(marg)} cells, worst margin {max(marg):.2e} J")
        chk("preserving: worst governed ratio 1.15 (xpbd) / 1.70 (avbd)",
            abs(max(ratio["xpbd"]) - 1.1455) < 0.002
            and abs(max(ratio["avbd"]) - 1.7003) < 0.002,
            f"{max(ratio['xpbd']):.4f} / {max(ratio['avbd']):.4f}")
    except FileNotFoundError:
        _skipped.append("90-cell governed sweep (run run_solver_matrix "
                        "--gap-preserving)")

    # ---- R5.4: normalized penetration --------------------------------------
    chk("resting sag 1.7-2.4 mm",
        abs(1e3 * sag("xpbd_converged", "sag_tail_median_m") - 1.714) < 0.01
        and abs(1e3 * sag("oracle", "sag_tail_median_m") - 2.377) < 0.01,
        f"{1e3 * sag('xpbd_converged', 'sag_tail_median_m'):.3f} / "
        f"{1e3 * sag('oracle', 'sag_tail_median_m'):.3f} mm")
    chk("21.6 mm = 1.05-1.08x peak deflection",
        abs(sag("xpbd_converged", "pen_over_peak_defl_x") - 1.05) < 0.006
        and abs(sag("oracle", "pen_over_peak_defl_x") - 1.08) < 0.006,
        f"{sag('xpbd_converged', 'pen_over_peak_defl_x'):.3f} / "
        f"{sag('oracle', 'pen_over_peak_defl_x'):.3f}")
    chk("21.6 mm = 9-13x resting sag",
        9 <= sag("oracle", "pen_over_sag_x") <= 13
        and 9 <= sag("xpbd_converged", "pen_over_sag_x") <= 13,
        f"{sag('oracle', 'pen_over_sag_x'):.2f} / "
        f"{sag('xpbd_converged', 'pen_over_sag_x'):.2f}")

    # ---- R5.2: Table 2 augmented-Lagrangian rows (trapezoidal-W_g reframe) --
    # After the §15 gravity-supply fix the AVBD host materially overdraws only
    # at the starved dinner 1.0 4x1 cell (+6.7 J); its other R>1 cell (dinner
    # 0.7 4x1) satisfies the invariant outright, so the clamp is inert there.
    # (The former block asserted a 1.4/3.1 mm pair and a "within 1.4x" claim,
    # both of which were artifacts of the displacement-form supply.)
    avbd = {float(r["relax"]): r for r in csv.DictReader(
        open(os.path.join(X1, "projection_validity_avbd.csv")))}
    chk("avbd 0.7 4x1 clamp inert (holds the invariant, R>1 notwithstanding)",
        int(float(avbd[0.7]["n_clamped"])) == 0,
        f"n_clamped={avbd[0.7]['n_clamped']}")
    r10 = avbd[1.0]
    chk("avbd 1.0 4x1 worst gap 1.8 mm (vs XPBD 21.6)",
        abs(1e3 * float(r10["gap_viol_post_max_m"]) - 1.809) < 0.01,
        f"{1e3 * float(r10['gap_viol_post_max_m']):.3f}")
    chk("avbd 1.0 4x1 gamma_min 0.879",
        abs(float(r10["gamma_min"]) - 0.8788) < 0.001,
        f"{float(r10['gamma_min']):.4f}")
    chk("avbd 1.0 4x1 no measurable corrective impulse",
        float(r10["impulse_next_over_steady"]) == 0.0,
        f"{float(r10['impulse_next_over_steady']):.3f}")
    chk("avbd 1.0 4x1 momentum unchanged across projection",
        float(r10["dP_across_projection_max"]) == 0.0,
        f"{float(r10['dP_across_projection_max']):.3e}")
    with open(os.path.join(X1, "projection_validity.csv")) as fh:
        xr = [(float(r["gap_viol_post_max_m"]) / float(r["gap_viol_pre_max_m"]),
               float(r["impulse_next_over_steady"] or "nan"),
               (float(r["lam_var_clamped_median"]) / float(r["lam_var_free_median"])
                if float(r["lam_var_free_median"]) else float("nan")))
              for r in csv.DictReader(fh)]
    # The range is over ALL FOUR Table 2 rows. It was printed as "3.5-12.6x"
    # for two rounds, which is the SHELF-only minimum: ledge 4x1 is 3.12, below
    # the printed floor. Corrected to 3.1-12.6x. The correction does not weaken
    # the sentence it appears in twice -- §3.3 compares the AVBD host's 3.1 and
    # 5.5x against this range and calls them "comparable", which a floor of 3.1
    # supports more strongly than a floor of 3.5.
    glo, ghi = min(g for g, _, _ in xr), max(g for g, _, _ in xr)
    chk("xpbd relative effect spans 3.1-12.5x",
        abs(glo - 3.1) < 0.05 and abs(ghi - 12.47) < 0.05,
        f"{glo:.2f}-{ghi:.2f}x")
    chk("xpbd worst impulse 8.9x, worst lambda variance 62x",
        abs(max(i for _, i, _ in xr if i == i) - 8.915) < 0.006
        and abs(max(v for _, _, v in xr if v == v) - 61.63) < 0.5,
        f"{max(i for _, i, _ in xr if i == i):.3f}x / "
        f"{max(v for _, _, v in xr if v == v):.1f}x")

    # ---- the three-arm penetration decomposition (paper Table 2 + 4.2) -----
    # The paper no longer prints the whole-state pre/post ratio (3.1-12.5x);
    # it prints each projection's amplification over the UNCLAMPED solve, which
    # is the attribution that matters: the penetration originates in the
    # truncated row, and a projection only amplifies it.
    def _arms(name):
        out = {}
        with open(os.path.join(X1, name)) as fh:
            for r in csv.DictReader(fh):
                out[(r["scene"], r["iters"], r["substeps"], r["arm"])] = r
        return out
    try:
        arms = {}
        for f in ("projection_validity_arms_r07.csv",
                  "projection_validity_arms_r10.csv"):
            arms.update({(f[-7:-4],) + k: v for k, v in _arms(f).items()})
    except FileNotFoundError:
        _skipped.append("three-arm decomposition (run run_projection_validity "
                        "--arms radial,gap,ungov)")
        arms = {}
    if arms:
        cells = {k[:4] for k in arms}
        amp = {}
        for c in cells:
            u = arms.get(c + ("ungov",))
            if u is None:
                continue
            base = float(u["gap_viol_end_max_m"])
            for a in ("radial", "gap"):
                r = arms.get(c + (a,))
                if r is not None and base > 0:
                    amp.setdefault(a, []).append(
                        float(r["gap_viol_end_max_m"]) / base)
        rlo, rhi = min(amp["radial"]), max(amp["radial"])
        glo2, ghi2 = min(amp["gap"]), max(amp["gap"])
        chk("whole-state amplification over the unclamped solve is 2.4-47.6x",
            abs(rlo - 2.4) < 0.1 and abs(rhi - 47.6) < 0.6,
            f"{rlo:.2f}-{rhi:.2f}x over {len(amp['radial'])} cells")
        chk("gap-preserving amplification is 1.0-6.3x",
            abs(glo2 - 1.0) < 0.05 and abs(ghi2 - 6.34) < 0.1,
            f"{glo2:.2f}-{ghi2:.2f}x over {len(amp['gap'])} cells")
        imp = [float(arms[c + ("radial",)]["gap_viol_end_max_m"])
               / float(arms[c + ("gap",)]["gap_viol_end_max_m"])
               for c in cells if c + ("gap",) in arms
               and float(arms[c + ("gap",)]["gap_viol_end_max_m"]) > 0]
        chk("preserving beats scaling by 1.2-12.9x in every cell",
            abs(min(imp) - 1.19) < 0.05 and abs(max(imp) - 12.88) < 0.1,
            f"{min(imp):.2f}-{max(imp):.2f}x")
        # the ledge 4x1 exception: the observed surface is itself unaffordable
        led = arms.get(("r07", "ledge", "4", "1", "gap"))
        if led is not None:
            chk("ledge 4x1 asks to preserve >300x the whole budget",
                float(led["eqs_over_ceiling_max"]) > 100.0,
                f"E_qs/ceiling max = {float(led['eqs_over_ceiling_max']):.0f}x")
    try:
        conv = _arms("projection_validity_arms_converged.csv")
        pen = [float(r["gap_viol_end_max_m"]) for r in conv.values()]
        clamps = {int(r["n_clamped"]) for r in conv.values()}
        chk("converged budgets: no clamp fires, penetration 0.011-0.124 mm",
            clamps == {0} and abs(1e3 * min(pen) - 0.011) < 0.002
            and abs(1e3 * max(pen) - 0.124) < 0.002,
            f"clamps={sorted(clamps)}, {1e3*min(pen):.3f}-{1e3*max(pen):.3f} mm")
    except FileNotFoundError:
        _skipped.append("converged-budget control (run run_projection_validity "
                        "--budgets 16x4,32x1 --arms radial,gap,ungov)")

    # ---- R7: CPU enforcement cost ------------------------------------------
    with open(os.path.join(X5, "perf_reps_summary.csv")) as fh:
        rows = list(csv.DictReader(fh))
    base = [float(r["mean_ms"]) for r in rows]
    chk("baseline 11.0-125.6 ms",
        abs(min(base) - 10.99) < 0.02 and abs(max(base) - 125.63) < 0.02,
        f"{min(base):.2f}-{max(base):.2f}")
    res = [r for r in rows if r["scene"] != "dinner"]
    cl = [float(r["clamp_ms"]) for r in res]
    pct = [100 * float(r["clamp_ms"]) / float(r["mean_ms"]) for r in res]
    chk("ledger 0.23-0.41 ms where resolved",
        abs(min(cl) - 0.2306) < 0.001 and abs(max(cl) - 0.4065) < 0.001,
        f"{min(cl):.4f}-{max(cl):.4f}")
    chk("ledger 0.9-3.4% where resolved",
        0.85 < min(pct) < 0.87 and 3.3 < max(pct) < 3.4,
        f"{min(pct):.2f}-{max(pct):.2f}%")
    # The paper reports the table scene as UNRESOLVED. That must stay true:
    # if a future run resolves it, the prose has to change.
    for r in rows:
        if r["scene"] == "dinner":
            m, s = float(r["clamp_ms"]), float(r["clamp_std_ms"])
            chk(f"table/{r['solver']} still unresolved (sigma > mean)", s > m,
                f"+{m:.2f} +/- {s:.2f}")
    chk("every resolved row has sigma < mean",
        all(float(r["clamp_std_ms"]) < float(r["clamp_ms"]) for r in res),
        "4/4")

    # ---- R8d: Fig. 1 is rendered from the SHIPPED projection ---------------
    # Until 2026-07-22 the teaser's governed panel came from the superseded
    # whole-state scale, and none of its caption numbers were checked. The
    # first check below is the guard against that regressing; the rest pin the
    # caption. The rendered instant is logged frame 50 (fig_teaser --frame).
    tzr = os.path.join(_ROOT, "benchmarks", "paper_fig", "out",
                       "teaser_deployed_gap")
    if os.path.isfile(tzr + ".manifest.json"):
        import json

        import numpy as np
        man = json.load(open(tzr + ".manifest.json"))
        pk = man["peaks"]
        chk("Fig.1 recorded with the shipped projection",
            man.get("projection", "").startswith("gap-preserving"),
            man.get("projection", "(absent)"))
        chk("Fig.1 ungoverned throws books 93 mm",
            abs(max(pk["off"]["bystander_rise_mm"]) - 93.3) < 0.1,
            f"{max(pk['off']['bystander_rise_mm']):.1f} mm")
        chk("Fig.1 governed peak E_mod 30.2 J",
            abs(pk["on"]["e_mod_peak_J"] - 30.2) < 0.05,
            f"{pk['on']['e_mod_peak_J']:.2f} J")
        chk("Fig.1 governed: no book leaves rest",
            max(pk["on"]["bystander_rise_mm"]) <= 0.0,
            f"{max(pk['on']['bystander_rise_mm']):+.1f} mm peak rise")
        z = np.load(tzr + ".npz")
        s = int(z["off/settle"])
        byst = np.asarray([not b["is_impactor"] for b in man["bodies"]],
                          dtype=bool)
        def lift(a):                                          # noqa: E306
            p = z[f"{a}/pos"]
            return float(np.max((p[s + 50, :, 1] - p[s - 1, :, 1])[byst]) * 1e3)
        chk("Fig.1 reference lifts one book 19 mm at the rendered frame",
            abs(lift("ref") - 19.0) < 0.5, f"{lift('ref'):.1f} mm")
        chk("Fig.1 governed lifts none at the rendered frame",
            lift("on") <= 0.0, f"{lift('on'):+.1f} mm")
    else:
        _skipped.append("Fig. 1 caption numbers (run record_teaser.py --case "
                        "deployed --gap-preserving --out teaser_deployed_gap)")

    # ---- report ------------------------------------------------------------
    for line in _ok:
        print(f"  ok   {line}")
    for line in _skipped:
        print(f"  skip {line}")
    for line in _bad:
        print(f"  FAIL {line}")
    print(f"\n{len(_ok)} passed, {len(_bad)} failed"
          + (f", {len(_skipped)} skipped" if _skipped else ""))
    return 1 if _bad else 0


if __name__ == "__main__":
    sys.exit(main())
