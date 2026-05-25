"""Benchmark scoring primitives.

Pass/fail rubric for the rigid-body trajectories produced by
`scripts/run_scenes.py::simulate`. See `benchmark/PATCH_MODE_BENCHMARK.md`
question Q2 for the design discussion.
"""

from dcr.benchmark.rubric import (
    BodyRubric,
    BodyResult,
    RunResult,
    quat_to_tilt_deg,
    evaluate_body,
    evaluate_run,
)

__all__ = [
    "BodyRubric",
    "BodyResult",
    "RunResult",
    "quat_to_tilt_deg",
    "evaluate_body",
    "evaluate_run",
]
