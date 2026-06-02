"""AVBD-native passive DCR (Phase A).

Wraps the vendored 6-DOF AVBD warp solver and re-exposes the surface
that `PassiveDCRCoupler` consumes. The patch-mode response math is
unchanged; only the rigid solve underneath is swapped from PGS
(`dcr.rigid.ConstraintSolver`) to AVBD.

See `prompts/avbd_native_dcr_followup_spec_v2.md` §1, §9 for the design,
and `~/.claude/plans/here-i-want-to-kind-valiant.md` for Phase A scope.
"""
from .world import AVBDDCRWorld, AVBDBodyDescriptor
from .contact_extract import extract_contacts, AVBDContactRecord

__all__ = [
    "AVBDDCRWorld",
    "AVBDBodyDescriptor",
    "extract_contacts",
    "AVBDContactRecord",
]
