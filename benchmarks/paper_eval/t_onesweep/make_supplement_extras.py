#!/usr/bin/env python3
"""Rebuild supplement_onesweep/ and add the scene-parameter tables (NEW script).

Edits no tracked harness file. It imports make_supplement.py, runs it verbatim so
the base package is rebuilt and its own anonymity gate is exercised, then adds the
scene-parameter artefacts this pass produced:

  code/t_onesweep/dump_scene_params.py   the extraction script, anonymized
  data/scene_params_cells.csv            28 rows: the 27 shipped-row cells and
                                         the Fig. 1 teaser scene
  data/scene_params_modes.csv            72 rows: per-mode m_i, omega_i, zeta_i,
                                         U_i, a_i, b_i for all four scenes
  data/scene_params.config.json          the run manifest

and finally re-runs make_supplement's own FORBIDDEN scan over the WHOLE package
and regenerates SHA256SUMS, so the shipped digests match the shipped bytes.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_supplement_extras.py
"""
from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import make_supplement as MS          # noqa: E402

OUT = MS.OUT

EXTRA_CODE = ["dump_scene_params.py"]
EXTRA_DATA = ["scene_params_cells.csv", "scene_params_modes.csv",
              "scene_params.config.json"]

EXTRA_MAP = [
    ("scene parameters of every shipped-row cell: M, h, alpha-tilde, w_r, "
     "sum a_i, L, rho and rho_mid for 3 scenes x 9 stiffness scales, plus the "
     "Fig. 1 teaser scene", "scene_params_cells.csv"),
    ("per-mode modal parameters at stiffness scale 1: m_i, k_i, omega_i, "
     "zeta_i, the contact-row shape value U_i, a_i = U_i^2/m_i and "
     "b_i = (omega_i h)^2", "scene_params_modes.csv"),
]

EXTRA_README = """

## Scene parameters

`data/scene_params_cells.csv` and `data/scene_params_modes.csv` carry every
parameter the closed forms need, so each shipped-row number in the paper can be
recomputed from the package. `code/t_onesweep/dump_scene_params.py` regenerates
both from the same scene builders the shipped-row runs use (it needs the
production host, like T4, T6 and T9).

Conventions used in both files:

- The modal bases are mass-normalized, so `m_i = 1` kg for every mode and
  `a_i = U_i^2`, where `U_i` is the mode's shape value at the contact row.
- `w_r` is the row-visible rigid mobility `1/M + j_a^T I^-1 j_a`; the column
  `M_row_kg` is `1/w_r` and is smaller than the impactor mass because of the
  corner lever arm.
- `a_tilde = alpha/h^2` with `alpha` the solver's support compliance, `1e-8` m/N
  in every scene.
- `rho = L/(w_m + 2 a_tilde)` with `w_m = w_r + sum a_i` and `L = sum a_i b_i`
  is the `kappa = 1` index; `rho_mid = (L + 2 sum a_i)/(w_r + 2 a_tilde)` is the
  `kappa = 2` index the shipped symplectic host is governed by.
- The stiffness sweep is zeta-preserving: at scale `s`, `omega_i(s) =
  sqrt(s) omega_i(1)` while `m_i`, `U_i` and `zeta_i` are unchanged. The modes
  table is therefore written once, at `s = 1`.
- The 27 shipped-row cells run at one iteration and one substep, so
  `h = 1/120` s; the Fig. 1 teaser runs at one iteration and eight substeps, so
  `h = 1/960` s.
"""


def _sha256sums():
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


def main():
    print("== base package ==")
    rc = MS.main()
    if rc != 0:
        print("base make_supplement.py FAILED its own gate; nothing added")
        return rc

    print("\n== scene-parameter extras ==")
    added = []
    for name in EXTRA_CODE:
        src = os.path.join(HERE, name)
        if not os.path.exists(src):
            print("  MISSING (abort): %s" % name)
            return 2
        with open(src, encoding="utf-8") as fh:
            body = MS.anonymize(fh.read())
        dst = os.path.join(OUT, "code", "t_onesweep", name)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(body)
        added.append(dst)
        print("  code/t_onesweep/%s" % name)
    for name in EXTRA_DATA:
        src = os.path.join(HERE, "out", name)
        if not os.path.exists(src):
            print("  MISSING (abort): out/%s" % name)
            return 2
        with open(src, encoding="utf-8") as fh:
            body = MS.anonymize(fh.read())
        dst = os.path.join(OUT, "data", name)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(body)
        added.append(dst)
        print("  data/%s" % name)

    # README: extend the number map, then append the conventions section.
    readme = os.path.join(OUT, "README.md")
    with open(readme, encoding="utf-8") as fh:
        text = fh.read()
    marker = "\n## Integrity\n"
    assert marker in text, "README layout changed; refusing to guess"
    extra_map = "".join("- %s\n  -> `data/%s`\n" % (c, f) for c, f in EXTRA_MAP)
    text = text.replace(marker, extra_map.rstrip("\n") + EXTRA_README + marker, 1)
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(text)
    added.append(readme)
    print("  README.md (number map + scene-parameter conventions)")

    # ---- anonymity gate over the WHOLE package --------------------------- #
    print("\n-- anonymity scan (whole package) --")
    leaks, scanned = [], 0
    for dirpath, _, filenames in os.walk(OUT):
        for n in sorted(filenames):
            p = os.path.join(dirpath, n)
            try:
                with open(p, encoding="utf-8") as fh:
                    body = fh.read()
            except (UnicodeDecodeError, ValueError):
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
    if leaks:
        print("  FAIL, author-identifying tokens present:")
        for p, t in leaks:
            print("    %s: %s" % (p, t))
        return 1
    print("  clean: no home path, username or author token in %d text files"
          % scanned)

    n = _sha256sums()
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fns in os.walk(OUT) for f in fns)
    print("\nsupplement_onesweep/: %d files, %.1f MB" % (n, total / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
