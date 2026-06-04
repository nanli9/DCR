"""Regression: the Phase-A patch modal back-reaction must not pump the
modal reservoir.

Before the dissipativity guard (passive_dcr.py, after the §9.6 scaling),
the truck scene's patch back-reaction `q̇ -= Φᵀλ` created modal energy
every step (its +½‖Φᵀλ‖² self-term), running E_modal to ~2e5 J and making
the slab flap forever — see docs/avbd_dcr_coupling_findings.md §5/§6. The
guard scales the impulse by the largest γ∈[0,1] keeping the back-reaction's
modal-energy change ≤ 0, so E_modal stays funded only by the bounded
injection and decays under Rayleigh damping.
"""
import numpy as np
import pytest

from dcr.modal.energy import modal_energy

try:
    from scripts.run_scenes_avbd import build_truck_scene
except Exception:  # pragma: no cover - scene builder optional in some envs
    build_truck_scene = None


@pytest.mark.skipif(build_truck_scene is None,
                    reason="truck scene builder unavailable")
def test_truck_patch_back_reaction_is_dissipative():
    world, coupler, _boxes, _mesh, _ = build_truck_scene(
        device="cpu", h=1.0 / 120.0, eta=0.5, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    freqs = coupler.modal.frequencies
    stp = coupler._stepper

    peak = 0.0
    for _ in range(180):
        world.step()
        peak = max(peak, float(modal_energy(stp.q, stp.qdot, freqs)))
        # The guard scale is always a valid fraction.
        assert 0.0 <= coupler.last_backreaction_gamma_min <= 1.0 + 1e-9

    # Pre-fix this exceeded 1e5 J by step ~180; the legitimate impact-driven
    # peak is ~7e2 J. 5e3 J leaves margin while still catching any regression
    # of the pumping back-reaction.
    assert peak < 5.0e3, f"modal reservoir ran away: peak E_modal = {peak:.3e} J"
