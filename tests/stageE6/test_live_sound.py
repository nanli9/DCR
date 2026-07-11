"""Tier 1 live-sound tests (Stage E6 demo).

Covers: the closed-form phasor synth against the reference bank (exactness of
the block/segment renderer), the streaming burst tracker against the offline
extractor (identical events from identical force streams), the live tap on
the real dinner scene with a stub engine (headless — no audio device), and a
real-output-stream smoke that skips gracefully without hardware.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.sound import AudioBasis, extract_impulses, render_modes_reference
from dcr.sound.events import SoundLog
from dcr.sound.live import BurstTracker, ComplexModalSynth, LiveExcitationTap
from dcr.sound.logger import RowCache


# ---------------------------------------------------------------------------
# Closed-form synth ≡ reference bank
# ---------------------------------------------------------------------------

def _mini_basis(r=4):
    rng = np.random.default_rng(1)
    return AudioBasis(
        name="mini", kind="corners",
        omega=2 * np.pi * np.array([220.0, 987.0, 3210.0, 7654.0])[:r],
        zeta=np.array([1e-3, 4e-3, 8e-3, 2e-2])[:r],
        weight=rng.uniform(0.5, 1.5, r),
        phi_corners=np.zeros((8, r)), corner_signs=np.zeros((8, 3)))


def test_phasor_synth_matches_reference_bank():
    fs = 44100.0
    basis = _mini_basis()
    n = 4096
    rng = np.random.default_rng(2)
    kick_at = np.sort(rng.choice(np.arange(1, n - 1), size=6, replace=False))
    kick_g = [rng.normal(size=basis.n_modes) for _ in kick_at]

    # Reference: velocity-jump tracks through the exact per-sample propagator.
    u = np.zeros((basis.n_modes, n))
    for pos, g in zip(kick_at, kick_g):
        u[:, pos] += g
    y_ref = basis.weight @ render_modes_reference(u, basis.omega, basis.zeta, fs)

    # Live synth: block/segment rendering with kicks at intra-block offsets,
    # exactly as LiveSoundEngine._callback drives it.
    block = 173                                   # odd on purpose
    syn = ComplexModalSynth(basis, fs, max_block=block)
    y_live = np.zeros(n)
    ki = 0
    for b0 in range(0, n, block):
        frames = min(block, n - b0)
        offs: dict[int, list] = {}
        while ki < len(kick_at) and kick_at[ki] < b0 + frames:
            offs.setdefault(int(kick_at[ki] - b0), []).append(kick_g[ki])
            ki += 1
        cur = 0
        for off in sorted(offs):
            syn.render_into(y_live, b0 + cur, off - cur)
            for g in offs[off]:
                syn.kick(g)
            cur = off
        syn.render_into(y_live, b0 + cur, frames - cur)

    assert np.allclose(y_live, y_ref, atol=1e-9, rtol=1e-8)


# ---------------------------------------------------------------------------
# Streaming tracker ≡ offline extractor
# ---------------------------------------------------------------------------

def _synthetic_log(n_sub=48, n_rows=3, h_sub=1.0 / 240.0):
    rng = np.random.default_rng(3)
    F = np.zeros((n_sub, n_rows), dtype=np.float32)
    # row 0: clean impact — rise over 2 substeps, plateau, release, re-hit
    F[10, 0], F[11, 0] = 300.0, 520.0
    F[12:18, 0] = 480.0
    F[24, 0], F[25:30, 0] = 200.0, 180.0
    # row 1: resting load with sub-floor jitter (must stay silent)
    F[:, 1] = 5.0 + 0.02 * rng.standard_normal(n_sub).astype(np.float32)
    # row 2: single-substep spike
    F[30, 2] = 90.0
    corner_x = rng.uniform(-1, 1, (n_sub, n_rows)).astype(np.float32)
    corner_z = rng.uniform(-0.5, 0.5, (n_sub, n_rows)).astype(np.float32)
    body_vy = rng.uniform(-3, 0, (n_sub, 2)).astype(np.float32)
    return SoundLog(
        h_sub=h_sub,
        row_body=np.array([0, 1, 0], dtype=np.int32),
        row_off=rng.uniform(-0.1, 0.1, (n_rows, 3)),
        F=F, corner_x=corner_x, corner_z=corner_z, body_vy=body_vy,
        e_mech=np.zeros(n_sub), body_mass=np.array([5.0, 0.5]))


def test_burst_tracker_matches_offline_extractor():
    log = _synthetic_log()
    j_floor = 1e-3
    off_ev = extract_impulses(log, j_floor=j_floor)

    cache = RowCache(
        cidx=np.arange(log.F.shape[1], dtype=np.int64),
        body=log.row_body.astype(np.int64), off=log.row_off,
        U=np.zeros((log.F.shape[1], 2)),
        y_rest=np.zeros(log.F.shape[1]), Il=np.zeros((2, 3, 3)))
    tracker = BurstTracker(cache, log.h_sub, j_floor=j_floor)
    live = []
    for k in range(log.n_substeps):
        live.extend(tracker.push(log.F[k], log.corner_x[k],
                                 log.corner_z[k], log.body_vy[k]))

    assert len(live) == off_ev.n_events >= 3
    live.sort(key=lambda e: (e.k_onset, e.row))
    order = np.lexsort((off_ev.row, off_ev.k_sub))
    for i, ev in enumerate(live):
        j = order[i]
        assert ev.k_onset == int(off_ev.k_sub[j])
        assert ev.row == int(off_ev.row[j])
        assert abs(ev.impulse - float(off_ev.impulse[j])) < 1e-12
        assert abs(ev.v_impact - float(off_ev.v_impact[j])) < 1e-6
        assert abs(ev.x - float(off_ev.x[j])) < 1e-6
        assert abs(ev.z - float(off_ev.z[j])) < 1e-6
    # Row 1's initial 0→5 N landing at k=0 is a genuine onset (both
    # extractors agree); the sub-floor jitter AFTER it must stay silent.
    row1 = [ev for ev in live if ev.row == 1]
    assert len(row1) == 1 and row1[0].k_onset == 0


# ---------------------------------------------------------------------------
# Live tap on the real dinner scene (headless — stub engine, no audio device)
# ---------------------------------------------------------------------------

def test_settle_arm_index():
    from dcr.sound import settle_arm_index

    # settle burst 0.01–0.10, quiet, impact at 0.35 → arm exactly there
    t = np.array([0.01, 0.02, 0.04, 0.08, 0.10, 0.35, 0.36, 0.9])
    assert settle_arm_index(t, quiet_gap=0.15) == 5
    # no settle noise: first event already past the gap from t=0 → play all
    assert settle_arm_index(np.array([0.3, 0.4]), quiet_gap=0.15) == 0
    # never-quiet scene: the mute_max deadline arms
    dense = np.arange(0.0, 2.0, 0.05)
    i = settle_arm_index(dense, quiet_gap=0.15, mute_max=0.5)
    assert np.isclose(dense[i], 0.5)
    # disabled
    assert settle_arm_index(t, quiet_gap=0.0) == 0
    # empty
    assert settle_arm_index(np.zeros(0)) == 0


def test_settle_prominence_breakthrough():
    from dcr.sound import settle_arm_index

    # A loud impact INSIDE the settle window (gap 0.02 < 0.15) breaks
    # through: settle clinks ~0.028 N·s, impact 2.1 ≥ 5×0.028.
    t = np.array([0.04, 0.05, 0.06, 0.08, 0.30, 0.31])
    j = np.array([0.028, 0.018, 0.004, 2.10, 0.20, 0.10])
    assert settle_arm_index(t, j, quiet_gap=0.15) == 3
    # Growing settle clinks below the absolute floor never false-arm:
    # 0.001 → 0.01 is 10× but 0.01 < 5 × arm_j_floor(0.02) = 0.1.
    t2 = np.array([0.02, 0.04, 0.30])
    j2 = np.array([0.001, 0.010, 0.500])
    assert settle_arm_index(t2, j2, quiet_gap=0.15) == 2
    # prominence disabled → gap rule only (impact at 0.08 gets swallowed,
    # arms at the post-crash quiet event)
    assert settle_arm_index(t, j, quiet_gap=0.15, prominence=0.0) == 4


class _StubEngine:
    def __init__(self):
        self.pushed = []

    def push_kicks(self, t_sim, kicks):
        self.pushed.append((t_sim, kicks))


def test_live_tap_dinner_headless():
    from scenes.reduced_dinner_table import build_reduced_dinner_table
    from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

    handle = build_reduced_dinner_table(
        h=1.0 / 120.0, device="cpu", iterations=6, avbd_substeps=2,
        pot_drop_xz=(0.0, 0.0), solver="avbd", support_basis="debug")

    rng = np.random.default_rng(0)
    r = 6
    table_basis = AudioBasis(
        name="synthetic", kind="grid",
        omega=2 * np.pi * np.linspace(200.0, 2000.0, r),
        zeta=np.full(r, 5e-3), weight=np.full(r, 1.0),
        phi_grid=0.05 * rng.standard_normal((N_GRID_X * N_GRID_Z, r)),
        length=2.2, width=1.1, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)

    engine = _StubEngine()
    tap = LiveExcitationTap(handle.world, engine, table_basis=table_basis)
    for _ in range(108):                          # 0.9 s: impact at ~0.32 s
        handle.world.step()
    tap.detach()

    assert tap.events_emitted >= 1
    assert len(engine.pushed) == tap.events_emitted
    assert tap.ledger.holds()                     # §15-form live inequality
    assert tap.ledger.cum_rigid_loss > 0.0
    g_all = np.concatenate([g for _, kicks in engine.pushed
                            for _, g in kicks])
    assert np.all(np.isfinite(g_all)) and np.any(g_all != 0.0)
    # Settle muting (default on): the t≈0 placement-gap clinks are swallowed;
    # everything played is at/after the pot impact (~0.33 s).
    assert tap.events_muted > 0
    assert min(t for t, _ in engine.pushed) > 0.25


def test_live_tap_low_drop_prominence_arming():
    """Drop from 0.25 m → impact at ~0.23 s, INSIDE the settle window
    (settle ends ~0.14 s, gap 0.09 < 0.15): the gap rule alone would swallow
    the crash; the prominence rule must arm on the loud pot impact."""
    from scenes.reduced_dinner_table import build_reduced_dinner_table
    from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

    handle = build_reduced_dinner_table(
        h=1.0 / 120.0, device="cpu", iterations=6, avbd_substeps=2,
        pot_drop_xz=(0.0, 0.0), pot_drop_height=0.25, solver="avbd",
        support_basis="debug")

    rng = np.random.default_rng(0)
    r = 4
    table_basis = AudioBasis(
        name="synthetic", kind="grid",
        omega=2 * np.pi * np.linspace(200.0, 1500.0, r),
        zeta=np.full(r, 5e-3), weight=np.full(r, 1.0),
        phi_grid=0.05 * rng.standard_normal((N_GRID_X * N_GRID_Z, r)),
        length=2.2, width=1.1, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)

    engine = _StubEngine()
    tap = LiveExcitationTap(handle.world, engine, table_basis=table_basis)
    for _ in range(60):                           # 0.5 s
        handle.world.step()
    tap.detach()

    assert tap.events_muted > 0                   # settle clinks swallowed
    assert tap.events_emitted >= 1                # …but the crash played
    t_first = min(t for t, _ in engine.pushed)
    assert 0.18 < t_first < 0.28                  # armed AT the impact


# ---------------------------------------------------------------------------
# Real output stream smoke (skips without audio hardware)
# ---------------------------------------------------------------------------

def test_engine_stream_smoke():
    sd = pytest.importorskip("sounddevice")
    from dcr.sound.live import LiveSoundEngine

    engine = LiveSoundEngine(fs=44100.0, blocksize=256, gain=0.01)
    engine.add_voice("v", _mini_basis())
    try:
        engine.start()
    except Exception as e:                        # no device in CI → skip
        pytest.skip(f"no audio output device: {e}")
    import time
    engine.push_kicks(0.0, [("v", np.full(4, 0.2))])
    time.sleep(0.35)
    engine.stop()
    st = engine.stats()
    assert st["blocks"] > 10
    assert st["kicks_played"] == 1
    assert st["peak_pre_gain"] > 0.0              # signal actually rendered
    assert st["max_cb_ms"] < 5.0                  # callback well under budget
