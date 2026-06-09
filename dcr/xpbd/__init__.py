"""DCR reduced-coupled modal response on an XPBD backend.

XPBD sibling of `dcr.avbd`. Same coupler design (monolithic Schur over the
rigid pose `z` and the reduced static-sag coordinate `q_s`, static/dynamic
split + exact-resonator IIR for the dynamic ring `q_d`) — the only thing
that changes is the host constraint solver.

The math is the proposal's §2.1 (`docs/proposal_modal_response_as_constraint.md`):
the modal amplitude `q` is a constrained co-DOF carrying its own column
`J_q = −Φ(x_s)` in the same gap as the rigid body, and the same multiplier
that pushes the rigid pose loads the modal coordinate through `J_q`. AVBD
hosts this through its augmented-Lagrangian primal block; XPBD hosts it
through its compliant-constraint formulation. The constraint is the same;
the projection is XPBD-style (compliance `α̃ = α / h²`, no AL escalation).
"""

from .world import XPBDWorld
from .reduced_coupled_xpbd import ReducedCoupledXPBDCoupler

__all__ = ["XPBDWorld", "ReducedCoupledXPBDCoupler"]
