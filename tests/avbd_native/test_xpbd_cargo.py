"""Stage 4 — XPBD-native cargo materials (CPU reference).

SolverXPBD.add_cargo registers a deformable cargo cube's elastic block a ∈ R^k as
its own block in the augmented modal vector Q = [q_support; a_cube] (no coupler).
Per material (rigid k=0 / fem_rigid / fem / abd), reusing dcr/avbd/cargo/* body
models: each support-contact row reads the cube's deformed corner
(R·Φ_c[pid]·a)_y and loads a via G_a; the elastic block is projected compliant
(per-mode for linear, re-linearized V⊥ for abd) in the same GS sweep.

Acceptance (CPU; device parity deferred to the batched device pass): per material
the cube deforms (k>0) or stays rigid (k=0), the support rings two-way, and the
body does not tunnel through the support.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.solver_xpbd import SolverXPBD
from scenes.reduced_scene_common import make_cargo_cube


def _drop_cargo(material, *, n=150, freeze=False):
    half, y_rest, size, mass = 0.05, 0.5, 0.10, 1.0
    cube = make_cargo_cube(material, size=size, mass=mass, n_elastic=6)
    w = 2.0 * np.pi * 25.0
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=8, device="cpu")
    s.set_modal_support(np.eye(1), np.array([[w * w]]),
                        np.array([[2.0 * 0.01 * w]]))
    s._freeze_qdot = freeze
    box = s.add_box(position=(0.0, y_rest + half + 0.03, 0.0),
                    half_extents=(half, half, half), mass=mass)
    cb = np.asarray(cube.corner_body, dtype=np.float64)
    support_rows = []
    for pid in range(cb.shape[0]):
        if cb[pid, 1] < 0.0:                       # bottom corners
            slot = s.add_support_contact_corner(
                box, tuple(cb[pid]), y_rest, np.ones(1))
            support_rows.append((slot, pid))
    s.add_cargo(box, cube, support_rows)
    peak_ke, peak_def = 0.0, 0.0
    for _ in range(n):
        s.step()
        assert np.all(np.isfinite(s.positions()))
        a = s.cargo_a(box.index)
        assert np.all(np.isfinite(a))
        peak_ke = max(peak_ke, float(s.last_modal_KE))
        peak_def = max(peak_def, float(np.abs(a).max()) if a.size else 0.0)
    return dict(peak_ke=peak_ke, peak_def=peak_def,
                y=float(s.positions()[box.index][1]), a=s.cargo_a(box.index))


@pytest.mark.parametrize("material", ["rigid", "fem_rigid", "fem", "abd"])
def test_xpbd_cargo_material(material):
    """Each material: support rings two-way, body stays on the support (no
    tunnel), and the cube deforms (k>0) — or carries no modes (rigid k=0)."""
    r = _drop_cargo(material)
    assert r["peak_ke"] > 1e-5, f"{material}: support should ring ({r['peak_ke']:.2e})"
    assert r["y"] > 0.5 - 0.03, f"{material}: tunneled the support (y={r['y']:.3f})"
    if material == "rigid":
        assert r["a"].size == 0, "rigid k=0 carries no elastic modes"
    else:
        assert r["peak_def"] > 1e-6, f"{material}: cube should flex ({r['peak_def']:.2e})"


def test_xpbd_cargo_two_way_vs_frozen():
    """fem_rigid cargo: dynamic rings, frozen q̇≡0 carries ~0 modal KE."""
    dyn = _drop_cargo("fem_rigid", freeze=False)["peak_ke"]
    frz = _drop_cargo("fem_rigid", freeze=True)["peak_ke"]
    assert dyn > 1e-4 and frz < 1e-9, (dyn, frz)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
