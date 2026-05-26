#!/usr/bin/env python3
"""Top-level orchestrator for the DCR follow-up benchmark suite.

Runs B1 → B7 in sequence (B7 is the user-added h-sweep extension), then
writes the top-level `benchmark/manifests/MANIFEST.json` (`benchmark/
BENCHMARK_PROMPT.md` §3.2). Prints a final summary table.

Reading: `benchmark/BENCHMARK_PROMPT.md` §6.5 estimates ~30 min on a
single workstation. On the dev machine this is closer to ~90 min at
h=5e-3 / B1–B6, plus 20 B7 runs. Use `--only B1,B2` etc. to scope.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


BENCHMARKS = [
    ("B1", "scripts.benchmark.run_b1"),
    ("B2", "scripts.benchmark.run_b2"),
    ("B3", "scripts.benchmark.run_b3"),
    ("B4", "scripts.benchmark.run_b4"),
    ("B5", "scripts.benchmark.run_b5"),
    ("B6", "scripts.benchmark.run_b6"),
    ("B7", "scripts.benchmark.run_b7"),
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--only", default=None,
                   help="Comma-separated benchmark IDs to run (e.g. B1,B3).")
    args = p.parse_args(argv)

    only = set(args.only.split(",")) if args.only else None
    started_at = time.time()
    results: list[tuple[str, int, float]] = []  # (id, rc, wall_s)
    for bid, mod in BENCHMARKS:
        if only is not None and bid not in only:
            continue
        print(f"\n========== {bid} ==========", flush=True)
        t0 = time.time()
        rc = subprocess.call([sys.executable, "-m", mod], cwd=_REPO_ROOT)
        wall = time.time() - t0
        results.append((bid, rc, wall))

    # Top-level manifest.
    print("\n========== top-level MANIFEST ==========", flush=True)
    subprocess.call([
        sys.executable, "-m", "scripts.write_top_manifest",
        "--manifests-dir", str(_REPO_ROOT / "benchmark/manifests"),
        "--out", str(_REPO_ROOT / "benchmark/manifests/MANIFEST.json"),
    ], cwd=_REPO_ROOT)

    # Final summary.
    total_wall = time.time() - started_at
    print("\n========== SUMMARY ==========")
    print(f"{'benchmark':<12} {'rc':>4} {'wall_s':>10}")
    for bid, rc, wall in results:
        flag = "OK" if rc == 0 else "FAIL"
        print(f"{bid:<12} {flag:>4} {wall:>10.1f}")
    print(f"{'total':<12} {'':>4} {total_wall:>10.1f}")
    return 0 if all(rc == 0 for _, rc, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
