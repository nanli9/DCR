#!/usr/bin/env python3
"""Per-benchmark manifest writer.

Globs `<runs-dir>/*_summary.json`, reads each, and emits the §3.1 manifest
JSON at `<out>`. The plotter reads ONLY the manifests; it never globs the
runs directory. So this script is the canonical end-of-benchmark step.

Failed runs (whose summary has `status == "failed"`) are included in the
manifest with that status + their failure reason so the plotter can skip
them with a warning per §3.1 / §6.4.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
from pathlib import Path


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return out
    except Exception:
        return "unknown"


def _file_path(runs_dir: Path, run_id: str, suffix: str) -> str | None:
    """Return relative path from repo root for an artifact, or None if missing."""
    repo_root = Path(__file__).resolve().parents[1]
    p = runs_dir / f"{run_id}{suffix}"
    if not p.exists():
        return None
    try:
        return str(p.resolve().relative_to(repo_root))
    except ValueError:
        return str(p.resolve())


def build_manifest(benchmark: str, title: str, runs_dir: Path,
                   logs_dir: Path | None = None) -> dict:
    runs_dir = Path(runs_dir)
    summary_paths = sorted(runs_dir.glob("*_summary.json"))
    entries = []
    for sp in summary_paths:
        with open(sp) as f:
            summary = json.load(f)
        run_id = summary.get("run_id", sp.stem.removesuffix("_summary"))
        files = {
            "energy_csv": _file_path(runs_dir, run_id, "_energy.csv"),
            "trajectory_csv": _file_path(runs_dir, run_id, "_trajectory.csv"),
            "summary_json": _file_path(runs_dir, run_id, "_summary.json"),
        }
        # Optional logs (B2 / B6).
        impulse = _file_path(runs_dir, run_id, "_impulse.csv")
        if impulse:
            files["impulse_csv"] = impulse
        timing = _file_path(runs_dir, run_id, "_timing.csv")
        if timing:
            files["timing_csv"] = timing
        if logs_dir:
            log_p = Path(logs_dir) / f"{run_id}.log"
            if log_p.exists():
                files["log"] = str(log_p.resolve().relative_to(
                    Path(__file__).resolve().parents[1]))

        entry = {
            "run_id": run_id,
            "scene": summary.get("scene", ""),
            "mode": summary.get("mode", ""),
            "flavor": summary.get("flavor", ""),
            "params": summary.get("params", {}),
            "files": files,
            "status": summary.get("status", "ok"),
        }
        if summary.get("status") == "failed":
            entry["failure_reason"] = summary.get("failure_reason", "")
        entries.append(entry)

    manifest = {
        "benchmark_id": benchmark,
        "title": title,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "n_runs": len(entries),
        "runs": entries,
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Build per-benchmark manifest JSON (§3.1).")
    p.add_argument("--benchmark", required=True,
                   help="Benchmark id (e.g. B1, B2, ...).")
    p.add_argument("--title", default="",
                   help="Human-readable title for the manifest.")
    p.add_argument("--runs-dir", required=True, type=Path)
    p.add_argument("--logs-dir", default=None, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)

    manifest = build_manifest(
        benchmark=args.benchmark, title=args.title or args.benchmark,
        runs_dir=args.runs_dir, logs_dir=args.logs_dir,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[write_manifest] {args.benchmark}: "
          f"{manifest['n_runs']} runs → {args.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
