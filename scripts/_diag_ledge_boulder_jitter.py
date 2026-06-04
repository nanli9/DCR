#!/usr/bin/env python3
"""WHY does the boulder jitter (more) on the ledge scene?

Re-investigation. Earlier claim was "stacked pillars leak E_loss → laundered to
the boulder by |λ_N| weight → patch kicks the boulder." This probe tests that
mechanism against the alternative: the boulder sits at x=0.30 on a cantilever
ledge clamped at x=-0.6, i.e. far out toward the FREE END where the modal
deflection Φ(x̄) is largest, so it both injects strongly AND receives the
strongest patch kick v_f = Φ(x̄)·q̇ — a self-sustaining loop localized at the
free end, independent of the pillars.

Discriminators (viewer default: prescribed+reservoir+δp, μ=1, η=0.5, β=0.25):
  FULL        : pedestal + 3 pillars + boulder
  BOULDER_ONLY: boulder alone on the ledge (no stack at all)
  PATCH_OFF   : β=0 (no distant-response back to any body)
  ETA0        : η=0 (no injection, empty reservoir)
  PASSIVE     : injection_scaling='passive' (no synthesis)

If BOULDER_ONLY still jitters ≈ FULL → it is NOT laundered from the pillars; it
is the free-end modal loop. Also reports Φ-amplitude at the boulder vs pedestal
contact to quantify the free-end amplification.
"""
from __future__ import annotations

import numpy as np

from dcr.avbd import AVBDDCRWorld
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.modal.passive_inject import eval_basis_at_point
from dcr.fem import Material, FEMModel
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy


def _fix_one_edge(mesh):
    v = mesh.vertices
    xmin = v[:, 0].min()
    return np.where(np.abs(v[:, 0] - xmin) < 1e-8)[0].astype(np.int32)


def build(with_stack: bool, eta: float, beta: float):
    """Replica of build_ledge_scene with an optional stack."""
    world = AVBDDCRWorld(h=1.0 / 120.0, eta=eta, device="cpu",
                         avbd_iterations=10, avbd_substeps=4)
    ledge_top = 0.04
    ledge_idx = world.add_floor(floor_y=ledge_top, friction=0.5, name="ledge")
    mesh = make_slab_tet_mesh(length=1.2, width=0.8, height=0.08,
                              nx=12, ny=8, nz=2)
    mat = Material(E=10.0e9, nu=0.3, rho=500.0)
    fem = FEMModel(mesh=mesh, material=mat,
                   fixed_nodes=_fix_one_edge(mesh), alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=15)
    coupler = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=ledge_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=beta, deformed_normal_method="patch_fit",
        causal_gating=False, modal_decay_gamma=1.0)
    world.add_passive_coupler(coupler)

    names = {}
    if with_stack:
        ped_h = (0.06, 0.05, 0.06)
        names["pedestal"] = world.add_box(
            mass=5.0, half_extents=ped_h,
            position=(0.0, ledge_top + ped_h[1] + 0.001, 0.0),
            friction=0.4, name="pedestal")
        pillar_h = (0.01, 0.04, 0.01)
        pedestal_top = ledge_top + 2 * ped_h[1] + 0.001
        offsets = [(0.04, 0.0, -0.035), (0.04, 0.0, 0.00), (0.04, 0.0, 0.035)]
        for si, (sx, _, sz) in enumerate(offsets):
            names[f"box_{si}"] = world.add_box(
                mass=0.5, half_extents=pillar_h,
                position=(sx, pedestal_top + pillar_h[1] + 0.001, sz),
                friction=0.5, name=f"box_{si}")
    bh = 0.08
    names["boulder"] = world.add_box(
        mass=50.0, half_extents=(bh, bh, bh),
        position=(0.30, ledge_top + bh + 0.8, 0.0), friction=0.5, name="boulder")
    return world, coupler, names


def viewer_default(coupler):
    coupler.use_impact_reservoir = True
    coupler.impulse_source = "delta_p"
    coupler.injection_scaling = "prescribed"
    coupler.prescribed_mu = 1.0


