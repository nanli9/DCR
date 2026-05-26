"""Shared driver helper: looping a run matrix + capturing failures.

Each `scripts/benchmark/run_b<N>.py` builds a list of `(run_id, cli_args)`
tuples and hands it to `run_matrix()`. The helper:

- creates the run+log directories,
- invokes `scripts.run_one.run(...)` for each cell in-process (so a
  subprocess crash is avoided and exceptions land in a tight `try`),
- on any per-cell failure, writes a `status: failed` summary stub and
  appends the traceback to `<logs_dir>/<run_id>.log` (per §6.4),
- writes the per-benchmark manifest at the end via
  `scripts.write_manifest.build_manifest`.

Per the user-approved plan: "the §6.5 wall is ~30 min; on this hardware
it is closer to ~90 min."
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# Ensure the scripts package is importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import run_one
from scripts.write_manifest import build_manifest


def _redirect_stdout_to(path: Path):
    """Context manager that mirrors stdout+stderr into a log file."""
    class _Tee:
        def __init__(self, *streams):
            self.streams = streams

        def write(self, data):
            for s in self.streams:
                s.write(data)
                s.flush()
            return len(data)

        def flush(self):
            for s in self.streams:
                s.flush()
    import contextlib

    @contextlib.contextmanager
    def cm():
        path.parent.mkdir(parents=True, exist_ok=True)
        log = open(path, "w")
        try:
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout = _Tee(old_out, log)
            sys.stderr = _Tee(old_err, log)
            try:
                yield
            finally:
                sys.stdout, sys.stderr = old_out, old_err
        finally:
            log.close()

    return cm()


def run_matrix(
    *,
    benchmark: str,
    title: str,
    runs_dir: Path,
    logs_dir: Path,
    manifest_path: Path,
    cells: list[dict[str, Any]],
    only: set[str] | None = None,
) -> int:
    """Execute one row per cell and write the per-benchmark manifest.

    Each cell is a dict that becomes the kwargs of an argparse.Namespace
    handed to `run_one.run()`. Missing fields default to the same values
    `run_one._build_parser()` would set. Returns the number of failed runs.

    `only`, if given, restricts execution to cells whose run_id is in
    the set (used by §6.2 dry-run gate).
    """
    runs_dir = Path(runs_dir)
    logs_dir = Path(logs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    n_total = len(cells)
    n_failed = 0
    print(f"[{benchmark}] {title} — {n_total} runs")
    for i, cell in enumerate(cells):
        run_id = cell["run_id"]
        if only is not None and run_id not in only:
            continue
        # Fill in the defaults `run_one._build_parser()` would set.
        defaults = dict(
            scene=cell["scene"], mode=cell["mode"],
            flavor=cell.get("flavor", "rest"),
            eta=cell.get("eta", 0.95),
            beta=cell.get("beta", 0.25),
            duration=cell.get("duration", 4.0),
            h=cell.get("h", None),
            damping_scale=cell.get("damping_scale", 1.0),
            restitution=cell.get("restitution", 0.15),
            material=cell.get("material", None),
            causal_gating=cell.get("causal_gating", False),
            run_id=run_id,
            out_dir=runs_dir,
            benchmark=benchmark,
            log_paper_side_channel=cell.get(
                "log_paper_side_channel", False),
            log_impulse_decomposition=cell.get(
                "log_impulse_decomposition", False),
            log_timing=cell.get("log_timing", False),
            late_phase_window_s=cell.get("late_phase_window_s", None),
        )
        args = argparse.Namespace(**defaults)
        log_path = logs_dir / f"{run_id}.log"
        print(f"  [{i+1}/{n_total}] {run_id}", flush=True)
        try:
            with _redirect_stdout_to(log_path):
                run_one.run(args)
        except Exception as exc:
            n_failed += 1
            with open(log_path, "a") as lf:
                lf.write("\n--- TRACEBACK ---\n")
                traceback.print_exc(file=lf)
            run_one.write_failed_summary(
                runs_dir, run_id, benchmark,
                args.scene, args.mode, args.flavor,
                {"eta": args.eta, "beta": args.beta,
                 "duration_s": args.duration,
                 "damping_scale": args.damping_scale,
                 "material": args.material or "default",
                 "causal_gating": args.causal_gating},
                exc,
            )
            print(f"    FAILED: {type(exc).__name__}: {exc}", flush=True)

    # Per-benchmark manifest.
    manifest = build_manifest(
        benchmark=benchmark, title=title,
        runs_dir=runs_dir, logs_dir=logs_dir,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[{benchmark}] manifest → {manifest_path} "
          f"({n_total - n_failed}/{n_total} ok)")
    return n_failed
