#!/usr/bin/env python3
"""Top-level MANIFEST.json writer (`benchmark/BENCHMARK_PROMPT.md` §3.2).

Globs `<manifests-dir>/B*_manifest.json`, reads each one's status and
run count, and emits `MANIFEST.json` listing all benchmarks. The plotter
reads ONLY this file to discover the per-benchmark manifests.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
from pathlib import Path


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _repo_relative(path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return str(path.resolve())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Build top-level MANIFEST.json (§3.2).")
    p.add_argument("--manifests-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--repo", default="",
                   help="Optional repo URL embedded in MANIFEST.")
    args = p.parse_args(argv)

    manifests = sorted(args.manifests_dir.glob("B*_manifest.json"))
    benchmarks = []
    for mp in manifests:
        with open(mp) as f:
            m = json.load(f)
        bid = m.get("benchmark_id", mp.stem.split("_")[0])
        # Status: "complete" if every run has status ok; else "partial".
        statuses = {r.get("status", "ok") for r in m.get("runs", [])}
        if statuses == {"ok"} or not statuses:
            status = "complete"
        elif "failed" in statuses:
            status = "partial"
        else:
            status = "complete"
        benchmarks.append({
            "id": bid,
            "manifest": _repo_relative(mp),
            "status": status,
            "n_runs": m.get("n_runs", 0),
        })

    top = {
        "schema_version": "1.0",
        "repo": args.repo,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "benchmarks": benchmarks,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(top, f, indent=2)
    print(f"[write_top_manifest] {len(benchmarks)} benchmarks → {args.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
