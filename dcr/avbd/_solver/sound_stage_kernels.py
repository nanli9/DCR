"""Device staging for the Stage E6 sound tap — "Stage A" of the GPU sound
architecture (docs/stageE6/sound_render.md).

Once per substep, entirely on-device, these kernels write the excitation
record the sound tap consumes into a fixed-capacity ring buffer indexed by a
device substep counter:

    snd_F[slot, s]   engaged normal force per support row,
                     F = −min(ρC + λ_eff, 0) — the SAME per-slot assembly as
                     `modal_qblock_kernels.k_modal_rowforce` and the host tap
                     `dcr.sound.logger.sample_substep`, evaluated on the
                     POST-SOLVE state (launched after the iteration loop)
    snd_cx/cz[slot, s]  corner world (x, z)
    snd_vy[slot, b]  per-body v_y
    snd_E[slot]      total rigid mechanical energy (passivity.
                     rigid_mechanical_energy form: ½m‖v‖² + ½ω_lᵀI_lω_l −
                     m(g·x), static m≤0 skipped, s=2/n quat→R)
    head             substep counter, incremented last (monotonic; slot =
                     head % capacity)

Everything is a fixed-shape `wp.launch` — no host interaction, no allocation
— so the sequence is CUDA-graph capturable inside the full-substep graph.
The host drains the ring ONCE PER FRAME (`dcr.sound.logger.DeviceRingSource`)
instead of forcing a device sync per substep the way `substep_end_hook` does
(and unlike a host hook, staging does not disqualify graph capture:
solver_6dof gates capture on `substep_end_hook is None`, not on this).

Parity target is the HOST tap, not the q-block: the modal surface term reads
the float32 `q_modal` mirror — refreshed post-solve by BOTH the host q-block
(`_solve_q_block` tail) and the device one (`k_modal_solve*`) — over the
SUPPORT block [0:r], exactly the tap's `U @ q[:r]`. On native-cargo scenes
both therefore share the same support-block approximation of C (cargo flex
excluded). Asserted against `sample_substep` in tests/stageE6.
"""
from __future__ import annotations

import warp as wp

wp.set_module_options({"enable_backward": False})

vec3d = wp.vec3d

_ZERO = wp.constant(wp.float64(0.0))
_ONE = wp.constant(wp.float64(1.0))
_HALF = wp.constant(wp.float64(0.5))


@wp.func
def _quat_to_R64(qx: wp.float64, qy: wp.float64, qz: wp.float64,
                 qw: wp.float64):
    """float64 XYZW quat → rotation, bit-faithful to passivity._quat_to_R_batch
    (s = 2/n, n < 1e-30 degenerate → identity)."""
    n = qx * qx + qy * qy + qz * qz + qw * qw
    if n < wp.float64(1e-30):
        return wp.mat33d(_ONE, _ZERO, _ZERO,
                         _ZERO, _ONE, _ZERO,
                         _ZERO, _ZERO, _ONE)
    s = wp.float64(2.0) / n
    return wp.mat33d(
        _ONE - s * (qy * qy + qz * qz), s * (qx * qy - qz * qw), s * (qx * qz + qy * qw),
        s * (qx * qy + qz * qw), _ONE - s * (qx * qx + qz * qz), s * (qy * qz - qx * qw),
        s * (qx * qz - qy * qw), s * (qy * qz + qx * qw), _ONE - s * (qx * qx + qy * qy))


