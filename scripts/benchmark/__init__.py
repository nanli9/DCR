"""Per-benchmark driver scripts for the DCR follow-up benchmark suite.

Each `run_b<N>.py` loops its run matrix, calls `scripts.run_one.run()`
once per cell, captures failures into `benchmark/logs/B<N>/<run_id>.log`,
then invokes `scripts.write_manifest` to emit the §3.1 manifest. The
top-level orchestrator `scripts/run_all_benchmarks.py` chains all
seven (B1–B6 + B7 h-sweep) and writes MANIFEST.json at the end.
"""
