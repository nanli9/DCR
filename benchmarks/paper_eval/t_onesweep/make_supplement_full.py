#!/usr/bin/env python3
"""Build the COMPLETE anonymous supplement for the one-sweep short paper (NEW).

WHY THIS EXISTS (2026-07-28 six-reviewer panel). Two defects in the shipped
packet:

  1. COVERAGE. `make_supplement.py`'s TSUITE_CODE stops at T11, so
     `run_t12_hypotheses.py` and `run_t13_ordering_kappa.py` and their CSVs were
     never shipped. The paper meanwhile cites T13 by name in a rendered Table 1
     row and in Sec. 4, and rests Rmk. 3.5's kappa_r split and the
     kappa in [1/2, 2] range on T12 alone. Both were unauditable.

  2. THE PACKAGE DID NOT RUN AT ALL. Every T-suite source opens with
         from benchmarks.paper_eval.t_onesweep import common as C
     and `common.write_csv` lazily imports `benchmarks.paper_eval.paper_config`.
     Neither module name exists inside the package, whose layout is
     `code/t_onesweep/`. On the author's machine the checks appear to pass only
     because the development virtualenv carries an editable-install `.pth` that
     silently puts the whole repository on sys.path. Scrub that one entry and
     all ten "self-contained" checks die with
         ModuleNotFoundError: No module named 'benchmarks'
     before executing a single line. The README's "pure numpy and
     self-contained" was false for a reviewer. This script ships a three-file
     import shim that makes the two module names resolve inside the package, and
     then PROVES the claim by re-running every runnable check from a clean copy
     with the repository removed from sys.path (`--verify`, on by default).

EDITS NO EXISTING HARNESS FILE. It imports `make_supplement_extras.py` (which
imports and runs `make_supplement.py`), so the base package and both existing
anonymity gates run verbatim, and then adds on top. Everything this pass adds is
declared in ONE table, TSCRIPTS, below.

REGISTERING A NEW T-SCRIPT IS ONE LINE. Append one `TS(...)` row to TSCRIPTS.
The row carries the source filename, its CSV stems (the matching
`.config.json` is picked up automatically), whether the check runs without the
production host, any frozen CSV it reads as input, and the README number-map
sentence. Nothing else in this file changes.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_supplement_full.py
     .venv/bin/python .../make_supplement_full.py --no-verify   (skip the re-run)
     .venv/bin/python .../make_supplement_full.py --zip         (also emit the
                                                                 EasyChair archive)
Out: supplement_onesweep/  (+ supplement_onesweep.zip with --zip)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import make_supplement as MS                    # noqa: E402
import make_supplement_extras as MSX            # noqa: E402

OUT = MS.OUT
ROOT = MS.ROOT
TSUITE = MS.TSUITE
PAPER_EVAL = os.path.join(ROOT, "benchmarks", "paper_eval")


# --------------------------------------------------------------------------- #
# THE ONE TABLE. One row per T-script added on top of the base package.        #
# --------------------------------------------------------------------------- #
@dataclass
class TS:
    """One T-suite script and everything the package needs to carry for it."""
    code: str                       # filename in benchmarks/paper_eval/t_onesweep/
    data: list                      # CSV stems in out/ (.config.json auto-added)
    claim: str                      # README number-to-source sentence
    runnable: bool = True           # True: runs from the package, no host needed
    reads: list = field(default_factory=list)   # frozen CSVs it reads as INPUT
    run_note: str = ""              # trailing comment on the README run line


TSCRIPTS = [
    TS("run_t12_hypotheses.py", ["t12_hypotheses"],
       "hypothesis pinning: the reconstruction-split dE at rel 5.5e-14 on 9000 "
       "cells; the mass-only boundary kappa^2 + b = 2 kappa_r + "
       "kappa_r(2-kappa_r) m/M with 0 of 4000 misclassified at each of five "
       "(kappa_r, kappa); the matched charge passive for every kappa at "
       "kappa_r = 1 and, under kappa_r = kappa, passive at every mass ratio iff "
       "kappa in [1/2, 2]; the over-deposit factor 1 + b m/(M+m); the damped "
       "amplitude gap 2 zeta omega h/(1 + M/m + b); the kappa = 2 reproducing "
       "charge mu* = m(2 + b/2); kappa = 1 exactness requiring zeta = 0. "
       "28/28 checks"),
    TS("run_t13_ordering_kappa.py", ["t13_ordering_kappa"],
       "reconstruction-general ordering: D_B/D_A = (1+b)^2 at every kappa; "
       "trailing-spring injection iff (kappa^2+b)/(1+b)^2 > 2 + m/M, so 0 of "
       "10,000 cells at kappa = 1 and 3840 of 10,000 at kappa = 2; failure band "
       "m/M < kappa^2 - 2 with edge b* = (sqrt(37)-5)/6 = 0.18046 at m = M; peak "
       "deposit (kappa^2-2)^2/[4(kappa^2-1)]. 56/56 checks, 40,705 rows, "
       "bit-identical to run_t5_ordering.py and to the shipped t5_ordering.csv "
       "at kappa = 1",
       reads=["t5_ordering.csv"],
       run_note="  # reads out/t5_ordering.csv"),
]
# ^^ TO REGISTER A NEW T-SCRIPT, APPEND ONE ROW HERE. Nothing else changes. ^^


@dataclass
class EX:
    """One verbatim source excerpt from the production host.

    The paper's header comment lists the solver's velocity-update block as
    "shipped in the supplement" and reads the paper's single most load-bearing
    empirical premise off it: that the shipped host recovers rigid velocity at
    kappa_r = 1 and commits the mode at kappa = 2, so every shipped-row result
    is the mixed (1, 2) case. The block was not in the package, so that premise
    was unauditable. Excerpts are quoted as .txt, not as importable sources: the
    host is still not redistributed.
    """
    src: str                        # repository-relative path
    first: str                      # substring identifying the first line
    last: str                       # substring identifying the last line
    dst: str                        # filename under code/host_excerpt/
    why: str                        # what the paper reads off it


EXCERPTS = [
    EX("dcr/avbd/_solver/solver_xpbd.py",
       "# ---- velocity update v =", "cargo_an[bi]) / h",
       "solver_velocity_update.txt",
       "The rigid read-back is V[i] = (X[i] - x_prev[i]) / h, i.e. kappa_r = 1 "
       "for every body, and under the shipped symplectic default the mode is "
       "committed by modal_midpoint_commit, i.e. kappa = 2. This is the "
       "(kappa_r, kappa) = (1, 2) case the shipped-row experiments run at."),
    EX("dcr/modal/symplectic_stepper.py",
       "def modal_midpoint_commit(", "return 2.0 * (q_next - q_n)",
       "modal_midpoint_commit.txt",
       "The kappa = 2 reconstruction itself: qdot^{n+1} = 2(q^{n+1} - q^n)/h "
       "- qdot^n."),
]

def extra_map():
    """The claim/filename pairs the README prints, built from TSCRIPTS so a new
    row needs no second edit. Names the gzipped file when the CSV was gzipped."""
    pairs = []
    for t in TSCRIPTS:
        stem = t.data[0]
        gz = os.path.exists(os.path.join(OUT, "data", stem + ".csv.gz"))
        pairs.append((t.claim, stem + (".csv.gz" if gz else ".csv")))
    return pairs

# ---- the import shim -------------------------------------------------------- #
# The T-suite sources import two absolute module paths that do not exist inside
# the package. These three generated files make them resolve, and nothing else.
SHIM_ROOT_INIT = '''"""Import-compatibility shim for the anonymous supplement (generated file).

