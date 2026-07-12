"""Tier 1 — LIVE impact-sound engine (Stage E6 demo, user-approved 2026-07-11).

Streams the same excitation the offline render replays, while the sim runs:

    sim thread (substep_end_hook)                audio thread (PortAudio cb)
    ─────────────────────────────                ───────────────────────────
    sample_substep  (logger.py, shared)          drain kick queue
    incremental burst tracker (events.py logic)  segment-render damped phasors
    AudioLedger deposit/admit (render.py, §15)   soft-clip → device
    push γ-scaled kicks ────────────────────────▶

Synthesis is CLOSED-FORM: each mode is a damped complex phasor
q̇_i[n] = Re(c_i z_iⁿ) with pole z_i = e^{(−ζ_iω_i + iω_{d,i})/fs} — the exact
solution of the paper's SDOF oscillator (Eq. 8) between kicks, so blocks are
rendered with one complex multiply per voice and NO per-sample Python loop
(callback budget ≪ block duration). A velocity jump g adds
Δc = g·(1 + i·ζω/ω_d), identical to `bank.py`'s impulse-invariant response;
parity is asserted in tests/stageE6/test_live_sound.py.

# DEVIATION (offline path): the live path applies the Hertz τ-shaping
# SPECTRALLY — kicks are pre-scaled by |Ĥ(ω_i; τ)| (shaping.half_sine_spectrum)
# instead of time-spreading a kernel. Same magnitude response the offline
# kernel realizes and EXACTLY the quantity the E6 ledger admits, so live
# excitation and live accounting agree by construction; the ~τ/2 ≤ 2 ms group
# delay of the kernel is dropped (inaudible).
#
# E6 bound (foundation §15 form, §6 quadratic cap — see render.AudioLedger):
# ledger runs on the SIM thread, single-threaded, per substep:
#     Σ E_kick,live ≤ η_audio · Σ ΔE_rigid_loss + ε_tol.
"""
from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .audio_basis import AudioBasis, phi_at_corner, phi_at_xz
from .events import LoadedTracker
from .render import AudioLedger
from .shaping import half_sine_spectrum, hertz_tau
from .logger import (
    DeviceRingSource,
    RowCache,
    build_row_cache,
    sample_substep,
    validate_native_host_world,
    validate_native_world_ring,
)


# ---------------------------------------------------------------------------
# Closed-form per-voice synthesizer
# ---------------------------------------------------------------------------

class ComplexModalSynth:
    """Damped-phasor bank for one voice (module docstring math).

    `zeta_contact` (optional) precomputes a second, CHOKED pole table with
    per-mode ζ_i → max(ζ_i, zeta_contact); `set_choked` switches decay tables
    while the phasor state c carries over continuously — a damping change,
    not a re-strike, exactly what a body picking up / losing support load
    does to its ring. Without `zeta_contact` the synth is single-table and
    behaves as before.
    # DEVIATION (contact choke): see render._render_voice_phasor — free-air
    # modal damping while a body rests loaded on the support is the audibly
    # wrong limit; constant choked ζ is a render-side contact-damping
    # heuristic (no stiffness/frequency shift). Disclosed in docs/stageE6.
    """

    def __init__(self, basis: AudioBasis, fs: float, max_block: int,
                 gain: float = 1.0, zeta_contact: float | None = None):
        omega = np.asarray(basis.omega, dtype=np.float64)
        zeta = np.asarray(basis.zeta, dtype=np.float64)
        self._T = 1.0 / float(fs)
        self._n_pow = int(max_block)
        # (Zpow, jump) per choke state; Zpow[:, n] = z^n for n = 0..max_block
        # (last column advances a block).
        self._tables = {False: self._pole_table(omega, zeta)}
        if zeta_contact is not None:
            self._tables[True] = self._pole_table(
                omega, np.maximum(zeta, float(zeta_contact)))
        self.choked = False
        self.w = np.asarray(basis.weight, dtype=np.float64) * float(gain)
        self.c = np.zeros(omega.shape[0], dtype=np.complex128)

    def _pole_table(self, omega: NDArray[np.float64],
                    zeta: NDArray[np.float64]) -> tuple:
        zc = np.clip(zeta, 0.0, 0.999999)
        omega_d = omega * np.sqrt(1.0 - zc ** 2)
        assert np.all(omega_d * self._T < np.pi), \
            "audio mode above render Nyquist"
        z = np.exp((-zc * omega + 1j * omega_d) * self._T)
        jump = 1.0 + 1j * (zc * omega / np.maximum(omega_d, 1e-30))
        return z[:, None] ** np.arange(self._n_pow + 1)[None, :], jump

    def set_choked(self, choked: bool) -> None:
        """Switch decay tables (no-op unless built with zeta_contact)."""
        if True in self._tables:
            self.choked = bool(choked)

    def kick(self, g: NDArray[np.float64]) -> None:
        """Apply velocity jumps g (r,) NOW (at the current render cursor)."""
        jump = self._tables[self.choked][1]
        self.c = self.c + np.asarray(g, dtype=np.float64) * jump

    def render_into(self, out: NDArray[np.float64], start: int,
                    length: int) -> None:
        """Add this voice's next `length` samples into out[start:...] and
        advance the phasor states."""
        if length <= 0:
            return
        Zpow = self._tables[self.choked][0]
        out[start:start + length] += \
            self.w @ (self.c[:, None] * Zpow[:, :length]).real
        self.c = self.c * Zpow[:, length]

    def reset(self) -> None:
        self.c[:] = 0.0
        self.choked = False


