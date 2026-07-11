"""Per-substep contact-impulse logger for the NATIVE modal path (Stage E6 demo).

Attaches to `Solver6DOF.substep_end_hook` (fires once per substep, after the
iteration loop — host hooks force a device sync, so this is a RECORDING-RUN
tool: zero cost when not attached, never on by default).

What it records per substep, for every SUPPORT_CONTACT row: the engaged normal
force the native q-block itself consumes,

    F_n = −min(ρ C + λ_eff, 0)        (reduced_support_solve.py sign
                                       conventions; spec §6 f_c = λ + ρC⁺;
                                       λ_eff = λ for hard rows, 0 for soft)

with C = corner_y − (y_rest + U_y·q) evaluated against the substep's final
modal amplitude — bit-identical to the q-block's own force assembly in
`solver_6dof._modal_qblock_solve`. Plus each body's v_y (pre-impact speed for
Hertz shaping) and the total rigid mechanical energy (KE + gravity PE, the
same quantity the §15 sim-path ledger differences) for the E6 audio budget.

The row cache + per-substep sampling live in module functions
(`build_row_cache` / `sample_substep`) shared with the Tier 1 live tap
(`dcr/sound/live.py`), so offline log and live stream read the identical
excitation.

Box-box (SelfCollision) rows are NOT logged — dinner-scene sound sources are
all support rows; body-body impact audio is a documented follow-up.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dcr.avbd._solver.passivity import (
    _quat_to_R_batch,
    local_inertia_from_invIl,
    rigid_mechanical_energy,
)
from .events import SoundLog


@dataclass
class RowCache:
    """Static support-row metadata + precomputed local inertia (constant for
    rigid bodies), built once per attached solver."""

    cidx: NDArray[np.int64]
    body: NDArray[np.int64]
    off: NDArray[np.float64]        # (n_rows, 3) body-frame corner offsets
    U: NDArray[np.float64]          # (n_rows, r) support-mode y-rows
    y_rest: NDArray[np.float64]
    Il: NDArray[np.float64]         # (n_bodies, 3, 3) local inertia

    @property
    def n_rows(self) -> int:
        return int(self.cidx.shape[0])


@dataclass
class SubstepSample:
    """One substep's excitation-relevant state."""

    F: NDArray[np.float32]          # (n_rows,) engaged normal force ≥ 0 [N]
    corner_x: NDArray[np.float32]   # (n_rows,) corner world x
    corner_z: NDArray[np.float32]   # (n_rows,) corner world z
    body_vy: NDArray[np.float32]    # (n_bodies,) v_y [m/s]
    e_mech: float                   # rigid mechanical energy [J]


def build_row_cache(s) -> RowCache:
    cidx = np.asarray(s._support_row_cidx, dtype=np.int64)
    return RowCache(
        cidx=cidx,
        body=np.asarray([int(s._rows[c].body_a) for c in cidx],
                        dtype=np.int64),
        off=np.asarray([np.asarray(s._rows[c].off_a, dtype=np.float64)
                        for c in cidx]),
        U=np.asarray([np.asarray(u, dtype=np.float64)
                      for u in s._support_U_y_rows]),
        y_rest=np.asarray([float(y) for y in s._support_y_rest],
                          dtype=np.float64),
        Il=local_inertia_from_invIl(
            np.asarray(s._inv_I_local, dtype=np.float64)),
    )


def _quats_wxyz(s, quat_raw: NDArray) -> NDArray[np.float64]:
    """Project-order (w,x,y,z) quats. Solver storage is (x,y,z,w) (warp
    convention — see passivity.rigid_mechanical_energy docstring); prefer the
    solver's own helper when present."""
    fn = getattr(s, "_psv_quats_wxyz", None)
    if fn is not None:
        return np.asarray(fn(), dtype=np.float64)
    return np.asarray(quat_raw, dtype=np.float64)[:, [3, 0, 1, 2]]


