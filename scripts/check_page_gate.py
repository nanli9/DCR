#!/usr/bin/env python3
"""Page gate v2 for the MIG 2026 short paper (plan docs/mig2026_short_paper_plan.md §8.2).

The MIG CFP allows 4-6 content pages EXCLUDING references. The C-round gate was
a manual `grep` over the build log; it was skipped for a "trivial" one-line
abstract edit (commit `cbf57b6`) and the paper silently spilled to 7 pages with
the body ending on p. 7. This script exists so the check is scriptable, cheap,
and unskippable.

It reads build artifacts only -- never the log's human prose, never grep:

  * body-end page  <- `\\newlabel{bodyend}` in build/main_short.aux
                      (a permanent `\\label{bodyend}` sits immediately before
                      `\\bibliographystyle` in main_short.tex)
  * total pages    <- "Output written on ... (N pages" in build/main_short.log
  * overfull boxes <- re.finditer(r'Overfull[^\\n]*') over the log

Usage (from the paper worktree, after latexmk):

    python ../scripts/check_page_gate.py
    python ../scripts/check_page_gate.py --max-body-page 6 --max-overfull 0

Exit status 0 = gate green, 1 = gate red, 2 = artifacts missing/unparseable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# `\newlabel{bodyend}{{<ref>}{<page>}{<title>}{<anchor>}{}}` -- hyperref writes
# five groups, plain LaTeX two; the page is always the second. Match lazily so a
# nested-brace title cannot swallow the page field.
_NEWLABEL = re.compile(
    r"\\newlabel\{(?P<name>[^}]*)\}\{\{(?P<ref>[^{}]*)\}\{(?P<page>[^{}]*)\}"
)
_OUTPUT_PAGES = re.compile(r"Output written on .*?\((?P<pages>\d+) pages?")
_OVERFULL = re.compile(r"Overfull[^\n]*")


def _read(path: Path) -> str:
    if not path.is_file():
        sys.stderr.write(f"gate: missing build artifact {path}\n")
        sys.stderr.write("gate: run `latexmk -pdf main_short.tex` first\n")
        raise SystemExit(2)
    return path.read_text(encoding="utf-8", errors="replace")


def body_end_page(aux: str, label: str) -> int:
    for m in _NEWLABEL.finditer(aux):
        if m.group("name") == label:
            page = m.group("page").strip()
            if not page.isdigit():
                sys.stderr.write(
                    f"gate: \\label{{{label}}} page field is {page!r}, not a number\n"
                )
                raise SystemExit(2)
            return int(page)
    sys.stderr.write(f"gate: no \\newlabel{{{label}}} in the .aux\n")
    sys.stderr.write(
        f"gate: main_short.tex must keep `\\label{{{label}}}` immediately before "
        "`\\bibliographystyle` (two builds may be needed after adding it)\n"
    )
    raise SystemExit(2)


def total_pages(log: str) -> int:
    matches = _OUTPUT_PAGES.findall(log)
    if not matches:
        sys.stderr.write("gate: no 'Output written on ... (N pages' line in the .log\n")
        raise SystemExit(2)
    return int(matches[-1])


def overfull_lines(log: str) -> list[str]:
    return [m.group(0).strip() for m in _OVERFULL.finditer(log)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--build-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "paper" / "build",
        help="directory holding main_short.aux / .log (default: ../paper/build)",
    )
    ap.add_argument("--stem", default="main_short", help="job name (default: main_short)")
    ap.add_argument("--label", default="bodyend", help="body-end label (default: bodyend)")
    ap.add_argument(
        "--max-body-page",
        type=int,
        default=6,
        help="CFP content-page limit, references excluded (default: 6)",
    )
    ap.add_argument(
        "--max-overfull",
        type=int,
        default=0,
        help="tolerated Overfull boxes (default: 0)",
    )
    ap.add_argument(
        "--show-overfull",
        type=int,
        default=10,
        help="how many Overfull lines to print when the gate fails (default: 10)",
    )
    args = ap.parse_args(argv)

    aux = _read(args.build_dir / f"{args.stem}.aux")
    log = _read(args.build_dir / f"{args.stem}.log")

    body = body_end_page(aux, args.label)
    total = total_pages(log)
    overfull = overfull_lines(log)

    failures: list[str] = []
    if body > args.max_body_page:
        failures.append(
            f"body ends on p. {body} > {args.max_body_page} "
            "(CFP: 4-6 content pages excluding references)"
        )
    if len(overfull) > args.max_overfull:
        failures.append(f"{len(overfull)} Overfull boxes > {args.max_overfull} tolerated")

    mark = "FAIL" if failures else "PASS"
    print(f"[{mark}] {args.stem}: body ends p. {body}, {total} pages total, "
          f"{len(overfull)} overfull")

    if failures:
        for f in failures:
            print(f"  - {f}")
        for line in overfull[: args.show_overfull]:
            print(f"    {line}")
        if len(overfull) > args.show_overfull:
            print(f"    ... and {len(overfull) - args.show_overfull} more")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