The validation sources were written to run from a repository root that is on
`sys.path`, where they say

    from benchmarks.paper_eval.t_onesweep import common as C
    from benchmarks.paper_eval.paper_config import write_manifest   (lazy)

In this package the same sources live in `code/t_onesweep/`, which Python puts
on `sys.path[0]` whenever you run one of them by path. This package therefore
sits next to them and makes both module names resolve here.

It adds no behaviour and changes no result:

  * `paper_eval/paper_config.py` is the repository file, anonymized, and only
    writes the `.config.json` provenance manifest next to a CSV. Its `git_sha()`
    returns "unknown" outside a checkout, which is the only difference you will
    see between a manifest you regenerate and the one shipped in `data/`.
  * `paper_eval/t_onesweep/__init__.py` re-points `__path__` at the directory
    the sources already live in, so `...t_onesweep.common` is the very same
    `code/t_onesweep/common.py` file you can read.
"""
'''
SHIM_PAPER_EVAL_INIT = '''"""Import-compatibility shim (generated file). See ../__init__.py."""
'''
SHIM_TSUITE_INIT = '''"""Import-compatibility shim (generated file). See ../../__init__.py.

`benchmarks.paper_eval.t_onesweep` IS the `code/t_onesweep/` directory three
levels up; this only tells Python so.
"""
import os

__path__ = [os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))]
'''

README_LAYOUT_OLD = ("- `code/t_onesweep/` the validation suite (T1 to T11 and the T4 index\n"
                     "  audit) and the figure builder.")
README_LAYOUT_NEW = ("- `code/t_onesweep/` the validation suite (T1 to T13 and the T4 index\n"
                     "  audit) and the figure builder.\n"
                     "- `code/t_onesweep/benchmarks/` a generated three-file import shim, so\n"
                     "  the sources resolve their two absolute module names inside this\n"
                     "  package. It adds no behaviour; read its docstring.\n"
                     "- `code/t_onesweep/out/` seeded with the frozen CSVs that some checks\n"
                     "  read as INPUT, and where a re-run writes its own output. The seeded\n"
                     "  copies are byte-identical to the same names under `data/`.\n"
                     "- `code/host_excerpt/` verbatim, line-numbered excerpts of the\n"
                     "  production host, quoted as evidence for the reconstruction\n"
                     "  convention. Text files, not importable modules.")

README_HOST_ANCHOR = ("host. This is stated so the package is not mistaken for a complete\n"
                      "reproduction of the shipped-row experiments.")
README_HOST_EXTRA = """

