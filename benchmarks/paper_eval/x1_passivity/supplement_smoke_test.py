#!/usr/bin/env python3
"""Clean-unpack smoke test for the supplementary bundle (plan §9.3.d).

Ships in the bundle as `smoke_test.py`. From a freshly unpacked
`code_snapshot.zip` it builds one scene from source and re-derives one cell of
the paper's 24-cell sweep on all three hosts, which is the paper's central
contrast in miniature:

    shelf drop, budget 4x1, modal relaxation 0.7, governor OFF

    position-based (XPBD)      violates the cumulative bound by ~1.7e5 J
    augmented-Lagrangian       does not, at this cell
    implicit sequential impulse does not

ASSERTIONS ARE QUALITATIVE ON PURPOSE. The printed digits are exact on arm64
(Apple silicon) and are expected to differ on x86-64: chaotic contact stacks
diverge across architectures under floating-point reassociation, which is why
the paper reports a single machine. So this checks the direction and the order
of magnitude, and prints the digits for comparison against the reference values
recorded below and in `data/solver_matrix.csv`.

What it does NOT check: the whole matrix, the iteration sweep, or any printed
number of §3.3-§3.5. Those are re-verified by
`benchmarks/paper_eval/verify_paper_numbers.py` (CSV reads, no simulation) and
by the `--check-frozen` paths named in `CLAIMS_INDEX.md`.

Run (from the bundle root, after unpacking the snapshot):
    python smoke_test.py
Exit status 0 = pass, 1 = fail, 2 = the snapshot could not be located.
"""
from __future__ import annotations

import os
import sys
import zipfile

# Frozen reference values, arm64 / Apple M4 / CPython 3.12 / float64.
# Source: data/solver_matrix.csv and data/eq2_utilization.csv, rows
# (solver, shelf, relax 0.7, 4 iterations, 1 substep).
REFERENCE = {
    "xpbd":    dict(R=6333.221296009669, violates=True,  margin_J=1.737997e5),
    "avbd":    dict(R=0.502239,          violates=False, margin_J=-2.053e-3),
    "impulse": dict(R=0.273496,          violates=False, margin_J=-3.676e-2),
}


def locate_snapshot() -> str:
    """Return a directory containing `dcr/`, unpacking the zip if needed."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "code_snapshot"), here,
                 os.path.dirname(here)):
        if os.path.isdir(os.path.join(cand, "dcr")):
            return cand
    zpath = os.path.join(here, "code_snapshot.zip")
    if os.path.isfile(zpath):
        dest = os.path.join(here, "code_snapshot")
        print(f"unpacking {os.path.basename(zpath)} -> {dest}/")
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(dest)
        if os.path.isdir(os.path.join(dest, "dcr")):
            return dest
    sys.stderr.write(
        "could not find the source snapshot: expected `code_snapshot/dcr/` or "
        "`code_snapshot.zip` next to this script\n")
    raise SystemExit(2)


def main() -> int:
    root = locate_snapshot()
    sys.path.insert(0, root)
    print(f"snapshot: {root}")

    from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES
    from benchmarks.paper_eval.x1_passivity.run_eq2_utilization import one

    # (1) Build one scene from source and check its structure against Table 1.
    H = SCENES["shelf"](device="cpu", iterations=4, avbd_substeps=1,
                        solver="xpbd")
    sol = H.world._solver
    rank, rows = len(sol._kq), len(sol._support)
    print(f"\nscene: shelf, modal rank r = {rank}, support rows = {rows}"
          f"   (Table 1: 16 and 48)")

    fails: list[str] = []
    if rank != 16:
        fails.append(f"modal rank {rank}, expected 16 (Table 1)")
    if rows != 48:
        fails.append(f"support rows {rows}, expected 48 (§2)")

    # (2) Re-derive the cell on all three hosts, governor OFF.
    print("\nshelf 4x1, relaxation 0.7, governor OFF"
          "   (reference: arm64 / Apple M4)")
    print(f"  {'host':<9} {'R':>14} {'violates':>9} {'margin [J]':>14}"
          f"   {'reference R':>14}")
    got = {}
    for host in ("xpbd", "avbd", "impulse"):
        r = one(SCENES["shelf"], host, 4, 1, 0.7)
        got[host] = r
        print(f"  {host:<9} {r['ratio_off']:>14.6g} "
              f"{str(r['eq2_violates']):>9} {r['margin_J']:>14.6g}"
              f"   {REFERENCE[host]['R']:>14.6g}")

    # (3) Qualitative assertions -- see the module docstring.
    for host, want in REFERENCE.items():
        if bool(got[host]["eq2_violates"]) != want["violates"]:
            fails.append(f"{host}: Eq. (2) violation flag is "
                         f"{got[host]['eq2_violates']}, expected "
                         f"{want['violates']}")

    R = got["xpbd"]["ratio_off"]
    if not 1e3 <= R <= 1e4:
        fails.append(f"xpbd R = {R:.4g}, expected the same order of magnitude "
                     f"as the frozen {REFERENCE['xpbd']['R']:.6g}")
    if got["xpbd"]["margin_J"] <= 1e4:
        fails.append(f"xpbd overdraw {got['xpbd']['margin_J']:.4g} J, expected "
                     f"> 1e4 J (frozen {REFERENCE['xpbd']['margin_J']:.4g})")
    for host in ("avbd", "impulse"):
        if got[host]["ratio_off"] >= 1.0:
            fails.append(f"{host}: R = {got[host]['ratio_off']:.4g}, expected "
                         f"< 1 at this cell")
        if got[host]["margin_J"] >= 0.0:
            fails.append(f"{host}: margin {got[host]['margin_J']:.4g} J, "
                         f"expected negative (no overdraw) at this cell")

    exact = abs(R - REFERENCE["xpbd"]["R"]) < 1e-6 * REFERENCE["xpbd"]["R"]
    if exact:
        print("\ndigits match the arm64 reference exactly")
    else:
        print("\ndigits DIFFER from the arm64 reference -- expected off "
              "arm64;\nthe assertions below are the portable result")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL {f}")
        print(f"\nsmoke test FAILED ({len(fails)} check(s))")
        return 1
    print("  ok   one scene built from source, structure matches Table 1")
    print("  ok   the position-based host overdraws the cumulative bound "
          "by >1e4 J")
    print("  ok   the other two hosts do not, at this cell")
    print("\nsmoke test PASSED")
    print("\nScope: one cell of 24. The paper's matrix-level counts (8/24, "
          "23/24, 0/24)\nare in data/solver_matrix.csv and "
          "data/eq2_utilization.csv; the augmented-\nLagrangian host does "
          "violate in 23 of 24 cells, but not at this one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
