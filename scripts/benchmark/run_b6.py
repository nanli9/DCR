#!/usr/bin/env python3
"""B6 — Cost / runtime overhead.

`benchmark/BENCHMARK_PROMPT.md` §5.6. 12 runs: 3 scenes × 4 modes
{coevoet, energy_prescribed, energy_prescribed_point_impulse,
energy_prescribed_patch}. flavor=barbic_james (rest for coevoet).
All runs write `_timing.csv` (§2.5).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark._driver import run_matrix


B6_MODES = [
    "coevoet",
    "energy_prescribed",
    "energy_prescribed_point_impulse",
    "energy_prescribed_patch",
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scenes", default="ledge,truck,shelf")
    p.add_argument("--duration", type=float, default=4.0)
    args = p.parse_args(argv)

    cells = []
    for scene in args.scenes.split(","):
        for mode in B6_MODES:
            flavor = "rest" if mode == "coevoet" else "barbic_james"
            cells.append({
                "run_id": f"{scene}__{mode}",
                "scene": scene,
                "mode": mode,
                "flavor": flavor,
                "duration": args.duration,
                "log_timing": True,
            })

    failed = run_matrix(
        benchmark="B6",
        title="Runtime breakdown per scene × mode",
        runs_dir=_REPO_ROOT / "benchmark/runs/B6_runtime",
        logs_dir=_REPO_ROOT / "benchmark/logs/B6",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B6_manifest.json",
        cells=cells,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
