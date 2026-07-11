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
from .events import ImpulseEvents, SoundLog, extract_impulses
from .shaping import half_sine_spectrum, hertz_tau, impulse_kernel


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
    receive the table-side excitation of every event; corner-kind voices are
    keyed by solver body index (`body_voices` in `render_soundtrack`)."""

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


def render_soundtrack(
    log: SoundLog,
    *,
    table_voice: Voice | None,
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
) -> tuple[NDArray[np.float64], dict]:
    """Render the logged run to a mono soundtrack.

    Every impact excites BOTH sides of its contact with the same impulse
    magnitude (Newton's third law): the table voice at the corner's world
    (x, z), and the impacting body's own voice (if registered) at its
    body-frame corner. One ledger admittance per event covers the combined
    EFFECTIVE (kernel-filtered) kick energy, processed in time order against
    the per-substep budget deposits (module docstring). `tau_ref_per_body`
    overrides the Hertz τ_ref per impacting body (material-pair stiffness —
    steel/ceramic on wood is shorter than the global default).
    """
    body_voices = body_voices or {}
    tau_ref_per_body = tau_ref_per_body or {}
    if events is None:
        events = extract_impulses(log, j_floor=j_floor)
    n_samples = int(np.ceil((log.duration + tail) * fs))
    ledger = AudioLedger(eta_audio=float(eta_audio))
    loss = log.rigid_loss_series()

    for v in ([table_voice] if table_voice else []) + list(body_voices.values()):
        v._splats.clear()

    # Time-ordered sweep: deposit each substep's budget, then admit its events.
    ev_i = 0
    for k in range(log.n_substeps):
        ledger.deposit(loss[k])
        while ev_i < events.n_events and int(events.k_sub[ev_i]) == k:
            j = float(events.impulse[ev_i])
            body_i = int(events.body[ev_i])
            tau = hertz_tau(events.v_impact[ev_i],
                            tau_ref=tau_ref_per_body.get(body_i, tau_ref),
                            v_ref=v_ref)
            g_table = g_body = None
            e_kick = 0.0
            if table_voice is not None:
                g_table = j * phi_at_xz(table_voice.basis,
                                        float(events.x[ev_i]),
                                        float(events.z[ev_i]))
                g_eff = g_table * half_sine_spectrum(table_voice.basis.omega,
                                                     tau)
                e_kick += 0.5 * float(g_eff @ g_eff)
            bv = body_voices.get(body_i)
            if bv is not None:
                g_body = j * phi_at_corner(bv.basis, events.off[ev_i])
                g_eff = g_body * half_sine_spectrum(bv.basis.omega, tau)
                e_kick += 0.5 * float(g_eff @ g_eff)
            gamma = ledger.admit(e_kick)
            if gamma > 0.0:
                k0, w = impulse_kernel(float(events.t[ev_i]), tau, fs)
                if g_table is not None:
                    table_voice._splats.append((k0, w, gamma * g_table))
                if g_body is not None:
                    bv._splats.append((k0, w, gamma * g_body))
            ev_i += 1

    master = np.zeros(n_samples, dtype=np.float64)
    per_voice_peak: dict[str, float] = {}
    for v in ([table_voice] if table_voice else []) + list(body_voices.values()):
        track = v.gain * _render_voice(v, n_samples, fs)
        per_voice_peak[v.name] = float(np.max(np.abs(track))) if track.size else 0.0
        master += track

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
        "fs": fs,
        "n_samples": n_samples,
    }
    return master, diag


def write_wav(path: str, audio: NDArray[np.float64], fs: float) -> None:
    """16-bit PCM mono WAV via scipy (no new dependency)."""
    from scipy.io import wavfile
    a = np.clip(np.asarray(audio, dtype=np.float64), -1.0, 1.0)
    wavfile.write(path, int(fs), (a * 32767.0).astype(np.int16))