# ---------------------------------------------------------------------------
# Incremental burst tracker (streaming twin of events.extract_impulses)
# ---------------------------------------------------------------------------

@dataclass
class _LiveEvent:
    k_onset: int
    row: int
    body: int
    impulse: float       # J [N·s]
    v_impact: float
    x: float
    z: float
    off: NDArray[np.float64]
    t: float             # onset sim time [s]


class BurstTracker:
    """Streaming version of `events.extract_impulses` — same open/accumulate/
    close-on-non-rising rule, same `j_floor`; parity-tested against the
    offline extractor on identical force streams."""

    def __init__(self, cache: RowCache, h_sub: float, j_floor: float = 1e-3):
        self.cache = cache
        self.h_sub = float(h_sub)
        self.j_floor = float(j_floor)
        n = cache.n_rows
        self._F_prev = np.zeros(n, dtype=np.float64)
        self._vy_prev: NDArray[np.float32] | None = None
        self._open_k = np.full(n, -1, dtype=np.int64)
        self._open_j = np.zeros(n, dtype=np.float64)
        self._onset_x = np.zeros(n, dtype=np.float64)
        self._onset_z = np.zeros(n, dtype=np.float64)
        self._onset_v = np.zeros(n, dtype=np.float64)
        self._k = 0

    def push(self, F: NDArray, corner_x: NDArray, corner_z: NDArray,
             body_vy: NDArray) -> list[_LiveEvent]:
        F = np.asarray(F, dtype=np.float64)
        dF = F - self._F_prev
        rising = dF > 0.0
        out: list[_LiveEvent] = []

        closing = np.nonzero(~rising & (self._open_k >= 0))[0]
        for r in closing:
            r = int(r)
            j = self._open_j[r] * self.h_sub
            if j > self.j_floor:
                out.append(_LiveEvent(
                    k_onset=int(self._open_k[r]), row=r,
                    body=int(self.cache.body[r]), impulse=float(j),
                    v_impact=float(self._onset_v[r]),
                    x=float(self._onset_x[r]), z=float(self._onset_z[r]),
                    off=self.cache.off[r],
                    t=float(self._open_k[r]) * self.h_sub))
            self._open_k[r] = -1
            self._open_j[r] = 0.0

        opening = np.nonzero(rising & (self._open_k < 0))[0]
        vy_pre = self._vy_prev if self._vy_prev is not None else body_vy
        for r in opening:
            r = int(r)
            self._open_k[r] = self._k
            self._onset_x[r] = float(corner_x[r])
            self._onset_z[r] = float(corner_z[r])
            self._onset_v[r] = abs(float(vy_pre[int(self.cache.body[r])]))
        self._open_j[rising] += dF[rising]

        self._F_prev = F
        self._vy_prev = np.asarray(body_vy, dtype=np.float32)
        self._k += 1
        return out


