"""M1.0 acceptance — the monolithic (z, q) numpy oracle.

Validates the foundation's two claims directly on the ground-truth oracle
(`dcr/avbd/modal_qblock.py`), independent of the warp solver:

  * Passivity: backward Euler on E(z,q) is unconditionally dissipative, so a
    free (no-input) run has monotone non-increasing total energy.
  * Two-way loop: with the dynamic q̇ predictor the support rings (modal KE > 0
    and it pushes a body back); the frozen-q̇ counterfactual gives ~zero ring.

See `../DCR-AVBD-Native/two_band_coupling.html`.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.modal_qblock import (
    Body, ModalScene, step_zq, modal_energy, total_energy,
)


def _modal_only_scene(r: int = 3, seed: int = 0) -> ModalScene:
    """A bare modal support (no bodies) for the free-ringdown test."""
    rng = np.random.default_rng(seed)
    omegas = np.array([40.0, 130.0, 280.0][:r], dtype=np.float64)
    Mq = np.eye(r)
    Kq = np.diag(omegas ** 2)
    Dq = np.zeros((r, r))                       # D_q = 0: still dissipates (BE)
    q = np.zeros(r)
    qdot = rng.standard_normal(r) * 0.5         # pluck the modes
    return ModalScene(bodies=[], Mq=Mq, Kq=Kq, Dq=Dq, q=q, qdot=qdot,
                      gravity=np.zeros(3))


def _cube_on_support(drop_h: float = 0.03) -> ModalScene:
    """One unit cube hovering above a 2-mode support, single bottom corner."""
    r = 2
    omegas = np.array([35.0, 110.0], dtype=np.float64)
    Mq = np.eye(r)
    Kq = np.diag(omegas ** 2)
    Dq = 0.02 * Mq + 2.0e-5 * Kq                # light Rayleigh
    m = 1.0
    half = 0.05
    I = (m * (2 * half) ** 2 / 6.0) * np.eye(3)  # solid cube inertia
    body = Body(
        mass=m, inertia_local=I,
        x=np.array([0.0, half + drop_h, 0.0]),   # bottom corner at drop_h
        q=np.array([0.0, 0.0, 0.0, 1.0]),
        v=np.zeros(3), omega=np.zeros(3),
        corner_off=np.array([[0.0, -half, 0.0]]),
        corner_U_y=np.array([[1.0, 0.4]]),       # mode shape at the corner
        corner_y_rest=np.array([0.0]),
        corner_lam=np.zeros(1),
    )
    return ModalScene(bodies=[body], Mq=Mq, Kq=Kq, Dq=Dq,
                      q=np.zeros(r), qdot=np.zeros(r),
                      gravity=np.array([0.0, -9.81, 0.0]), penalty=2.0e5)


def test_free_modal_ringdown_is_energy_monotone():
    """Passivity: a plucked free support loses energy every step (Ė ≤ 0)."""
    scene = _modal_only_scene()
    h = 1.0e-3
    E_prev = total_energy(scene)
    E0 = E_prev
    for _ in range(400):
        step_zq(scene, h, n_iter=4)
        E = total_energy(scene)
        assert E <= E_prev + 1e-12, f"energy rose: {E_prev:.6e} -> {E:.6e}"
        E_prev = E
    assert E_prev < 0.5 * E0, "free ring should decay substantially"


def test_two_way_counterfactual_dynamic_rings_frozen_does_not():
    """Dynamic q̇ predictor → support rings; frozen q̇ → quasi-static, no ring."""
    h = 1.0e-3
    n_steps = 220

    dyn = _cube_on_support()
    peak_dyn = 0.0
    for _ in range(n_steps):
        step_zq(dyn, h, n_iter=6, freeze_qdot=False)
        peak_dyn = max(peak_dyn, modal_energy(dyn))

    frz = _cube_on_support()
    peak_frz = 0.0
    for _ in range(n_steps):
        step_zq(frz, h, n_iter=6, freeze_qdot=True)
        peak_frz = max(peak_frz, modal_energy(frz))
        assert np.allclose(frz.qdot, 0.0), "frozen counterfactual keeps q̇ ≡ 0"

    # The dynamic mode carries kinetic energy (it rings); the frozen one is
    # quasi-static and carries essentially none.
    assert peak_dyn > 1e-7, f"dynamic support should ring (peak KE {peak_dyn:.2e})"
    assert peak_dyn > 20.0 * max(peak_frz, 1e-30), (
        f"dynamic ring {peak_dyn:.2e} should dwarf frozen {peak_frz:.2e}")


def test_dropped_cube_loads_the_mode_and_settles():
    """The contact load deflects q (two-way: body presses surface down)."""
    scene = _cube_on_support(drop_h=0.04)
    h = 1.0e-3
    for _ in range(400):
        step_zq(scene, h, n_iter=6)
    # the mode is excited (nonzero amplitude) and the cube has not fallen
    # through the support surface.
    assert abs(scene.q[0]) > 1e-5, "first mode should be loaded by the drop"
    b = scene.bodies[0]
    surf = b.corner_y_rest[0] + float(b.corner_U_y[0] @ scene.q)
    corner_y = b.x[1] - 0.05
    assert corner_y - surf > -2e-3, "cube must not tunnel through the surface"


def test_total_energy_passivity_on_settling_drop():
    """Total mechanical energy is monotone non-increasing each free step
    once the cube is in contact (backward Euler dissipates; gravity is in PE)."""
    scene = _cube_on_support(drop_h=0.02)
    h = 1.0e-3
    # let it make contact first
    for _ in range(40):
        step_zq(scene, h, n_iter=6)
    E_prev = total_energy(scene)
    for _ in range(300):
        step_zq(scene, h, n_iter=6)
        E = total_energy(scene)
        assert E <= E_prev + 1e-6, f"energy rose: {E_prev:.6e} -> {E:.6e}"
        E_prev = E


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
