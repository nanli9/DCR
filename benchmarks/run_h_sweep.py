"""CSV benchmark: sweep DCR distant-velocity modes × timestep h.

Run with:

    uv run python -m benchmarks.run_h_sweep \
        [--modes coevoet,bounded_coevoet,energy_prescribed,energy_prescribed_point_impulse] \
        [--h-values 1e-3,2.5e-3,5e-3,1e-2] \
        [--steps-per-h 0]               # 0 → derive from --sim-time / h
        [--sim-time 1.5] \
        [--beta 0.25] \
        [--budget-source min_rigid_loss_modal] \
        [--out benchmarks/output/h_sweep.csv]

Produces one CSV row per (mode, h, step) plus a `#`-prefixed footer with the
headline coefficient-of-variation summary across h, per mode. CoV is computed
on mean realized ΔKE per kicked body — the physical kick strength the artist
perceives. See docs/distant_velocity_modes.md for the paper-level framing.

Output is stdlib csv (no pandas — CLAUDE.md tech-stack constraint).
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dcr.dcr import DCRWorld, PassiveDCRCoupler
from dcr.fem import FEMModel, Material
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis
from dcr.rigid import ConstraintSolver, make_dynamic_box, make_static_plane


# ---------------------------------------------------------------------------
# Scene builder (matches tests/stageDV/test_dcr_velocity_modes.py:_build_scene)
# ---------------------------------------------------------------------------

def _build_slab_modal() -> ModalAnalysis:
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    tol = 1e-8
    xs = mesh.vertices[:, 0]
    zs = mesh.vertices[:, 2]
    x_min, x_max = xs.min(), xs.max()
    z_min, z_max = zs.min(), zs.max()
    on_xmin = np.abs(xs - x_min) < tol
    on_xmax = np.abs(xs - x_max) < tol
    on_zmin = np.abs(zs - z_min) < tol
    on_zmax = np.abs(zs - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)
    fem_model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                         alpha0=2.0, alpha1=1e-5)
    return ModalAnalysis(fem=fem_model, num_modes=10)


@dataclass
class ModeSetup:
    """Map a benchmark mode name to (coupler.dcr_velocity_mode, enforce_bound).

    The benchmark CLI exposes 4 modes; the coupler implements 3 proposal
    paths. "bounded_coevoet" is just "coevoet" with the rigid-energy cap on.
    """
    coupler_mode: str
    enforce_rigid_energy_bound: bool


BENCHMARK_MODES: dict[str, ModeSetup] = {
    "coevoet": ModeSetup("coevoet", False),
    "bounded_coevoet": ModeSetup("coevoet", True),
    "energy_prescribed": ModeSetup("energy_prescribed", True),
    "energy_prescribed_point_impulse": ModeSetup(
        "energy_prescribed_point_impulse", True),
}


def build_scene(
    mode_name: str,
    h: float,
    eta: float = 1.0,
    beta: float = 0.25,
    budget_source: str = "min_rigid_loss_modal",
):
    setup = BENCHMARK_MODES[mode_name]
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=eta,
        enforce_rigid_energy_bound=setup.enforce_rigid_energy_bound,
    )
    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)
    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=table_idx,
        dcr_velocity_mode=setup.coupler_mode,
        energy_response_beta=beta,
        energy_budget_source=budget_source,
    )
    world.add_passive_coupler(coupler)
    # Staggered scene: A bounces, B rests on slab (see tests/stageDV).
    ball_a = make_dynamic_box(
        mass=1.0, hx=0.04, hy=0.04, hz=0.04,
        position=(-0.3, 0.5, 0.0), restitution=0.7, friction=0.5,
    )
    ball_b = make_dynamic_box(
        mass=1.0, hx=0.04, hy=0.04, hz=0.04,
        position=(0.3, 0.04, 0.0), restitution=0.0, friction=0.5,
    )
    world.add_body(ball_a)
    world.add_body(ball_b)
    return world, coupler


# ---------------------------------------------------------------------------
# Per-step metrics
# ---------------------------------------------------------------------------

def _norms_for_dv_dict(world: DCRWorld, dv_dict: dict[int, float]
                       ) -> tuple[float, float, float]:
    """(mean ‖Δv‖, max ‖Δv‖, mean realized ΔKE) for a scalar-dv dict."""
    speeds: list[float] = []
    dKE: list[float] = []
    for body_idx, dv in dv_dict.items():
        if dv <= 0.0:
            continue
        body = world.bodies[body_idx]
        if body.is_static or body.mass <= 0.0:
            continue
        speeds.append(float(dv))
        dKE.append(0.5 * body.mass * dv * dv)
    if not speeds:
        return 0.0, 0.0, 0.0
    return float(np.mean(speeds)), float(np.max(speeds)), float(np.mean(dKE))


def _norms_for_point_impulse(
    world: DCRWorld, kicks: list,
) -> tuple[float, float, float, float, float]:
    """(mean ‖Δv_lin‖, max ‖Δv_lin‖, mean realized ΔKE, mean ‖Δω‖, max ‖Δω‖).

    Δv_lin = J/m · u (linear component at the COM).
    Δω     = J · I_inv · (r × u).
    Realized ΔKE = ½ J² k.
    """
    if not kicks:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    linears: list[float] = []
    angulars: list[float] = []
    dKE: list[float] = []
    for kk in kicks:
        body = world.bodies[kk.body_idx]
        if body.is_static or body.mass <= 0.0:
            continue
        linears.append(float(kk.J_mag / body.mass))  # ‖(J/m)·u‖ = J/m
        rxu = np.cross(kk.r, kk.u)
        I_inv = body.inertia_world_inv()
        dom = kk.J_mag * (I_inv @ rxu)
        angulars.append(float(np.linalg.norm(dom)))
        k = (1.0 / body.mass) + float(rxu @ I_inv @ rxu)
        dKE.append(0.5 * kk.J_mag * kk.J_mag * k)
    return (float(np.mean(linears)), float(np.max(linears)),
            float(np.mean(dKE)),
            float(np.mean(angulars)), float(np.max(angulars)))


# ---------------------------------------------------------------------------
# Run one (mode, h) cell
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "mode", "h", "step", "time", "scene",
    "dcr_velocity_mode", "energy_response_beta", "energy_budget_source",
    "enforce_rigid_energy_bound",
    "E_available", "E_target", "E_loss",
    "mean_delta_v", "max_delta_v",
    "mean_dKE_per_kick",
    "E_rigid_out_before_cap", "E_rigid_out_after_cap",
    "n_clip", "rho_violation",
    "dv_ratio",
    "mean_delta_v_coevoet", "max_delta_v_coevoet",
    "mean_delta_v_energy_A", "max_delta_v_energy_A",
    "mean_delta_v_energy_B", "max_delta_v_energy_B",
    "mean_angular_dv_B", "max_angular_dv_B",
]


def run_one_cell(
    mode_name: str, h: float, n_steps: int,
    beta: float, budget_source: str,
) -> tuple[list[dict], float]:
    """Run one (mode, h) cell. Returns (rows, mean_dKE_per_kick_over_run).

    The mean_dKE_per_kick_over_run is the headline value used for CoV.
    """
    eps = 1e-12
    world, coupler = build_scene(
        mode_name=mode_name, h=h,
        beta=beta, budget_source=budget_source,
    )
    setup = BENCHMARK_MODES[mode_name]
    rows: list[dict] = []
    n_clip = 0
    n_violations = 0
    all_dKE: list[float] = []
    for step in range(n_steps):
        world.step()
        # Active-mode metrics
        if coupler.last_point_impulse_kicks is not None:
            (mean_dv, max_dv, mean_dKE,
             mean_dom, max_dom) = _norms_for_point_impulse(
                world, coupler.last_point_impulse_kicks)
        else:
            # The applied dict is either coevoet or energy_A depending on mode.
            if setup.coupler_mode == "coevoet":
                active_dict = coupler.last_dcr_velocities_coevoet
            elif setup.coupler_mode == "energy_prescribed":
                active_dict = coupler.last_dcr_velocities_energy_A
            else:
                active_dict = {}
            mean_dv, max_dv, mean_dKE = _norms_for_dv_dict(world, active_dict)
            mean_dom = max_dom = 0.0
        # Diagnostic snapshots of every proposal (computed regardless of mode)
        m_c, M_c, _ = _norms_for_dv_dict(
            world, coupler.last_dcr_velocities_coevoet)
        m_A, M_A, _ = _norms_for_dv_dict(
            world, coupler.last_dcr_velocities_energy_A)
        if coupler.last_point_impulse_kicks is not None:
            m_B, M_B, _, _, _ = _norms_for_point_impulse(
                world, coupler.last_point_impulse_kicks)
        else:
            m_B = M_B = 0.0
        if world.last_dcr_clipped:
            n_clip += 1
        if world.last_E_rigid_out_after_cap > world.last_E_loss + 1e-9:
            n_violations += 1
        if mean_dKE > 0:
            all_dKE.append(mean_dKE)
        dv_ratio = mean_dv / max(m_c, eps) if m_c > 0 else 0.0
        rows.append({
            "mode": mode_name, "h": h,
            "step": step, "time": world.time, "scene": "two_ball_staggered",
            "dcr_velocity_mode": coupler.dcr_velocity_mode,
            "energy_response_beta": coupler.energy_response_beta,
            "energy_budget_source": coupler.energy_budget_source,
            "enforce_rigid_energy_bound": world.enforce_rigid_energy_bound,
            "E_available": coupler.last_E_available,
            "E_target": coupler.last_E_target,
            "E_loss": world.last_E_loss,
            "mean_delta_v": mean_dv, "max_delta_v": max_dv,
            "mean_dKE_per_kick": mean_dKE,
            "E_rigid_out_before_cap": world.last_E_rigid_out_before_cap,
            "E_rigid_out_after_cap": world.last_E_rigid_out_after_cap,
            "n_clip": n_clip, "rho_violation": n_violations,
            "dv_ratio": dv_ratio,
            "mean_delta_v_coevoet": m_c, "max_delta_v_coevoet": M_c,
            "mean_delta_v_energy_A": m_A, "max_delta_v_energy_A": M_A,
            "mean_delta_v_energy_B": m_B, "max_delta_v_energy_B": M_B,
            "mean_angular_dv_B": mean_dom, "max_angular_dv_B": max_dom,
        })
    mean_dKE_run = float(np.mean(all_dKE)) if all_dKE else 0.0
    return rows, mean_dKE_run


# ---------------------------------------------------------------------------
# CoV summary
# ---------------------------------------------------------------------------

def _cov(values: list[float]) -> float:
    arr = np.array(values, dtype=np.float64)
    mu = float(np.mean(arr))
    if mu <= 0.0:
        return 0.0
    return float(np.std(arr) / mu)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modes", type=str,
                    default="coevoet,bounded_coevoet,energy_prescribed,"
                            "energy_prescribed_point_impulse")
    ap.add_argument("--h-values", type=str,
                    default="1e-3,2.5e-3,5e-3,1e-2")
    ap.add_argument("--sim-time", type=float, default=1.5,
                    help="Simulation time per cell (seconds).")
    ap.add_argument("--steps-per-h", type=int, default=0,
                    help="Override n_steps; 0 = derive from --sim-time / h.")
    ap.add_argument("--beta", type=float, default=0.25,
                    help="energy_response_beta for the energy_* modes.")
    ap.add_argument("--budget-source", type=str,
                    default="min_rigid_loss_modal",
                    help="energy_budget_source for the energy_* modes.")
    ap.add_argument("--out", type=str,
                    default="benchmarks/output/h_sweep.csv")
    args = ap.parse_args()

    modes = args.modes.split(",")
    h_values = [float(x) for x in args.h_values.split(",")]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Per-mode CoV bookkeeping
    headline: dict[str, list[float]] = {m: [] for m in modes}

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for mode_name in modes:
            for h in h_values:
                n_steps = (args.steps_per_h
                           if args.steps_per_h > 0
                           else int(round(args.sim_time / h)))
                print(f"[run] mode={mode_name:>34s}  h={h:>8.4g}  "
                      f"steps={n_steps}", flush=True)
                rows, mean_dKE = run_one_cell(
                    mode_name=mode_name, h=h, n_steps=n_steps,
                    beta=args.beta, budget_source=args.budget_source,
                )
                writer.writerows(rows)
                headline[mode_name].append(mean_dKE)

        # Footer: per-mode CoV summary (commented out so a downstream CSV
        # parser that skips '#' lines reads the data cleanly).
        f.write("#\n")
        f.write("# CoV summary across h (std/mean of mean ΔKE-per-kick per "
                "cell)\n")
        f.write(f"# h values: {h_values}\n")
        f.write("# mode                                 mean_dKE_per_cell"
                "                                CoV\n")
        for mode_name in modes:
            vals = headline[mode_name]
            cov = _cov(vals)
            f.write(f"# {mode_name:<36s} {vals}  CoV={cov:.4f}\n")

    # Also print the summary to stdout.
    print("\nCoV summary across h (std/mean of mean ΔKE-per-kick per cell):")
    print(f"  h values: {h_values}")
    for mode_name in modes:
        vals = headline[mode_name]
        cov = _cov(vals)
        print(f"  {mode_name:<36s} {vals}  CoV={cov:.4f}")
    print(f"\nCSV written to {out_path}")


if __name__ == "__main__":
    main()
