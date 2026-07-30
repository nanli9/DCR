#!/usr/bin/env python3
"""Build the blind evaluation set: 7 verified MIG short papers + 1 candidate manuscript.

Lowest-common-denominator evidence: TITLE + ABSTRACT only for every entry, because
2 of the 7 corpus papers are abstract-only. No full-text set is built.
"""
import json
import random
import re
import textwrap
from pathlib import Path

ROOT = Path("/Users/nan/Desktop/DCR/MIG_short")
MANIFEST = ROOT / "corpus_manifest.json"

# ---------------------------------------------------------------------------
# The candidate manuscript. Title and abstract taken verbatim from
# /Users/nan/Desktop/DCR/paper/onesweep_short.tex (\title, \begin{abstract}),
# cross-checked against page 1 of onesweep_short.pdf. LaTeX math is transcribed
# to plain-text Unicode; no word is added, removed, or paraphrased.
# ---------------------------------------------------------------------------
MS_TITLE = (
    "A Per-Row Danger Index and a Reconstruction-Matched Effective Mass for "
    "One-Sweep Passive Contact Coupling in Fixed-Budget Position-Based Solvers"
)

MS_ABSTRACT = (
    "Position-based engines resolve contacts under a small, fixed local iteration "
    "budget, and a cheap way to make a stiff prop ring is to carry a few global modal "
    "amplitudes as extra unknowns in the unilateral contact row. At a few iterations "
    "per substep such a row can add energy rather than remove it. That it happens is "
    "known and not our claim; practitioner accounts report it as a tuning hazard "
    "without a framework. We supply that framework for the shared contact-to-modal "
    "row, parameterized by the host's velocity reconstruction q̇+ = κ Δq/h, "
    "which one cold read-back of Δq/h against 2Δq/h identifies. A pre-solve "
    "danger index ρ, a ratio of two quadratic forms a host already assembles, "
    "predicts whether one mass-only sweep injects; the sign boundary is "
    "κ² + (ωh)² = 2 + m/M. Charging the restorative block at the "
    "reconstruction-matched operator κ² M_c + h² K_c, in both the "
    "denominator and the correction, makes one sweep passive for any κ ≠ 0 "
    "(rigid read-back at Δz/h) and any number of coupled coordinates, and at "
    "κ = 1 with ζ = 0 it reproduces the converged implicit step exactly. "
    "Reconstruction dependence is a main finding: the mass-only and "
    "backward-Euler-shaped weights inject at low stiffness on the shipped symplectic "
    "host (κ = 2); the matched one does not. The closed forms are machine-checked "
    "to 10⁻¹² relative on a 58,081-cell phase map and a nonmodal "
    "mass-spring collapse, and in exact rational arithmetic for the operator identity; "
    "on a shipped contact row the matched weight is passive on all 27 cells, and a "
    "three-arm weight swap takes the modal-energy overrun count from 8 of 24 to 0. "
    "Every theorem is confined to one sweep from a cold start with e = 0 and one "
    "normal-only row."
)

# ---------------------------------------------------------------------------
# De-identification rules applied UNIFORMLY to every entry.
# ---------------------------------------------------------------------------
# 1. Typography normalization: curly quotes -> straight, spaced en/em dash -> " - ",
#    non-breaking space -> space. Applied to all 8 entries so no entry stands out
#    by character set.
TYPO = {
    "‘": "'", "’": "'",           # curly single quotes
    "“": '"', "”": '"',           # curly double quotes
    " ": " ",                          # nbsp
    "–": "-", "—": "-",           # en dash, em dash
    "−": "-",                          # minus sign
}

# 2. In-text year markers. The only one present in any abstract is a citation year;
#    the named prior work is kept (it is a substantive calibration signal) but the
#    year is dropped so no entry can be dated from its own text.
YEAR_BRACKET = re.compile(r"\s*\[\s*(19|20)\d{2}\s*\]")