@wp.kernel
def k_snd_stage_rows(
    r: int,                                   # support modal block size
    capacity: int,
    head: wp.array(dtype=int),
    support_row_idx: wp.array(dtype=int),     # slot → c-row index
    c_active: wp.array(dtype=int),
    c_body_a: wp.array(dtype=int),
    c_off_a: wp.array(dtype=wp.vec3),
    c_penalty: wp.array(dtype=float),
    c_lambda: wp.array(dtype=float),
    c_stiffness: wp.array(dtype=float),
    c_alpha_C0: wp.array(dtype=float),
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    U_y: wp.array2d(dtype=wp.float64),        # (n_sup, R) row gradient W
    q32: wp.array(dtype=float),               # float32 q_modal mirror (R,)
    y_rest: wp.array(dtype=wp.float64),       # (n_sup,) ORIGINAL rest height
    snd_F: wp.array2d(dtype=float),           # (cap, n_sup) out: engaged N ≥ 0
    snd_cx: wp.array2d(dtype=float),          # (cap, n_sup) out: corner x
    snd_cz: wp.array2d(dtype=float),          # (cap, n_sup) out: corner z
):
    """Per support slot: the tap's force record (module docstring). Mirrors
    `sample_substep` exactly: C against y_rest + U[:, :r]·q[:r], hard rows
    (isinf stiffness → > 1e30 in f32) subtract α·C0 and add λ, inactive rows
    record F = 0 (corner still recorded). dim = n_sup."""
    s = wp.tid()
    slot = head[0] % capacity
    cidx = support_row_idx[s]
    bi = c_body_a[cidx]
    qq = q[bi]
    R = _quat_to_R64(wp.float64(qq[0]), wp.float64(qq[1]),
                     wp.float64(qq[2]), wp.float64(qq[3]))
    off = c_off_a[cidx]
    r_w = R * vec3d(wp.float64(off[0]), wp.float64(off[1]), wp.float64(off[2]))
    cx = wp.float64(x[bi][0]) + r_w[0]
    cy = wp.float64(x[bi][1]) + r_w[1]
    cz = wp.float64(x[bi][2]) + r_w[2]
    uq = _ZERO
    for kk in range(r):
        uq += U_y[s, kk] * wp.float64(q32[kk])
    C = cy - (y_rest[s] + uq)
    lam_eff = _ZERO
    if wp.float64(c_stiffness[cidx]) > wp.float64(1e30):
        C = C - wp.float64(c_alpha_C0[cidx])
        lam_eff = wp.float64(c_lambda[cidx])
    f = wp.min(wp.float64(c_penalty[cidx]) * C + lam_eff, _ZERO)
    if c_active[cidx] == 0:
        f = _ZERO
    snd_F[slot, s] = wp.float32(-f)
    snd_cx[slot, s] = wp.float32(cx)
    snd_cz[slot, s] = wp.float32(cz)


@wp.kernel
def k_snd_stage_bodies(
    capacity: int,
    head: wp.array(dtype=int),
    v: wp.array(dtype=wp.vec3),
    snd_vy: wp.array2d(dtype=float),          # (cap, n_b) out
):
    """Per body: v_y (the tap's pre-impact-speed source). dim = n_b."""
    bi = wp.tid()
    snd_vy[head[0] % capacity, bi] = v[bi][1]


@wp.kernel
def k_snd_stage_energy_advance(
    n_b: int,
    capacity: int,
    gx: wp.float64, gy: wp.float64, gz: wp.float64,
    head: wp.array(dtype=int),
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    v: wp.array(dtype=wp.vec3),
    omega: wp.array(dtype=wp.vec3),
    mass: wp.array(dtype=wp.float64),         # (n_b,) — NOT inverse
    Il: wp.array(dtype=wp.mat33d),            # (n_b,) body-LOCAL inertia
    snd_E: wp.array(dtype=wp.float64),        # (cap,) out
):
    """Rigid mechanical energy of the substep + head advance. dim = 1 —
    a single sequential fp64 thread (n_b is O(10²); deterministic sum order,
    microseconds). Runs LAST: the other stage kernels read head[0] for their
    slot, so the increment here publishes the substep."""
    e = _ZERO
    for bi in range(n_b):
        m = mass[bi]
        if m > _ZERO:
            vv = v[bi]
            vx = wp.float64(vv[0])
            vy = wp.float64(vv[1])
            vz = wp.float64(vv[2])
            e += _HALF * m * (vx * vx + vy * vy + vz * vz)
            qq = q[bi]
            R = _quat_to_R64(wp.float64(qq[0]), wp.float64(qq[1]),
                             wp.float64(qq[2]), wp.float64(qq[3]))
            om = omega[bi]
            wl = wp.transpose(R) * vec3d(wp.float64(om[0]), wp.float64(om[1]),
                                         wp.float64(om[2]))
            e += _HALF * wp.dot(wl, Il[bi] * wl)
            px = wp.float64(x[bi][0])
            py = wp.float64(x[bi][1])
            pz = wp.float64(x[bi][2])
            e -= m * (gx * px + gy * py + gz * pz)
    slot = head[0] % capacity
    snd_E[slot] = e
    head[0] = head[0] + 1
