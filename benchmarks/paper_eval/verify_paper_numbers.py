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
    tex = open(TEX).read()

    # ---- R5.1 / R5.1c: governed accuracy + spectral content ----------------
    g = _sections(os.path.join(X1, "governed_accuracy.csv"))
    arm = lambda a, k: float(g[f"arm:{a}"][k])           # noqa: E731
    acc = lambda r, k: float(g[f"accuracy:{r}"][k])      # noqa: E731
    sag = lambda r, k: float(g[f"sag:{r}"][k])           # noqa: E731

    chk("E_mod ungoverned 1555.6 J",
        abs(arm("ungoverned", "e_modal_peak_J") - 1555.6) < 0.1,
        f"{arm('ungoverned', 'e_modal_peak_J'):.1f}")
    chk("E_mod governed 29.26 J",
        abs(arm("governed", "e_modal_peak_J") - 29.26) < 0.01,
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
        and abs(acc("oracle", "governed_E_err_x") - 3.696) < 0.01,
        f"{acc('oracle', 'ungoverned_E_err_x'):.1f} -> "
        f"{acc('oracle', 'governed_E_err_x'):.3f}")
    chk("energy error 189x -> 3.6x (xpbd fixed point)",
        abs(acc("xpbd_converged", "ungoverned_E_err_x") - 189.2) < 0.5
        and abs(acc("xpbd_converged", "governed_E_err_x") - 3.558) < 0.01,
        f"{acc('xpbd_converged', 'ungoverned_E_err_x'):.1f} -> "
        f"{acc('xpbd_converged', 'governed_E_err_x'):.3f}")
    chk("Linf 6.5 -> 14.3 mm (governed is WORSE)",
        abs(1e3 * acc("oracle", "ungoverned_linf_m") - 6.5) < 0.06
        and abs(1e3 * acc("oracle", "governed_linf_m") - 14.3) < 0.06
        and acc("oracle", "governed_linf_m") > acc("oracle", "ungoverned_linf_m"),
        f"{1e3 * acc('oracle', 'ungoverned_linf_m'):.2f} -> "
        f"{1e3 * acc('oracle', 'governed_linf_m'):.2f} mm")
    chk("Linf 33% -> 71% of reference peak",
        abs(100 * acc("oracle", "ungoverned_linf_rel") - 33) < 1
        and abs(100 * acc("oracle", "governed_linf_rel") - 71) < 1,
        f"{100 * acc('oracle', 'ungoverned_linf_rel'):.1f}% -> "
        f"{100 * acc('oracle', 'governed_linf_rel'):.1f}%")

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

    # ---- R5.2: Table 2 augmented-Lagrangian rows ---------------------------
    want = {0.7: (1.43, 1.17, 0.729), 1.0: (3.11, 1.39, 0.6016)}
    rel = {}
    with open(os.path.join(X1, "projection_validity_avbd.csv")) as fh:
        for r in csv.DictReader(fh):
            rx = float(r["relax"])
            gap, imp, gmin = want[rx]
            tag = f"table({rx})"
            # The P-round page squeeze removed Table 2's AVBD rows, so the
            # clamp counts are no longer printed and asserting them "in tex"
            # became a stale check that failed for two rounds. What the tex
            # DOES still print for this host is checked below: the absolute
            # worst gaps, the "within 1.4x" claim, and the relative ratios.
            rel[rx] = (float(r["gap_viol_post_max_m"])
                       / float(r["gap_viol_pre_max_m"]))
            chk(f"{tag} impulse and lambda-variance within 1.4x of steady",
                float(r["impulse_next_over_steady"]) <= 1.4
                and (float(r["lam_var_clamped_median"])
                     / float(r["lam_var_free_median"])) <= 1.4,
                f"{float(r['impulse_next_over_steady']):.3f}x / "
                f"{float(r['lam_var_clamped_median']) / float(r['lam_var_free_median']):.3f}x")
            chk(f"{tag} worst gap {gap} mm",
                abs(1e3 * float(r["gap_viol_post_max_m"]) - gap) < 0.006,
                f"{1e3 * float(r['gap_viol_post_max_m']):.3f}")
            chk(f"{tag} impulse ratio {imp}x",
                abs(float(r["impulse_next_over_steady"]) - imp) < 0.006,
                f"{float(r['impulse_next_over_steady']):.3f}")
            chk(f"{tag} gamma_min {gmin}",
                abs(float(r["gamma_min"]) - gmin) < 0.001,
                f"{float(r['gamma_min']):.4f}")
            chk(f"{tag} momentum unchanged across projection",
                float(r["dP_across_projection_max"]) == 0.0,
                f"{float(r['dP_across_projection_max']):.3e}")

    # The printed cross-host comparison: AVBD an order of magnitude gentler in
    # absolute terms, comparable in relative terms (3.1 and 5.5x vs 3.5-12.6x).
    chk("avbd relative effect 3.1x and 5.5x",
        abs(rel[0.7] - 3.1) < 0.05 and abs(rel[1.0] - 5.5) < 0.05,
        f"{rel[0.7]:.2f}x / {rel[1.0]:.2f}x")
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
    chk("xpbd relative effect spans 3.1-12.6x",
        abs(glo - 3.1) < 0.05 and abs(ghi - 12.6) < 0.05,
        f"{glo:.2f}-{ghi:.2f}x")
    chk("tex prints the corrected 3.1-12.6x range (both sites)",
        tex.count(r"$3.1$--$12.6\times$") == 2
        and r"$3.5$--$12.6\times$" not in tex,
        f"{tex.count(r'$3.1$--$12.6\times$')} site(s) corrected, "
        f"{tex.count(r'$3.5$--$12.6\times$')} stale")
    chk("xpbd worst impulse 8.7x, worst lambda variance 58x",
        abs(max(i for _, i, _ in xr if i == i) - 8.693) < 0.006
        and abs(max(v for _, _, v in xr if v == v) - 58.5) < 0.5,
        f"{max(i for _, i, _ in xr if i == i):.3f}x / "
        f"{max(v for _, _, v in xr if v == v):.1f}x")

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

    # ---- report ------------------------------------------------------------
    for line in _ok:
        print(f"  ok   {line}")
    for line in _bad:
        print(f"  FAIL {line}")
    print(f"\n{len(_ok)} passed, {len(_bad)} failed")
    return 1 if _bad else 0


if __name__ == "__main__":
    sys.exit(main())
