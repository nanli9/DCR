#!/usr/bin/env python3
"""Complete and package the anonymous supplement for the one-sweep short paper.

WHY THIS EXISTS (panel item C, 2026-07-29). Both six-reviewer panels scored the
missing supplementary artifact as a weakness. The package on disk was built
2026-07-28 19:30, BEFORE the T14 evidence and the cost measurements landed in
the paper (PDF 22:39), so it does not carry what the paper now cites BY NAME:

  MISSING CODE   run_t14_passive_family.py, run_t14_equalcost.py,
                 run_t14_warm_multirow.py, run_tcost.py,
                 x1_passivity/run_weight_swap_energy.py, make_figs_singlecol.py
  MISSING DATA   t14_passive_family.csv, t14_equalcost.csv,
                 t14_equalcost_summary.csv, t14_warm_multirow.csv,
                 tcost_shipped.csv, tcost_kernels.csv, tcost_charges.csv,
                 tcost_stability.csv, t6_ews_corroboration.csv,
                 weight_swap_energy.csv

The last two are older gaps, not T14 fallout: the base builder ships only the
CSVs listed in its own NUMBER_MAP, and neither the T6 corroboration output nor
the total-energy readout was ever in that list, although the paper prints
numbers from both ("8/24 -> 0/24" and "10, 1 and 0 of 24").

EDITS NO EXISTING HARNESS FILE. It imports make_supplement_full.py (which
imports make_supplement_extras.py, which imports make_supplement.py), extends
that file's declared TSCRIPTS table in memory, and adds the handful of artifacts
that table cannot express (a second code directory, a figure builder, data-only
rows). Every existing gate runs verbatim.

WHAT IT ADDS ON TOP OF make_supplement_full.py

  1. Five registered T-suite rows (four new scripts plus the T6 output whose
     driver already shipped without its CSV), one optional row that activates
     only when the mass-arm warm baseline lands.
  2. The third shipped-host driver and its CSV under code/x1_passivity/.
  3. The single-column figure builder the paper names, and the row-index figure
     repair scripts when they exist.
  4. A HARDER anonymity gate: make_supplement.py's path patterns plus author
     name, institutional address, and code-host URL patterns.
  5. A COMPLETENESS gate the previous builders had no equivalent of: every
     `*.csv` and every `run_*.py` named anywhere in paper/onesweep_short.tex
     must be present in the package, or the build fails and writes nothing.
     This is what would have caught the 2026-07-28 drift automatically.
  6. The EasyChair archive, written next to the paper as well as at the
     repository root, with its size reported.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_supplement_r8.py
     ... --no-verify     skip the clean-copy re-run of every analytic check
     ... --no-zip        build and gate only, do not write the archive
Out: supplement_onesweep/, supplement_onesweep.zip, paper/supplement_onesweep.zip
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import make_supplement as MS                    # noqa: E402
import make_supplement_full as MSF              # noqa: E402

TS = MSF.TS
OUT = MSF.OUT
ROOT = MSF.ROOT
TSUITE = MSF.TSUITE
XSUITE = MS.XSUITE
PAPER_TEX = os.path.join(ROOT, "paper", "onesweep_short.tex")


# --------------------------------------------------------------------------- #
# 1. T-suite rows appended to make_supplement_full.TSCRIPTS                    #
# --------------------------------------------------------------------------- #
NEW_TSCRIPTS = [
    TS("run_t14_passive_family.py", ["t14_passive_family"],
       "passive family (Cor. 3.4, Table 1 row T14a): W = c G^-1 telescopes "
       "Eq. (6) to dE = (v^2/2D^2)[c(c-2) a - w_r - 2 a_tilde], so exactly "
       "c in [0,2] is passive; 2500 randomized symmetric charges each met with "
       "an adversarial row, all 1222 inside the Loewner interval passive and "
       "all 1278 outside injecting; 720 exact-rational cells with the closed "
       "form and the sign law as equalities of rationals; the far endpoint "
       "c = 2 returns the converged amplitude to 2e-16, cross-checked against "
       "the shipped t11_accuracy.csv columns; c = 1 keeps at least 100% "
       "headroom to the injection threshold on all 4000 margin cells (median "
       "171%) while c = 2 is under 1% on 0.20825 of them (median 36%)",
       reads=["t11_accuracy.csv"],
       run_note="  # T14a; reads out/t11_accuracy.csv"),
    TS("run_t14_warm_multirow.py", ["t14_warm_multirow"],
       "warm and two-row boundary (Table 1 row T14c; measurement only, nothing "
       "here is a theorem): the warm instrument matches the simulated sweep to "
       "6.8e-15 relative on 13,050 cells and reduces to Eq. (6) cold; the "
       "mass-only index calls safe a row that injects on 2795 of 43,783 warm "
       "and two-row cells; the matched charge still injects on 4099 of 43,898; "
       "order alone flips 734 signs over 8095 two-row cells; the shipped "
       "kappa = 2 midpoint pairing is clean, 0 false negatives and 0 false "
       "positives of 4104 active cells; the cold control misclassifies 0 of "
       "4800; resting contact stays secularly bounded over 20,000 substeps",
       run_note="  # T14c"),
    TS("run_t14_equalcost.py", ["t14_equalcost", "t14_equalcost_summary"],
       "equal cost (Table 1 row T14b) on the same 27 shipped cells as T4 and "
       "T9: the mass-only weight injects on 22, 17, 9, 6 and 2 cells at 1, 2, "
       "4, 8 and 16 iterations, the last still overshooting one cell by 28.3 "
       "times its incoming kinetic energy, while the matched weight injects on "
       "0 at one iteration for 1.004 times the substep cost; median returned "
       "amplitude 0.567 (matched, one iteration) against 0.853 (mass-only, 16 "
       "iterations), the 64-iteration converged step being 1.0 at 20.5 times "
       "the cost. Ratios only; absolute microseconds are never quoted",
       runnable=False),
    TS("run_tcost.py",
       ["tcost_shipped", "tcost_kernels", "tcost_charges", "tcost_stability"],
       "cost: the matched weight runs at 0.99231 to 1.01753 times the "
       "mass-only default on the shipped rows (3 scenes x 5 trials, r = 16, 16 "
       "and 24 modes), and a dense G^-1 row costs 6.812 to 14.481 times the "
       "diagonal accumulation for r = 4 to 64 (8 timing blocks x 1000 rows). "
       "Ratios measured between two costs on one host; the absolute "
       "microseconds are a numpy reference implementation and are not "
       "production representative, as the manifests state",
       runnable=False),
    TS("run_t6_ews_reuse.py", ["t6_ews_corroboration"],
       "system-level corroboration of the boundary on the frozen 24-cell "
       "weight swap (no rerun; reads weight_swap_full.csv READ-ONLY): 8 "
       "injecting cells under the explicit mass-only weight against 0 under "
       "the implicit one, the explicit arm bit-faithful to the frozen baseline "
       "below 1e-6, and the logged inverse mobility matching 1 + (omega h)^2 "
       "within 5% on every row",
       runnable=False),
]

# Activates only when the artifact exists, so item J's mass-arm baseline needs
# no edit here: land the script and its CSV, re-run this builder.
OPTIONAL_TSCRIPTS = [
    TS("run_t14_massarm_baseline.py", ["t14_massarm_baseline"],
       "mass-only weight on the warm and two-row cells: the injection count "
       "of the weight itself, on the same deterministic populations as "
       "run_t14_warm_multirow.py, so the index-miss count and the injection "
       "count are reported on stated denominators",
       run_note="  # mass-arm warm baseline"),
]


# --------------------------------------------------------------------------- #
# 2-3. Artifacts the TSCRIPTS table cannot express                            #
# --------------------------------------------------------------------------- #
# (source dir, filename, destination subdir under code/)
EXTRA_CODE = [
    (XSUITE, "run_weight_swap_energy.py", "x1_passivity", True),
    (TSUITE, "make_figs_singlecol.py", "t_onesweep", True),
    (TSUITE, "fix_rowindex_legend.py", "t_onesweep", False),
    (TSUITE, "make_rowindex_r8.py", "t_onesweep", False),
]

# (source out/ dir, csv stem, README claim); the .config.json rides along.
EXTRA_DATA = [
    (XSUITE, "weight_swap_energy",
     "per-substep TOTAL mechanical energy on the same 24-cell grid, i.e. the "
     "theorem's own E+ > E- sign rather than the modal ratio: 10 of 24 cells "
     "above the window start under the explicit weight, 1 of 24 under "
     "backward-Euler (that one at 1.2e-5 of the impactor kinetic energy) and 0 "
     "of 24 matched; the position-based update's ballistic drift makes those "
     "counts lower bounds"),
]

# Files already gzipped at the source, copied byte for byte. Optional rows are
# skipped silently when absent so a companion artifact can land later.
EXTRA_RAW = [
    (TSUITE, "t14_massarm_baseline_cells.csv.gz", False,
     "per-cell dump behind the mass-arm baseline summary: one row per warm or "
     "two-row cell with its measured sign, so the counts can be recomputed "
     "rather than taken on trust"),
]

# Build tools and figure builders: named in the paper's header comments as
# provenance for how an artifact was made, not as evidence a number rests on.
# The completeness gate does not require them inside the package.
NOT_EVIDENCE = {
    "make_supplement.py", "make_supplement_extras.py", "make_supplement_full.py",
    "make_supplement_r8.py", "make_figs.py", "make_figs_singlecol.py",
    "make_rowindex_r8.py", "fix_rowindex_legend.py", "run_all.py",
}

# CSV stems the paper names but that are inputs to, or intermediates of, a
# shipped artifact rather than files of their own. Empty by design: every
# exemption here is a hole in the audit trail and must be argued for.
DATA_EXEMPT: set = set()


# --------------------------------------------------------------------------- #
# 4. Harder anonymity gate                                                    #
# --------------------------------------------------------------------------- #
# make_supplement.FORBIDDEN covers absolute user paths and the username in a
# path. Double-blind review needs more than paths: a name in a docstring, an
# institutional address in a manifest, or a code-host URL in a comment
# deanonymizes just as completely. Case-sensitive where a case-insensitive form
# would collide with ordinary numeric code (the author's username is a
# substring of numpy's nan spellings).
EXTRA_FORBIDDEN = [
    (re.compile(r"\bNan\b"), "author given name"),
    (re.compile(r"nli\d+"), "author account identifier"),
    (re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}"), "email address"),
    (re.compile(r"\busc\.edu\b", re.I), "institutional domain"),
    (re.compile(r"\b(github|gitlab|bitbucket)\.(com|org|io)\b", re.I), "code-host URL"),
    (re.compile(r"\bcompshare\b", re.I), "named remote machine"),
    (re.compile(r"Desktop/DCR"), "author working-directory name"),
]


# --------------------------------------------------------------------------- #
def _anon_copy(src, dst):
    with open(src, encoding="utf-8") as fh:
        body = MS.anonymize(fh.read())
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(body)


def add_extra_code():
    """Ship EXTRA_CODE. Required rows abort the build when absent."""
    for src_dir, name, sub, required in EXTRA_CODE:
        src = os.path.join(src_dir, name)
        if not os.path.exists(src):
            if required:
                print("  MISSING (abort): %s" % name)
                return None
            print("  skipped (not present): %s" % name)
            continue
        _anon_copy(src, os.path.join(OUT, "code", sub, name))
        print("  code/%s/%s" % (sub, name))
    return True


def add_extra_data():
    """Ship EXTRA_DATA: a CSV plus the manifest its run wrote."""
    for src_dir, stem, _claim in EXTRA_DATA:
        csv_src = os.path.join(src_dir, "out", stem + ".csv")
        if not os.path.exists(csv_src):
            print("  MISSING (abort): %s/out/%s.csv" % (os.path.basename(src_dir), stem))
            return None
        size = os.path.getsize(csv_src)
        if size > MS.GZIP_OVER:
            import gzip
            dst = os.path.join(OUT, "data", stem + ".csv.gz")
            with open(csv_src, "rb") as fi, gzip.open(dst, "wb", compresslevel=9) as fo:
                shutil.copyfileobj(fi, fo)
            print("  data/%s.csv.gz" % stem)
        else:
            shutil.copy2(csv_src, os.path.join(OUT, "data", stem + ".csv"))
            print("  data/%s.csv" % stem)
        man = os.path.join(src_dir, "out", stem + ".config.json")
        if os.path.exists(man):
            _anon_copy(man, os.path.join(OUT, "data", stem + ".config.json"))
            print("  data/%s.config.json" % stem)

    for src_dir, name, required, _claim in EXTRA_RAW:
        src = os.path.join(src_dir, "out", name)
        if not os.path.exists(src):
            if required:
                print("  MISSING (abort): out/%s" % name)
                return None
            print("  skipped (not present): %s" % name)
            continue
        shutil.copy2(src, os.path.join(OUT, "data", name))
        print("  data/%s" % name)
    return True


# --------------------------------------------------------------------------- #
# README patches on top of make_supplement_full.patch_readme                  #
# --------------------------------------------------------------------------- #
README_EDITS = [
    ("the validation suite (T1 to T13 and the T4 index",
     "the validation suite (T1 to T14 and the T4 index",
     "layout: T-range"),
    ("- `code/x1_passivity/` the two shipped-host weight-swap drivers.",
     "- `code/x1_passivity/` the three shipped-host weight-swap drivers.",
     "layout: driver count"),
    ("T4, T6 and T9 drive a production position-based solver that is not\n"
     "redistributed here. Their drivers are included so the protocol, the\n"
     "exact contact-row weights and the operating points are auditable, and\n"
     "their outputs are included as CSVs, but re-running them needs that\n"
     "host. This is stated so the package is not mistaken for a complete\n"
     "reproduction of the shipped-row experiments.",
     "T4, T6, T9, the equal-cost arm T14b and the cost measurements drive a\n"
     "production position-based solver that is not redistributed here. Their\n"
     "drivers are included so the protocol, the exact contact-row weights and\n"
     "the operating points are auditable, and their outputs are included as\n"
     "CSVs, but re-running them needs that host. This is stated so the package\n"
     "is not mistaken for a complete reproduction of the shipped-row\n"
     "experiments.",
     "not-runnable list"),
    ("  `.config.json` manifest each run wrote. CSVs over 2 MB ship\n"
     "  gzipped, which here is the 241x241 phase map and the T13\n"
     "  ordering sweep.",
     "  `.config.json` manifest each run wrote. CSVs over 2 MB ship\n"
     "  gzipped, which here is the 241x241 phase map and the T13\n"
     "  ordering sweep; the mass-arm per-cell dump ships gzipped as its\n"
     "  own harness wrote it.",
     "layout: gzip sentence"),
]


def extra_readme_map():
    out = "".join("- %s\n  -> `data/%s.csv`\n" % (claim, stem)
                  for _d, stem, claim in EXTRA_DATA)
    out += "".join(
        "- %s\n  -> `data/%s`\n" % (claim, name)
        for d, name, _req, claim in EXTRA_RAW
        if os.path.exists(os.path.join(OUT, "data", name)))
    return out


def patch_readme_r8():
    """make_supplement_full's README patch, then this pass's corrections."""
    if MSF._patch_readme_orig() is None:
        return None
    path = os.path.join(OUT, "README.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for old, new, what in README_EDITS:
        if old not in text:
            print("  README %s anchor not found; refusing to guess" % what)
            return None
        text = text.replace(old, new, 1)
        print("  README %s" % what)
    marker = "\n## Scene parameters\n"
    if marker not in text:
        marker = "\n## Integrity\n"
    if marker not in text:
        print("  README number-map end not found; refusing to guess")
        return None
    text = text.replace(marker, extra_readme_map() + marker, 1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("  README number map (%d data-only entries)" % len(EXTRA_DATA))
    return [path]


def seed_inputs_r8():
    """make_supplement_full's frozen-input seeding, then this pass's files."""
    if MSF._seed_inputs_orig() is None:
        return None
    print("\n== extra code ==")
    if add_extra_code() is None:
        return None
    print("\n== extra data ==")
    if add_extra_data() is None:
        return None
    return True


# --------------------------------------------------------------------------- #
# 5. Completeness gate: the package against what the paper promises           #
# --------------------------------------------------------------------------- #
def completeness():
    """Every CSV and every run_*.py the .tex names must be in the package.

    The paper is the specification. This reads it at build time, so a number
    added to the body tomorrow fails this gate tomorrow rather than shipping an
    unauditable claim, which is exactly the 2026-07-28 drift.
    """
    if not os.path.exists(PAPER_TEX):
        return ["paper source not found: %s" % PAPER_TEX]

    with open(PAPER_TEX, encoding="utf-8") as fh:
        tex = fh.read()

    want_csv = sorted(set(re.findall(r"\b([a-z0-9_]+\.csv)", tex)) - DATA_EXEMPT)
    want_py = sorted(set(re.findall(r"\b((?:run|make|dump|selftest|fix)_[a-z0-9_]+\.py)",
                                    tex)) - NOT_EVIDENCE)

    have_data = set(os.listdir(os.path.join(OUT, "data")))
    have_code = set()
    for dirpath, _, filenames in os.walk(os.path.join(OUT, "code")):
        have_code.update(filenames)

    missing = []
    for name in want_csv:
        if name not in have_data and name + ".gz" not in have_data:
            missing.append("data/%s  (cited in the paper, absent)" % name)
    for name in want_py:
        if name not in have_code:
            missing.append("code/**/%s  (cited in the paper, absent)" % name)

    print("  paper cites %d CSVs and %d evidence scripts" % (len(want_csv), len(want_py)))
    if not missing:
        print("  every one is in the package")
    return missing


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the clean-copy re-run of every analytic check")
    ap.add_argument("--no-zip", action="store_true",
                    help="build and gate only; write no archive")
    args = ap.parse_args()

    # ---- register everything before the base builder runs ---------------- #
    for row in NEW_TSCRIPTS:
        MSF.TSCRIPTS.append(row)
    for row in OPTIONAL_TSCRIPTS:
        code_ok = os.path.exists(os.path.join(TSUITE, row.code))
        data_ok = all(os.path.exists(os.path.join(TSUITE, "out", s + ".csv"))
                      for s in row.data)
        if code_ok and data_ok:
            MSF.TSCRIPTS.append(row)
            print("optional row ACTIVE: %s" % row.code)
        else:
            print("optional row inactive (not on disk yet): %s  "
                  "[re-run this builder once it lands]" % row.code)

    MS.FORBIDDEN = list(MS.FORBIDDEN) + EXTRA_FORBIDDEN
    MSF._seed_inputs_orig = MSF.seed_inputs
    MSF.seed_inputs = seed_inputs_r8
    MSF._patch_readme_orig = MSF.patch_readme
    MSF.patch_readme = patch_readme_r8

    argv = ["make_supplement_full.py"] + (["--no-verify"] if args.no_verify else [])
    saved, sys.argv = sys.argv, argv
    try:
        rc = MSF.main()
    finally:
        sys.argv = saved
    if rc != 0:
        print("\nbase build failed (rc=%d); nothing packaged" % rc)
        return rc

    print("\n-- completeness gate (package vs paper/onesweep_short.tex) --")
    missing = completeness()
    if missing:
        print("  FAIL, the paper cites artifacts the package does not carry:")
        for m in missing:
            print("    %s" % m)
        return 4

    # SHA256SUMS was written before the completeness gate; the gate reads only.
    if args.no_zip:
        print("\n--no-zip: archive not written")
        return 0

    archive, size = MSF.make_zip()
    beside = os.path.join(ROOT, "paper", os.path.basename(archive))
    shutil.copy2(archive, beside)
    print("\narchive: %s  (%d bytes, %.2f MB)" % (archive, size, size / 1e6))
    print("beside the paper: %s" % beside)
    return 0


if __name__ == "__main__":
    sys.exit(main())
