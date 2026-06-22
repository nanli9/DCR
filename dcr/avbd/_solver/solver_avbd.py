"""SolverAVBD — the native Augmented-Lagrangian 6-DOF solver.

This is the AVBD projection backend of the shared constraint interface
(`dcr/avbd/_solver/constraints.py`). It IS the validated `Solver6DOF`
implementation — the colored AL primal (box↔box SAT + face-clip manifold,
box↔floor with the AL contact/friction force), the dual/penalty update, and the
native (z, q) modal + cargo q-block (M1/M2, GPU-resident, parity-tested) — exposed
under the canonical name, plus a thin `add_cargo` alias so it satisfies the
common `Solver` Protocol verbatim.

NO numerics change: `SolverAVBD` is behaviour-identical to `Solver6DOF`. It
overrides nothing that touches the solve; it only adds the common method name.
This is the Stage-1 behaviour-neutral parity contract
(`prompts/native_dual_solver_build_plan.md`).

Migration note (plan Decision #5)
---------------------------------
The plan's eventual end-state is the in-place class rename `Solver6DOF ->
SolverAVBD` with a `Solver6DOF = SolverAVBD` alias. To keep Stage 0/1
behaviour-neutral and low-risk, that cosmetic rename of the 2862-line module is
deferred to the Stage-6 cleanup; here `SolverAVBD` subclasses `Solver6DOF` and
`Solver6DOF` stays importable. External code should prefer the `SolverAVBD`
name (or `make_solver("avbd", ...)`).

Spec: AVBD §3.3 (Augmented Lagrangian) + `two_band_coupling.html` (Approach B,
the native (z, q) modal/cargo constraint).
"""
from __future__ import annotations

from .solver_6dof import Solver6DOF

__all__ = ["SolverAVBD"]


class SolverAVBD(Solver6DOF):
    """AVBD backend of the shared `Solver` interface (`constraints.Solver`).

    Inherits the full `Solver6DOF` implementation unchanged. The only addition
    is the common-interface `add_cargo` name (the AVBD-native cargo block is
    `add_cargo_native`).
    """

    def add_cargo(self, body, cargo_body, support_rows) -> None:
        """Common-interface alias for `add_cargo_native`. AVBD projects the
        cargo cube's elastic block `a ∈ ℝ^k` as the augmented q-block of the same
        implicit step (two_band_coupling.html — M2). `support_rows` maps each of
        the cube's SUPPORT_CONTACT slots to its corner pid `(slot, pid)`."""
        self.add_cargo_native(body, cargo_body, support_rows)