# ---------------------------------------------------------------------------
# Audio-thread engine
# ---------------------------------------------------------------------------

class LiveSoundEngine:
    """Owns the PortAudio output stream and the per-voice phasor banks.
    `push_kicks` is called from the sim thread; the callback drains, places
    kicks at sample offsets that preserve their relative sim timing within
    the block, and segment-renders."""

    def __init__(self, fs: float = 44100.0, blocksize: int = 256,
                 gain: float = 0.35):
        self.fs = float(fs)
        self.blocksize = int(blocksize)
        self.gain = float(gain)
        self._voices: dict[object, ComplexModalSynth] = {}
        self._q: queue.SimpleQueue = queue.SimpleQueue()
        self._stream = None
        # stats
        self.blocks = 0
        self.kicks_played = 0
        self.underruns = 0
        self.max_cb_ms = 0.0
        self.peak_pre_gain = 0.0
        self.clipped_blocks = 0

    def add_voice(self, key, basis: AudioBasis, gain: float = 1.0,
                  zeta_contact: float | None = None) -> None:
        if basis.n_modes == 0:
            return
        self._voices[key] = ComplexModalSynth(
            basis, self.fs, self.blocksize, gain=gain,
            zeta_contact=zeta_contact)

    @property
    def voice_keys(self):
        return set(self._voices.keys())

    def push_kicks(self, t_sim: float,
                   kicks: list[tuple[object, NDArray[np.float64]]]) -> None:
        """Sim-thread entry: schedule (voice_key, g) kicks stamped t_sim."""
        if kicks:
            self._q.put(("kicks", float(t_sim), kicks))

    def push_choke(self, t_sim: float, key, choked: bool) -> None:
        """Sim-thread entry: switch a voice's choke state. Applied at BLOCK
        granularity (≤ blocksize/fs ≈ 6 ms slop vs the kick timeline —
        inaudible for a damping change; disclosed approximation)."""
        self._q.put(("choke", float(t_sim), key, bool(choked)))

    def start(self) -> None:
        import sounddevice as sd     # lazy: repo must work without it
        kwargs: dict = {}
        try:
            sd.check_output_settings(samplerate=self.fs, channels=1)
        except Exception:
            # Default output unset/unusable (headless launch contexts leave
            # sd.default at -1, and even query_devices(kind="output")
            # resolves through it) — enumerate and take the first
            # output-capable device; if none exists, OutputStream raises.
            try:
                for i, d in enumerate(sd.query_devices()):
                    if int(d.get("max_output_channels", 0)) > 0:
                        kwargs["device"] = i
                        break
            except Exception:
                pass
        # Warm the render path (numpy/BLAS first-call costs land here, not in
        # the first real callback — the verification run's only >5 ms callback
        # was the cold first block).
        buf = np.zeros(self.blocksize, dtype=np.float64)
        for v in self._voices.values():
            v.render_into(buf, 0, self.blocksize)
            v.reset()
        self._stream = sd.OutputStream(
            samplerate=self.fs, blocksize=self.blocksize, channels=1,
            dtype="float32", latency="low", callback=self._callback, **kwargs)
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def reset_voices(self) -> None:
        for v in self._voices.values():
            v.reset()

    def stats(self) -> dict:
        return dict(blocks=self.blocks, kicks_played=self.kicks_played,
                    underruns=self.underruns, max_cb_ms=self.max_cb_ms,
                    peak_pre_gain=self.peak_pre_gain,
                    clipped_blocks=self.clipped_blocks,
                    voices=len(self._voices))

    # ---- audio thread ------------------------------------------------
    def _drain(self, frames: int) -> tuple[dict[int, list], dict]:
        """Queue → ({sample_offset: [(voice_key, g), ...]}, {key: choked}),
        kick offsets preserving relative sim timing within this block
        (earliest drained kick plays at offset 0 — "ASAP" scheduling; AV sync
        error ≈ one block + hook lag). Choke flips collapse to their LAST
        drained value and apply at block start (push_choke docstring)."""
        by_off: dict[int, list] = {}
        chokes: dict = {}
        t0 = None
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            if item[0] == "choke":
                chokes[item[2]] = item[3]
                continue
            _, t_sim, kicks = item
            if t0 is None:
                t0 = t_sim
            off = int(np.clip(round((t_sim - t0) * self.fs), 0, frames - 1))
            by_off.setdefault(off, []).extend(kicks)
        return by_off, chokes

    def _callback(self, outdata, frames, _time_info, status) -> None:
        t_cb = time.perf_counter()
        if status:
            self.underruns += 1
        try:
            buf = np.zeros(frames, dtype=np.float64)
            by_off, chokes = self._drain(frames)
            for key, flag in chokes.items():
                syn = self._voices.get(key)
                if syn is not None:
                    syn.set_choked(flag)
            cur = 0
            for off in sorted(by_off):
                for v in self._voices.values():
                    v.render_into(buf, cur, off - cur)
                for key, g in by_off[off]:
                    syn = self._voices.get(key)
                    if syn is not None:
                        syn.kick(g)
                        self.kicks_played += 1
                cur = off
            for v in self._voices.values():
                v.render_into(buf, cur, frames - cur)

            self.peak_pre_gain = max(self.peak_pre_gain,
                                     float(np.max(np.abs(buf))))
            out = np.tanh(self.gain * buf)       # soft limiter
            if np.max(np.abs(self.gain * buf)) > 1.0:
                self.clipped_blocks += 1
            outdata[:, 0] = out.astype(np.float32)
            self.blocks += 1
        except Exception:                        # never kill the audio thread
            outdata.fill(0.0)
            self.underruns += 1
        self.max_cb_ms = max(self.max_cb_ms,
                             (time.perf_counter() - t_cb) * 1e3)


