"""Per-step wall-clock timing log for the B6 runtime benchmark.

Writes the §2.5 timing CSV: one row per simulation step with a breakdown
of the wall time spent in each major phase of `DCRWorld.step()`:

    t_rigid_solve_ms        — rigid-body PGS solve
    t_modal_step_ms         — passive-coupler modal stepping (qdot kick,
                              passive_alpha, IIR sub-steps)
    t_deformed_normal_ms    — deformed-normal computation (patch_fit /
                              barbic_james / rest)
    t_distant_response_ms   — _compute_distant_response_* dispatch as a
                              whole (includes deformed-normal time)
    t_total_step_ms         — full step wall time

All times use `time.perf_counter_ns()` for monotonicity. Enable by
setting `world.enable_timing_log = True` and assigning a `TimingLog()`
instance — `scripts/run_one.py` does this when `--log-timing` is set.

The `t_modal_step_ms` and `t_deformed_normal_ms` columns are populated
by the coupler itself via small `time.perf_counter_ns()` calls around
its own steps; the world reads `coupler.last_timing_*` at end-of-step.
For non-instrumented modes / steps where the coupler didn't run, those
columns log 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TimingLogEntry:
    """One row of `<run_id>_timing.csv` (§2.5)."""
    step: int
    t: float
    t_rigid_solve_ms: float
    t_modal_step_ms: float
    t_deformed_normal_ms: float
    t_distant_response_ms: float
    t_total_step_ms: float


@dataclass
class TimingLog:
    entries: list[TimingLogEntry] = field(default_factory=list)

    def append(self, entry: TimingLogEntry) -> None:
        self.entries.append(entry)

    def __len__(self) -> int:
        return len(self.entries)

    def to_csv(self, path) -> None:
        """Write the §2.5 schema. Empty log → header-only file."""
        import csv
        from pathlib import Path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "step", "t",
                "t_rigid_solve_ms", "t_modal_step_ms",
                "t_deformed_normal_ms", "t_distant_response_ms",
                "t_total_step_ms",
            ])
            for e in self.entries:
                w.writerow([
                    e.step, f"{e.t:.6f}",
                    f"{e.t_rigid_solve_ms:.6f}",
                    f"{e.t_modal_step_ms:.6f}",
                    f"{e.t_deformed_normal_ms:.6f}",
                    f"{e.t_distant_response_ms:.6f}",
                    f"{e.t_total_step_ms:.6f}",
                ])
