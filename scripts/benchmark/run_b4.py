#!/usr/bin/env python3
"""B4 — η parameter sweep.

`benchmark/BENCHMARK_PROMPT.md` §5.4. 6 runs: truck × energy_prescribed_patch
× barbic_james × β=0.25 × η ∈ {0.10, 0.25, 0.50, 0.75, 0.95, 1.00}.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark._driver import run_matrix


B4_ETAS = [0.10, 0.25, 0.50, 0.75, 0.95, 1.00]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--duration", type=float, default=4.0)
    args = p.parse_args(argv)

    cells = []
    for eta in B4_ETAS:
        cells.append({
            "run_id": f"truck__energy_prescribed_patch__eta{eta:g}",
            "scene": "truck",
            "mode": "energy_prescribed_patch",
            "flavor": "barbic_james",
            "beta": 0.25,
            "eta": eta,
            "duration": args.duration,
        })

    failed = run_matrix(
        benchmark="B4",
        title="η sweep at fixed scene/mode",
        runs_dir=_REPO_ROOT / "benchmark/runs/B4_eta_sweep",
        logs_dir=_REPO_ROOT / "benchmark/logs/B4",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B4_manifest.json",
        cells=cells,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
