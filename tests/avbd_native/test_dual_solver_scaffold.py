"""Stage 0 — shared constraint API + dual-solver scaffolding.

Smoke-tests the seam from prompts/native_dual_solver_build_plan.md Stage 0:

* the shared constraint interface (`constraints`) imports and exposes the
  descriptions + `Solver` Protocol + `make_solver` factory;
* `make_solver("avbd", ...)` resolves to `SolverAVBD`, which satisfies the
  `Solver` Protocol and drives the native (z, q) modal path with NO coupler;
* a throwaway smoke scene (box on the live modal surface) builds and steps;
* `make_solver("xpbd", ...)` is a stub that errors (rigid core lands Stage 2).

CPU-only (CLAUDE.md rule 6 — reference path first); the device path is exercised
by the existing native suite.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.constraints import (
    Solver,
    make_solver,
    BoxBody,
    FloorContact,
    ModalSupport,
    SupportContactCorner,
    Cargo,
)
from dcr.avbd._solver.solver_avbd import SolverAVBD
from dcr.avbd._solver.solver_6dof import Solver6DOF


def test_descriptions_construct():
    """The solver-agnostic constraint descriptions build with sane defaults."""
    b = BoxBody(position=(0, 1, 0), half_extents=(0.1, 0.1, 0.1), mass=1.0)
    assert b.orientation == (0.0, 0.0, 0.0, 1.0)
    fc = FloorContact(body=0)
    assert fc.floor_y == 0.0 and fc.friction is None
    ms = ModalSupport(Mq=np.eye(1), Kq=np.eye(1), Dq=np.zeros((1, 1)))
    assert ms.q0 is None
    sc = SupportContactCorner(body=0, off_a=(0, -0.1, 0), y_rest=0.5,
                              U_y_row=np.ones(1))
    assert sc.stiffness == 1.0e9
    cg = Cargo(body=0, cargo_body=object())
    assert cg.support_rows == []


def test_make_solver_avbd_resolves():
    """solver='avbd' resolves to SolverAVBD (== Solver6DOF behaviour) and
    satisfies the shared Solver Protocol."""
    s = make_solver("avbd", device="cpu", iterations=4, substeps=1)
    assert isinstance(s, SolverAVBD)
    assert isinstance(s, Solver6DOF)  # behaviour-identical: subclass, no overrides of the solve
    assert isinstance(s, Solver)      # structural conformance to the shared interface


def test_make_solver_xpbd_constructs_and_conforms():
    """solver='xpbd' now resolves to the standalone SolverXPBD (Stage 2 rigid
    core). It satisfies the shared Solver Protocol; modal/cargo raise until
    Stage 3/4."""
    from dcr.avbd._solver.solver_xpbd import SolverXPBD
    s = make_solver("xpbd", device="cpu", iterations=8, substeps=4)
    assert isinstance(s, SolverXPBD)
    assert isinstance(s, Solver)  # structural conformance to the shared interface
    with pytest.raises(NotImplementedError, match="Stage 3"):
        s.set_modal_support(np.eye(1), np.eye(1), np.zeros((1, 1)))
    with pytest.raises(NotImplementedError, match="Stage 4"):
        s.add_cargo(0, object(), [])


def test_make_solver_unknown_kind():
    with pytest.raises(ValueError, match="unknown solver kind"):
        make_solver("pgs", device="cpu")


def test_avbd_smoke_scene_native_modal_no_coupler():
    """A throwaway smoke scene: a rigid box rests on the live modal surface
    y_rest + U_y·q via the native (z, q) q-block (set_modal_support +
    add_support_contact_corner). No coupler, no hook. The box should settle, the
    support should ring two-way (nonzero modal KE), and nothing should NaN."""
    s = make_solver("avbd", device="cpu", iterations=8, substeps=2)

    y_rest = 0.5
    half = 0.1
    # A single-mode support (mass-normalized ⇒ M_q = I, K_q = ω², D_q Rayleigh).
    omega2 = (2.0 * np.pi * 30.0) ** 2  # ~30 Hz mode
    s.set_modal_support(
        Mq=np.eye(1),
        Kq=np.array([[omega2]]),
        Dq=np.array([[2.0 * 0.02 * np.sqrt(omega2)]]),  # ζ ≈ 0.02
        q0=np.zeros(1),
        qdot0=np.zeros(1),
    )

    # Box dropped just above the modal surface.
    box = s.add_box(position=(0.0, y_rest + half + 0.02, 0.0),
                    half_extents=(half, half, half), mass=1.0)
    # Retype the four bottom corners to ride the live surface (U_y = 1 here:
    # the corner sees the full modal amplitude).
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            s.add_support_contact_corner(
                box, off_a=(sx * half, -half, sz * half),
                y_rest=y_rest, U_y_row=np.ones(1))

    # No coupler is anywhere in sight — this is the native solver only.
    peak_modal_KE = 0.0
    for _ in range(120):
        s.step()
        assert np.all(np.isfinite(s.positions())), "no NaN in body state"
        assert np.all(np.isfinite(s.modal_q)), "no NaN in modal q"
        peak_modal_KE = max(peak_modal_KE, float(s.last_modal_KE))

    # Two-way coupling: the drop excites the support (it rings).
    assert peak_modal_KE > 1e-12, f"support never rang ({peak_modal_KE:.2e})"
    # The box settled near the (slightly deflected) rest surface, did not fall
    # through, and did not blow up.
    y_final = float(s.positions()[box.index][1])
    assert y_rest - 0.05 < y_final < y_rest + half + 0.05, y_final


def test_solver_avbd_add_cargo_alias_exists():
    """SolverAVBD.add_cargo is the common-interface alias for add_cargo_native
    (forwarding is exercised end-to-end by the cargo tests)."""
    s = make_solver("avbd", device="cpu")
    assert hasattr(s, "add_cargo")
    assert callable(s.add_cargo)
