"""Coherent impact impulse bank (coherent_impact_impulse_bank_fix).

Low-iteration AVBD smears one sharp impact across many small per-frame contact
impulses. The per-frame modal injection in `passive_dcr.py` then computes

    Σ_i ½‖s_i‖²        (s_i = Φ(x_i)ᵀ J_i, the per-frame modal kick)

which discards the positive cross terms a *coherent* strike would keep:

    ½‖Σ_i s_i‖²  =  Σ_i ½‖s_i‖²  +  Σ_{i<j} s_iᵀ s_j .

This module reconstructs the coherent strike from the smeared sequence. It banks
the impulses belonging to one physical impact event over a short causal window
and injects the event-level modal energy ½‖Σ_i s_i‖² once (spec §2, §3).

Every injection is bounded by an explicit passive energy budget `B_event` funded
by η·E_loss (spec §4). The budget — NOT the gates — is the iron-clad passivity
net: during a sustained (static) load the rigid body loses ~no kinetic energy, so
E_loss ≈ 0 → B_event ≈ 0 → the caller's `passive_alpha` returns α≈0 and nothing
is injected, no matter how directionally coherent the banked impulse looks. The
coherence gates (spec §8) are accuracy (timing / attribution) only; the worst a
misfiring gate can do is mistime an injection *within* budget.

# DEVIATION from foundation §15: the modal kick is the SUM of a short causal
# window of per-frame impulses, not a single-frame impulse — it re-sharpens an
# impact the soft solve smeared. It is still capped by the same passive_alpha
# budget, so the §15 inequality ΔE_modal ≤ η·ΔE_rigid_loss holds per event and
# globally (spec §18 honest framing).

# DEVIATION from spec §5: the unspent residual (1−α)·S_event carry is omitted.
# On a window-fire injection the accumulation is reset in full, so a sustained
# contact re-sharpens each window independently and the banked impulse can never
# grow without bound. This is strictly conservative (it discards, never
# fabricates, energy) and removes the unbounded-rest-accumulation failure mode.

This module is pure logic: it never touches the modal stepper or evaluates the
modal basis. The caller (`PassiveDCRCoupler`) owns `q̇`, calls `passive_alpha`,
applies the kick, measures the realized ΔE_modal, and debits it back here — so a
single global ledger (`cum_E_modal_injected`) carries the passivity signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ImpactKey:
    """Stable per-impact identity (spec §7). Keyed on the (rigid partner, modal
    support) body pair so a contact that flickers row-to-row at low AVBD
    iterations still maps to the same event — there is no persistent contact
    patch id in this repo, so the patch component of the spec key collapses to
    this 2-tuple."""
    body_id: int       # rigid partner (the non-elastic side of the contact)
    support_id: int    # = coupler.elastic_body_idx


@dataclass
class ImpactEvent:
    """One coherent impact event (spec §4).

    `S_event` is the running Σ_i s_i (the coherent modal impulse); in
    `modal_sum` mode it IS the injected kick, and in both modes it (with
    `sum_sq_si`) gives the coherence ratio R = ‖Σ s_i‖² / Σ‖s_i‖². For
    `impulse_reconstruct` mode the injected kick is Φ(x̄)ᵀ J_event, computed by
    the caller; this event tracks `J_event` and the impulse-weighted `x_bar`.
    """
    S_event: NDArray[np.float64]      # Σ_i s_i  (n_modes,)
    J_event: NDArray[np.float64]      # Σ_i J_i  (3,)
    x_bar: NDArray[np.float64]        # impulse-weighted contact point (3,)
    normal_ref: NDArray[np.float64]   # representative impact normal (3,)
    B_event: float = 0.0              # passive energy budget (subsumes reservoir)
    Jmag_sum: float = 0.0             # Σ_i ‖J_i‖ (x_bar denominator)
    sum_sq_si: float = 0.0            # Σ_i ‖s_i‖²  (R_coherence numerator denom)
    samples: int = 0                  # samples accrued in the current window
    last_sample_step: int = -1        # bank step index of the most recent sample
    age: int = 0                      # steps since last deposit (expiry clock)


@dataclass
class ImpactBank:
    """Short-lived bank of coherent impact events (spec §2, §6-§10).

    Lifecycle per simulation step, driven by the caller:
        begin_step()                 — age, λ_B-decay budgets, expire stale events
        deposit(contacts, lam, E)    — add η·E_loss to event budgets (once)
        accumulate(key, ...)         — gate + bank each engaged contact's impulse
        ready_keys()                 — events to inject this step (inject policy)
        event(key) / mark_spent(...) — caller injects, then debits the realized ΔE
    """
    n_modes: int
    mode: str = "impulse_reconstruct"        # | "modal_sum" (ablation)
    inject_policy: str = "end_of_window"     # | "every_frame"
    window: int = 4                          # samples to gather before firing
    max_event_age: int = 8                   # delete an event this many steps
    decay: float = 0.65                      # λ_B: budget decay per step
    coherence_cos_min: float = 0.5           # §8.1 directional gate
    normal_cos_min: float = 0.7              # §8.2 normal gate
    patch_radius: float = 0.05               # §8.3 m; ‖x_i − x̄‖ ceiling
    tangential_dominance_max: float = 2.0    # §8.5b ‖J_t‖/(|J_n|+ε) ceiling
    b_max_factor: float = 1.0                # B_max = factor · decaying_peak(E)
    eps: float = 1e-10

    events: dict = field(default_factory=dict)
    _step: int = 0
    _recent_peak_dep: float = 0.0

    # Per-step + cumulative diagnostics.
    last_E_deposit: float = 0.0
    last_E_spent: float = 0.0
    last_E_expired: float = 0.0
    cum_E_deposit: float = 0.0
    cum_E_spent: float = 0.0
    cum_E_expired: float = 0.0
    last_n_events: int = 0
    _R_sum: float = 0.0
    _R_count: int = 0

    def __post_init__(self) -> None:
        if self.mode not in ("impulse_reconstruct", "modal_sum"):
            raise ValueError(
                "impact_bank_mode must be 'impulse_reconstruct' or "
                f"'modal_sum'; got {self.mode!r}")
        if self.inject_policy not in ("end_of_window", "every_frame"):
            raise ValueError(
                "inject_policy must be 'end_of_window' or 'every_frame'; "
                f"got {self.inject_policy!r}")
        if self.window < 1:
            raise ValueError(f"window must be >= 1; got {self.window}")
        if self.max_event_age < 1:
            raise ValueError(f"max_event_age must be >= 1; got {self.max_event_age}")
        if not 0.0 <= self.decay <= 1.0:
            raise ValueError(f"decay must be in [0, 1]; got {self.decay}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def begin_step(self) -> float:
        """§8.4/§10: advance the clock, λ_B-decay every budget, and expire
        events older than `max_event_age` steps since their last deposit.
        Returns the expired budget energy (logged, never refunded)."""
        self._step += 1
        self.last_E_expired = 0.0
        self.last_E_spent = 0.0   # accrued across this step's mark_spent calls
        dead: list[ImpactKey] = []
        for key, ev in self.events.items():
            ev.age += 1
            ev.B_event *= self.decay
            if ev.age > self.max_event_age:
                self.last_E_expired += max(0.0, ev.B_event)
                dead.append(key)
        for key in dead:
            del self.events[key]
        self.cum_E_expired += self.last_E_expired
        return self.last_E_expired

    def _get_or_create(self, key: ImpactKey) -> ImpactEvent:
        ev = self.events.get(key)
        if ev is None:
            ev = ImpactEvent(
                S_event=np.zeros(self.n_modes, dtype=np.float64),
                J_event=np.zeros(3, dtype=np.float64),
                x_bar=np.zeros(3, dtype=np.float64),
                normal_ref=np.zeros(3, dtype=np.float64),
            )
            self.events[key] = ev
        return ev

    def deposit(
        self,
        contacts: list,
        lam: NDArray[np.float64],
        E_total: float,
        key_fn,
    ) -> None:
        """§4: deposit D^n = E_total (= η·E_loss) across the engaged event keys,
        weighted by Σ|λ_N| over each key (fallback weight). λ_B decay was
        already applied in begin_step(), so add on top:
        B_event ← min(B_max, B_event + D). Resets each touched event's age."""
        self.last_E_deposit = 0.0
        if E_total <= 0.0 or not contacts:
            return
        # Decaying running peak of the per-step deposit → B_max ceiling (§4).
        self._recent_peak_dep = max(E_total, self.decay * self._recent_peak_dep)
        b_max = self.b_max_factor * self._recent_peak_dep
        key_w: dict[ImpactKey, float] = {}
        for ci, c in enumerate(contacts):
            key = key_fn(c)
            if key is None:
                continue
            lamN = abs(float(lam[3 * ci])) if 3 * ci < len(lam) else 0.0
            key_w[key] = key_w.get(key, 0.0) + lamN
        if not key_w:
            return
        wsum = sum(key_w.values())
        n = len(key_w)
        for key, w in key_w.items():
            frac = (w / wsum) if wsum > self.eps else (1.0 / n)
            D = frac * E_total
            ev = self._get_or_create(key)
            ev.B_event = min(b_max, ev.B_event + D)
            ev.age = 0
            self.last_E_deposit += D
        self.cum_E_deposit += self.last_E_deposit

    def accumulate(
        self,
        key: ImpactKey,
        s_i: NDArray[np.float64],
        J_i: NDArray[np.float64],
        x_i: NDArray[np.float64],
        n_i: NDArray[np.float64],
        jn_abs: float,
        jt_abs: float,
    ) -> str:
        """§8: gate the incoming impulse, and if it is plausibly part of the
        same physical impact, bank it. Returns a short reason string
        ('accumulated' | 'no_event' | 'rejected_*') for diagnostics/tests.

        An event must already exist (i.e. a budget was deposited on its key)
        for accumulation to fire — a contact with no deposited budget has no
        impact to reconstruct."""
        ev = self.events.get(key)
        if ev is None:
            return "no_event"

        # §8.5b tangential dominance — keep the bank to impact-like (normal)
        # contacts, not frictional scraping.
        if jt_abs > self.tangential_dominance_max * (jn_abs + self.eps):
            return "rejected_tangential"

        si_norm = float(np.linalg.norm(s_i))
        if ev.samples == 0:
            # Seed the event — accept unconditionally and set the references.
            ev.normal_ref = np.asarray(n_i, dtype=np.float64).copy()
            ev.x_bar = np.asarray(x_i, dtype=np.float64).copy()
        else:
            # §8.2 normal coherence (do not merge opposite faces / orientations).
            nn = float(np.linalg.norm(n_i)) * float(np.linalg.norm(ev.normal_ref))
            if nn > self.eps:
                if float(np.dot(n_i, ev.normal_ref)) < self.normal_cos_min * nn:
                    return "rejected_normal"
            # §8.1 directional coherence — in modal space for modal_sum, in
            # physical impulse space for impulse_reconstruct. Either rejects an
            # antiparallel sample (spec Test 2: s, −s ⇒ no fake energy).
            if self.mode == "modal_sum":
                u_acc, u_in, du = ev.S_event, s_i, si_norm
            else:
                u_acc, u_in, du = ev.J_event, J_i, float(np.linalg.norm(J_i))
            den = float(np.linalg.norm(u_acc)) * du
            if den > self.eps:
                if float(np.dot(u_in, u_acc)) < self.coherence_cos_min * den:
                    return "rejected_directional"
            # §8.3 patch radius — keep one spatial impact region per event.
            if float(np.linalg.norm(np.asarray(x_i) - ev.x_bar)) > self.patch_radius:
                return "rejected_patch"

        # Accept: bank the sample.
        ev.S_event = ev.S_event + s_i           # Σ s_i (coherence + modal_sum kick)
        ev.sum_sq_si += si_norm * si_norm
        jm = float(np.linalg.norm(J_i))
        denom = ev.Jmag_sum + jm
        if denom > self.eps:
            ev.x_bar = (ev.Jmag_sum * ev.x_bar + jm * np.asarray(x_i)) / denom
        ev.Jmag_sum = denom
        ev.J_event = ev.J_event + np.asarray(J_i, dtype=np.float64)
        ev.samples += 1
        ev.last_sample_step = self._step
        return "accumulated"

    def ready_keys(self) -> list[ImpactKey]:
        """Events to inject this step (spec §10).
        end_of_window: fire when a full window is gathered OR the contact
        stopped feeding this step (separation). every_frame: fire whenever any
        sample is banked."""
        out: list[ImpactKey] = []
        for key, ev in self.events.items():
            if ev.samples <= 0:
                continue
            if self.inject_policy == "every_frame":
                out.append(key)
            else:  # end_of_window
                ended = ev.last_sample_step < self._step
                if ev.samples >= self.window or ended:
                    out.append(key)
        return out

    def event(self, key: ImpactKey) -> ImpactEvent:
        return self.events[key]

    def coherence_ratio(self, ev: ImpactEvent) -> float:
        """R = ‖Σ s_i‖² / Σ‖s_i‖² (spec §11). ≫1 ⇒ a coherent strike was
        smeared and banking will recover it; ≈1 ⇒ the impulses are genuinely
        incoherent and banking cannot help (the §14 estimator is needed)."""
        num = float(np.dot(ev.S_event, ev.S_event))
        return num / (ev.sum_sq_si + self.eps)

    def mark_spent(self, key: ImpactKey, dE: float) -> None:
        """Debit the caller-measured realized ΔE_modal from the event budget and
        reset the window accumulation (full reset — see module DEVIATION). The
        leftover budget survives (it decays via λ_B and expires via age)."""
        ev = self.events.get(key)
        if ev is None:
            return
        dE = max(0.0, float(dE))
        ev.B_event = max(0.0, ev.B_event - dE)
        self.last_E_spent += dE
        self.cum_E_spent += dE
        # Record the coherence ratio for this fired window (diagnostic).
        if ev.sum_sq_si > self.eps:
            self._R_sum += self.coherence_ratio(ev)
            self._R_count += 1
        # Reset the accumulation for the next window.
        ev.S_event = np.zeros(self.n_modes, dtype=np.float64)
        ev.J_event = np.zeros(3, dtype=np.float64)
        ev.Jmag_sum = 0.0
        ev.sum_sq_si = 0.0
        ev.samples = 0

    def end_step(self) -> None:
        """Refresh per-step rollups after the caller finishes injecting."""
        self.last_n_events = len(self.events)

    def mean_R_coherence(self) -> float:
        return (self._R_sum / self._R_count) if self._R_count > 0 else 0.0

    def total_budget(self) -> float:
        return float(sum(max(0.0, ev.B_event) for ev in self.events.values()))