What the host DOES have to make auditable is its velocity reconstruction, since
every shipped-row result is read at that convention. `code/host_excerpt/` quotes
the two blocks verbatim with their source paths and line numbers: the rigid
read-back `V[i] = (X[i] - x_prev[i]) / h`, which is `kappa_r = 1` for every body,
and the modal commit `qdot = 2(q - q^n)/h - qdot^n` that the symplectic default
selects, which is `kappa = 2`. The shipped rows are therefore the mixed
`(kappa_r, kappa) = (1, 2)` case, and that can now be checked without the host."""

README_GZ_OLD = ("  `.config.json` manifest each run wrote. The two 241x241 phase-map\n"
                 "  CSVs are gzipped.")
README_GZ_NEW = ("  `.config.json` manifest each run wrote. CSVs over 2 MB ship\n"
                 "  gzipped, which here is the 241x241 phase map and the T13\n"
                 "  ordering sweep.")

README_RUN_ANCHOR = "python code/t_onesweep/run_t4_index_audit.py  # reads t4_shipped.csv"

README_CLEANROOM = """
## Reproduced from a clean interpreter

Every command in the run block under *What runs from this package alone* was
re-run from a fresh copy of this package on a machine where the source
repository is NOT importable, and each exited zero. Run them from the package
root; they do not care about the working directory beyond that. The only
prerequisite is Python 3 with numpy: there is nothing to install and no path to
set.

Each check regenerates its own CSV into `code/t_onesweep/out/`. For the
deterministic checks that CSV is byte-identical to the copy shipped in `data/`
(the seeds are fixed in the sources); the accompanying `.config.json` differs in
`git_sha` and `generated_utc` only, because a package unpacked outside a
checkout has no commit to report.
"""


# --------------------------------------------------------------------------- #
def _anon_copy(src, dst):
    with open(src, encoding="utf-8") as fh:
        body = MS.anonymize(fh.read())
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(body)


def _write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def add_tscripts():
    """Ship every TSCRIPTS row: source, CSV (gzipped when large), manifest."""
    added = []
    for t in TSCRIPTS:
        src = os.path.join(TSUITE, t.code)
        if not os.path.exists(src):
            print("  MISSING (abort): %s" % t.code)
            return None
        dst = os.path.join(OUT, "code", "t_onesweep", t.code)
        _anon_copy(src, dst)
        added.append(dst)
        print("  code/t_onesweep/%s" % t.code)

        for stem in t.data:
            csv_src = os.path.join(TSUITE, "out", stem + ".csv")
            if not os.path.exists(csv_src):
                print("  MISSING (abort): out/%s.csv" % stem)
                return None
            size = os.path.getsize(csv_src)
            if size > MS.GZIP_OVER:
                csv_dst = os.path.join(OUT, "data", stem + ".csv.gz")
                with open(csv_src, "rb") as fi, \
                        gzip.open(csv_dst, "wb", compresslevel=9) as fo:
                    shutil.copyfileobj(fi, fo)
                print("  data/%s.csv.gz  (%.1f MB -> %.1f MB)"
                      % (stem, size / 1e6, os.path.getsize(csv_dst) / 1e6))
            else:
                csv_dst = os.path.join(OUT, "data", stem + ".csv")
                shutil.copy2(csv_src, csv_dst)
                print("  data/%s.csv" % stem)
            added.append(csv_dst)

            man_src = os.path.join(TSUITE, "out", stem + ".config.json")
            if os.path.exists(man_src):
                man_dst = os.path.join(OUT, "data", stem + ".config.json")
                _anon_copy(man_src, man_dst)
                added.append(man_dst)
                print("  data/%s.config.json" % stem)
    return added


EXCERPT_HEADER = """{sep}
VERBATIM SOURCE EXCERPT, quoted as evidence. Not an importable module.

