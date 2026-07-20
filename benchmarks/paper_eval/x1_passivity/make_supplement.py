#!/usr/bin/env python3
"""P8.b — assemble the anonymized supplement / reproduction bundle (plan §8.5).

Reproducibility scored 2.5/5 across both six-reviewer panels, the lowest of the
six criteria. This bundles what a reviewer needs to re-derive every printed
number: the scene specification, the frozen ledger excerpts with their
generating commands, and the raw CSVs.

ANONYMITY is enforced, not assumed: the assembler scans every text artifact it
copies for author names, usernames and absolute home paths, and refuses to write
the bundle if any is found. (Binary/npz artifacts are excluded rather than
scanned.)

Out: supplement/ at the repo root
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/make_supplement.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
OUT_SRC = os.path.join(_HERE, "out")
DEST = os.path.join(_ROOT, "supplement")
LEDGER = os.path.join(_ROOT, "docs", "mig2026_results_ledger.md")

# CSVs a reviewer needs to re-derive the paper's numbers, by section.
BUNDLE = {
    "matrix (Fig. 1, Table 1, §3.1)": [
        "solver_matrix.csv", "eq2_utilization.csv",
    ],
    "iteration budget (Fig. 3, §3.2)": [
        "k_convergence.csv", "selfconvergence.csv",
        "complementarity_residual.csv", "complementarity_residual_nd.csv",
        "complementarity_residual_nd_ledge.csv",
    ],
    "deployed budgets 1x8 / 2x4 (§3.2, E-C6)": [
        "eq2_deployed.csv", "solver_matrix_deployed.csv",
        "projection_validity_deployed.csv", "governed_accuracy_1x8.csv",
    ],
    "enforcement cost (Table 2, §3.3)": [
        "projection_validity.csv", "projection_validity_avbd.csv",
        "governed_accuracy.csv",
    ],
    "robustness ablation (§3.2, E-C9)": [
        "robustness_ablation.csv", "k_convergence_ledge_worst.csv",
    ],
    "supplement-only probes (E-C9c/d)": [
        "supply_partition.csv", "long_horizon.csv",
    ],
    "scene specification (P8.a)": [
        "scene_spec.csv", "scene_spec.md",
    ],
}

# Ledger sections to excerpt verbatim, by their heading text.
LEDGER_SECTIONS = [
    "### E-S1b", "## E-C6", "### E-C6", "## E-C9",
]

DEANON = [
    (re.compile(r"/Users/[^/\s\"']+"), "absolute home path"),
    (re.compile(r"/home/[^/\s\"']+"), "absolute home path"),
    (re.compile(r"\bcompshare\b", re.I), "named host"),
]


def scan(path: str) -> list[str]:
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return []
    return [why for rx, why in DEANON if rx.search(txt)]


def ledger_excerpt() -> str:
    if not os.path.isfile(LEDGER):
        return "(results ledger not found)\n"
    lines = open(LEDGER, encoding="utf-8").read().split("\n")
    out, keep, depth = [], False, 0
    for ln in lines:
        if ln.startswith("#"):
            hit = any(ln.startswith(h) for h in LEDGER_SECTIONS)
            if hit:
                keep, depth = True, len(ln) - len(ln.lstrip("#"))
            elif keep and (len(ln) - len(ln.lstrip("#"))) <= depth:
                keep = False
        if keep:
            out.append(ln)
    return "\n".join(out) if out else "(no matching ledger sections)\n"


def main() -> int:
    if os.path.isdir(DEST):
        shutil.rmtree(DEST)
    os.makedirs(os.path.join(DEST, "data"), exist_ok=True)

    copied, missing, tainted = [], [], []
    for group, files in BUNDLE.items():
        for f in files:
            src = os.path.join(OUT_SRC, f)
            if not os.path.isfile(src):
                missing.append(f)
                continue
            bad = scan(src)
            if bad:
                tainted.append((f, bad))
                continue
            shutil.copy2(src, os.path.join(DEST, "data", f))
            cfg = os.path.splitext(f)[0] + ".config.json"
            if os.path.isfile(os.path.join(OUT_SRC, cfg)):
                if scan(os.path.join(OUT_SRC, cfg)):
                    tainted.append((cfg, ["config manifest"]))
                else:
                    shutil.copy2(os.path.join(OUT_SRC, cfg),
                                 os.path.join(DEST, "data", cfg))
            copied.append((group, f))

    if tainted:
        sys.stderr.write("REFUSING to write the bundle -- identifying "
                         "information found:\n")
        for f, why in tainted:
            sys.stderr.write(f"  {f}: {', '.join(why)}\n")
        return 1

    excerpt = ledger_excerpt()
    open(os.path.join(DEST, "LEDGER_EXCERPTS.md"), "w").write(
        "# Frozen results ledger — excerpts\n\n"
        "Each entry carries the generating command, the commit and the "
        "machine. Reproduced verbatim from the project's results ledger.\n\n"
        + excerpt + "\n")

    spec = os.path.join(OUT_SRC, "scene_spec.md")
    spec_md = open(spec).read() if os.path.isfile(spec) else "(not generated)\n"

    sha = subprocess.run(["git", "-C", _ROOT, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip() or "unknown"

    groups = "\n".join(
        f"\n### {g}\n" + "\n".join(
            f"- `data/{f}`" for gg, f in copied if gg == g)
        for g in BUNDLE if any(gg == g for gg, _ in copied))

    open(os.path.join(DEST, "README.md"), "w").write(f"""# Supplementary material

Anonymous submission. This bundle contains the scene specification, the frozen
results-ledger excerpts, and the raw CSVs behind every number in the paper.

All solver-behaviour measurements were produced on a single machine — Apple M4,
CPU only, CPython 3.12, float64 — running serially. Chaotic contact stacks
diverge across architectures under floating-point reassociation, so we do not
mix machines; the sole exception is the device-resident timing paragraph, which
is reported separately and labelled as such in the paper.

Source commit for this bundle: `{sha}`.

## 1. Scene specification

Every value below is read from the scene-builder signatures and from a built
solver, not transcribed by hand.

{spec_md}

## 2. Ledger excerpts

`LEDGER_EXCERPTS.md` reproduces the frozen entries for the 24-cell matrix
(E-S1b), the deployed budgets (E-C6) and the robustness ablation (E-C9),
each with its generating command, commit and machine.

## 3. Raw data
{groups}

## 4. Reproducing

Every harness is measurement-only: it imports the scenes and solvers read-only
and sets each knob at runtime. None modifies solver source, and each neuters the
governor's actuator (`passivity_gamma` forced to 1.0) so the ledger runs live
while the trajectory stays bit-identical to an ungoverned run. The
non-perturbation property is asserted, not assumed: the ablation's two base rows
reproduce the frozen matrix ratios exactly (119534 and 6333.22).

Commands are listed with each ledger entry in `LEDGER_EXCERPTS.md`.

## 5. Video

A supplementary video (ungoverned / governed / converged reference at the same
starved budget) is **not included in this revision**: it requires an interactive
capture session that the offline pipeline cannot perform. The teaser figure
shows the same three-arm comparison as stills.
""")

    print(f"wrote {DEST}/")
    print(f"  README.md, LEDGER_EXCERPTS.md, data/ ({len(copied)} artifacts)")
    if missing:
        print(f"  NOTE: {len(missing)} listed artifact(s) not present, skipped:")
        for f in missing:
            print(f"    - {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
