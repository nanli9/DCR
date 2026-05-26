#!/usr/bin/env python3
"""B1 — Energy conservation: paper DCR vs follow-up.

`benchmark/BENCHMARK_PROMPT.md` §5.1. Six runs: for each scene
∈ {ledge, truck, shelf}, one paper-baseline (mode=coevoet, flavor=rest)
plus one passive (mode=energy_prescribed_patch, flavor=barbic_james).
Defaults otherwise.
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
    p.add_argument("--only", default=None,
                   help="Comma-separated subset of run_ids (for §6.2 gate).")
    p.add_argument("--scenes", default="ledge,truck,shelf",
                   help="Comma-separated scenes (default all three).")
    p.add_argument("--duration", type=float, default=4.0)
    args = p.parse_args(argv)

    only = set(args.only.split(",")) if args.only else None
    scenes = args.scenes.split(",")

    cells = []
    for scene in scenes:
        cells.append({
            "run_id": f"B1-paper-{scene}",
            "scene": scene,
            "mode": "coevoet",
            "flavor": "rest",
            "duration": args.duration,
            "log_paper_side_channel": True,
        })
        cells.append({
            "run_id": f"B1-passive-{scene}",
            "scene": scene,
            "mode": "energy_prescribed_patch",
            "flavor": "barbic_james",
            "duration": args.duration,
        })

    failed = run_matrix(
        benchmark="B1",
        title="Energy conservation: paper DCR vs follow-up",
        runs_dir=_REPO_ROOT / "benchmark/runs/B1_energy_conservation",
        logs_dir=_REPO_ROOT / "benchmark/logs/B1",
        manifest_path=_REPO_ROOT / "benchmark/manifests/B1_manifest.json",
        cells=cells,
        only=only,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
