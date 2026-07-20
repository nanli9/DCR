#!/usr/bin/env python3
"""Q1 — assemble the anonymized supplement / reproduction bundle (plan §9.3).

Reproducibility scored 2.00/5 with the six-reviewer video panel, the floor of
the six criteria — and it was scored against a package the panel never received.
The P8 bundle (README + ledger excerpts + CSVs) existed; what it lacked was the
part that makes a bundle *runnable*: source, a claim->data->command index,
pinned versions, a smoke test, checksums, and the video. This assembles all of
it.

WHAT IS IN THE BUNDLE
  README.md              orientation, machine/version record, how to re-run
  CLAIMS_INDEX.md        every results section -> data file -> command
  LEDGER_EXCERPTS.md     the frozen ledger entries, verbatim
  data/                  the raw CSVs + their .config.json manifests
  code_snapshot.zip      the source needed to re-derive them (no .git)
  smoke_test.py          clean-unpack check: builds a scene, re-derives a cell
  requirements-freeze.txt
  teaser_video.mp4
  SHA256SUMS

THREE THINGS THIS REFUSES TO DO
  1. Ship identifying information. Every text artifact, INCLUDING every file in
     the code snapshot and the member paths of the zips, is scanned. A
     confirmed hit aborts the run. This is not belt-and-braces: the first run of
     this scanner found `https://github.com/<author-account>/AVBD` in a vendored
     module docstring, which the P8 scan (home paths + one host name) missed.
  2. Ship a searchable commit hash. Git hashes are redacted to `<commit>` in the
     review copy; the mapping is written OUTSIDE the bundle for camera-ready.
  3. Ship a claim index that has drifted from the paper. Every index row names a
     tex anchor that must still occur in `main_short.tex` and a command that
     must still occur in the results ledger. Either check failing aborts.

Out: supplement/ and mig26_supplement.zip at the repo root
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/make_supplement.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
X1 = os.path.join(_HERE, "out")
X3 = os.path.join(_ROOT, "benchmarks", "paper_eval", "x3_ground_truth", "out")
X5 = os.path.join(_ROOT, "benchmarks", "paper_eval", "x5_perf", "out")
DEST = os.path.join(_ROOT, "supplement")
ZIP_OUT = os.path.join(_ROOT, "mig26_supplement.zip")
LEDGER = os.path.join(_ROOT, "docs", "mig2026_results_ledger.md")
TEX = os.path.join(_ROOT, "paper", "main_short.tex")
VIDEO = os.path.join(_ROOT, "benchmarks", "paper_fig", "out", "teaser_video.mp4")
SMOKE_SRC = os.path.join(_HERE, "supplement_smoke_test.py")
COMMIT_MAP = os.path.join(_ROOT, "supplement_commit_map.private.md")

# --------------------------------------------------------------------------
# 1. What data goes in, grouped as the paper's results sections are numbered.
# --------------------------------------------------------------------------
BUNDLE: dict[str, list[tuple[str, str]]] = {
    "§2 scene specification and row counts": [
        (X1, "scene_spec.csv"), (X1, "scene_spec.md"),
    ],
    "§3.1 one row, three hosts, 24 cells (Fig. 2, Table 1)": [
        (X1, "solver_matrix.csv"), (X1, "eq2_utilization.csv"),
        (X1, "substep_sweep.csv"),
    ],
    "§3.2 iteration budget and convergence (Fig. 3)": [
        (X1, "k_convergence.csv"), (X1, "selfconvergence.csv"),
        (X1, "complementarity_residual.csv"),
        (X1, "complementarity_residual_nd.csv"),
        (X1, "complementarity_residual_nd_ledge.csv"),
    ],
    "§3.2 deployed budgets 1x8 / 2x4": [
        (X1, "eq2_deployed.csv"), (X1, "solver_matrix_deployed.csv"),
        (X1, "projection_validity_deployed.csv"),
        (X1, "governed_accuracy_1x8.csv"),
    ],
    "§3.2 robustness ablation and worst-cell ladder": [
        (X1, "robustness_ablation.csv"), (X1, "k_convergence_ledge_worst.csv"),
    ],
    "§3.3 cost of enforcement (Table 2)": [
        (X1, "projection_validity.csv"), (X1, "projection_validity_avbd.csv"),
        (X1, "governed_accuracy.csv"),
    ],
    "§3.4 reduced response against a full-FEM reference": [
        (X3, "ledge_convergence.csv"), (X3, "ledge_falloff.csv"),
    ],
    "§3.5 runtime cost": [
        (X5, "perf_reps_summary.csv"), (X5, "perf_device.csv"),
        (X5, "perf_device_budget.csv"),
    ],
    "§4 limitations: supply partition and long-horizon recycling": [
        (X1, "supply_partition.csv"), (X1, "long_horizon.csv"),
    ],
}

# Ledger sections excerpted verbatim, by heading text. Every bundled CSV's
# provenance (command + commit + machine) must be reachable from one of these.
LEDGER_SECTIONS = [
    "### E-S1b", "## E-S2", "## E-S3", "## E-C6", "### E-C6", "## E-C9",
    "### E-C9e",
    "## R1", "## R3", "## R4", "## R5", "## R7",
]

# --------------------------------------------------------------------------
# 2. The code snapshot: everything needed to re-derive the numbers, no more.
# --------------------------------------------------------------------------
SNAPSHOT_ROOTS = ["dcr", "scenes", "benchmarks/paper_eval", "pyproject.toml"]

# `scripts/` and `benchmarks/paper_fig/` are deliberately NOT snapshotted: no
# paper_eval harness imports either (checked), they carry viewer/diagnostic
# surface irrelevant to the numbers, and paper_fig/data/ holds large frozen
# artifacts from other suites.
SNAPSHOT_DROP = re.compile(
    r"(^|/)(__pycache__|out)/"          # generated + per-suite outputs
    r"|\.(pdf|png|mp4|npz|obj|msh|wav|pyc)$"
    r"|(^|/)make_supplement\.py$"       # this file: it holds the DEANON patterns
)


def snapshot_paths() -> list[str]:
    out = subprocess.run(["git", "-C", _ROOT, "ls-files"] + SNAPSHOT_ROOTS,
                         capture_output=True, text=True).stdout.split()
    return sorted(p for p in out if not SNAPSHOT_DROP.search(p))


def blob(path: str) -> bytes:
    """Read `path` at HEAD, so no uncommitted working-tree state can ship."""
    r = subprocess.run(["git", "-C", _ROOT, "show", f"HEAD:{path}"],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"not at HEAD: {path}")
    return r.stdout


# --------------------------------------------------------------------------
# 3. Anonymity. CONFIRMED patterns abort; REVIEW patterns are printed in full
#    with context and abort too -- the operator adjudicates and adds an
#    explicit redaction, never an auto-pass (plan §9.3.g).
# --------------------------------------------------------------------------
DEANON_CONFIRMED = [
    (re.compile(r"/Users/[^/\s\"']+"), "absolute home path"),
    (re.compile(r"/home/[^/\s\"']+"), "absolute home path"),
    (re.compile(r"\bcompshare\b", re.I), "named host"),
    (re.compile(r"\bcpod-[0-9a-z]+\b", re.I), "named compute pod"),
    (re.compile(r"nli62220"), "username"),
    (re.compile(r"usc\.edu"), "institution domain"),
    # TLD must be alphabetic: `vx@0.1s` in a diagnostic script is not an email.
    (re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b"), "email address"),
]
# Case-sensitive author given name. Known false positives are lower-case
# (`nan` the float) or embedded (`domi*nan*t`); `\b` + case-sensitivity
# excludes both, so any hit here is reviewed by hand.
DEANON_REVIEW = [(re.compile(r"\bNan\b"), "author given name")]

# Repository URLs are adjudicated one at a time: a link to somebody else's
# public repo is a citation and stays; a link to ours is a deanonymization.
URL_RX = re.compile(r"(github\.com|gitlab|git@)[^\s\"'）)]*")
URL_ALLOW = [
    "github.com/savant117/avbd-demo2d",   # third party: the AVBD demo we cite
]

# Git hashes: 7-40 hex chars, at least one hex letter OTHER than `e` (so float
# mantissas like `1.19534e5` are not tokens), not adjacent to a word char or
# dot (so a 64-char SHA-256 in SHA256SUMS is never touched).
HASH_RX = re.compile(
    r"(?<![\w.])(?=[0-9a-f]{7,40}(?![\w.]))(?=[0-9a-f]*[a-df])[0-9a-f]{7,40}(?![\w.])")

# Redactions applied to text before it is written or scanned. Each is a real
# finding, not a precaution -- see the module docstring.
REDACTIONS = [
    (re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/AVBD"),
     "<anonymized upstream repository>",
     "author's own GitHub account in a vendored-module docstring"),
]


def redact(text: str, hashes: bool = True) -> tuple[str, dict[str, str]]:
    """Apply the redaction list; optionally replace git hashes. Returns the
    text and the {hash: placeholder} mapping for the private commit map."""
    for rx, repl, _why in REDACTIONS:
        text = rx.sub(repl, text)
    seen: dict[str, str] = {}
    if hashes:
        def sub(m: re.Match) -> str:
            seen[m.group(0)] = "<commit>"
            return "<commit>"
        text = HASH_RX.sub(sub, text)
    return text, seen


def scan(name: str, text: str) -> tuple[list[str], list[str]]:
    """Returns (confirmed, review) findings for one artifact."""
    confirmed = [f"{name}: {why} -- {m.group(0)!r}"
                 for rx, why in DEANON_CONFIRMED for m in rx.finditer(text)]
    for m in URL_RX.finditer(text):
        url = m.group(0)
        if not any(a in url for a in URL_ALLOW):
            confirmed.append(f"{name}: unadjudicated repository URL -- {url!r}")
    review = [f"{name}: {why} -- ...{text[max(0, m.start()-40):m.end()+40]}..."
              for rx, why in DEANON_REVIEW for m in rx.finditer(text)]
    return confirmed, review


# --------------------------------------------------------------------------
# 4. The claim index. Every row is checked against the paper and the ledger:
#    `tex` must still occur in main_short.tex and `cmd` in the results ledger.
#    A paper edit that drops a claim, or a harness rename, breaks the build.
# --------------------------------------------------------------------------
M = "run_solver_matrix.py"
E = "run_eq2_utilization.py"
CLAIMS: list[tuple[str, str, str, str, str]] = [
    # (paper site, printed quantity, data file, generating command, tex anchor)
    ("§2, Table 1", "one row law instantiated at 48 / 40 / 200 support rows",
     "scene_spec.csv", "make_scene_spec.py",
     r"$48$ such rows on the shelf"),
    ("§2, Table 1", "modal rank r = 16 / 16 / 24 (realized basis size)",
     "scene_spec.csv", "make_scene_spec.py",
     r"$16$ (shelf), $16$ (ledge), $24$ (table)"),
    ("§3.1, Fig. 2 top", "R > 1 in 8/24 (XPBD), 2/24 (AVBD), 0/24 (impulse)",
     "solver_matrix.csv", M,
     r"XPBD exceeds $1$ in $8/24$ cells"),
    ("§3.1", "worst R = 1.19534e5 at ledge, relax 1.0, 4x1",
     "solver_matrix.csv", M, r"worst case $1.19534\times10^{5}$"),
    ("§3.1", "peak modal 4.44e7 J against an incident 371 J",
     "solver_matrix.csv", M, r"$4.44\times10^{7}$~J against an incident"),
    ("§3.1", "substep refinement alone does not converge the row "
             "(0.300 at 32x1 vs 3.13 at 4x8, overdrawing 481 J)",
     "substep_sweep.csv",
     f"{E} --scenes shelf --budgets 4x1,4x2,4x4,4x8 --relaxes 0.7,1.0 "
     "--out substep_sweep",
     r"it is $3.13$, overdrawing by $481$~J"),
    ("§3.1, Fig. 2 bottom", "Eq. (2) violated in 23/24 AVBD cells, 8/24 XPBD, "
                            "0/24 impulse; AVBD worst 15.1 J",
     "eq2_utilization.csv", f"{E} --check-frozen",
     r"in $23$ of $24$ cells although $R$ flags"),
    ("§3.1", "governed: all 72 cells satisfy Eq. (2); worst ratio 1.22 / 0.87",
     "solver_matrix.csv", M, r"falls to $1.22$ (XPBD) and $0.87$ (AVBD)"),
    ("§3.2, Fig. 3", "XPBD 2.96e4 (K=1) -> 0.300 (K=32); reference 0.2735; "
                     "implicit spread 4.9e-4 over K=2...500",
     "k_convergence.csv", "run_k_convergence.py",
     r"(spread $4.9\times10^{-4}$)"),
    ("§3.2", "penetration 27.9 mm (K=1) -> 3.6 um (K=64); separated-row "
             "multiplier 84x -> 139x (K=24) -> 0 (K=64)",
     "complementarity_residual_nd.csv", "probe_complementarity_residual_nd.py",
     r"to $3.6\,\mu$m by $K{=}64$"),
    ("§3.2", "XPBD self-convergence plateaus at 0.2996; peak agrees to 2.4%, "
             "trajectories differ by 6.8 mm (34% of reference peak)",
     "selfconvergence.csv", "run_selfconvergence.py",
     r"plateaus by $K\approx64$ at $0.2996$"),
    ("§3.2", "deployed 1x8 / 2x4: XPBD violates 6/6 (worst R = 2282), "
             "AVBD 5/6 by <= 0.16 J, impulse 0/6",
     "eq2_deployed.csv", f"{E} --budgets 1x8,2x4 --relaxes 0.7 --out eq2_deployed",
     r"worst $R=2282$"),
    ("§3.2", "governed at the deployed budgets: all 18 satisfy Eq. (2), "
             "worst R = 1.022",
     "solver_matrix_deployed.csv",
     f"{M} --budgets 1x8,2x4 --relaxes 0.7 --out solver_matrix_deployed",
     r"(worst $R = 1.022$)"),
    ("§3.2", "not a knife-edge: 24/24 perturbed configurations violate, "
             "R spans 2.5 to 4.7e5; excluding the stiff cluster leaves 584 J",
     "robustness_ablation.csv", "run_robustness_ablation.py",
     r"$R$ spanning $2.5$ to $4.7\times10^{5}$"),
    ("§3.2", "worst cell converges: R falls 8.5e5 -> 0.165 over K=1...32",
     "k_convergence_ledge_worst.csv",
     "run_k_convergence.py --scene ledge --relax 1.0 --out k_convergence_ledge_worst",
     r"$R$ falls $8.5\times10^{5}\to0.165$"),
    ("§3.3, Table 2", "post-projection contact validity, XPBD: clamp counts, "
                      "gap violation med/max, corrective impulse, lambda variance",
     "projection_validity.csv", "run_projection_validity.py",
     r"1.25 / \textbf{21.6}"),
    ("§3.3", "AVBD is gentler in absolute terms (worst 1.4 and 3.1 mm) and "
             "comparable in relative terms (3.1x and 5.5x)",
     "projection_validity_avbd.csv", "run_projection_validity_avbd.py",
     r"worst violations $1.4$ and $3.1$~mm"),
    ("§3.3", "accuracy at shelf 8x2: 1555.6 J -> 29.26 J against 7.92 J; "
             "energy error 196x -> 3.7x; trajectory 6.5 mm -> 14.3 mm",
     "governed_accuracy.csv", "run_governed_accuracy.py",
     r"falls $196{\times}\to3.7{\times}$"),
    ("§3.3", "deployed 1x8: energy 2823x -> 3.7x, trajectory 108% -> 96%",
     "governed_accuracy_1x8.csv",
     "run_governed_accuracy.py --scene shelf --cell 1x8 --relax 0.7 "
     "--out governed_accuracy_1x8",
     r"$2823{\times}\to3.7{\times}$"),
    ("§3.3", "governed projection at deployed budgets: worst penetration 9.8 mm",
     "projection_validity_deployed.csv",
     "run_projection_validity.py --scenes shelf,ledge --budgets 1x8,2x4 "
     "--relax 0.7 --out projection_validity_deployed",
     r"worst penetration $9.8$~mm against $21.6$"),
    ("§3.4", "reduced/reference peak-deflection ratio 0.38 -> 0.88 as h "
             "refines; ring frequency agrees to 0.4% (78.0 vs 78.3 Hz)",
     "ledge_convergence.csv", "(x3_ground_truth harness; see ledger)",
     r"$0.38\to0.54\to0.79\to0.88$"),
    ("§3.4", "far-field falloff tracks the reference at Spearman rho = 0.89",
     "ledge_falloff.csv", "(x3_ground_truth harness; see ledger)",
     r"Spearman $\rho=0.89$"),
    ("§3.5", "CPU: baseline 11.0-125.6 ms; ledger adds 0.23-0.41 ms "
             "(0.9-3.4%) where it resolves above run-to-run variance",
     "perf_reps_summary.csv",
     "run_perf_reps.py --only shelf,ledge,dinner --reps 10 --frames 100",
     r"$0.23$--$0.41$~ms"),
    ("§3.5", "device-resident monitor path: 5.0-8.9 ms/step at 16x4",
     "perf_device.csv", "(x5_perf device harness; see ledger)",
     r"$5.0$--$8.9$~ms/step"),
    ("§3.5", "all four scenes meet a 120 Hz budget at 16x2 or below",
     "perf_device_budget.csv", "(x5_perf device harness; see ledger)",
     r"at $16{\times}2$ or below"),
    ("§4", "supply partition dependence is bounded (coarsening ratio <= 1.083)",
     "supply_partition.csv", "probe_supply_partition.py",
     r"depends on the substep \emph{partition}"),
    ("§4", "recycling is steady state, not a window artifact, over a 10x horizon",
     "long_horizon.csv", "probe_long_horizon.py",
     r"Energy returning from"),
    ("§4", "return channel 0.4-27% (impulse), 3-32% (XPBD), 102-118% (AVBD)",
     "eq2_utilization.csv", f"{E} --check-frozen",
     r"$0.4$--$27\%$"),
]


def check_claims(ledger: str) -> list[str]:
    """Every claim row must still point at a live tex anchor and a live
    command. Returns the list of failures."""
    tex = open(TEX, encoding="utf-8").read() if os.path.isfile(TEX) else None
    bad = []
    for site, what, data, cmd, anchor in CLAIMS:
        if tex is not None:
            # tex is hard-wrapped: compare with newlines collapsed.
            flat_t = re.sub(r"\s+", " ", tex)
            flat_a = re.sub(r"\s+", " ", anchor)
            if flat_a not in flat_t:
                bad.append(f"{site}: tex anchor gone -- {anchor!r}")
        stem = cmd.split()[0]
        if stem.endswith(".py") and stem not in ledger:
            bad.append(f"{site}: harness not in the ledger -- {stem}")
    return bad


# --------------------------------------------------------------------------
# 5. Assembly
# --------------------------------------------------------------------------
def ledger_excerpt() -> str:
    if not os.path.isfile(LEDGER):
        return "(results ledger not found)\n"
    out, keep, depth = [], False, 0
    for ln in open(LEDGER, encoding="utf-8").read().split("\n"):
        if ln.startswith("#"):
            if any(ln.startswith(h) for h in LEDGER_SECTIONS):
                keep, depth = True, len(ln) - len(ln.lstrip("#"))
            elif keep and (len(ln) - len(ln.lstrip("#"))) <= depth:
                keep = False
        if keep:
            out.append(ln)
    return "\n".join(out) if out else "(no matching ledger sections)\n"


def freeze_versions() -> str:
    """Pin the environment. Read through `importlib.metadata` rather than
    `pip freeze`: this project's virtualenv is uv-managed and has no `pip`, so
    shelling out silently produced an empty freeze file on the first run.

    The interpreter's architecture is recorded too, and is not incidental: the
    printed digits are arm64-exact and x86-64 reassociation diverges on chaotic
    contact stacks (README §1).
    """
    import importlib.metadata as md
    import platform

    dists = sorted(
        {d.metadata["Name"]: d.version for d in md.distributions()
         if d.metadata["Name"]}.items(),
        key=lambda kv: kv[0].lower())
    body = "\n".join(f"{n}=={v}" for n, v in dists)
    return (f"# CPython {sys.version.split()[0]} on "
            f"{platform.system()} {platform.machine()}\n"
            f"# Read from importlib.metadata ({len(dists)} distributions).\n"
            f"{body}\n")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    confirmed: list[str] = []
    review: list[str] = []
    commit_map: dict[str, str] = {}

    ledger_raw = open(LEDGER, encoding="utf-8").read() if os.path.isfile(LEDGER) else ""

    claim_bad = check_claims(ledger_raw)
    if claim_bad:
        sys.stderr.write("REFUSING: the claim index has drifted from the "
                         "paper or the ledger:\n")
        for b in claim_bad:
            sys.stderr.write(f"  {b}\n")
        return 1

    if os.path.isdir(DEST):
        shutil.rmtree(DEST)
    os.makedirs(os.path.join(DEST, "data"), exist_ok=True)

    # ---- data -------------------------------------------------------------
    copied: list[tuple[str, str]] = []
    missing: list[str] = []
    for group, files in BUNDLE.items():
        for src_dir, f in files:
            src = os.path.join(src_dir, f)
            if not os.path.isfile(src):
                missing.append(f)
                continue
            text = open(src, encoding="utf-8", errors="replace").read()
            c, r = scan(f, text)
            confirmed += c
            review += r
            shutil.copy2(src, os.path.join(DEST, "data", f))
            copied.append((group, f))
            cfg = os.path.splitext(f)[0] + ".config.json"
            cfg_src = os.path.join(src_dir, cfg)
            if os.path.isfile(cfg_src):
                man = json.load(open(cfg_src))
                if isinstance(man.get("git_sha"), str):
                    commit_map[man["git_sha"]] = f"{cfg}:git_sha"
                    man["git_sha"] = "<commit>"
                blob_txt = json.dumps(man, indent=2)
                c, r = scan(cfg, blob_txt)
                confirmed += c
                review += r
                open(os.path.join(DEST, "data", cfg), "w").write(blob_txt + "\n")

    # ---- code snapshot ----------------------------------------------------
    snap = os.path.join(DEST, "code_snapshot.zip")
    paths = snapshot_paths()
    with zipfile.ZipFile(snap, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            c, _r = scan(f"code_snapshot.zip:{p}", p)      # member PATH itself
            confirmed += c
            raw = blob(p)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                zf.writestr(p, raw)
                continue
            text, seen = redact(text)
            commit_map.update({h: p for h in seen})
            c, r = scan(f"code_snapshot.zip:{p}", text)
            confirmed += c
            review += r
            zf.writestr(p, text)

    # ---- prose ------------------------------------------------------------
    excerpt, seen = redact(ledger_excerpt())
    commit_map.update({h: "LEDGER_EXCERPTS.md" for h in seen})
    excerpt_md = (
        "# Frozen results ledger — excerpts\n\n"
        "Each entry carries its generating command, commit and machine, "
        "reproduced verbatim from the project's results ledger. Commit "
        "identifiers read `<commit>`: a searchable hash would identify the "
        "authors, so they are restored for the camera-ready version. The code "
        "those commits name is in `code_snapshot.zip`.\n\n" + excerpt + "\n")

    claims_md = build_claims_md()
    readme_md = build_readme(copied)

    for name, text in (("LEDGER_EXCERPTS.md", excerpt_md),
                       ("CLAIMS_INDEX.md", claims_md),
                       ("README.md", readme_md)):
        text, seen = redact(text)
        commit_map.update({h: name for h in seen})
        c, r = scan(name, text)
        confirmed += c
        review += r
        open(os.path.join(DEST, name), "w").write(text)

    # ---- smoke test, versions, video --------------------------------------
    if os.path.isfile(SMOKE_SRC):
        text, seen = redact(open(SMOKE_SRC, encoding="utf-8").read())
        commit_map.update({h: "smoke_test.py" for h in seen})
        c, r = scan("smoke_test.py", text)
        confirmed += c
        review += r
        open(os.path.join(DEST, "smoke_test.py"), "w").write(text)
    else:
        missing.append("supplement_smoke_test.py")

    reqs = freeze_versions()
    c, r = scan("requirements-freeze.txt", reqs)
    confirmed += c
    review += r
    open(os.path.join(DEST, "requirements-freeze.txt"), "w").write(reqs)

    if os.path.isfile(VIDEO):
        shutil.copy2(VIDEO, os.path.join(DEST, "teaser_video.mp4"))
    else:
        missing.append("teaser_video.mp4")

    # ---- the gate ---------------------------------------------------------
    if confirmed or review:
        shutil.rmtree(DEST)
        sys.stderr.write("REFUSING to write the bundle.\n")
        if confirmed:
            sys.stderr.write(f"\nCONFIRMED identifying information "
                             f"({len(confirmed)}):\n")
            for x in confirmed[:40]:
                sys.stderr.write(f"  {x}\n")
        if review:
            sys.stderr.write(f"\nNEEDS MANUAL REVIEW ({len(review)}) -- "
                             "adjudicate each, then add an explicit "
                             "redaction; never auto-pass:\n")
            for x in review[:40]:
                sys.stderr.write(f"  {x}\n")
        return 1

    # ---- checksums + one zip ---------------------------------------------
    files = []
    for dirpath, _dirs, names in os.walk(DEST):
        for n in sorted(names):
            files.append(os.path.relpath(os.path.join(dirpath, n), DEST))
    files = sorted(f for f in files if f != "SHA256SUMS")
    with open(os.path.join(DEST, "SHA256SUMS"), "w") as fh:
        for f in files:
            fh.write(f"{sha256(os.path.join(DEST, f))}  {f}\n")

    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files + ["SHA256SUMS"]:
            member = f"mig26_supplement/{f}"
            c, _r = scan(f"zip member path: {member}", member)
            if c:
                os.remove(ZIP_OUT)
                sys.stderr.write("REFUSING: identifying zip member path\n")
                for x in c:
                    sys.stderr.write(f"  {x}\n")
                return 1
            zf.write(os.path.join(DEST, f), member)

    # ---- the private mapping, OUTSIDE the bundle --------------------------
    with open(COMMIT_MAP, "w") as fh:
        fh.write("# Private commit map (NOT in the bundle)\n\n"
                 "Redacted `<commit>` placeholders in `mig26_supplement.zip`, "
                 "for restoration in the camera-ready.\n\n"
                 "| hash | where |\n|---|---|\n")
        for h, where in sorted(commit_map.items()):
            fh.write(f"| `{h}` | {where} |\n")

    n_snap = len(paths)
    print(f"wrote {DEST}/ and {os.path.basename(ZIP_OUT)}")
    print(f"  data/            {len(copied)} artifacts")
    print(f"  code_snapshot    {n_snap} files "
          f"({os.path.getsize(snap) / 1024:.0f} KiB)")
    print(f"  scan             PASS (0 confirmed, 0 needing review)")
    print(f"  commit map       {len(commit_map)} hash(es) redacted "
          f"-> {os.path.basename(COMMIT_MAP)}")
    print(f"  zip              {os.path.getsize(ZIP_OUT) / 1024 / 1024:.2f} MiB")
    if missing:
        print(f"  NOTE: {len(missing)} artifact(s) not present, skipped:")
        for f in missing:
            print(f"    - {f}")
    return 0


def build_claims_md() -> str:
    rows = "\n".join(
        f"| {site} | {what} | `data/{data}` | `{cmd}` |"
        for site, what, data, cmd, _anchor in CLAIMS)
    return f"""# Claim → data → command

