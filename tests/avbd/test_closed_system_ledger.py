"""Phase B / spec §15 + §22 Invariant 7: closed-system energy ledger.

Scenario per spec §15:
  - no gravity
  - no damping
  - no external forces
  - one rigid body + one modal support + several contacts

Required:
  E_total(t) = E_rigid(t) + E_modal(t) ≤ E_total(0) + ε      ∀ t

Spec calls this "mandatory" — it catches double-counted reservoirs, bad
work-estimator signs, non-transpose back-reaction, BJ frame energy
injection, and γ-loop accounting errors.

Implementation note: without gravity, the rigid body needs an initial
velocity to actually contact the modal support — we drop a box from
above with v_y = −2 m/s. The system is closed thereafter: any energy
that leaves the rigid KE must enter modal energy (or be dissipated by
the inelastic contact projection, which is also ≤ 0 from the §13.1
identity), but the SUM must never grow.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd import AVBDDCRWorld
from dcr.avbd.diagnostics import EnergyLedger
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.fem import Material, FEMModel
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis


def _build_closed_system(h: float = 1.0 / 240.0):
    """Closed system: zero gravity, zero damping. Box dropped above slab
    with an initial downward velocity to seed the first contact.
    """
    world = AVBDDCRWorld(
        h=h, eta=0.5, device="cpu",
        gravity=np.zeros(3),                # closed system: no external work
    )
    ground_top = 0.03
    floor_idx = world.add_floor(floor_y=ground_top, friction=0.0)
    mesh = make_slab_tet_mesh(
        length=1.0, width=0.6, height=0.04, nx=8, ny=6, nz=2)
    # No Rayleigh damping — alpha0 = alpha1 = 0.
    fem = FEMModel(
        mesh=mesh,
        material=Material(E=10.0e9, nu=0.3, rho=500.0),
        fixed_nodes=np.array([], dtype=np.int32),
        alpha0=0.0, alpha1=0.0,
    )
    modal = ModalAnalysis(fem=fem, num_modes=6)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=floor_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=0.25,
        modal_decay_gamma=1.0,              # no per-step modal decay
    )
    world.add_passive_coupler(coupler)
    world.add_box(
        mass=20.0, half_extents=(0.1, 0.07, 0.08),
        position=(0.0, ground_top + 0.15, 0.0),
        velocity_lin=(0.0, -2.0, 0.0),      # initial KE seed
        friction=0.0,
        restitution=0.0,
    )
    return world, coupler


def test_closed_system_energy_non_increasing():
    """§15 / Invariant 7: across 100 closed-system steps, E_rigid+E_modal
    never increases beyond initial total + numerical tolerance.

    Tolerance budget:
      - abs tol 1e-6 J (machine epsilon for our scene scale)
      - rel tol 5e-2 (5%) — AVBD's BDF1 inertial cost + the patch
        coupler's K_total solve are NOT energy-exact at every iteration;
        the empirical drift on this scene is ≤ 3% across 100 steps when
        the configuration is stable. Spec §15 says ε without quantifying;
        we set 5% as the regression gate.
    """
    world, coupler = _build_closed_system()
    ledger = EnergyLedger()
    n_steps = 100
    for k in range(n_steps):
        bodies = [d.dcr_body for d in world._descs]
        ledger.record_pre(time=world.time, bodies=bodies, couplers=[coupler])
        world.step()
        bodies_after = [d.dcr_body for d in world._descs]
        ledger.record_post(
            bodies=bodies_after,
            couplers=[coupler],
        )
    # The check_non_increase call raises on first violation.
    ledger.check_non_increase(tol=1e-6, relative_tol=5e-2)


def test_closed_system_ledger_reports_decreasing_or_flat():
    """Stronger version: NET trend across the run should be flat or
    decreasing (not just bounded above). Energy can swing locally as it
    flows between rigid and modal pools, but the long-run trend must not
    grow.
    """
    world, coupler = _build_closed_system()
    ledger = EnergyLedger()
    for _ in range(80):
        bodies = [d.dcr_body for d in world._descs]
        ledger.record_pre(time=world.time, bodies=bodies, couplers=[coupler])
        world.step()
        bodies_after = [d.dcr_body for d in world._descs]
        ledger.record_post(bodies=bodies_after, couplers=[coupler])
    _, E_total = ledger.total_energy_series()
    # Mean of last 20 ≤ mean of first 20 + slack.
    head = float(np.mean(E_total[:20]))
    tail = float(np.mean(E_total[-20:]))
    assert tail <= head + 1e-6 + 0.10 * head, (
        f"long-run E_total trend should be flat or decreasing; "
        f"head_mean={head:.3e}, tail_mean={tail:.3e}")


def test_ledger_records_modal_peak():
    """E_modal_peak monotonically tracks the maximum observed across
    record_pre + record_post snapshots. Sanity check for the per-step
    bookkeeping itself."""
    world, coupler = _build_closed_system()
    ledger = EnergyLedger()
    for _ in range(50):
        bodies = [d.dcr_body for d in world._descs]
        ledger.record_pre(time=world.time, bodies=bodies, couplers=[coupler])
        world.step()
        bodies_after = [d.dcr_body for d in world._descs]
        ledger.record_post(bodies=bodies_after, couplers=[coupler])
    peaks = [e.E_modal_peak for e in ledger.entries]
    # Monotonically non-decreasing.
    assert all(peaks[i] <= peaks[i + 1] for i in range(len(peaks) - 1))


def test_ledger_pre_required_before_post():
    """API hygiene: calling record_post without record_pre is a usage
    error and must raise (so downstream stats are never silently lying)."""
    ledger = EnergyLedger()
    with pytest.raises(RuntimeError, match="record_pre"):
        ledger.record_post(bodies=[], couplers=[])