def sample_substep(s, cache: RowCache) -> SubstepSample:
    """Read the substep's engaged support forces + energy from the solver —
    the same force assembly as `_modal_qblock_solve` (module docstring)."""
    x = s.x.numpy().astype(np.float64)
    quat_raw = s.q.numpy()
    v = s.v.numpy().astype(np.float64)
    om = s.omega.numpy().astype(np.float64)
    pen = s.c_penalty.numpy().astype(np.float64)
    lam = s.c_lambda.numpy().astype(np.float64)
    stiff = s.c_stiffness.numpy().astype(np.float64)
    act = s.c_active.numpy()
    aC0 = s.c_alpha_C0.numpy().astype(np.float64)
    q_modal = s._q_modal_host
    r = cache.U.shape[1]
    qm = (np.asarray(q_modal, dtype=np.float64)[:r]
          if q_modal is not None else np.zeros(r))

    wxyz = _quats_wxyz(s, quat_raw)
    R_all = _quat_to_R_batch(wxyz)                       # (n_bodies, 3, 3)
    rb = cache.body
    r_w = np.einsum("nij,nj->ni", R_all[rb], cache.off)  # (n_rows, 3)
    corner = x[rb] + r_w
    C = corner[:, 1] - (cache.y_rest + cache.U @ qm)
    ci = cache.cidx
    hard = np.isinf(stiff[ci])
    C = C - np.where(hard, aC0[ci], 0.0)
    lam_eff = np.where(hard, lam[ci], 0.0)
    f = np.minimum(pen[ci] * C + lam_eff, 0.0)
    f = np.where(act[ci] == 0, 0.0, f)

    e_mech = rigid_mechanical_energy(
        v, om, wxyz, np.asarray(s._mass, dtype=np.float64),
        s._inv_I_local, X=x, gravity=np.asarray(s.gravity, np.float64),
        Il=cache.Il)
    return SubstepSample(
        F=(-f).astype(np.float32),
        corner_x=corner[:, 0].astype(np.float32),
        corner_z=corner[:, 2].astype(np.float32),
        body_vy=v[:, 1].astype(np.float32),
        e_mech=float(e_mech),
    )


def validate_native_host_world(world) -> object:
    """Common guards for excitation taps; returns the solver."""
    if not getattr(world, "_native_modal_enabled", False):
        raise RuntimeError(
            "sound tap: world is not on the native modal path "
            "(call enable_reduced_modal_support first)")
    if getattr(world, "solver_kind", "avbd") != "avbd":
        raise NotImplementedError(
            "sound tap: only the AVBD/Solver6DOF host path is wired; "
            "XPBD-native logging is a follow-up")
    s = world._solver
    if getattr(s, "_modal_resident", False):
        raise NotImplementedError(
            "sound tap: device-resident q-block — use the CPU host path "
            "(device readback staging is a follow-up)")
    return s


@dataclass
class SoundImpulseLogger:
    """Accumulates the per-substep record; `finalize()` → `events.SoundLog`."""

    h_sub: float = 0.0
    _solver: object = field(default=None, repr=False)
    _prev_hook: object = field(default=None, repr=False)
    _cache: RowCache | None = field(default=None, repr=False)

    _F: list = field(default_factory=list, repr=False)
    _cx: list = field(default_factory=list, repr=False)
    _cz: list = field(default_factory=list, repr=False)
    _vy: list = field(default_factory=list, repr=False)
    _em: list = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    def attach(self, solver) -> None:
        """Chain onto `substep_end_hook` (any existing hook still fires)."""
        self._solver = solver
        self._prev_hook = solver.substep_end_hook

        def _hook(s) -> None:
            if self._prev_hook is not None:
                self._prev_hook(s)
            self._on_substep_end(s)

        solver.substep_end_hook = _hook

    def detach(self) -> None:
        if self._solver is not None:
            self._solver.substep_end_hook = self._prev_hook
            self._solver = None

    # ------------------------------------------------------------------
    def _on_substep_end(self, s) -> None:
        if self.h_sub == 0.0:
            self.h_sub = float(s.dt)      # inside the substep loop dt = sub_dt
        if (self._cache is None
                or len(s._support_row_cidx) != self._cache.n_rows):
            self._cache = build_row_cache(s)
        smp = sample_substep(s, self._cache)
        self._F.append(smp.F)
        self._cx.append(smp.corner_x)
        self._cz.append(smp.corner_z)
        self._vy.append(smp.body_vy)
        self._em.append(smp.e_mech)

    # ------------------------------------------------------------------
    def finalize(self) -> SoundLog:
        if not self._F:
            raise RuntimeError("SoundImpulseLogger: no substeps recorded")
        s = self._solver
        return SoundLog(
            h_sub=float(self.h_sub),
            row_body=self._cache.body.astype(np.int32),
            row_off=self._cache.off,
            F=np.stack(self._F, axis=0),
            corner_x=np.stack(self._cx, axis=0),
            corner_z=np.stack(self._cz, axis=0),
            body_vy=np.stack(self._vy, axis=0),
            e_mech=np.asarray(self._em, dtype=np.float64),
            body_mass=np.asarray(
                s._mass if s is not None else [], dtype=np.float64),
        )


def attach_sound_logger(world) -> SoundImpulseLogger:
    """Wire a logger into an `AVBDDCRWorld` running the NATIVE modal path.

    Requirements (clear errors otherwise): `enable_reduced_modal_support` was
    called (native q-block engaged), solver_kind == "avbd" (the Solver6DOF
    host path — XPBD-native logging is a documented follow-up), and the
    q-block is host-resident (device runs need a readback stage, follow-up).
    """
    s = validate_native_host_world(world)
    logger = SoundImpulseLogger()
    logger.attach(s)
    return logger