Every results section of the paper, the bundled file that carries its numbers,
and the command that produced that file. Commands run from the root of an
unpacked `code_snapshot.zip`; those under `§3.1`–`§3.3` and `§4` live in
`benchmarks/paper_eval/x1_passivity/`, `§3.4` in `x3_ground_truth/`, `§3.5` in
`x5_perf/`. Full invocations, with the commit and machine each was frozen on,
are in `LEDGER_EXCERPTS.md`.

This table is checked mechanically when the bundle is built: each row names a
phrase that must still occur in the paper source and a harness that must still
occur in the results ledger, so a claim cannot be edited out of the paper, or a
harness renamed, without the check failing.

| paper site | printed quantity | data | command |
|---|---|---|---|
{rows}

## Re-verifying without re-running anything

Three entry points check printed numbers against these CSVs directly:

- `verify_paper_numbers.py` — re-reads the §3.3 accuracy, contact-validity and
  §3.5 runtime numbers from the CSVs and asserts each. Pure file reads, no
  simulation, about a second:

  ```sh
  python code_snapshot/benchmarks/paper_eval/verify_paper_numbers.py --data data
  ```

  One check compares against the paper source, which this bundle does not ship;
  it reports `skip` unless you pass `--tex <path to main_short.tex>`. All
  others run.
