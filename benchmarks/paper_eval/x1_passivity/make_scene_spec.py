#!/usr/bin/env python3
"""P8.a — the scene-specification table for the supplement (plan §8.5).

Reproducibility was the panels' lowest-scoring criterion (2.5/5). The paper
names its three scenes but never prints their geometry, material, masses, drop
heights, realized modal rank or damping, so no reader can rebuild them.

This emits that table. Every value is READ FROM THE CODE, not transcribed:
geometry/material/impactor come from the `build_reduced_*` signature defaults
via `inspect`, and the realized rank and spectrum are read back from a built
solver. Transcribing them by hand is exactly how Table 1's modal rank came to
print the REQUESTED mode count instead of the delivered one (findings.md):
`reduced_scene_common.py:242` clamps the local-mode count to the number of
distinct contact zones, so `n_modes_global + n_modes_local` is a request, not a
rank.

Writes Markdown (for the supplement README) and LaTeX (if the table is ever
wanted in-paper; it does not fit the current page gate).

Out: out/{scene_spec.md, scene_spec.tex, scene_spec.csv}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/make_scene_spec.py
"""
from __future__ import annotations

import csv
import inspect
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# The table scene names its support `table_*` and its impactor `pot_*`; the
# shelf/ledge builders use `support_*`/`impactor_*`. Alias so one table covers
# all three rather than printing dashes for a scene that does have the value.
ALIASES = {
    "support_length": "table_length", "support_width": "table_width",
    "support_thickness": "table_thickness", "support_top": "table_top",
    "impactor_mass": "pot_mass", "impactor_drop_height": "pot_drop_height",
}

# (builder kwarg, printed label, unit, format)
FIELDS = [
    ("support_length",       "support length",        "m",     "{:.2f}"),
    ("support_width",        "support width",         "m",     "{:.2f}"),
    ("support_thickness",    "support thickness",     "m",     "{:.3f}"),
    ("support_top",          "support top height",    "m",     "{:.3f}"),
    ("youngs",               "Young's modulus E",     "Pa",    "{:.3g}"),
    ("density",              "density",               "kg/m^3", "{:.0f}"),
    ("poisson",              "Poisson ratio",         "-",     "{:.2f}"),
    ("impactor_mass",        "impactor mass",         "kg",    "{:.1f}"),
    ("impactor_drop_height", "impactor drop height",  "m",     "{:.2f}"),
    ("impactor_v0",          "impactor initial speed", "m/s",  "{:.1f}"),
    ("rayleigh_alpha0",      "Rayleigh alpha_0",      "1/s",   "{:.1f}"),
    ("rayleigh_alpha1",      "Rayleigh alpha_1",      "s",     "{:.1e}"),
    ("n_modes_global",       "global modes REQUESTED", "-",    "{:.0f}"),
    ("n_modes_local",        "local modes REQUESTED",  "-",    "{:.0f}"),
    ("h",                    "timestep h",            "s",     "{:.6f}"),
]


def defaults(fn) -> dict:
    sig = inspect.signature(fn)
    return {k: p.default for k, p in sig.parameters.items()
            if p.default is not inspect.Parameter.empty}


def realized(scene: str) -> dict:
    """Rank, spectrum and support-row count, read back from a built solver."""
    H = SCENES[scene](device="cpu", iterations=4, avbd_substeps=1, solver="xpbd")
    sol = H.world._solver
    kq = np.asarray(sol._kq, dtype=np.float64)
    mq = getattr(sol, "_mq", None)
    mqv = np.ones_like(kq) if mq is None else np.asarray(mq, dtype=np.float64)
    f = np.sort(np.sqrt(np.maximum(kq / np.where(mqv > 0, mqv, 1.0), 0.0))
                / (2 * np.pi))
    out = dict(rank_realized=int(f.size), f_min_Hz=float(f[0]),
               f_max_Hz=float(f[-1]), n_support_rows=len(sol._support),
               n_bodies=len(H.world._descs))
    if f.size > 1:
        ratios = f[1:] / np.maximum(f[:-1], 1e-30)
        j = int(np.argmax(ratios))
        if ratios[j] > max(6.0, 3.0 * float(np.median(ratios))):
            out["stiff_cluster_from_Hz"] = float(f[j + 1])
            out["n_stiff"] = int(f.size - j - 1)
        else:
            out["n_stiff"] = 0
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    names = ["shelf", "ledge", "dinner"]
    label = {"shelf": "shelf", "ledge": "ledge", "dinner": "table"}
    D = {n: defaults(SCENES[n]) for n in names}
    R = {n: realized(n) for n in names}

    rows = []
    for key, lab, unit, fmt in FIELDS:
        r = {"quantity": lab, "unit": unit}
        for n in names:
            v = D[n].get(key)
            if v is None and key in ALIASES:
                v = D[n].get(ALIASES[key])
            r[label[n]] = (fmt.format(v) if isinstance(v, (int, float)) else "--")
        rows.append(r)
    for key, lab, unit, fmt in [
        ("rank_realized",       "modal rank r REALIZED",  "-",  "{:.0f}"),
        ("n_stiff",             "  of which stiff cluster", "-", "{:.0f}"),
        ("f_min_Hz",            "lowest mode",            "Hz", "{:.1f}"),
        ("f_max_Hz",            "highest mode",           "Hz", "{:.0f}"),
        ("n_support_rows",      "support rows (eq. 1)",   "-",  "{:.0f}"),
        ("n_bodies",            "dynamic bodies",         "-",  "{:.0f}"),
    ]:
        r = {"quantity": lab, "unit": unit}
        for n in names:
            v = R[n].get(key)
            r[label[n]] = (fmt.format(v) if isinstance(v, (int, float)) else "--")
        rows.append(r)

    cols = ["quantity", "unit", "shelf", "ledge", "table"]
    with open(os.path.join(OUT, "scene_spec.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    md = ["| quantity | unit | shelf | ledge | table |",
          "|---|---|---|---|---|"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    md.append("")
    md.append("Seeds: none. The CPU path has no RNG; every run is "
              "bit-deterministic on a fixed machine (Apple M4, CPython 3.12).")
    md.append("")
    md.append("**REQUESTED vs REALIZED modes.** `n_modes_local` is clamped to "
              "the number of distinct contact zones "
              "(`scenes/reduced_scene_common.py:242`, deduped within 15 mm, "
              "because coincident bumps make Mq singular), so the delivered "
              "rank is smaller than `n_modes_global + n_modes_local` on the "
              "shelf and ledge. The paper's Table 1 prints the REALIZED rank.")
    open(os.path.join(OUT, "scene_spec.md"), "w").write("\n".join(md) + "\n")

    tex = [r"\begin{tabular}{@{}llrrr@{}}", r"\toprule",
           r"quantity & unit & shelf & ledge & table \\", r"\midrule"]
    for r in rows:
        tex.append(" & ".join(str(r[c]).replace("_", r"\_").replace("^", r"\^{}")
                              for c in cols) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}"]
    open(os.path.join(OUT, "scene_spec.tex"), "w").write("\n".join(tex) + "\n")

    print("\n".join(md))
    print(f"\nwrote {OUT}/scene_spec.{{md,tex,csv}}")


if __name__ == "__main__":
    main()
