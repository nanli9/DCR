"""Per-contact impulse log for the B2 deformed-normal benchmark.

Writes the §2.4 impulse CSV: one row per (step, contact) with both the
rest normal and the deformed normal the coupler used, plus the
normal/two-tangential impulses extracted from the PGS solver's `lam`
vector. The downstream plotter uses this to compute tangential-leak
fractions and rest-vs-deformed angle distributions.

Sampling point: end of `DCRWorld.step()`, after the rigid-body solver
has produced `lam` and after the coupler has computed any deformed
normals for the contacts it touched. The deformed normals come from
`coupler.last_deformed_normals[contact_index]` — coupler dispatch
helpers stash them whenever they call `self._deformed_normal(...)`.

Lives on the WORLD so it can see both the solver result and the coupler
state in the same place per step.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class ImpulseLogEntry:
    """One row of `<run_id>_impulse.csv` (`benchmark/BENCHMARK_PROMPT.md` §2.4).

    `J_normal`, `J_tangential_u`, `J_tangential_v` are the per-contact
    impulses (in Ns) extracted from the solver's `lam` vector. The two
    tangential components are along the friction basis directions
    returned by `rigid.solver._pick_friction_dirs(normal)`.

    `n_deformed_*` is the deformed normal the coupler used. When the
    coupler didn't touch this contact this step (e.g. it's a new
    impact, not a resting contact), the deformed normal is taken
    equal to the rest normal — same numeric path as the "rest" flavor.
    """
    step: int
    t: float
    body_name: str
    contact_x: float
    contact_y: float
    contact_z: float
    J_normal: float
    J_tangential_u: float
    J_tangential_v: float
    n_rest: NDArray[np.float64]      # shape (3,)
    n_deformed: NDArray[np.float64]  # shape (3,)


@dataclass
class ImpulseLog:
    """Accumulator over a single run."""
    entries: list[ImpulseLogEntry] = field(default_factory=list)

    def append(self, entry: ImpulseLogEntry) -> None:
        self.entries.append(entry)

    def __len__(self) -> int:
        return len(self.entries)

    def to_csv(self, path) -> None:
        """Write one row per (step, contact) in §2.4 schema."""
        import csv
        from pathlib import Path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "step", "t", "body_name",
                "contact_x", "contact_y", "contact_z",
                "J_normal", "J_tangential_u", "J_tangential_v",
                "n_rest_x", "n_rest_y", "n_rest_z",
                "n_deformed_x", "n_deformed_y", "n_deformed_z",
            ])
            for e in self.entries:
                nr = np.asarray(e.n_rest, dtype=np.float64)
                nd = np.asarray(e.n_deformed, dtype=np.float64)
                w.writerow([
                    e.step, f"{e.t:.6f}", e.body_name,
                    f"{e.contact_x:.6e}", f"{e.contact_y:.6e}",
                    f"{e.contact_z:.6e}",
                    f"{e.J_normal:.6e}", f"{e.J_tangential_u:.6e}",
                    f"{e.J_tangential_v:.6e}",
                    f"{nr[0]:.6e}", f"{nr[1]:.6e}", f"{nr[2]:.6e}",
                    f"{nd[0]:.6e}", f"{nd[1]:.6e}", f"{nd[2]:.6e}",
                ])

    def cumulative_J_per_body(self) -> dict[str, tuple[float, float]]:
        """Return `{body_name: (cum_J_normal, cum_J_tangential)}` over the
        whole run. `cum_J_tangential` is √(J_u² + J_v²) summed per step.
        Used by `dcr.benchmark.summary.compute_summary` to fill
        `bodies[].cum_J_*` (§2.3).
        """
        totals: dict[str, list[float]] = {}
        for e in self.entries:
            cn, ct = totals.setdefault(e.body_name, [0.0, 0.0])
            cn += float(abs(e.J_normal))
            ct += float(np.hypot(e.J_tangential_u, e.J_tangential_v))
            totals[e.body_name] = [cn, ct]
        return {k: (v[0], v[1]) for k, v in totals.items()}