- `run_eq2_utilization.py --check-frozen` — re-runs the 24-cell sweep and
  asserts it reproduces the frozen ratios exactly. This is also the
  non-perturbation proof: the accounting runs live while the trajectory stays
  bit-identical to an ungoverned run.
- `run_governed_accuracy.py --check-frozen` — the same for §3.3.

`smoke_test.py` in this bundle runs the cheapest version of the second one.

## What is NOT re-derivable from this bundle

Stated so the omissions are not mistaken for oversights:

- **Device-resident timings (§3.5, second paragraph).** Measured on an NVIDIA
  RTX 4090; the CSVs are here, the hardware is not. Every other number in the
  paper comes from the single CPU machine described in the README.
- **The full-FEM reference (§3.4).** The comparison CSVs are here; regenerating
  them needs the unreduced FEM harness and hours of compute, so this bundle
  ships the results rather than the means to reproduce them cheaply.
- **The video's rendered frames.** `teaser_video.mp4` is rendered from frozen
  traces; the traces are large binaries and are not bundled.
"""


def build_readme(copied: list[tuple[str, str]]) -> str:
    groups = "\n".join(
        f"\n### {g}\n" + "\n".join(f"- `data/{f}`" for gg, f in copied if gg == g)
        for g in BUNDLE if any(gg == g for gg, _ in copied))
    spec = os.path.join(X1, "scene_spec.md")
    spec_md = open(spec).read() if os.path.isfile(spec) else "(not generated)\n"
    return f"""# Supplementary material

