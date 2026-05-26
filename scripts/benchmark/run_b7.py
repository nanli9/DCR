#!/usr/bin/env python3
"""B7 — Timestep h sweep (extension beyond `benchmark/BENCHMARK_PROMPT.md`).

User-requested extension on 2026-05-26: sweep the rigid timestep h to
characterize how the energy injection, §15 invariant, runtime, and
qualitative dynamics depend on it. Five h values, two scenes, two modes
→ 20 runs. flavor=barbic_james (rest for coevoet). β/η/duration default.
Each run also writes `_timing.csv` so cost-vs-h can be plotted alongside
B6's per-mode cost profile.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark._driver import run_matrix


# Five h values spanning two decades. 5e-3 is the current scene-builder
# default; 1e-2 is the BENCHMARK_PROMPT.md §4 default. 1e-3 stress-tests
# stability; 2.5e-2 stress-tests coarse-step admissibility.
B7_HS = [1e-3, 2.5e-3, 5e-3, 1e-2, 2.5e-2]
B7_MODES = ["coevoet", "energy_prescribed_patch"]
B7_SCENES = ["truck", "shelf"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scenes", default=",".join(B7_SCENES))
    p.add_argument("--duration", type=float, default=4.0)
    args = p.parse_args(argv)

    cells = []
    for scene in args.scenes.split(","):
        for mode in B7_MODES:
            flavor = "rest" if mode == "coevoet" else "barbic_james"
            for h in B7_HS:
                cells.append({
                    "run_id": f"{scene}__{mode}__h{h:g}",
                    "scene": scene,
                    "mode": mode,
                    "flavor": flavor,
                    "h": h,
                    "duration": args.duration,
                    "log_timing": True,
                })

    failed = run_matrix(
        benchmark="B7",
        title="Timestep h sweep (extension)",
        runs_dir=_REPO_ROOT / "benchmark/runs/B7_h_sweep",
        logs_dir=_REPO_ROOT / "benchmark/logs/B7",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B7_manifest.json",
        cells=cells,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
