#!/usr/bin/env python3
"""B3 — β parameter sweep.

`benchmark/BENCHMARK_PROMPT.md` §5.3. 45 runs: scenes ×
{energy_prescribed, energy_prescribed_point_impulse, energy_prescribed_patch}
× β ∈ {0.10, 0.25, 0.50, 0.75, 1.00}. flavor=barbic_james, η=0.95 fixed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark._driver import run_matrix


B3_MODES = [
    "energy_prescribed",
    "energy_prescribed_point_impulse",
    "energy_prescribed_patch",
]
B3_BETAS = [0.10, 0.25, 0.50, 0.75, 1.00]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scenes", default="ledge,truck,shelf")
    p.add_argument("--duration", type=float, default=4.0)
    args = p.parse_args(argv)

    cells = []
    for scene in args.scenes.split(","):
        for mode in B3_MODES:
            for beta in B3_BETAS:
                cells.append({
                    "run_id": f"{scene}__{mode}__b{beta:g}",
                    "scene": scene,
                    "mode": mode,
                    "flavor": "barbic_james",
                    "beta": beta,
                    "duration": args.duration,
                })

    failed = run_matrix(
        benchmark="B3",
        title="β sweep across modes × scenes",
        runs_dir=_REPO_ROOT / "benchmark/runs/B3_beta_sweep",
        logs_dir=_REPO_ROOT / "benchmark/logs/B3",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B3_manifest.json",
        cells=cells,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
