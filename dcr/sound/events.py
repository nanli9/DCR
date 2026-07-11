"""Impulse-event extraction from the logged per-substep contact forces
(Stage E6 demo).

`SoundLog` is the raw record `logger.SoundImpulseLogger` produces: per substep,
the engaged normal force of every SUPPORT_CONTACT row (the same
f = min(ρC + λ_eff, 0) the native q-block consumes — reduced_support_solve.py
sign conventions, spec §6 f_c = λ + ρC⁺), the corner world (x, z), each body's
vertical velocity, and the total rigid mechanical energy (for the E6 budget).

`extract_impulses` turns the force streams into discrete excitation events by
HIGH-PASSING each row's force and aggregating contiguous rises into one event
per impact burst:

    ΔF⁺[k] = max(F[k] − F[k−1], 0),   J_burst = Σ_burst ΔF⁺ · h_sub

# DEVIATION (excitation gate): this mirrors the coupler's own overlay
# high-pass (reduced_support_solve.py `# DEVIATION (overlay HP)`): a steady
# resting load has ΔF = 0 and stays silent; onsets, rattle re-hits, and load
# shifts excite in proportion to their force RISE. J_burst approximates the
# incremental contact impulse of the impact (exact for a from-zero hit,
# approximate when a load shift overlaps a rest force) — render-side
# approximation, disclosed in docs/stageE6.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class SoundLog:
    """Raw per-substep contact record (arrays over [n_substeps, ...])."""

    h_sub: float                                   # substep duration [s]
    row_body: NDArray[np.int32]                    # (n_rows,) solver body idx
    row_off: NDArray[np.float64]                   # (n_rows, 3) body-frame corner
    F: NDArray[np.float32]                         # (n_sub, n_rows) engaged N ≥ 0
    corner_x: NDArray[np.float32]                  # (n_sub, n_rows) world x
    corner_z: NDArray[np.float32]                  # (n_sub, n_rows) world z
    body_vy: NDArray[np.float32]                   # (n_sub, n_bodies) v_y [m/s]
    e_mech: NDArray[np.float64]                    # (n_sub,) rigid mech energy [J]
    body_mass: NDArray[np.float64]                 # (n_bodies,)

    @property
    def n_substeps(self) -> int:
        return int(self.F.shape[0])

    @property
    def duration(self) -> float:
        return self.n_substeps * self.h_sub

    def rigid_loss_series(self) -> NDArray[np.float64]:
        """Per-substep rigid mechanical-energy DROP (≥ 0), the E6 budget
        source: loss[k] = max(0, E[k−1] − E[k]) (foundation §15's
        ΔE_rigid_loss, measured on the same mechanical energy the native
        clamp uses — gravity PE included so settling funds the budget)."""
        e = self.e_mech
        loss = np.zeros_like(e)
        loss[1:] = np.maximum(e[:-1] - e[1:], 0.0)
        return loss

    def to_npz(self, path: str) -> None:
        np.savez_compressed(
            path, h_sub=np.array(self.h_sub), row_body=self.row_body,
            row_off=self.row_off, F=self.F, corner_x=self.corner_x,
            corner_z=self.corner_z, body_vy=self.body_vy,
            e_mech=self.e_mech, body_mass=self.body_mass)

    @staticmethod
    def from_npz(path: str) -> "SoundLog":
        d = np.load(path, allow_pickle=False)
        return SoundLog(
            h_sub=float(d["h_sub"]), row_body=d["row_body"],
            row_off=d["row_off"], F=d["F"], corner_x=d["corner_x"],
            corner_z=d["corner_z"], body_vy=d["body_vy"],
            e_mech=d["e_mech"], body_mass=d["body_mass"])


@dataclass
class ImpulseEvents:
    """Flat arrays of extracted excitation events, time-ascending."""

    t: NDArray[np.float64]          # (n_ev,) event time [s] (burst onset)
    k_sub: NDArray[np.int32]        # (n_ev,) onset substep index
    row: NDArray[np.int32]          # (n_ev,) support-row index
    body: NDArray[np.int32]         # (n_ev,) solver body index
    impulse: NDArray[np.float64]    # (n_ev,) J [N·s]
    v_impact: NDArray[np.float64]   # (n_ev,) |v_y| just before onset [m/s]
    x: NDArray[np.float64]          # (n_ev,) corner world x at onset
    z: NDArray[np.float64]          # (n_ev,) corner world z at onset
    off: NDArray[np.float64] = field(default_factory=lambda: np.zeros((0, 3)))

    @property
    def n_events(self) -> int:
        return int(self.t.shape[0])


def settle_arm_index(t: NDArray[np.float64],
                     impulse: NDArray[np.float64] | None = None,
                     quiet_gap: float = 0.15,
                     mute_max: float = 1.5,
                     prominence: float = 5.0,
                     arm_j_floor: float = 2.0e-2) -> int:
    """Index of the first event to PLAY under settle-muting.

    Scenes start with every resting body a placement gap (~1 mm) above the
    support, so t≈0 produces a burst of real-but-unwanted settle clinks
    (dinner measurement: 222 events in the first 0.15 s, v ≈ 0.05 m/s, J ≤
    0.028 N·s) before the intended impact (pot at 0.333 s, J = 2.13 N·s,
    preceded by a 192 ms silent gap). Scene-agnostic arming — the FIRST rule
    that fires plays that event and everything after:

    1. quiet gap: a `quiet_gap` event-free window has passed (events are
       "the scene settling" as long as they keep coming);
    2. prominence: the event's impulse is ≥ `prominence` × the loudest clink
       muted so far (floored by `arm_j_floor`) — an impact landing INSIDE
       the settle window (low drop height, launched impactors) is loud, the
       settle is quiet, so it breaks through instead of being swallowed;
       applies once ≥ 1 event has been muted (needs a noise estimate);
    3. deadline: t ≥ `mute_max`, the backstop for never-quiet scenes.

    quiet_gap = 0 disables muting entirely; prominence = 0 disables rule 2.
    """
    t = np.asarray(t, dtype=np.float64)
    if quiet_gap <= 0.0:
        return 0
    jj = None if impulse is None else np.asarray(impulse, dtype=np.float64)
    last = 0.0
    j_settle_max = 0.0
    for i in range(t.shape[0]):
        if t[i] >= mute_max or (t[i] - last) >= quiet_gap:
            return i
        if (jj is not None and prominence > 0.0 and i > 0
                and jj[i] >= prominence * max(j_settle_max, arm_j_floor)):
            return i
        last = float(t[i])
        if jj is not None:
            j_settle_max = max(j_settle_max, float(jj[i]))
    return int(t.shape[0])


def filter_settle(events: ImpulseEvents, quiet_gap: float = 0.15,
                  mute_max: float = 1.5,
                  prominence: float = 5.0,
                  arm_j_floor: float = 2.0e-2) -> tuple[ImpulseEvents, int]:
    """Apply `settle_arm_index` to an (already time-sorted) event set;
    returns (filtered_events, n_muted)."""
    i0 = settle_arm_index(events.t, events.impulse, quiet_gap=quiet_gap,
                          mute_max=mute_max, prominence=prominence,
                          arm_j_floor=arm_j_floor)
    if i0 == 0:
        return events, 0
    return ImpulseEvents(
        t=events.t[i0:], k_sub=events.k_sub[i0:], row=events.row[i0:],
        body=events.body[i0:], impulse=events.impulse[i0:],
        v_impact=events.v_impact[i0:], x=events.x[i0:], z=events.z[i0:],
        off=events.off[i0:]), i0


def extract_impulses(log: SoundLog, j_floor: float = 1.0e-3) -> ImpulseEvents:
    """Force streams → burst-aggregated impulse events (module docstring).

    A burst opens on the first substep with ΔF⁺ > 0, accumulates J while
    consecutive substeps keep rising, and closes on the first non-rising
    substep. One impact = one event (no per-substep flam); rattle re-hits
    reopen. v_impact reads the body's v_y one substep BEFORE onset (the
    pre-contact approach speed — the hook logs post-substep states).

    `j_floor` [N·s] gates out resting-load jitter: bodies riding the ringing
    support see their support force fluctuate every substep, producing
    thousands of sub-mN·s "bursts" that are numerical load noise, not audible
    impacts (dinner-scene measurement: 23k events at 1e-5, 1k at 1e-3, real
    impacts ≥ 5e-2). The default keeps a 60 g utensil landing at 0.3 m/s
    (J ≈ 1.8e-2) with an order of margin.
    """
    F = np.asarray(log.F, dtype=np.float64)
    n_sub, n_rows = F.shape
    dF = np.diff(F, axis=0, prepend=np.zeros((1, n_rows)))
    rising = dF > 0.0

    t_l: list[float] = []
    k_l: list[int] = []
    row_l: list[int] = []
    imp_l: list[float] = []
    v_l: list[float] = []
    x_l: list[float] = []
    z_l: list[float] = []
    off_l: list[np.ndarray] = []

    # Per-row open-burst state (onset index, accumulated J).
    open_k = np.full(n_rows, -1, dtype=np.int64)
    open_j = np.zeros(n_rows, dtype=np.float64)

    def _close(r: int) -> None:
        k0 = int(open_k[r])
        j = float(open_j[r]) * log.h_sub
        if j > j_floor:
            b = int(log.row_body[r])
            k_pre = max(k0 - 1, 0)
            t_l.append(k0 * log.h_sub)
            k_l.append(k0)
            row_l.append(r)
            imp_l.append(j)
            v_l.append(abs(float(log.body_vy[k_pre, b])))
            x_l.append(float(log.corner_x[k0, r]))
            z_l.append(float(log.corner_z[k0, r]))
            off_l.append(np.asarray(log.row_off[r], dtype=np.float64))
        open_k[r] = -1
        open_j[r] = 0.0

    for k in range(n_sub):
        rise_rows = np.nonzero(rising[k])[0]
        flat_rows = np.nonzero(~rising[k] & (open_k >= 0))[0]
        for r in flat_rows:
            _close(int(r))
        for r in rise_rows:
            r = int(r)
            if open_k[r] < 0:
                open_k[r] = k
            open_j[r] += dF[k, r]
    for r in np.nonzero(open_k >= 0)[0]:
        _close(int(r))

    order = np.argsort(np.asarray(k_l, dtype=np.int64), kind="stable")
    return ImpulseEvents(
        t=np.asarray(t_l, dtype=np.float64)[order],
        k_sub=np.asarray(k_l, dtype=np.int32)[order],
        row=np.asarray(row_l, dtype=np.int32)[order],
        body=np.asarray([int(log.row_body[r]) for r in row_l],
                        dtype=np.int32)[order],
        impulse=np.asarray(imp_l, dtype=np.float64)[order],
        v_impact=np.asarray(v_l, dtype=np.float64)[order],
        x=np.asarray(x_l, dtype=np.float64)[order],
        z=np.asarray(z_l, dtype=np.float64)[order],
        off=(np.stack(off_l, axis=0)[order] if off_l
             else np.zeros((0, 3))),
    )