Source : {src}
Lines  : {lo}-{hi} of {total}

WHY IT IS HERE
{why}

The production host is not redistributed with this package (see the README
section "What does NOT run from this package"). This excerpt is quoted so the
reconstruction convention the paper reads off the host is auditable without it.
{sep}

"""


def add_excerpts():
    """Ship every EXCERPTS row: a line-range slice, located by marker."""
    added = []
    for e in EXCERPTS:
        src = os.path.join(ROOT, e.src)
        if not os.path.exists(src):
            print("  MISSING (abort): %s" % e.src)
            return None
        with open(src, encoding="utf-8") as fh:
            lines = fh.readlines()
        lo = hi = None
        for i, ln in enumerate(lines):
            if lo is None and e.first in ln:
                lo = i
            elif lo is not None and e.last in ln:
                hi = i
                break
        if lo is None or hi is None:
            print("  MARKER NOT FOUND (abort): %s in %s" % (e.dst, e.src))
            return None
        body = EXCERPT_HEADER.format(sep="=" * 74, src=e.src, lo=lo + 1,
                                     hi=hi + 1, total=len(lines), why=e.why)
        body += "".join(lines[lo:hi + 1])
        dst = os.path.join(OUT, "code", "host_excerpt", e.dst)
        _write(dst, MS.anonymize(body))
        added.append(dst)
        print("  code/host_excerpt/%s  (%s lines %d-%d)"
              % (e.dst, e.src, lo + 1, hi + 1))
    return added


def add_shim():
    """Three generated files + the repository's paper_config.py, anonymized."""
    base = os.path.join(OUT, "code", "t_onesweep", "benchmarks")
    _write(os.path.join(base, "__init__.py"), SHIM_ROOT_INIT)
    _write(os.path.join(base, "paper_eval", "__init__.py"), SHIM_PAPER_EVAL_INIT)
    _write(os.path.join(base, "paper_eval", "t_onesweep", "__init__.py"),
           SHIM_TSUITE_INIT)
    added = [os.path.join(base, "__init__.py"),
             os.path.join(base, "paper_eval", "__init__.py"),
             os.path.join(base, "paper_eval", "t_onesweep", "__init__.py")]
    pc_src = os.path.join(PAPER_EVAL, "paper_config.py")
    if not os.path.exists(pc_src):
        print("  MISSING (abort): benchmarks/paper_eval/paper_config.py")
        return None
    pc_dst = os.path.join(base, "paper_eval", "paper_config.py")
    _anon_copy(pc_src, pc_dst)
    added.append(pc_dst)
    for p in added:
        print("  %s" % os.path.relpath(p, OUT))
    return added


def seed_inputs():
    """Copy every frozen INPUT CSV a registered check reads into code/.../out/."""
    wanted = sorted({name for t in TSCRIPTS for name in t.reads})
    added = []
    seed_dir = os.path.join(OUT, "code", "t_onesweep", "out")
    os.makedirs(seed_dir, exist_ok=True)
    for name in wanted:
        src = os.path.join(TSUITE, "out", name)
        if not os.path.exists(src):
            print("  MISSING (abort): out/%s" % name)
            return None
        dst = os.path.join(seed_dir, name)
        shutil.copy2(src, dst)
        added.append(dst)
        print("  code/t_onesweep/out/%s  (frozen input)" % name)
    return added