# ---------------------------------------------------------------------------
# Sim-thread tap
# ---------------------------------------------------------------------------

class LiveExcitationTap:
    """Streams the solver's contact excitation into the engine: burst-track,
    deposit/admit on the E6 ledger, push γ-scaled Ĥ-shaped kicks + choke
    state. Two sample sources feed the SAME consumer (`_consume`):

    - source="hook" (default): per-substep host sampling via
      substep_end_hook — the CPU host path (forces per-substep syncs; the
      solver disables CUDA-graph capture while any host hook is set).
    - source="ring": the device staging ring (Stage A,
      sound_stage_kernels.py) drained ONCE PER FRAME — the CUDA path (works
      on CPU too; parity-tested). The caller must call `drain()` after each
      `world.step()`; kicks then arrive in per-frame batches, which the
      engine's ASAP scheduler already handles (≤ 1 frame extra latency).
    """

    def __init__(self, world, engine: LiveSoundEngine, *,
                 table_basis: AudioBasis | None,
                 body_bases: dict[int, AudioBasis] | None = None,
                 tau_ref_per_body: dict[int, float] | None = None,
                 tau_ref: float = 8.0e-4,
                 eta_audio: float = 1.0,
                 j_floor: float = 1.0e-3,
                 settle_quiet: float = 0.15,
                 settle_max: float = 1.5,
                 arm_prominence: float = 5.0,
                 arm_j_floor: float = 2.0e-2,
                 choke_load_on: float = 0.25,
                 choke_load_off: float = 0.10,
                 source: str = "hook"):
        self.source = str(source)
        self._solver = (validate_native_world_ring(world)
                        if self.source == "ring"
                        else validate_native_host_world(world))
        self.engine = engine
        self.table_basis = table_basis
        self.body_bases = body_bases or {}
        self.tau_ref_per_body = tau_ref_per_body or {}
        self.tau_ref = float(tau_ref)
        self.j_floor = float(j_floor)
        self.ledger = AudioLedger(eta_audio=float(eta_audio))
        # Settle muting (events.settle_arm_index rules, streamed): swallow the
        # t≈0 placement-gap/static-sag clinks; arm at the first event after a
        # `settle_quiet` event-free window, OR at an event `arm_prominence`×
        # louder than the loudest muted clink (impacts inside the settle
        # window break through — low drops / launched impactors), OR at the
        # `settle_max` deadline. settle_quiet = 0 disables.
        self.settle_quiet = float(settle_quiet)
        self.settle_max = float(settle_max)
        self.arm_prominence = float(arm_prominence)
        self.arm_j_floor = float(arm_j_floor)
        self._armed = self.settle_quiet <= 0.0
        self._last_ev_t = 0.0
        self._settle_j_max = 0.0
        self.events_muted = 0
        # Contact-load gate → voice choking (events.LoadedTracker; choke state
        # flows regardless of settle arming — it is state, not an event).
        self.choke_load_on = float(choke_load_on)
        self.choke_load_off = float(choke_load_off)
        self._loadgate: LoadedTracker | None = None
        self.chokes_pushed = 0
        self._cache: RowCache | None = None
        self._tracker: BurstTracker | None = None
        self._h_sub: float = 0.0
        self._ring: DeviceRingSource | None = None
        self._e_prev: float | None = None
        self._prev_hook = None
        self.events_emitted = 0
        if self.source == "ring":
            self._ring = DeviceRingSource(self._solver)
            self._init_stream(self._ring.cache, self._ring.h_sub,
                              self._solver)
        else:
            self._attach()

    def _init_stream(self, cache: RowCache, h_sub: float, s) -> None:
        self._cache = cache
        self._h_sub = float(h_sub)
        self._tracker = BurstTracker(cache, self._h_sub,
                                     j_floor=self.j_floor)
        # Gate resets to all-unloaded on (re)build; loaded bodies re-fire
        # their choke-on transition on the next update.
        self._loadgate = LoadedTracker(
            row_body=cache.body,
            body_mass=np.asarray(s._mass, dtype=np.float64),
            g_mag=float(np.linalg.norm(
                np.asarray(s.gravity, dtype=np.float64))) or 9.81,
            on_frac=self.choke_load_on, off_frac=self.choke_load_off)

    def _attach(self) -> None:
        self._prev_hook = self._solver.substep_end_hook

        def _hook(s) -> None:
            if self._prev_hook is not None:
                self._prev_hook(s)
            self._on_substep_end(s)

        self._solver.substep_end_hook = _hook

    def detach(self) -> None:
        if self._solver is None:
            return
        if self.source == "ring":
            self._solver.disable_sound_stage()
            self._ring = None
        else:
            self._solver.substep_end_hook = self._prev_hook
        self._solver = None

    # ------------------------------------------------------------------
    def _on_substep_end(self, s) -> None:
        if (self._cache is None
                or len(s._support_row_cidx) != self._cache.n_rows):
            self._init_stream(build_row_cache(s), float(s.dt), s)
        self._consume(sample_substep(s, self._cache))

    def drain(self) -> int:
        """Ring source only: pull the frame's staged substeps through the
        consumer; returns how many. Call after `world.step()`."""
        assert self._ring is not None, "drain() needs source='ring'"
        smps = self._ring.drain()
        for smp in smps:
            self._consume(smp)
        return len(smps)

    def _consume(self, smp) -> None:
        # E6 budget deposit (render.AudioLedger docstring; foundation §15).
        if self._e_prev is not None:
            self.ledger.deposit(max(self._e_prev - smp.e_mech, 0.0))
        self._e_prev = smp.e_mech

        t_now = float(self._tracker._k) * self._h_sub
        for b, flag in self._loadgate.update(smp.F):
            if b in self.body_bases:
                self.engine.push_choke(t_now, b, flag)
                self.chokes_pushed += 1

        for ev in self._tracker.push(smp.F, smp.corner_x, smp.corner_z,
                                     smp.body_vy):
            if not self._armed:
                if (ev.t >= self.settle_max
                        or (ev.t - self._last_ev_t) >= self.settle_quiet
                        or (self.arm_prominence > 0.0
                            and self.events_muted > 0
                            and ev.impulse >= self.arm_prominence
                            * max(self._settle_j_max, self.arm_j_floor))):
                    self._armed = True
                else:
                    # Settle clink: swallow — no push, no ledger debit (a kick
                    # that never plays must not consume budget).
                    self._last_ev_t = ev.t
                    self._settle_j_max = max(self._settle_j_max, ev.impulse)
                    self.events_muted += 1
                    continue
            tau = hertz_tau(ev.v_impact,
                            tau_ref=self.tau_ref_per_body.get(ev.body,
                                                              self.tau_ref))
            kicks: list[tuple[object, NDArray[np.float64]]] = []
            e_kick = 0.0
            if self.table_basis is not None:
                g = (ev.impulse * phi_at_xz(self.table_basis, ev.x, ev.z)
                     * half_sine_spectrum(self.table_basis.omega, tau))
                e_kick += 0.5 * float(g @ g)
                kicks.append(("table", g))
            bb = self.body_bases.get(ev.body)
            if bb is not None:
                g = (ev.impulse * phi_at_corner(bb, ev.off)
                     * half_sine_spectrum(bb.omega, tau))
                e_kick += 0.5 * float(g @ g)
                kicks.append((ev.body, g))
            gamma = self.ledger.admit(e_kick)
            if gamma > 0.0 and kicks:
                self.engine.push_kicks(
                    ev.t, [(k, gamma * g) for k, g in kicks])
                self.events_emitted += 1


