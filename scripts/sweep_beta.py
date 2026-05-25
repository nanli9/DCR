"""Energy-injection vs β sweep.

For each (scene, mode) pair (modes that have a non-trivial β), runs
the scene with β ∈ {0.1, 0.25, 0.5, 1.0}, records the energy log per
β, and renders a single overlay PNG per (scene, mode).

Visual question this answers:
  * does cumulative modal injection scale with β as the formulation
    expects (∝ β when not bound-clipped, asymptoting at the §15 cap
    when clipped)?
  * does E_modal(t) shape stay similar across β values, just
    re-amplitude'd?

Run: uv run python scripts/sweep_beta.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from dcr.benchmark.energy_log import EnergyLog
from dcr.benchmark.plots import plot_param_sweep
from scripts.analyze_patch_mode import SCENE_BUILDERS
from scripts.run_scenes import simulate


PLOT_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "plots"

# Modes where β actually does something.
COMPARABLE_MODES = [
    "energy_prescribed",
    "energy_prescribed_point_impulse",
    "energy_prescribed_patch",
]

BETA_GRID = [0.1, 0.25, 0.5, 1.0]


def sweep_one(scene: str, mode: str, n_steps: int = 600):
    print(f"\n----- scene={scene}  mode={mode}  β={BETA_GRID} -----",
          flush=True)
    logs: dict[float, EnergyLog] = {}
    for beta in BETA_GRID:
        ds = 5.0 if mode == "energy_prescribed_patch" else 1.0
        builder = SCENE_BUILDERS[scene]
        world, coupler, body_info, _mesh, _title = builder(
            velocity_mode=mode, beta=beta, damping_scale=ds)
        world.enable_energy_logging = True
        world.energy_log = EnergyLog()
        simulate(world, coupler, body_info, n_steps=n_steps)
        peak = (float(world.energy_log.E_modal().max())
                if len(world.energy_log) else 0.0)
        cum = (float(world.energy_log.cumulative_modal_injected()[-1])
               if len(world.energy_log) else 0.0)
        inv = world.energy_log.invariant_violation()
        print(f"  β={beta:.2f}  E_modal_peak={peak:>8.3f} J   "
              f"∑E_inj={cum:>8.3f} J   §15_viol={inv:>9.2e}", flush=True)
        logs[beta] = world.energy_log

    plot_path = PLOT_DIR / f"sweep_beta_{scene}_{mode}.png"
    plot_param_sweep(logs, param_name="β", scene=scene, mode=mode,
                     out_path=plot_path)
    print(f"  plot: {plot_path.relative_to(PLOT_DIR.parents[1])}", flush=True)


def main():
    n_steps = 600
    for scene in ["shelf", "truck", "ledge"]:
        for mode in COMPARABLE_MODES:
            try:
                sweep_one(scene, mode, n_steps=n_steps)
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {e}", flush=True)
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