def patch_readme():
    path = os.path.join(OUT, "README.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    for old, new, what in (
            (README_LAYOUT_OLD, README_LAYOUT_NEW, "layout bullet"),
            (README_GZ_OLD, README_GZ_NEW, "gzip sentence"),
            (README_HOST_ANCHOR, README_HOST_ANCHOR + README_HOST_EXTRA,
             "host-excerpt anchor")):
        if old not in text:
            print("  README %s not found; refusing to guess" % what)
            return None
        text = text.replace(old, new, 1)

    if README_RUN_ANCHOR not in text:
        print("  README run block not found; refusing to guess")
        return None
    run_lines = "".join(
        "\npython code/t_onesweep/%s%s" % (t.code, t.run_note)
        for t in TSCRIPTS if t.runnable)
    text = text.replace(README_RUN_ANCHOR, README_RUN_ANCHOR + run_lines, 1)

    # The number-map entries belong at the end of the number map, which
    # make_supplement_extras.py follows with its scene-parameter prose. Land
    # them before that heading, not before "## Integrity", or they read as part
    # of the scene-parameter section.
    map_marker = "\n## Scene parameters\n"
    if map_marker not in text:
        map_marker = "\n## Integrity\n"
    if map_marker not in text:
        print("  README number map end not found; refusing to guess")
        return None
    extra = "".join("- %s\n  -> `data/%s`\n" % (c, f) for c, f in extra_map())
    text = text.replace(map_marker, extra + map_marker, 1)

    marker = "\n## Integrity\n"
    if marker not in text:
        print("  README integrity marker not found; refusing to guess")
        return None
    text = text.rstrip("\n") + "\n"
    text = text.replace(marker, "\n" + README_CLEANROOM.strip("\n") + "\n" + marker, 1)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("  README.md (layout, run block, number map, clean-room section)")
    return [path]


def gate():
    """make_supplement's own FORBIDDEN scan over every file, gz contents too."""
    leaks, scanned = [], 0
    for dirpath, _, filenames in os.walk(OUT):
        for n in sorted(filenames):
            p = os.path.join(dirpath, n)
            try:
                if n.endswith(".gz"):
                    with gzip.open(p, "rt", encoding="utf-8") as fh:
                        body = fh.read()
                else:
                    with open(p, encoding="utf-8") as fh:
                        body = fh.read()
            except (UnicodeDecodeError, ValueError, OSError):
                continue
            scanned += 1
            for pat, why in MS.FORBIDDEN:
                mm = pat.search(body)
                if mm:
                    leaks.append((os.path.relpath(p, OUT),
                                  "%s: %r" % (why, mm.group(0))))
    for dirpath, dirnames, filenames in os.walk(OUT):
        for n in list(dirnames) + list(filenames):
            if n == MS.USER or n.startswith(MS.USER + "."):
                leaks.append((n, "filename is the username"))
    return leaks, scanned


def sha256sums():
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
            sums.append("%s  %s" % (hh.hexdigest(), os.path.relpath(p, OUT)))
    with open(os.path.join(OUT, "SHA256SUMS"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(sums, key=lambda s: s.split("  ", 1)[1])) + "\n")
    return len(sums)


# --------------------------------------------------------------------------- #
# CLEAN-ROOM VERIFICATION                                                      #
# --------------------------------------------------------------------------- #
ISORUN = '''"""Run a script with the source repository scrubbed from sys.path.

Reproduces a reviewer's interpreter on a developer machine, where an
editable-install .pth silently puts the repository on sys.path.
"""
import os
import runpy
import sys

BLOCK = os.path.abspath(sys.argv[1])
target = os.path.abspath(sys.argv[2])
sys.path[:] = [p for p in sys.path if p and os.path.abspath(p) != BLOCK]
sys.path.insert(0, os.path.dirname(target))
sys.argv = [target] + sys.argv[3:]
runpy.run_path(target, run_name="__main__")
'''

# Every check the README claims runs from the package alone. Base list plus the
# runnable TSCRIPTS rows.
BASE_RUNNABLE = [
    "selftest_common.py",
    "run_t1_identities.py", "run_t2_phasemap.py", "run_t3_nonmodal.py",
    "run_t5_ordering.py", "run_t7_reconstruction.py", "run_t8_relaxation.py",
    "run_t10_multimode.py", "run_t11_accuracy.py", "run_t4_index_audit.py",
]


