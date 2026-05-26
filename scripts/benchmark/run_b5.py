#!/usr/bin/env python3
"""B5 — Material sensitivity (wood vs steel).

`benchmark/BENCHMARK_PROMPT.md` §5.5. 2 runs: truck × energy_prescribed_patch
× barbic_james × β=0.70 × causal_gating=True × duration=8 s, with the
slab material toggled between wood and steel. Per-body summary blocks
gain a `late_phase` block over the last 3 s (`late_phase_window_s=3.0`).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.benchmark._driver import run_matrix


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--duration", type=float, default=8.0)
    args = p.parse_args(argv)

    cells = []
    for material in ("wood", "steel"):
        cells.append({
            "run_id": f"truck__patch__bj__{material}",
            "scene": "truck",
            "mode": "energy_prescribed_patch",
            "flavor": "barbic_james",
            "beta": 0.70,
            "damping_scale": 1.0,
            "causal_gating": True,
            "duration": args.duration,
            "material": material,
            "late_phase_window_s": 3.0,
        })

    failed = run_matrix(
        benchmark="B5",
        title="Material sensitivity: wood vs steel",
        runs_dir=_REPO_ROOT / "benchmark/runs/B5_material",
        logs_dir=_REPO_ROOT / "benchmark/logs/B5",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B5_manifest.json",
        cells=cells,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
