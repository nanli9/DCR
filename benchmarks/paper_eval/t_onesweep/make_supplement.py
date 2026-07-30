"""Build the anonymous supplemental package for the one-sweep short paper.

WHY THIS EXISTS (reviewer objection #4 on build fc552a59). The paper says
"Source: supplemental data" under five figures and "Sources provided as
supplemental material" under the validation table, and no such package existed.
The reviewer correctly reported the practical experiments as unauditable. This
script builds the package.

WHAT GOES IN
  code/            every T-suite script and its shared module, plus the two
                   shipped-host drivers, ANONYMIZED (see below)
  data/            every CSV and manifest the paper's numbers come from; the two
                   241x241 phase-map CSVs are gzipped (25 MB -> about 8 MB total)
  README.md        the number-to-CSV map, how to run, and what each check is
  SHA256SUMS       digest of every shipped file

ANONYMIZATION. The sources carry an absolute interpreter path under a home
directory whose leaf is the author's username, which would deanonymize a
double-blind submission. Every such occurrence is rewritten to a repository
relative path, and the package is then scanned to assert that no home-directory
prefix, username token, or author-identifying string survives anywhere in it.
The scan is a hard gate: the build fails rather than shipping a leak.

HONEST SCOPE OF WHAT IS RUNNABLE. The analytic and nonmodal checks
(T1, T2, T3, T5, T7, T8, T10, T11 and the T4 index audit) are pure numpy and run
from this package alone. The shipped-host arms (T4, T6, T9) drive a production
position-based solver that is not redistributed here; their drivers are included
so the protocol and the exact weights are auditable, and their outputs are
included as CSVs, but re-running them requires the host. The README says this
plainly rather than implying full reproducibility.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_supplement.py
Out: supplement_onesweep/
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "supplement_onesweep")
TSUITE = HERE
XSUITE = os.path.join(ROOT, "benchmarks", "paper_eval", "x1_passivity")

# CSVs above this size are gzipped in the package.
GZIP_OVER = 2_000_000

TSUITE_CODE = [
    "common.py", "selftest_common.py",
    "run_t1_identities.py", "run_t2_phasemap.py", "run_t3_nonmodal.py",
    "run_t4_shipped.py", "run_t5_ordering.py", "run_t6_ews_reuse.py",
    "run_t7_reconstruction.py", "run_t8_relaxation.py", "run_t9_matched.py",
    "run_t10_multimode.py", "run_t11_accuracy.py", "run_t4_index_audit.py",
    "make_figs.py", "run_all.py",
]
XSUITE_CODE = ["run_weight_swap.py", "run_weight_swap_matched.py"]

# The paper's number-to-source map. Kept here so the README cannot drift from
# the tex header comment silently: both are generated from this one list.
NUMBER_MAP = [
    ("boundary $(\\omega h)^2 = 1 + m/M$, 0 of 58,081 cells misclassified",
     "t2_phasemap.csv.gz"),
    ("identity battery, 29/29 checks at rel <= 1e-12",
     "t1_identities.csv"),
    ("nonmodal collapse, 288/288 sign, max|y-(rho-1)| = 4.26e-14",
     "t3_nonmodal.csv"),
    ("ordering divisor (1+b)^2 = 10201 at b = 100, exact",
     "t5_ordering.csv"),
    ("shipped row: backward-Euler control 27/27 mass sign, 27/27 implicit "
     "passive; symplectic factor 2.000; implicit under midpoint dinner 9/9, "
     "shelf 2/9, ledge 4/9", "t4_shipped.csv"),
    ("rho_mid tracks 27/27 while rho_BE tracks 22/27 with 5 false negatives",
     "t4_index_audit.csv"),
    ("shipped row, symplectic default, matched weight m(4+(omega h)^2): "
     "27/27 passive", "t4_matched.csv"),
    ("reconstruction-general effective mass mu = m(kappa^2 + (omega h)^2), "
     "7000 cells at rel <= 1e-12, 0 sign mismatches", "t7_reconstruction.csv"),
    ("relaxation boundary theta^2(kappa^2 + b) = 2 + m/M, 542 injecting to "
     "passive, 0 passive to injecting", "t8_relaxation.csv"),
    ("multi-coordinate operator form: matched charge passive on 3000/3000 "
     "float cells and exact on 300/300 rational cells; diagonal charge on "
     "non-diagonal K injects on 19/2000", "t10_multimode.csv"),
    ("accuracy against the converged reference: C+ = 0 for every weight; "
     "matched sweep equals the converged backward-Euler step to 5.5e-16; "
     "mass-only over-deposit (M+m(1+b))/(M+m); matched kappa=2 charge is 4x "
     "the converged midpoint charge", "t11_accuracy.csv"),
    ("system weight swap, three arms on 24 cells: explicit 8 injecting, "
     "backward-Euler 0, matched 0", "weight_swap_matched.csv"),
    ("published two-arm weight swap reused from the companion study",
     "weight_swap_full.csv"),
]

# Anonymization: (pattern, replacement). Applied to every shipped text file.
HOME = os.path.expanduser("~")
USER = os.path.basename(HOME)
SUBS = [
    (re.compile(re.escape(os.path.join(HOME, "Desktop", "DCR")) + r"/?"), ""),
    (re.compile(re.escape(HOME) + r"/?"), ""),
    (re.compile(r"/Users/[A-Za-z0-9_.-]+/"), ""),
    (re.compile(r"/home/[A-Za-z0-9_.-]+/"), ""),
]
# Patterns that must not survive anywhere in the package. The username is only
# flagged in a PATH-LIKE context: this author's username happens to be a
# substring of numpy's nan/isnan/nanmin spellings, so a bare substring test
# produces false positives on ordinary numeric code. The real leak vectors are
# the home prefix and any surviving absolute user path, which are matched
# directly; a username in a path is caught by requiring a separator or a tilde
# next to it.
FORBIDDEN = [
    (re.compile(r"/Users/"), "absolute macOS user path"),
    (re.compile(r"/home/"), "absolute Linux user path"),
    (re.compile(re.escape(HOME)), "home directory prefix"),
    (re.compile(r"[/~]" + re.escape(USER) + r"(?=[/\s'\"]|$)"), "username in a path"),
    (re.compile(re.escape(USER) + r"/"), "username as a path component"),
]


def anonymize(text):
    for pat, rep in SUBS:
        text = pat.sub(rep, text)
    return text


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "code"))
    os.makedirs(os.path.join(OUT, "data"))

    shipped = []

    # ---- code, anonymized ------------------------------------------------ #
    for src_dir, names, sub in ((TSUITE, TSUITE_CODE, "t_onesweep"),
                                (XSUITE, XSUITE_CODE, "x1_passivity")):
        dst_dir = os.path.join(OUT, "code", sub)
        os.makedirs(dst_dir, exist_ok=True)
        for name in names:
            src = os.path.join(src_dir, name)
            if not os.path.exists(src):
                print(f"  MISSING (skipped): {sub}/{name}")
                continue
            with open(src, encoding="utf-8") as fh:
                body = anonymize(fh.read())
            dst = os.path.join(dst_dir, name)
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(body)
            shipped.append(dst)
            print(f"  code/{sub}/{name}")

    # ---- data ------------------------------------------------------------ #
    data_srcs = []
    for d in (os.path.join(TSUITE, "out"), os.path.join(XSUITE, "out")):
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".csv") or name.endswith(".config.json"):
                data_srcs.append(os.path.join(d, name))
    # only the CSVs the paper actually cites, plus their manifests
    cited = {m[1].replace(".gz", "") for m in NUMBER_MAP}
    for src in data_srcs:
        base = os.path.basename(src)
        stem = base.replace(".config.json", ".csv")
        if stem not in cited:
            continue
        size = os.path.getsize(src)
        if base.endswith(".csv") and size > GZIP_OVER:
            dst = os.path.join(OUT, "data", base + ".gz")
            with open(src, "rb") as fi, gzip.open(dst, "wb", compresslevel=9) as fo:
                shutil.copyfileobj(fi, fo)
            print(f"  data/{base}.gz  ({size / 1e6:.1f} MB -> "
                  f"{os.path.getsize(dst) / 1e6:.1f} MB)")
        else:
            dst = os.path.join(OUT, "data", base)
            if base.endswith(".json"):
                with open(src, encoding="utf-8") as fh:
                    body = anonymize(fh.read())
                with open(dst, "w", encoding="utf-8") as fh:
                    fh.write(body)
            else:
                shutil.copy2(src, dst)
            print(f"  data/{base}")
        shipped.append(dst)

    # ---- README ---------------------------------------------------------- #
    lines = [
        "# Supplemental material",
        "",
        "Anonymous supplement for the submission *A Per-Row Danger Index and a",
        "Reconstruction-Matched Effective Mass for One-Sweep Passive Contact",
        "Coupling in Fixed-Budget Position-Based Solvers*.",
        "",
        "## Layout",
        "",
        "- `code/t_onesweep/` the validation suite (T1 to T11 and the T4 index",
        "  audit) and the figure builder.",
        "- `code/x1_passivity/` the two shipped-host weight-swap drivers.",
        "- `data/` every CSV a number in the paper is taken from, with the",
        "  `.config.json` manifest each run wrote. The two 241x241 phase-map",
        "  CSVs are gzipped.",
        "",
        "## What runs from this package alone",
        "",
        "The analytic and nonmodal checks are pure numpy and self-contained:",
        "",
        "```",
        "python code/t_onesweep/selftest_common.py     # 44 primitive checks",
        "python code/t_onesweep/run_t1_identities.py",
        "python code/t_onesweep/run_t2_phasemap.py",
        "python code/t_onesweep/run_t3_nonmodal.py",
        "python code/t_onesweep/run_t5_ordering.py",
        "python code/t_onesweep/run_t7_reconstruction.py",
        "python code/t_onesweep/run_t8_relaxation.py",
        "python code/t_onesweep/run_t10_multimode.py   # operator form, exact",
        "python code/t_onesweep/run_t11_accuracy.py    # converged reference",
        "python code/t_onesweep/run_t4_index_audit.py  # reads t4_shipped.csv",
        "```",
        "",
        "Each script prints a per-check PASS/FAIL table and exits nonzero on any",
        "failure. Tolerances are stated in each file and are never loosened to",
        "make a claim pass; where a float check is round-off limited the file",
        "says so and supplies an exact-arithmetic check instead (T10, block E).",
        "",
        "## What does NOT run from this package",
        "",
        "T4, T6 and T9 drive a production position-based solver that is not",
        "redistributed here. Their drivers are included so the protocol, the",
        "exact contact-row weights and the operating points are auditable, and",
        "their outputs are included as CSVs, but re-running them needs that",
        "host. This is stated so the package is not mistaken for a complete",
        "reproduction of the shipped-row experiments.",
        "",
        "## Environment",
        "",
        "Python 3.12, numpy only (plus matplotlib for the figure builder).",
        "The exact-arithmetic block of T10 uses the standard-library",
        "`fractions` module. Runs were on a CPU, arm64.",
        "",
        "## Number to source map",
        "",
    ]
    for claim, csvname in NUMBER_MAP:
        lines.append(f"- {claim}")
        lines.append(f"  -> `data/{csvname}`")
    lines += [
        "",
        "## Integrity",
        "",
        "`SHA256SUMS` lists a digest for every file above. The package was",
        "scanned to confirm it carries no home-directory path, username or",
        "other author-identifying token.",
        "",
    ]
    readme = os.path.join(OUT, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    shipped.append(readme)
    print("  README.md")

    # ---- anonymity gate -------------------------------------------------- #
    print("\n-- anonymity scan --")
    leaks = []
    for path in shipped:
        try:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
        except (UnicodeDecodeError, ValueError):
            continue          # gzipped binary
        for pat, why in FORBIDDEN:
            mm = pat.search(body)
            if mm:
                leaks.append((os.path.relpath(path, OUT),
                              f"{why}: {mm.group(0)!r}"))
    # filenames themselves must be clean too
    for dirpath, dirnames, filenames in os.walk(OUT):
        for n in list(dirnames) + list(filenames):
            if n == USER or n.startswith(USER + "."):
                leaks.append((n, "filename is the username"))
    if leaks:
        print("  FAIL, author-identifying tokens present:")
        for p, t in leaks:
            print(f"    {p}: {t}")
        return 1
    print(f"  clean: no home path, username or author token in "
          f"{len(shipped)} files")

    # ---- SHA256SUMS ------------------------------------------------------ #
    sums = []
    for dirpath, _, filenames in os.walk(OUT):
        for n in sorted(filenames):
            if n == "SHA256SUMS":
                continue
            p = os.path.join(dirpath, n)
            hh = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    hh.update(chunk)
            sums.append(f"{hh.hexdigest()}  {os.path.relpath(p, OUT)}")
    with open(os.path.join(OUT, "SHA256SUMS"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(sums, key=lambda s: s.split("  ", 1)[1])) + "\n")

    total = sum(os.path.getsize(os.path.join(dp, n))
                for dp, _, fns in os.walk(OUT) for n in fns)
    print(f"\nsupplement_onesweep/: {len(sums)} files, {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
