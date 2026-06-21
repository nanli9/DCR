"""M1.4 — the production shelf scene driven through the native modal path.

`build_reduced_shelf(solver="native")` wires the support's modal q as a native
solver DOF (no coupler). Validates the real scene runs, the support rings on
impact (two-way), the frozen-q̇ counterfactual does not, and nothing tunnels.
"""
from __future__ import annotations

import numpy as np
import pytest

from scenes.reduced_shelf import build_reduced_shelf


def _run(freeze: bool, n_steps: int = 70):
    h = build_reduced_shelf(
        device="cpu", solver="native",
        impactor_drop_height=0.05, impactor_mass=4.0,
        iterations=8, avbd_substeps=4,
    )
    s = h.world._solver
    s._modal_freeze_qdot = freeze
    peak_KE = 0.0
    for _ in range(n_steps):
        h.world.step()
        peak_KE = max(peak_KE, s.last_modal_KE)
    P = s.positions()
    assert np.all(np.isfinite(P)), "no NaNs in body positions"
    return h, s, peak_KE, P


def test_native_shelf_runs_and_rings():
    h, s, peak_KE, P = _run(freeze=False)
    # The drop loads + rings the modal support (two-way energy loop).
    assert s.last_q_norm > 1e-6, "support should be deflected by the drop"
    assert peak_KE > 1e-9, f"support should ring (peak modal KE {peak_KE:.2e})"
    # No body fell far below the shelf surface (no tunneling).
    assert float(P[:, 1].min()) > -0.05, "no body should tunnel through"


def test_native_shelf_two_way_counterfactual():
    _, _, peak_dyn, _ = _run(freeze=False)
    _, s_frz, peak_frz, _ = _run(freeze=True)
    assert np.allclose(s_frz.modal_qdot, 0.0), "frozen keeps q̇ ≡ 0"
    assert peak_dyn > 5.0 * max(peak_frz, 1e-30), (
        f"dynamic ring {peak_dyn:.2e} should dominate frozen {peak_frz:.2e}")


def test_native_shelf_no_coupler_attached():
    """Faithfulness: the native path attaches NO coupler / hook."""
    h, s, _, _ = _run(freeze=False, n_steps=2)
    assert h.world.reduced_coupled_coupler is None, "no coupler on native path"
    assert s.iteration_hook is None, "no iteration_hook on native path"
    assert s.substep_begin_hook is None and s.substep_end_hook is None
    assert h.world._native_modal_enabled is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
