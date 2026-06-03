"""Phase B / spec §15 + §21: closed-system energy ledger + diagnostics log.

Spec §21 lists 30+ scalars to log per step. Phase B ships the subset
that's load-bearing for the energy invariants (Inv 1, 2, 7); the cosmetic
diagnostics (BJ angles, AVBD objective, performance counters) hook in
later when the moving-support solve lands (§7).

The `EnergyLedger` is the testable surface for spec §15 (closed-system
non-increase of E_rigid + E_modal under no gravity / no damping / no
external work). It just records a time-series of (E_rigid, E_modal)
each step and exposes a `check_non_increase` assertion that callers
(or pytest fixtures) can invoke at end of run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from ..modal.energy import modal_energy as _modal_energy
from ..rigid.body import RigidBody
from ..rigid.energy import rigid_kinetic_energy as _rigid_ke


# ---------------------------------------------------------------------------
# §21 per-step log entry (subset — the load-bearing scalars only)
# ---------------------------------------------------------------------------

@dataclass
class EnergyLogEntry:
    """One row of the per-step diagnostics table (spec §21 subset).

    Field names match the spec verbatim where present. Optional fields
    default to None and are populated as the corresponding pipeline
    stage comes online (e.g. `gamma_support_scale` lights up only when
    the §12 line search runs).
    """
    step_id: int
    time: float

    E_rigid_pre: float
    E_rigid_post: float
    E_modal_pre: float
    E_modal_post: float
    E_modal_peak: float

    E_modal_injected: float = 0.0
    E_modal_injection_budget: float = 0.0
    alpha_modal_injection: float = 0.0

    # §12 / moving support (None until that solve fires this step).
    E_support_budget: float | None = None
    W_support_to_rigid: float | None = None
    gamma_support_scale: float | None = None
    num_passivity_reruns: int = 0

    # §22 invariant accounting (set at log() time).
    invariant_1_violated: bool = False
    invariant_2_violated: bool = False

    def E_total_pre(self) -> float:
        return self.E_rigid_pre + self.E_modal_pre

    def E_total_post(self) -> float:
        return self.E_rigid_post + self.E_modal_post


# ---------------------------------------------------------------------------
# §15: closed-system energy ledger
# ---------------------------------------------------------------------------

@dataclass
class EnergyLedger:
    """Records (E_rigid + E_modal) at every step and provides the §15
    closed-system non-increase check.

    Use:
        ledger = EnergyLedger()
        ledger.record_pre(step_id=0, time=0.0, bodies=..., couplers=...)
        world.step()
        ledger.record_post(bodies=..., couplers=...)
        ...
        ledger.check_non_increase(tol=1e-6)        # raises if violated

    `record_pre`/`record_post` are decoupled so callers can also wire in
    the §22 invariant accounting (modal injection, support work) between
    the pre and post snapshots.
    """
    entries: list[EnergyLogEntry] = field(default_factory=list)
    _current: EnergyLogEntry | None = None
    _running_E_modal_peak: float = 0.0
    _next_step_id: int = 0

    def record_pre(
        self,
        time: float,
        bodies: Sequence[RigidBody],
        couplers: Sequence,
    ) -> None:
        """Open a new step row, capturing E_rigid + E_modal BEFORE world.step().

        `couplers` is iterable of `PassiveDCRCoupler` instances (we read
        `_stepper.q`, `_stepper.qdot`, `modal.frequencies` off each).
        """
        E_r = float(_rigid_ke(list(bodies)))
        E_m = self._total_modal_energy(couplers)
        self._running_E_modal_peak = max(self._running_E_modal_peak, E_m)
        self._current = EnergyLogEntry(
            step_id=self._next_step_id,
            time=float(time),
            E_rigid_pre=E_r,
            E_rigid_post=E_r,         # filled in by record_post
            E_modal_pre=E_m,
            E_modal_post=E_m,
            E_modal_peak=self._running_E_modal_peak,
        )

    def record_post(
        self,
        bodies: Sequence[RigidBody],
        couplers: Sequence,
        **kwargs,
    ) -> EnergyLogEntry:
        """Close the current row with E_rigid + E_modal AFTER world.step().

        `**kwargs` lets callers set the optional Phase B fields
        (E_modal_injected, alpha_modal_injection, E_support_budget,
        W_support_to_rigid, gamma_support_scale, num_passivity_reruns).
        """
        if self._current is None:
            raise RuntimeError(
                "EnergyLedger.record_post() called without record_pre()")
        E_r = float(_rigid_ke(list(bodies)))
        E_m = self._total_modal_energy(couplers)
        self._running_E_modal_peak = max(self._running_E_modal_peak, E_m)

        e = self._current
        e.E_rigid_post = E_r
        e.E_modal_post = E_m
        e.E_modal_peak = self._running_E_modal_peak
        for k, v in kwargs.items():
            if not hasattr(e, k):
                raise AttributeError(f"unknown EnergyLogEntry field {k!r}")
            setattr(e, k, v)
        self.entries.append(e)
        self._current = None
        self._next_step_id += 1
        return e

    # ----- §15 / Invariant 7 ----------------------------------------------

    def check_non_increase(
        self,
        tol: float = 1e-6,
        relative_tol: float = 0.0,
    ) -> None:
        """Spec §15 / Invariant 7: under no gravity / no damping / no external
        work, E_rigid + E_modal must not increase across the run.

            E_total(t) ≤ E_total(0) + ε

        Raises AssertionError on the first step where the bound is
        violated, with full context (step_id, time, before/after values).

        `relative_tol` adds a fractional slack scaled by the initial
        E_total — use ε_rel ≈ 1e-4 to absorb solver round-off without
        masking real leaks.
        """
        if not self.entries:
            return
        E0 = self.entries[0].E_total_pre()
        slack = float(tol) + float(relative_tol) * abs(E0)
        for e in self.entries:
            if e.E_total_post() > E0 + slack:
                raise AssertionError(
                    f"§15 closed-system violation at step {e.step_id} "
                    f"(t={e.time:.4f}): "
                    f"E_total_post={e.E_total_post():.6e} > "
                    f"E_total(0)={E0:.6e} + slack={slack:.3e}; "
                    f"excess={e.E_total_post() - E0:.6e}")

    def total_energy_series(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (time_array, E_total_post_array). Useful for plotting."""
        t = np.array([e.time for e in self.entries], dtype=np.float64)
        E = np.array([e.E_total_post() for e in self.entries],
                     dtype=np.float64)
        return t, E

    def rigid_modal_series(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (time, E_rigid_post, E_modal_post) arrays."""
        t = np.array([e.time for e in self.entries], dtype=np.float64)
        Er = np.array([e.E_rigid_post for e in self.entries], dtype=np.float64)
        Em = np.array([e.E_modal_post for e in self.entries], dtype=np.float64)
        return t, Er, Em

    # ----- helpers --------------------------------------------------------

    @staticmethod
    def _total_modal_energy(couplers) -> float:
        total = 0.0
        for coupler in couplers:
            omega = coupler.modal.frequencies
            total += _modal_energy(
                coupler._stepper.q, coupler._stepper.qdot, omega)
        return float(total)