def run(label, with_stack=True, eta=0.5, beta=0.25, scaling="prescribed",
        n=600):
    world, coupler, names = build(with_stack, eta, beta)
    viewer_default(coupler)
    coupler.injection_scaling = scaling
    b_idx = names["boulder"]
    bodies = world.bodies

    vy = np.zeros(n)
    ypos = np.zeros(n)
    modalE = np.zeros(n)
    patch_lam = np.zeros(n)
    vf = np.zeros(n)
    for step in range(n):
        world.step()
        vy[step] = float(bodies[b_idx].velocity[1])
        ypos[step] = float(bodies[b_idx].position[1])
        modalE[step] = float(modal_energy(
            coupler._stepper.q, coupler._stepper.qdot,
            coupler.modal.frequencies))
        if coupler.last_patch_kicks:
            for pk in coupler.last_patch_kicks:
                if pk.body_idx == b_idx:
                    patch_lam[step] = float(np.linalg.norm(pk.lam))
                    vf[step] = float(np.linalg.norm(pk.v_f))

    # Detect impact: first step the boulder's downward speed collapses after
    # the fall (|vy| crosses below 0.05 m/s having been > 1 m/s).
    falling = np.where(vy < -1.0)[0]
    impact = int(falling[-1]) + 1 if len(falling) else 60
    impact = min(impact, n - 1)

    def win(a, lo, hi):
        seg = a[lo:hi]
        return seg if len(seg) else a[-1:]

    # Phases relative to impact.
    tr = (impact, min(impact + 60, n))        # transient: 0.5 s post-impact
    late = (min(impact + 180, n - 1), n)       # late: ≥1.5 s post-impact
    vt = win(vy, *tr)
    vl = win(vy, *late)
    return {
        "label": label, "impact": impact,
        "tr_std": float(np.std(vt)), "tr_max": float(np.max(np.abs(vt))),
        "tr_flips": int(np.sum(np.diff(np.sign(vt)) != 0)),
        "late_std": float(np.std(vl)), "late_max": float(np.max(np.abs(vl))),
        "peak_vy": float(np.max(np.abs(vy[impact:]))),
        "peak_step": int(impact + np.argmax(np.abs(vy[impact:]))),
        "modalE_tr": float(np.mean(win(modalE, *tr))),
        "modalE_late": float(np.mean(win(modalE, *late))),
        "lam_tr": float(np.mean(win(patch_lam, *tr))),
        "vf_tr": float(np.mean(win(vf, *tr))),
    }


def phi_amplitude():
    """Compare ‖Φ(x̄)‖ (modal deflection sensitivity) at the boulder contact
    (x=0.30, free-end side) vs the pedestal contact (x=0.0, near clamp)."""
    world, coupler, names = build(with_stack=True, eta=0.5, beta=0.25)
    surf = coupler._surface
    U = coupler.modal.U_surf
    svi = coupler.modal.surface_vertex_indices
    v2s = coupler._vert_to_surf_idx
    out = {}
    for nm, x in [("pedestal x=0.0", np.array([0.0, 0.04, 0.0])),
                  ("boulder  x=0.30", np.array([0.30, 0.04, 0.0]))]:
        Phi = eval_basis_at_point(x, surf, U, svi, v2s)  # (3, m)
        # ‖Φ‖_F = sensitivity of surface velocity at x to a unit modal velocity
        out[nm] = float(np.linalg.norm(Phi))
    return out


def main():
    print("Φ(x̄) Frobenius norm (surface-velocity sensitivity to q̇):")
    for k, v in phi_amplitude().items():
        print(f"   {k}: ‖Φ‖_F = {v:.4f}")
    amp = phi_amplitude()
    ratio = amp["boulder  x=0.30"] / amp["pedestal x=0.0"]
    print(f"   → boulder/pedestal Φ-amplitude ratio = {ratio:.2f}×\n")

    configs = [
        ("FULL  (prescribed, stack)        ", dict()),
        ("BOULDER_ONLY (prescribed)        ", dict(with_stack=False)),
        ("PATCH_OFF  β=0 (stack)           ", dict(beta=0.0)),
        ("ETA0  η=0 (stack)                ", dict(eta=0.0)),
        ("PASSIVE scaling (stack)          ", dict(scaling="passive")),
        ("BOULDER_ONLY PATCH_OFF β=0       ", dict(with_stack=False, beta=0.0)),
    ]
    print("Boulder vy jitter — TRANSIENT = 0.5s post-impact, LATE = ≥1.5s:")
    print(f"{'config':<34}{'impact':>7}{'tr_std':>10}{'tr_max':>10}"
          f"{'tr_flip':>8}{'late_std':>10}{'peak_vy':>10}"
          f"{'modalE_tr':>10}{'|v_f|tr':>9}")
    rows = {}
    for label, kw in configs:
        r = run(label, **kw)
        rows[label.strip()] = r
        print(f"{label:<34}{r['impact']:>7d}{r['tr_std']:>10.2e}"
              f"{r['tr_max']:>10.2e}{r['tr_flips']:>8d}{r['late_std']:>10.2e}"
              f"{r['peak_vy']:>10.2e}{r['modalE_tr']:>10.3g}{r['vf_tr']:>9.2e}")

    print("\n" + "=" * 76)
    full = rows["FULL  (prescribed, stack)"]
    bonly = rows["BOULDER_ONLY (prescribed)"]
    patchoff = rows["PATCH_OFF  β=0 (stack)"]
    passive = rows["PASSIVE scaling (stack)"]
    frac = bonly["tr_std"] / full["tr_std"] if full["tr_std"] else 0.0
    print(f"BOULDER_ONLY transient jitter is {frac*100:.0f}% of FULL "
          f"→ {'NOT laundered from pillars (self-sustaining)' if frac > 0.5 else 'pillar-dependent'}")
    print(f"PATCH_OFF transient jitter = {patchoff['tr_std']:.2e} "
          f"({patchoff['tr_std']/full['tr_std']*100:.1f}% of FULL) "
          f"→ patch is {'THE transmission path' if patchoff['tr_std'] < 0.1*full['tr_std'] else 'not the only path'}")
    print(f"PRESCRIBED vs PASSIVE transient jitter: "
          f"{full['tr_std']:.2e} vs {passive['tr_std']:.2e} "
          f"({full['tr_std']/passive['tr_std']:.1f}×)")
    print("=" * 76)


if __name__ == "__main__":
    main()
