#!/usr/bin/env python3
"""B2 — Deformed normal comparison (rest / patch_fit / Barbič-James).

`benchmark/BENCHMARK_PROMPT.md` §5.2. 15 runs: 3 scenes × 5 cells.
All runs additionally write `_impulse.csv` (§2.4).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark._driver import run_matrix


B2_CELLS_PER_SCENE = [
    # (mode, flavor) — keys match `benchmark/BENCHMARK_PROMPT.md` §5.2.
    ("coevoet", "rest"),
    ("energy_prescribed_point_impulse", "rest"),
    ("energy_prescribed_point_impulse", "patch_fit"),
    ("energy_prescribed_point_impulse", "barbic_james"),
    ("energy_prescribed_patch", "barbic_james"),
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scenes", default="ledge,truck,shelf")
    p.add_argument("--duration", type=float, default=4.0)
    args = p.parse_args(argv)

    cells = []
    for scene in args.scenes.split(","):
        for mode, flavor in B2_CELLS_PER_SCENE:
            cells.append({
                "run_id": f"{scene}__{mode}__{flavor}",
                "scene": scene,
                "mode": mode,
                "flavor": flavor,
                "duration": args.duration,
                "log_impulse_decomposition": True,
            })

    failed = run_matrix(
        benchmark="B2",
        title="Deformed normal: rest / patch_fit / barbic_james",
        runs_dir=_REPO_ROOT / "benchmark/runs/B2_deformed_normal",
        logs_dir=_REPO_ROOT / "benchmark/logs/B2",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B2_manifest.json",
        cells=cells,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