Anonymous submission. This bundle contains the source, the scene specification,
the frozen results-ledger excerpts, and the raw data behind every number in the
paper, plus the supplementary video.

```
README.md              this file
CLAIMS_INDEX.md        every results section -> data file -> command
LEDGER_EXCERPTS.md     the frozen ledger entries (command, commit, machine)
data/                  raw CSVs and their .config.json manifests
code_snapshot.zip      the source needed to re-derive them
smoke_test.py          clean-unpack check (see §4)
requirements-freeze.txt
teaser_video.mp4       the supplementary video (see §5)
SHA256SUMS
```

Commit identifiers read `<commit>` throughout: a searchable hash would identify
the authors. `code_snapshot.zip` is the exact source state those commits name.

## 1. Machine, versions, and what is exact

Every solver-behaviour measurement was produced on a single machine — **Apple
M4, CPU only, CPython 3.12, float64, arm64** — running serially. The one
exception is the device-resident timing paragraph (NVIDIA RTX 4090), reported
separately and labelled as such in the paper.

We do not mix machines, and the reason bears on reproducing this work:
**chaotic contact stacks diverge across architectures under floating-point
reassociation.** The printed digits are exact on arm64 and should be expected
to differ on x86-64 — in a recorded instance, three contact tests and one
scene's standing-pillar outcome differed between the two. What is portable is
the *qualitative* result: which host violates the bound, by how many orders of
magnitude, and that the violation decays with iteration count. `smoke_test.py`
therefore asserts qualitatively and prints the digits for comparison.

