"""Stage E6 GPU sound architecture — Stage A/B parity tests (CPU device).

The device staging kernels (`dcr/avbd/_solver/sound_stage_kernels.py`) and
the per-frame ring drain (`dcr.sound.logger.DeviceRingSource`) must produce
the SAME excitation stream as the host hook tap (`sample_substep`), on warp's
CPU device — the same kernels run on CUDA, so this is the local half of the
validation; the 4090 run re-asserts it on real CUDA (device-parity idiom of
tests/avbd_native).

Tolerances: the staging kernel reads the float32 `q_modal` mirror where the
host tap reads the float64 `_q_modal_host` (both post-solve, see the kernel
module docstring), so F carries an f32-rounding-of-q difference amplified by
the AVBD penalty ρ — bounded well under 0.05 N against 10²-N impacts. Corners
and v_y are float64-from-float32 on both sides (tight); e_mech differs only
by summation order.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.sound import AudioBasis
from dcr.sound.live import LiveExcitationTap
from dcr.sound.logger import attach_sound_logger


def _build_dinner():
    from scenes.reduced_dinner_table import build_reduced_dinner_table
    return build_reduced_dinner_table(
        h=1.0 / 120.0, device="cpu", iterations=6, avbd_substeps=2,
        pot_drop_xz=(0.0, 0.0), solver="avbd", support_basis="debug")


def _support_basis(r=4):
    from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z
    rng = np.random.default_rng(0)
    return AudioBasis(
        name="synthetic", kind="grid",
        omega=2 * np.pi * np.linspace(200.0, 1500.0, r),
        zeta=np.full(r, 5e-3), weight=np.full(r, 1.0),
        phi_grid=0.05 * rng.standard_normal((N_GRID_X * N_GRID_Z, r)),
        length=2.2, width=1.1, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)


# ---------------------------------------------------------------------------
# Stage A: staged ring record ≡ host hook sampler, same run
# ---------------------------------------------------------------------------

def test_ring_staging_matches_hook_sampler():
    handle = _build_dinner()
    world = handle.world
    hook_log = attach_sound_logger(world, source="hook")
    ring_log = attach_sound_logger(world, source="ring")
    n_steps = 108                                 # 0.9 s: impact at ~0.32 s
    for _ in range(n_steps):
        world.step()
        ring_log.drain()                          # per-frame cadence
    a = hook_log.finalize()
    hook_log.detach()
    b = ring_log.finalize()
    ring_log.detach()

    assert a.n_substeps == b.n_substeps == n_steps * 2
    assert a.h_sub == b.h_sub
    assert a.F.shape == b.F.shape
    assert float(a.F.max()) > 100.0               # the pot actually landed
    # Engaged force: f32-mirror-q vs f64-host-q, amplified by ρ (docstring).
    assert np.allclose(b.F, a.F, atol=5e-2, rtol=1e-4)
    # Corner world (x, z): float64 math from identical float32 state.
    assert np.allclose(b.corner_x, a.corner_x, atol=1e-5)
    assert np.allclose(b.corner_z, a.corner_z, atol=1e-5)
    # v_y: read straight from the same float32 array on both sides.
    assert np.array_equal(b.body_vy, a.body_vy)
    # Mechanical energy: summation order only.
    assert np.allclose(b.e_mech, a.e_mech, rtol=1e-9, atol=1e-6)


# ---------------------------------------------------------------------------
# Stage B: ring tap ≡ hook tap — events, kicks, chokes, ledger — same run
# ---------------------------------------------------------------------------

class _StubEngine:
    fs = 44100.0

    def __init__(self):
        self.pushed = []
        self.chokes = []
        self.noise = []

    def push_kicks(self, t_sim, kicks):
        self.pushed.append((t_sim, kicks))

    def push_choke(self, t_sim, key, choked):
        self.chokes.append((t_sim, key, choked))

    def push_noise(self, t_sim, samples):
        self.noise.append((t_sim, samples))


def test_ring_tap_event_and_ledger_parity_with_hook_tap():
    handle = _build_dinner()
    world = handle.world
    basis = _support_basis()

    eng_hook, eng_ring = _StubEngine(), _StubEngine()
    tap_hook = LiveExcitationTap(world, eng_hook, support_basis=basis,
                                 source="hook")
    tap_ring = LiveExcitationTap(world, eng_ring, support_basis=basis,
                                 source="ring")
    for _ in range(108):
        world.step()
        tap_ring.drain()
    tap_hook.detach()
    tap_ring.detach()

    assert tap_hook.events_emitted >= 1
    assert tap_ring.events_emitted == tap_hook.events_emitted
    assert tap_ring.events_muted == tap_hook.events_muted
    assert tap_ring.chokes_pushed == tap_hook.chokes_pushed
    # Ledger totals (deposits differ only by e_mech summation order; kicks by
    # the f32-q force delta).
    assert np.isclose(tap_ring.ledger.cum_rigid_loss,
                      tap_hook.ledger.cum_rigid_loss, rtol=1e-6, atol=1e-9)
    assert np.isclose(tap_ring.ledger.cum_kick_energy,
                      tap_hook.ledger.cum_kick_energy, rtol=1e-4, atol=1e-9)
    assert tap_ring.ledger.holds() and tap_hook.ledger.holds()
    # Kick-by-kick: same times, same voices, near-identical g.
    assert len(eng_ring.pushed) == len(eng_hook.pushed)
    for (t_r, kicks_r), (t_h, kicks_h) in zip(eng_ring.pushed,
                                              eng_hook.pushed):
        assert t_r == t_h
        assert len(kicks_r) == len(kicks_h)
        for (k_r, g_r), (k_h, g_h) in zip(kicks_r, kicks_h):
            assert k_r == k_h
            # Small-J bursts accumulate the f32-mirror-q force delta over a
            # couple of substeps → ≲1% relative on the quietest kicks.
            assert np.allclose(g_r, g_h, rtol=1e-2, atol=1e-8)


# ---------------------------------------------------------------------------
# Graph-signature wiring: toggling staging must invalidate captured graphs
# ---------------------------------------------------------------------------

def test_sound_stage_toggles_graph_signature():
    handle = _build_dinner()
    handle.world.step()                # flush: signature inputs exist after
    s = handle.world._solver
    sig_off = s._current_graph_signature()
    s.enable_sound_stage()
    sig_on = s._current_graph_signature()
    assert sig_on != sig_off
    s.disable_sound_stage()
    assert s._current_graph_signature() == sig_off


def test_hook_logger_rejects_resident_ring_allows():
    """The guard split: hook tap refuses a device-resident q-block (it would
    force per-substep syncs); the ring tap is the sanctioned path there. On
    CPU _modal_resident is False, so simulate the resident flag."""
    handle = _build_dinner()
    world = handle.world
    world._solver._modal_resident = True
    with pytest.raises(NotImplementedError, match="ring"):
        attach_sound_logger(world, source="hook")
    log = attach_sound_logger(world, source="ring")   # allowed
    log.detach()
    world._solver._modal_resident = False
