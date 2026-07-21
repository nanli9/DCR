"""Offline soundtrack render (Stage E6 demo): events → capped excitation →
modal bank → WAV.

The E6 sound-energy bound: the audio band may only be excited with energy the
rigid contacts actually dissipated. Per substep the ledger deposits
η_audio · max(−ΔE_rigid_mech, 0); each impact's kick energy is admitted against
the reservoir and scaled down when it would overdraw:

    Σ E_kick,audio  ≤  η_audio · Σ ΔE_rigid_loss + ε_tol       (cumulative)

which is the foundation's core inequality (§15) applied to the render band,
enforced with the quadratic scaling of §6 (kick energy is quadratic in the
scale, so γ = √(reservoir / E_kick) projects onto the budget). With
mass-normalized modes a velocity kick g carries E_kick = ½‖g‖² (M_q = I,
paper Eq. 7).

# DEVIATION (foundation §15): the sim-path ledger bounds the REALIZED modal
# mechanical-energy change; the open-loop audio bank has no back-reaction, so
# the bound here is on the Σ of injected kick energies (phase cross-terms with
# already-ringing modes are unbudgeted, zero-mean). The admitted kick is the
# KERNEL-FILTERED effective kick ĝ_i = g_i·|Ĥ(ω_i; τ)| (shaping.
# half_sine_spectrum): that is the energy the bank actually receives — the
# raw ½‖g‖² of a point impulse overcounts what a finite-τ contact delivers to
# high modes (and diverges with mode count). Render-side analogue, disclosed
# in docs/stageE6.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .audio_basis import AudioBasis, phi_at_corner, phi_at_xz
from .bank import render_modes_lfilter
from .events import ImpulseEvents, LoadedTracker, SoundLog, extract_impulses
from .shaping import (
    contact_noise_burst,
    half_sine_spectrum,
    hertz_tau,
    impulse_kernel,
)


@dataclass
class AudioLedger:
    """Cumulative reservoir ledger for the audio band (mirrors
    `dcr.avbd._solver.passivity.PassivityLedger` semantics; §15 form,
    §6 quadratic cap — see module docstring)."""

    eta_audio: float = 1.0
    tol: float = 1.0e-9
    reservoir: float = 0.0
    cum_rigid_loss: float = 0.0
    cum_kick_energy: float = 0.0
    n_events: int = 0
    n_capped: int = 0
    min_gamma: float = 1.0

    def deposit(self, rigid_loss: float) -> None:
        """Credit η_audio · max(loss, 0) [J] into the reservoir."""
        loss = max(float(rigid_loss), 0.0)
        self.cum_rigid_loss += loss
        self.reservoir += self.eta_audio * loss

    def admit(self, e_kick: float) -> float:
        """Admit a kick of energy e_kick = ½‖g‖²; return γ ∈ [0, 1] scaling g
        so γ²·e_kick fits the reservoir (§6: energy quadratic in the scale)."""
        self.n_events += 1
        e = max(float(e_kick), 0.0)
        if e <= self.reservoir + self.tol:
            gamma = 1.0
        elif self.reservoir <= 0.0:
            gamma = 0.0
        else:
            gamma = float(np.sqrt(self.reservoir / e))
        realized = gamma * gamma * e
        self.reservoir = max(self.reservoir - realized, 0.0)
        self.cum_kick_energy += realized
        if gamma < 1.0:
            self.n_capped += 1
            self.min_gamma = min(self.min_gamma, gamma)
        return gamma

    def holds(self) -> bool:
        """Cumulative E6 inequality (§15 form)."""
        return (self.cum_kick_energy
                <= self.eta_audio * self.cum_rigid_loss + self.tol)


@dataclass
class Voice:
    """One synthesizer voice: a basis plus a listening gain. Grid-kind voices
    receive the SUPPORT-side excitation of every event (the scene's deformable
    slab — dinner table, road, ledge, shelf board, cargo slab); corner-kind
    voices are keyed by solver body index (`body_voices` in
    `render_soundtrack`)."""

    name: str
    basis: AudioBasis
    gain: float = 1.0

    # Filled during render: (start_sample, kernel_weights, g (r,)) per event.
    _splats: list[tuple[int, NDArray[np.float64], NDArray[np.float64]]] = \
        field(default_factory=list, repr=False)


def _render_voice(voice: Voice, n_samples: int, fs: float,
                  chunk: int = 16) -> NDArray[np.float64]:
    """Splat this voice's kick events into per-mode q̇-jump tracks and run the
    bank, `chunk` modes at a time (bounds peak memory at chunk × N floats)."""
    basis = voice.basis
    out = np.zeros(n_samples, dtype=np.float64)
    if not voice._splats:
        return out
    r = basis.n_modes
    for c0 in range(0, r, chunk):
        c1 = min(c0 + chunk, r)
        u = np.zeros((c1 - c0, n_samples), dtype=np.float64)
        for k0, w, g in voice._splats:
            lo = max(k0, 0)
            hi = min(k0 + w.shape[0], n_samples)
            if hi <= lo:
                continue
            u[:, lo:hi] += g[c0:c1, None] * w[None, lo - k0:hi - k0]
        qd = render_modes_lfilter(u, basis.omega[c0:c1], basis.zeta[c0:c1], fs)
        out += basis.weight[c0:c1] @ qd
    return out


def _render_voice_phasor(
    voice: Voice,
    n_samples: int,
    fs: float,
    zeta_contact: float,
    toggles: list[tuple[int, bool]],
    seg_chunk: int = 65536,
) -> NDArray[np.float64]:
    """Damped-phasor render of one CHOKEABLE body voice — the offline twin of
    `live.ComplexModalSynth`. Impulse-invariant per sample exactly like
    `bank.render_modes_lfilter` (z^n = e^{(−ζω+iω_d)nT}), so with no toggles
    it matches `_render_voice` to float precision (tests/stageE6 asserts).

    Kicks arrive as the same kernel-weighted splats `_render_voice` consumes;
    each kernel sample is a q̇ jump of w_j·g. `toggles` is the body's
    time-sorted (sample, loaded) list switching between the free pole set and
    the choked one (ζ_i → max(ζ_i, zeta_contact)), phasor state carried
    across the switch — a damping change, not a re-strike.

    # DEVIATION (contact choke): the bank is open-loop, so a body resting
    # loaded on the support would otherwise keep ringing with free-air ζ —
    # audibly wrong (real contact chokes the ring; part of why everything
    # sounded like a sustained "ting"). Constant choked ζ is a render-side
    # contact-damping heuristic: no stiffness/frequency shift, support voice
    # never choked, gate = LoadedTracker hysteresis on the logged support
    # forces. Ledger unaffected — choking only removes modal energy faster,
    # so the admitted kick energy remains the §15-form upper bound.
    # Disclosed in docs/stageE6.
    """
    basis = voice.basis
    out = np.zeros(n_samples, dtype=np.float64)
    if not voice._splats:
        return out
    T = 1.0 / float(fs)
    omega = np.asarray(basis.omega, dtype=np.float64)

    def _pole_set(zeta: NDArray[np.float64]) -> tuple:
        zc = np.clip(np.asarray(zeta, dtype=np.float64), 0.0, 0.999999)
        omega_d = omega * np.sqrt(1.0 - zc ** 2)
        pole = (-zc * omega + 1j * omega_d) * T          # ln z, per sample
        jump = 1.0 + 1j * (zc * omega / np.maximum(omega_d, 1e-30))
        return pole, jump

    tables = {False: _pole_set(basis.zeta),
              True: _pole_set(np.maximum(basis.zeta, float(zeta_contact)))}

    # Action timeline: (sample, order, payload); toggles (order 0) apply
    # before kicks (order 1) landing on the same sample.
    actions: list[tuple[int, int, object]] = []
    for k0, w, g in voice._splats:
        for j in range(w.shape[0]):
            sj = k0 + j
            if 0 <= sj < n_samples and w[j] != 0.0:
                actions.append((sj, 1, float(w[j]) * g))
    for s_t, flag in toggles:
        if 0 <= s_t < n_samples:
            actions.append((int(s_t), 0, bool(flag)))
    actions.sort(key=lambda a: (a[0], a[1]))

    c = np.zeros(basis.n_modes, dtype=np.complex128)
    choked = False
    cur = 0

    def _advance(upto: int) -> None:
        nonlocal cur, c
        while cur < upto:
            length = min(upto - cur, seg_chunk)
            pole = tables[choked][0]
            ph = np.exp(pole[:, None] * np.arange(length)[None, :])
            out[cur:cur + length] += basis.weight @ (c[:, None] * ph).real
            c = c * np.exp(pole * length)
            cur += length

    for s_a, kind, payload in actions:
        _advance(s_a)
        if kind == 0:
            choked = bool(payload)
        else:
            c = c + payload * tables[choked][1]
    _advance(n_samples)
    return out


def render_soundtrack(
    log: SoundLog,
    *,
    support_voice: Voice | None,
    body_voices: dict[int, Voice] | None = None,
    fs: float = 44100.0,
    eta_audio: float = 1.0,
    tail: float = 1.5,
    tau_ref: float = 8.0e-4,
    v_ref: float = 1.0,
    normalize_peak: float = 0.7,
    j_floor: float = 1.0e-3,
    events: ImpulseEvents | None = None,
    tau_ref_per_body: dict[int, float] | None = None,
    zeta_contact: float | None = 0.08,
    choke_load_on: float = 0.25,
    choke_load_off: float = 0.10,
    noise_frac: float = 0.35,
    noise_seed: int = 2026,
) -> tuple[NDArray[np.float64], dict]:
    """Render the logged run to a mono soundtrack.

    Every impact excites BOTH sides of its contact with the same impulse
    magnitude (Newton's third law): the support voice at the corner's world
    (x, z), and the impacting body's own voice (if registered) at its
    body-frame corner. One ledger admittance per event covers the combined
    EFFECTIVE (kernel-filtered) kick energy, processed in time order against
    the per-substep budget deposits (module docstring). `tau_ref_per_body`
    overrides the Hertz τ_ref per impacting body (material-pair stiffness —
    steel/ceramic on wood is shorter than the global default).

    `zeta_contact`: choked modal ζ applied to a BODY voice while its body
    carries support load (`_render_voice_phasor` DEVIATION note; gate =
    `LoadedTracker` hysteresis at `choke_load_on/off` × m·g). The support voice
    — permanently loaded by construction — is never choked. None disables
    (pure-LTI path for every voice, the pre-choke behavior).

    `noise_frac`: per-event contact-noise transient level (`shaping.
    contact_noise_burst` DEVIATION note; 0 disables). Accounting and mix are
    one knob, consistently: the burst is charged to the ledger as
    e_noise = noise_frac² · e_kick (admitted TOGETHER with the modal kick, so
    γ covers both and the §15-form bound covers the whole played program),
    and its output amplitude is γ · noise_frac · ‖w ⊙ ĝ‖ (the event's own
    listening-weighted effective-kick norm, gains folded) — i.e. the
    noise:modal loudness ratio equals noise_frac by construction.
    `noise_seed` makes renders reproducible.
    """
    body_voices = body_voices or {}
    tau_ref_per_body = tau_ref_per_body or {}
    if events is None:
        events = extract_impulses(log, j_floor=j_floor)
    n_samples = int(np.ceil((log.duration + tail) * fs))
    ledger = AudioLedger(eta_audio=float(eta_audio))
    loss = log.rigid_loss_series()

    # Per-body choke toggles from the logged support forces (substep grid →
    # sample indices). SoundLog stores no gravity; scenes use standard g and
    # the gate is a heuristic threshold, so 9.81 is assumed here.
    choke_toggles: dict[int, list[tuple[int, bool]]] = {}
    if zeta_contact is not None and body_voices:
        gate = LoadedTracker(
            row_body=np.asarray(log.row_body, dtype=np.int64),
            body_mass=np.asarray(log.body_mass, dtype=np.float64),
            g_mag=9.81, on_frac=choke_load_on, off_frac=choke_load_off)
        choke_toggles = {b: [] for b in body_voices}
        for k in range(log.n_substeps):
            for b, flag in gate.update(log.F[k]):
                if b in choke_toggles:
                    choke_toggles[b].append(
                        (int(round(k * log.h_sub * fs)), flag))

    for v in ([support_voice] if support_voice else []) + list(body_voices.values()):
        v._splats.clear()

    # Time-ordered sweep: deposit each substep's budget, then admit its events.
    rng_noise = np.random.default_rng(int(noise_seed))
    noise_splats: list[tuple[int, NDArray[np.float64]]] = []
    ev_i = 0
    for k in range(log.n_substeps):
        ledger.deposit(loss[k])
        while ev_i < events.n_events and int(events.k_sub[ev_i]) == k:
            j = float(events.impulse[ev_i])
            body_i = int(events.body[ev_i])
            tau = hertz_tau(events.v_impact[ev_i],
                            tau_ref=tau_ref_per_body.get(body_i, tau_ref),
                            v_ref=v_ref)
            g_support = g_body = ge_support = ge_body = None
            e_kick = 0.0
            if support_voice is not None:
                g_support = j * phi_at_xz(support_voice.basis,
                                        float(events.x[ev_i]),
                                        float(events.z[ev_i]))
                ge_support = g_support * half_sine_spectrum(
                    support_voice.basis.omega, tau)
                e_kick += 0.5 * float(ge_support @ ge_support)
            bv = body_voices.get(body_i)
            if bv is not None:
                g_body = j * phi_at_corner(bv.basis, events.off[ev_i])
                ge_body = g_body * half_sine_spectrum(bv.basis.omega, tau)
                e_kick += 0.5 * float(ge_body @ ge_body)
            # Noise transient charged with the kick (docstring: γ covers both).
            e_noise = float(noise_frac) ** 2 * e_kick
            gamma = ledger.admit(e_kick + e_noise)
            if gamma > 0.0:
                k0, w = impulse_kernel(float(events.t[ev_i]), tau, fs)
                s_out2 = 0.0                 # event output scale ‖w ⊙ ĝ‖²
                if g_support is not None:
                    support_voice._splats.append((k0, w, gamma * g_support))
                    wg = support_voice.gain * support_voice.basis.weight * ge_support
                    s_out2 += float(wg @ wg)
                if g_body is not None:
                    bv._splats.append((k0, w, gamma * g_body))
                    wg = bv.gain * bv.basis.weight * ge_body
                    s_out2 += float(wg @ wg)
                if noise_frac > 0.0 and s_out2 > 0.0:
                    burst = contact_noise_burst(tau, fs, rng_noise)
                    noise_splats.append(
                        (k0, gamma * float(noise_frac)
                         * np.sqrt(s_out2) * burst))
            ev_i += 1

    master = np.zeros(n_samples, dtype=np.float64)
    per_voice_peak: dict[str, float] = {}
    voice_items = (([(None, support_voice)] if support_voice else [])
                   + list(body_voices.items()))
    n_choke_toggles = 0
    for bidx, v in voice_items:
        if bidx is not None and zeta_contact is not None:
            tg = choke_toggles.get(bidx, [])
            n_choke_toggles += len(tg)
            track = v.gain * _render_voice_phasor(
                v, n_samples, fs, float(zeta_contact), tg)
        else:
            track = v.gain * _render_voice(v, n_samples, fs)
        per_voice_peak[v.name] = float(np.max(np.abs(track))) if track.size else 0.0
        master += track

    if noise_splats:
        noise_track = np.zeros(n_samples, dtype=np.float64)
        for k0, s in noise_splats:
            lo = max(k0, 0)
            hi = min(k0 + s.shape[0], n_samples)
            if hi > lo:
                noise_track[lo:hi] += s[lo - k0:hi - k0]
        per_voice_peak["noise"] = float(np.max(np.abs(noise_track)))
        master += noise_track

    peak = float(np.max(np.abs(master))) if master.size else 0.0
    if peak > 0.0 and normalize_peak > 0.0:
        master *= normalize_peak / peak

    diag = {
        "n_events": events.n_events,
        "n_admitted": ledger.n_events,
        "n_capped": ledger.n_capped,
        "min_gamma": ledger.min_gamma,
        "cum_rigid_loss_J": ledger.cum_rigid_loss,
        "cum_kick_energy_J": ledger.cum_kick_energy,
        "e6_holds": ledger.holds(),
        "raw_peak": peak,
        "per_voice_peak": per_voice_peak,
        "n_choke_toggles": n_choke_toggles,
        "n_noise_bursts": len(noise_splats),
        "fs": fs,
        "n_samples": n_samples,
    }
    return master, diag


def write_wav(path: str, audio: NDArray[np.float64], fs: float) -> None:
    """16-bit PCM mono WAV via scipy (no new dependency)."""
    from scipy.io import wavfile
    a = np.clip(np.asarray(audio, dtype=np.float64), -1.0, 1.0)
    wavfile.write(path, int(fs), (a * 32767.0).astype(np.int16))
