"""Stage E0: Energy bookkeeping demo and acceptance plots.

Generates:
  docs/stageE0/bouncing_ball_energy.png — E_rigid, E_loss at each bounce
  docs/stageE0/free_fall_energy.png — E_rigid drift in free fall
  docs/stageE0/modal_decay.png — E_modal decay vs analytical envelope
  docs/stageE0/energy.csv — raw energy log
"""
from __future__ import annotations

import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dcr.rigid import World, make_dynamic_sphere, make_static_plane
from dcr.rigid.energy import rigid_kinetic_energy
from dcr.modal.energy import modal_energy

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "stageE0")
os.makedirs(OUT_DIR, exist_ok=True)


def bouncing_ball_demo() -> None:
    """E0.4 criterion 1: bouncing ball, restitution=0.5."""
    eps_r = 0.5
    sphere = make_dynamic_sphere(
        mass=1.0, radius=0.1, position=(0, 2.0, 0), restitution=eps_r)
    plane = make_static_plane(friction=0.0)

    world = World(h=1e-3)
    world.add_body(sphere)
    world.add_body(plane)
    world.log_energy = True

    times, ke_vals = [], []
    for _ in range(8000):
        world.step()
        times.append(world.time)
        ke_vals.append(rigid_kinetic_energy(world.bodies))

    times = np.array(times)
    ke_vals = np.array(ke_vals)

    # Extract E_loss events
    loss_times = [r.t for r in world.energy_log if r.E_loss > 1e-10]
    loss_vals = [r.E_loss for r in world.energy_log if r.E_loss > 1e-10]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.plot(times, ke_vals, "b-", linewidth=0.5, label="E_rigid")
    ax1.set_ylabel("E_rigid (J)")
    ax1.set_title(f"Bouncing ball (eps_r={eps_r}): kinetic energy")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.stem(loss_times, loss_vals, linefmt="r-", markerfmt="ro", basefmt="k-",
             label="E_loss per step")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("E_loss (J)")
    ax2.set_title("Energy lost at each bounce")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "bouncing_ball_energy.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved bouncing_ball_energy.png")

    # Report eps_r^2 factor
    # Find pairs of consecutive bounce events
    bounce_E_pre = [r.E_rigid_pre for r in world.energy_log if r.E_loss > 1e-10]
    for i in range(1, min(len(bounce_E_pre), 5)):
        ratio = bounce_E_pre[i] / bounce_E_pre[0] if bounce_E_pre[0] > 0 else 0
        print(f"  Bounce {i}: E_pre ratio to first = {ratio:.4f} "
              f"(expected ~ {eps_r**(2*i):.4f})")

    # Save CSV
    csv_path = os.path.join(OUT_DIR, "energy.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "E_rigid_pre", "E_rigid_post", "E_loss"])
        for r in world.energy_log:
            writer.writerow([r.t, r.E_rigid_pre, r.E_rigid_post, r.E_loss])
    print(f"  Saved energy.csv ({len(world.energy_log)} records)")


def free_fall_demo() -> None:
    """E0.4 criterion 2: free fall, no contact."""
    sphere = make_dynamic_sphere(mass=1.0, radius=0.1, position=(0, 100.0, 0))

    world = World(h=1e-2)
    world.add_body(sphere)
    world.log_energy = True

    times, ke_vals = [], []
    for _ in range(300):
        world.step()
        times.append(world.time)
        ke_vals.append(rigid_kinetic_energy(world.bodies))

    times = np.array(times)
    ke_vals = np.array(ke_vals)

    # Analytical: KE = 0.5 * m * (g*t)^2
    ke_analytical = 0.5 * 1.0 * (9.81 * times) ** 2

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(times, ke_vals, "b-", label="E_rigid (sim)")
    ax.plot(times, ke_analytical, "r--", label="0.5 m (gt)^2 (analytical)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("E_rigid (J)")
    ax.set_title("Free fall: rigid KE vs analytical")
    ax.legend()
    ax.grid(True, alpha=0.3)

    drift = np.abs(ke_vals - ke_analytical)
    max_drift = np.max(drift)
    ax.text(0.02, 0.98, f"Max drift: {max_drift:.2e} J",
            transform=ax.transAxes, va="top", fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "free_fall_energy.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved free_fall_energy.png (max drift = {max_drift:.2e} J)")


def modal_decay_demo() -> None:
    """E0.4 criterion 3: modal energy decay at Rayleigh rate."""
    omega_j = 50.0
    xi_j = 0.02
    T = np.pi / (2.0 * omega_j)

    q = np.array([0.0])
    qdot = np.array([1.0])
    omega = np.array([omega_j])
    omega_d = omega_j * np.sqrt(1.0 - xi_j ** 2)

    E0 = modal_energy(q, qdot, omega)

    n_steps = 1000
    times, energies = [], []
    t = 0.0

    for _ in range(n_steps):
        exp_decay = np.exp(-xi_j * omega_j * T)
        cos_wd = np.cos(omega_d * T)
        sin_wd = np.sin(omega_d * T)

        q_new = exp_decay * (
            q[0] * cos_wd
            + (qdot[0] + xi_j * omega_j * q[0]) / omega_d * sin_wd
        )
        qdot_new = exp_decay * (
            qdot[0] * cos_wd
            - (omega_j ** 2 * q[0] + xi_j * omega_j * qdot[0]) / omega_d * sin_wd
        )

        q[0] = q_new
        qdot[0] = qdot_new
        t += T
        times.append(t)
        energies.append(modal_energy(q, qdot, omega))

    times = np.array(times)
    energies = np.array(energies)
    envelope = E0 * np.exp(-2 * xi_j * omega_j * times)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(times, energies, "b-", linewidth=0.5, label="E_modal (exact stepper)")
    ax.plot(times, envelope, "r--", linewidth=1.5, label="E0 exp(-2 xi omega t)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("E_modal (J)")
    ax.set_title(f"Modal energy decay (omega={omega_j}, xi={xi_j})")
    ax.set_yscale("log")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "modal_decay.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved modal_decay.png")
    print(f"  Final E_modal / E0 = {energies[-1]/E0:.6e}")
    print(f"  Analytical ratio   = {np.exp(-2*xi_j*omega_j*times[-1]):.6e}")


if __name__ == "__main__":
    print("Stage E0: Energy bookkeeping\n")
    print("1. Bouncing ball energy loss:")
    bouncing_ball_demo()
    print("\n2. Free fall energy drift:")
    free_fall_demo()
    print("\n3. Modal energy decay:")
    modal_decay_demo()
    print("\nDone. Plots saved to docs/stageE0/")