def verify():
    """Copy the package somewhere clean and run every runnable check there."""
    names = BASE_RUNNABLE + [t.code for t in TSCRIPTS if t.runnable]
    tmp = tempfile.mkdtemp(prefix="supp_verify_")
    pkg = os.path.join(tmp, "supplement_onesweep")
    shutil.copytree(OUT, pkg)
    iso = os.path.join(tmp, "_isorun.py")
    with open(iso, "w", encoding="utf-8") as fh:
        fh.write(ISORUN)

    print("  clean copy: %s" % pkg)
    print("  repository removed from sys.path: %s" % ROOT)
    ok = True
    results = []
    for name in names:
        script = os.path.join(pkg, "code", "t_onesweep", name)
        pr = subprocess.run([sys.executable, iso, ROOT, script],
                            cwd=pkg, capture_output=True, text=True)
        tail = (pr.stdout or pr.stderr).strip().splitlines()
        tail = tail[-1] if tail else ""
        results.append((name, pr.returncode, tail))
        if pr.returncode != 0:
            ok = False
            print("  FAIL rc=%d  %s" % (pr.returncode, name))
            for ln in (pr.stderr or pr.stdout).strip().splitlines()[-6:]:
                print("        %s" % ln)
        else:
            print("  PASS  %-28s %s" % (name, tail[:70]))

    # regenerated CSVs against the shipped ones
    print("\n  -- regenerated vs shipped CSV --")
    regen_dir = os.path.join(pkg, "code", "t_onesweep", "out")
    same = diff = 0
    for n in sorted(os.listdir(regen_dir)) if os.path.isdir(regen_dir) else []:
        if not n.endswith(".csv"):
            continue
        shipped = os.path.join(pkg, "data", n)
        shipped_gz = shipped + ".gz"
        if os.path.exists(shipped):
            with open(shipped, "rb") as fh:
                ref = fh.read()
        elif os.path.exists(shipped_gz):
            with gzip.open(shipped_gz, "rb") as fh:
                ref = fh.read()
        else:
            continue
        with open(os.path.join(regen_dir, n), "rb") as fh:
            got = fh.read()
        if got == ref:
            same += 1
        else:
            diff += 1
            print("     DIFFERS: %s" % n)
    print("     %d byte-identical, %d differing" % (same, diff))
    if diff:
        ok = False
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, results


def make_zip():
    base = os.path.join(ROOT, "supplement_onesweep")
    archive = shutil.make_archive(base, "zip", root_dir=ROOT,
                                  base_dir="supplement_onesweep")
    return archive, os.path.getsize(archive)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the clean-copy re-run")
    ap.add_argument("--zip", action="store_true",
                    help="also write supplement_onesweep.zip for EasyChair")
    args = ap.parse_args()

    print("== base package (make_supplement.py + make_supplement_extras.py) ==")
    rc = MSX.main()
    if rc != 0:
        print("base build FAILED its own gate; nothing added")
        return rc

    print("\n== registered T-scripts (%d) ==" % len(TSCRIPTS))
    if add_tscripts() is None:
        return 2
    print("\n== host excerpts (%d) ==" % len(EXCERPTS))
    if add_excerpts() is None:
        return 2
    print("\n== import shim ==")
    if add_shim() is None:
        return 2
    print("\n== frozen inputs ==")
    if seed_inputs() is None:
        return 2
    print("\n== README ==")
    if patch_readme() is None:
        return 2

    print("\n-- anonymity gate (whole package, gz contents included) --")
    leaks, scanned = gate()
    if leaks:
        print("  FAIL, author-identifying tokens present:")
        for p, t in leaks:
            print("    %s: %s" % (p, t))
        return 1
    print("  clean: no home path, username or author token in %d text files"
          % scanned)

    n = sha256sums()
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fns in os.walk(OUT) for f in fns)
    print("\nsupplement_onesweep/: %d files, %.1f MB" % (n, total / 1e6))

    if not args.no_verify:
        print("\n-- clean-room verification --")
        ok, _ = verify()
        if not ok:
            print("  VERIFICATION FAILED; the package does not run as documented")
            return 3
        print("  every documented check ran and exited zero")

    if args.zip:
        archive, size = make_zip()
        print("\narchive: %s  (%.1f MB)"
              % (os.path.relpath(archive, ROOT), size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