# ---------------------------------------------------------------------------
# One-call wiring
# ---------------------------------------------------------------------------

@dataclass
class LiveSound:
    engine: LiveSoundEngine
    tap: LiveExcitationTap

    def stop(self) -> None:
        self.tap.detach()
        self.engine.stop()

    def drain(self) -> int:
        """Ring-source runs: forward staged substeps to the tap (call once
        per frame, after stepping). No-op for the hook source."""
        return self.tap.drain() if self.tap.source == "ring" else 0

    def stats(self) -> dict:
        d = self.engine.stats()
        d.update(events_emitted=self.tap.events_emitted,
                 events_muted=self.tap.events_muted,
                 armed=self.tap._armed,
                 e6_holds=self.tap.ledger.holds(),
                 n_capped=self.tap.ledger.n_capped,
                 cum_kick_J=self.tap.ledger.cum_kick_energy,
                 cum_loss_J=self.tap.ledger.cum_rigid_loss,
                 chokes_pushed=self.tap.chokes_pushed,
                 bodies_loaded=(int(self.tap._loadgate.loaded.sum())
                                if self.tap._loadgate is not None else 0))
        return d


def attach_live_sound(
    world,
    *,
    table_basis: AudioBasis | None,
    body_bases: dict[int, AudioBasis] | None = None,
    body_gains: dict[int, float] | None = None,
    tau_ref_per_body: dict[int, float] | None = None,
    tau_ref: float = 8.0e-4,
    eta_audio: float = 1.0,
    j_floor: float = 1.0e-3,
    settle_quiet: float = 0.15,
    settle_max: float = 1.5,
    fs: float = 44100.0,
    blocksize: int = 256,
    gain: float = 0.35,
    table_gain: float = 1.0,
    zeta_contact: float | None = 0.08,
    source: str = "hook",
) -> LiveSound:
    """Build engine + voices, start the stream, attach the tap. Call
    `.stop()` before rebuilding the world; attach a fresh one after.

    `zeta_contact`: choked modal ζ for BODY voices while they carry support
    load (ComplexModalSynth choke DEVIATION note; the table voice — the
    permanent support — is never choked). None disables.

    `source`: "hook" (host per-substep sampling, CPU path) or "ring" (device
    staging drained per frame — the CUDA path; caller must call `.drain()`
    after each `world.step()`)."""
    engine = LiveSoundEngine(fs=fs, blocksize=blocksize, gain=gain)
    if table_basis is not None:
        engine.add_voice("table", table_basis, gain=table_gain)
    body_gains = body_gains or {}
    for idx, basis in (body_bases or {}).items():
        engine.add_voice(idx, basis, gain=body_gains.get(idx, 1.0),
                         zeta_contact=zeta_contact)
    engine.start()
    tap = LiveExcitationTap(
        world, engine, table_basis=table_basis, body_bases=body_bases,
        tau_ref_per_body=tau_ref_per_body, tau_ref=tau_ref,
        eta_audio=eta_audio, j_floor=j_floor,
        settle_quiet=settle_quiet, settle_max=settle_max, source=source)
    return LiveSound(engine=engine, tap=tap)
