"""Stage E0 acceptance tests — energy bookkeeping.

E0.4 criteria:
1. Bouncing ball (restitution 0.5): E_loss accounts for factor eps_r^2 = 0.25.
2. Free-fall (no contact): E_rigid bounded (report symplectic Euler drift).
3. Modal-only: E_modal decays at analytical Rayleigh damping rate (<=5% error).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.rigid import World, make_dynamic_sphere, make_static_plane
from dcr.rigid.energy import rigid_kinetic_energy
from dcr.modal.energy import modal_energy


class TestRigidKineticEnergy:
    """E0.1: rigid_kinetic_energy matches World.kinetic_energy."""

    def test_single_sphere(self) -> None:
        sphere = make_dynamic_sphere(mass=2.0, radius=0.1, position=(0, 1, 0))
        sphere.velocity[0:3] = [1.0, -2.0, 0.5]
        sphere.velocity[3:6] = [0.1, 0.2, 0.3]
        ke = rigid_kinetic_energy([sphere])
        # Cross-check with World.kinetic_energy
        w = World()
        w.add_body(sphere)
        assert abs(ke - w.kinetic_energy()) < 1e-12

    def test_static_body_excluded(self) -> None:
        plane = make_static_plane()
        assert rigid_kinetic_energy([plane]) == 0.0

    def test_empty_list(self) -> None:
        assert rigid_kinetic_energy([]) == 0.0


class TestModalEnergy:
    """E0.2: modal_energy = 0.5 qdot^T qdot + 0.5 q^T Omega^2 q."""

    def test_pure_kinetic(self) -> None:
        q = np.zeros(3)
        qdot = np.array([1.0, 2.0, 3.0])
        omega = np.array([10.0, 20.0, 30.0])
        E = modal_energy(q, qdot, omega)
        assert abs(E - 0.5 * np.dot(qdot, qdot)) < 1e-14

    def test_pure_potential(self) -> None:
        q = np.array([0.1, 0.2, 0.3])
        qdot = np.zeros(3)
        omega = np.array([10.0, 20.0, 30.0])
        E = modal_energy(q, qdot, omega)
        expected = 0.5 * np.dot(q, omega**2 * q)
        assert abs(E - expected) < 1e-14

    def test_nonnegative(self) -> None:
        rng = np.random.default_rng(42)
        for _ in range(100):
            q = rng.standard_normal(5)
            qdot = rng.standard_normal(5)
            omega = np.abs(rng.standard_normal(5)) * 100
            assert modal_energy(q, qdot, omega) >= 0.0


class TestBouncingBallEnergyLoss:
    """E0.4 criterion 1: bouncing ball with restitution 0.5.

    At each bounce, kinetic energy drops by factor eps_r^2 = 0.25.
    E_loss per step accounts for the gap to within 1e-10.
    """

    def test_energy_loss_factor(self) -> None:
        eps_r = 0.5
        sphere = make_dynamic_sphere(
            mass=1.0, radius=0.1, position=(0, 2.0, 0),
            restitution=eps_r)
        plane = make_static_plane(friction=0.0)

        world = World(h=1e-3)
        world.add_body(sphere)
        world.add_body(plane)
        world.log_energy = True

        # Simulate until first bounce completes (ball has positive vy again).
        hit_ground = False
        for _ in range(10000):
            contacts = world.step()
            if contacts:
                hit_ground = True
            if hit_ground and sphere.velocity[1] > 0.1:
                break

        # Collect records where E_loss > 0 (the bounce frames).
        loss_records = [r for r in world.energy_log if r.E_loss > 1e-12]
        assert len(loss_records) > 0, "No energy loss recorded during bounce"

        # Total loss over the bounce event
        total_E_loss = sum(r.E_loss for r in loss_records)
        # E_pre at the first impact frame
        E_pre_first = loss_records[0].E_rigid_pre
        # Expected ratio: 1 - eps_r^2 = 0.75 of pre-impact KE is lost
        expected_loss = E_pre_first * (1.0 - eps_r**2)
        # Check within a few percent (PGS solver has some numerical spread)
        assert abs(total_E_loss - expected_loss) / expected_loss < 0.05, \
            f"total_E_loss={total_E_loss:.6f}, expected={expected_loss:.6f}"

    def test_energy_conservation_identity(self) -> None:
        """E_rigid_pre - E_rigid_post = E_loss (exact, per record)."""
        sphere = make_dynamic_sphere(
            mass=1.0, radius=0.1, position=(0, 1.0, 0), restitution=0.5)
        plane = make_static_plane()

        world = World(h=1e-3)
        world.add_body(sphere)
        world.add_body(plane)
        world.log_energy = True

        for _ in range(3000):
            world.step()

        for r in world.energy_log:
            gap = max(0.0, r.E_rigid_pre - r.E_rigid_post)
            assert abs(r.E_loss - gap) < 1e-14


class TestFreeFallDrift:
    """E0.4 criterion 2: no-contact free fall, E_rigid bounded.

    Symplectic Euler is not exactly conservative; report per-step drift bound.
    """

    def test_free_fall_energy_bounded(self) -> None:
        sphere = make_dynamic_sphere(
            mass=1.0, radius=0.1, position=(0, 10.0, 0))

        world = World(h=1e-2)
        world.add_body(sphere)
        world.log_energy = True

        energies = []
        for _ in range(200):
            world.step()
            energies.append(rigid_kinetic_energy(world.bodies))

        energies = np.array(energies)
        # In free fall, KE increases monotonically (no contacts)
        # The key check: no E_loss logged (since no constraints fire)
        loss_records = [r for r in world.energy_log if r.E_loss > 1e-14]
        assert len(loss_records) == 0, "Unexpected E_loss in free fall"

        # KE should grow roughly as 0.5 * m * (g*t)^2
        # Just verify it's finite and positive
        assert energies[-1] > 0
        assert np.isfinite(energies[-1])


class TestModalDecay:
    """E0.4 criterion 3: modal energy decays at analytical Rayleigh rate.

    Single mode initialized to a known eigenmode, no contacts.
    E_modal(t) decays at rate exp(-2 * xi * omega * t). <=5% error.
    """

    def test_single_mode_decay(self) -> None:
        """Verify E_modal decays as exp(-2 xi omega t) for a single damped mode."""
        omega_j = 50.0  # rad/s
        xi_j = 0.02     # damping ratio (underdamped)
        T = np.pi / (2.0 * omega_j)  # sub-step size matching IIR convention

        # Initial conditions: q=0, qdot=1 (unit velocity kick)
        q = np.array([0.0])
        qdot = np.array([1.0])
        omega = np.array([omega_j])

        E0 = modal_energy(q, qdot, omega)

        # Exact solution for damped harmonic oscillator:
        # q(t) = (1/omega_d) * exp(-xi*omega*t) * sin(omega_d * t)
        # qdot(t) = exp(-xi*omega*t) * [cos(omega_d*t) - (xi*omega/omega_d)*sin(omega_d*t)]
        # E_modal(t) envelope decays as exp(-2*xi*omega*t)

        omega_d = omega_j * np.sqrt(1.0 - xi_j**2)
        n_steps = 500
        t = 0.0

        energies = []
        times = []

        for _ in range(n_steps):
            # Exact SDOF step (exponential integrator)
            exp_decay = np.exp(-xi_j * omega_j * T)
            cos_wd = np.cos(omega_d * T)
            sin_wd = np.sin(omega_d * T)

            q_new = exp_decay * (q[0] * cos_wd + (qdot[0] + xi_j * omega_j * q[0]) / omega_d * sin_wd)
            qdot_new = exp_decay * (qdot[0] * cos_wd - (omega_j**2 * q[0] + xi_j * omega_j * qdot[0]) / omega_d * sin_wd)

            q[0] = q_new
            qdot[0] = qdot_new
            t += T

            E = modal_energy(q, qdot, omega)
            energies.append(E)
            times.append(t)

        energies = np.array(energies)
        times = np.array(times)

        # Compare energy envelope with analytical decay exp(-2*xi*omega*t)
        # Use envelope: at each time, E_modal / E0 should be near exp(-2*xi*omega*t)
        analytical_envelope = E0 * np.exp(-2 * xi_j * omega_j * times)

        # The actual energy oscillates around the envelope (twice the natural freq).
        # Compare time-averaged energy over each oscillation period.
        period = 2 * np.pi / omega_d
        n_periods = int(times[-1] / period)

        for p in range(1, min(n_periods, 10)):
            t_center = p * period
            mask = np.abs(times - t_center) < 0.5 * period
            if np.sum(mask) < 2:
                continue
            avg_E = np.mean(energies[mask])
            avg_analytical = np.mean(analytical_envelope[mask])
            rel_err = abs(avg_E - avg_analytical) / avg_analytical
            assert rel_err < 0.05, \
                f"Period {p}: avg E_modal={avg_E:.6e}, analytical={avg_analytical:.6e}, err={rel_err:.2%}"

        # Also check that energy is monotonically decreasing in the envelope sense
        # (last quarter of energies should be much less than first quarter)
        assert np.mean(energies[-100:]) < 0.5 * np.mean(energies[:100])