Package versions are pinned in `requirements-freeze.txt`.

## 2. Scene specification

Every value below is read from the scene-builder signatures and from a built
solver, not transcribed by hand.

{spec_md}

## 3. Data

`CLAIMS_INDEX.md` maps each of these to the paper claim it supports and the
command that produced it.
{groups}

## 4. Reproducing

Unpack the snapshot and run the smoke test:

```sh
unzip code_snapshot.zip -d code_snapshot
python -m venv .venv && .venv/bin/pip install -r requirements-freeze.txt
.venv/bin/python smoke_test.py
```

It builds one scene from source and re-derives one cell of the 24-cell sweep on
all three hosts — the paper's central contrast in miniature — asserting the
qualitative outcome and printing the digits.

Every harness in `benchmarks/paper_eval/` is measurement-only: it imports the
scenes and solvers read-only and sets each knob at runtime. None modifies solver
source, and each neuters the governor's actuator (`passivity_gamma` forced to
1.0) so the reservoir accounting runs live while the trajectory stays
bit-identical to an ungoverned run. That non-perturbation property is asserted,
not assumed: the ablation's two base rows reproduce the frozen matrix ratios
exactly (119534 and 6333.22).

Full invocations are listed with each entry in `LEDGER_EXCERPTS.md`.

## 5. Video

`teaser_video.mp4` (44.8 s, 1920x1080, H.264, no audio) shows three arms at the
canonical shelf cell: ungoverned, governed, and the position-based host's own
high-iteration self-reference (500x1), at identical camera and true scale. It
was rendered headlessly from frozen traces — no interactive capture — by
`benchmarks/paper_fig/make_teaser_video.py`.

It is deliberately not only a success reel. The steel-board case shows the
governed run tracking the reference closely; the soft-board case that follows
shows the same bound suppressing legitimate motion, captioned *bounded, but not
faithful*, and the closing card states what the paper claims and what it does
not.

## 6. Verifying this bundle

```sh
shasum -a 256 -c SHA256SUMS
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