def normalize(s: str) -> str:
    for a, b in TYPO.items():
        s = s.replace(a, b)
    s = YEAR_BRACKET.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main() -> None:
    man = json.loads(MANIFEST.read_text())

    entries = []
    for p in man["papers"]:
        entries.append({
            "source": "corpus",
            "real_id": p["id"],
            "title": normalize(p["title"]),
            "abstract": normalize(p["abstract"]),
            "year": p["year"],
            "doi": p["doi"],
            "what_we_have": p["what_we_have"],
        })
    entries.append({
        "source": "manuscript",
        "real_id": "candidate_manuscript",
        "title": normalize(MS_TITLE),
        "abstract": normalize(MS_ABSTRACT),
        "year": None,
        "doi": None,
        "what_we_have": "full_text (deliberately reduced to title+abstract for parity)",
    })

    # -------------------------------------------------------------------
    # Ordering: seeded shuffle, rejected until the manuscript sits strictly
    # inside the list AND the order is not sorted by year / id / manifest
    # position (checked below). Seed is fixed only so the build is
    # reproducible; it carries no information about identity.
    # -------------------------------------------------------------------
    rng = random.Random(20260730)
    for _ in range(10000):
        order = entries[:]
        rng.shuffle(order)
        idx = next(i for i, e in enumerate(order) if e["source"] == "manuscript")
        # strictly interior, and away from both ends (positions 3..6 of 8) so that
        # neither "first" nor "last" nor "the one at the edge" is a usable hint
        if not (2 <= idx <= len(order) - 3):
            continue
        years = [e["year"] for e in order if e["year"] is not None]
        if years == sorted(years) or years == sorted(years, reverse=True):
            continue
        # no two same-source-file neighbours clustering by availability
        avail = [e["what_we_have"].startswith("abstract_only") for e in order]
        if avail == sorted(avail) or avail == sorted(avail, reverse=True):
            continue
        break
    else:
        raise SystemExit("no acceptable ordering found")

    for i, e in enumerate(order, start=1):
        e["pid"] = f"P{i:02d}"

    ms_pid = next(e["pid"] for e in order if e["source"] == "manuscript")

    # -------------------------------------------------------------------
    # blind_set.md - the ONLY file the rankers see.
    # -------------------------------------------------------------------
    lines = [
        "# Blind Evaluation Set",
        "",
        f"{len(order)} entries, each given as title and abstract only, in a uniform format.",
        "Authors, affiliations, venue, dates, identifiers, and provenance have been removed",
        "from every entry, and typography has been normalized. The order is arbitrary.",
        "",
        "---",
        "",
    ]
    for e in order:
        lines.append(f"## {e['pid']}")
        lines.append("")
        lines.append(f"**Title.** {e['title']}")
        lines.append("")
        lines.append("**Abstract.** " + e["abstract"])
        lines.append("")
        lines.append("---")
        lines.append("")
    (ROOT / "blind_set.md").write_text("\n".join(lines).rstrip() + "\n")

    # -------------------------------------------------------------------
    # blind_key.json - MUST NOT be shown to the rankers.
    # -------------------------------------------------------------------
    key = {
        "WARNING": "DO NOT GIVE THIS FILE TO THE RANKERS. It de-anonymizes blind_set.md.",
        "built": "2026-07-30",
        "n_entries": len(order),
        "evidence_level": "title+abstract for every entry (lowest common denominator; "
                          "2 of 7 corpus papers are abstract-only, so no full-text set was built)",
        "candidate_id": ms_pid,
        "mapping": [
            {
                "pid": e["pid"],
                "source": e["source"],
                "real_id": e["real_id"],
                "title": e["title"],
                "year": e["year"],
                "doi": e["doi"],
                "is_candidate": e["source"] == "manuscript",
            }
            for e in order
        ],
    }
    (ROOT / "blind_key.json").write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n")

    print(f"n_entries = {len(order)}   candidate = {ms_pid}")
    for e in order:
        wc = len(e["abstract"].split())
        tw = len(e["title"].split())
        flag = "  <-- CANDIDATE" if e["source"] == "manuscript" else ""
        print(f"  {e['pid']}  abs_words={wc:4d}  title_words={tw:2d}  {e['real_id']}{flag}")


if __name__ == "__main__":
    main()
