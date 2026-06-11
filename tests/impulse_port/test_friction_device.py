"""Device-resident contact-friction kernel (`k_contact_friction`) parity.

The numpy `apply_contact_friction` is the reference; this asserts the Warp
kernel reproduces it bit-for-bit (f32 round-off only). The kernel COMPILES and
RUNS on the Warp CPU device, so this parity runs everywhere — no CUDA needed.

What this does NOT cover: the in-graph integration (`enable_device_friction` →
`_substep_end_device` launching the kernel inside the captured CUDA graph). That
path is CUDA-gated (`_use_device` is False on CPU) and is validated on a GPU
machine, ALONGSIDE the V2-B device band — see `test_v2b.py` and the
`gpu-resident-validation-both` memory marker. When asked to "validate fully GPU
resident", run BOTH this and the V2-B device-band tests on CUDA.
"""
from __future__ import annotations

import numpy as np
import pytest

wp = pytest.importorskip("warp")

from dcr.avbd import reduced_coupled_kernels as K
from dcr.dcr.impulse_port import (
    apply_velocity_band, apply_contact_friction, _mu_of)

_H = 1.0 / 120.0


def _warmed_scene():
    """Shelf XPBD mirror, warmed with the band ON so v/ω/q_s and the per-corner
    caches are realistic (the band injects the yaw spin friction must damp)."""
    from scenes.reduced_shelf import build_reduced_shelf
    from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd

    base = build_reduced_shelf(device="cpu")
    base.rs.reset_state()
    xh = mirror_to_xpbd(base, h=_H, substeps=4, iterations=4, device="cpu")
    w, c = xh.world, xh.coupler
    c.device_resident = False
    c.anchor_includes_q_d = False
    for _ in range(120):
        w.step()
        apply_velocity_band(c, w.solver, eta=1.0)
    return w, c


def _device_arrays(c, solver, v0, om0, mu, dev):
    """Flat CSR built from the coupler's per-body caches (row_active=1 so the
    kernel's own margin test does the gating, exactly like the numpy loop)."""
    f64 = wp.float64
    tracked = [int(b) for b in c.tracked_body_indices]
    q_s = np.asarray(c.rs.q_s, np.float64)
    inv_m = solver.inv_mass.numpy().astype(np.float64)
    inv_I = solver.inv_I.numpy().astype(np.float64).reshape(-1, 3)
    nbod = inv_m.shape[0]
    mass = np.where(inv_m > 0, 1.0 / np.where(inv_m > 0, inv_m, 1.0), 0.0)
    I_loc = np.zeros((nbod, 3, 3))
    for b in range(nbod):
        Ib = np.where(inv_I[b] > 0, 1.0 / np.where(inv_I[b] > 0, inv_I[b], 1.0), 0.0)
        I_loc[b] = np.diag(Ib)
    row_body, row_off, row_U = [], [], []
    body_ids = np.zeros(max(1, len(tracked)), np.int32)
    for t, b in enumerate(tracked):
        body_ids[t] = b
        off = c._row_off_by_body[b]
        U = c._row_U_y_by_body[b]
        for j in range(off.shape[0]):
            row_body.append(b)
            row_off.append(off[j])
            row_U.append(U[j])
    total = len(row_body)
    A = lambda a, dt: wp.array(a, dtype=dt, device=dev)
    return dict(
        x=A(solver.x.numpy().astype(np.float32), wp.vec3),
        q=A(solver.q.numpy().astype(np.float32), wp.quat),
        v=A(v0.astype(np.float32), wp.vec3),
        omega=A(om0.astype(np.float32), wp.vec3),
        mass=A(mass.astype(np.float32), float),
        I=A(I_loc.astype(np.float32), wp.mat33),
        counts=A(np.array([len(tracked), total, total], np.int32), int),
        body_ids=A(body_ids, int),
        row_body=A(np.array(row_body, np.int32), int),
        row_off=A(np.array(row_off, np.float64), wp.vec3d),
        row_U=A(np.array(row_U, np.float64), f64),
        row_active=A(np.ones(total, np.int32), int),
        q_s=A(q_s, f64), r=int(q_s.shape[0]),
        vf=wp.zeros(nbod, dtype=wp.vec3d, device=dev),
        of=wp.zeros(nbod, dtype=wp.vec3d, device=dev),
        fd=wp.zeros(2, dtype=f64, device=dev))


@pytest.mark.parametrize("dev", ["cpu"])
def test_friction_kernel_matches_numpy(dev):
    if dev == "cuda" and not wp.is_cuda_available():
        pytest.skip("no CUDA device")
    w, c = _warmed_scene()
    solver = w.solver
    v0 = solver.v.numpy().copy()
    om0 = solver.omega.numpy().copy()
    mu = _mu_of(solver, 0)

    # numpy reference
    solver.v.assign(v0)
    solver.omega.assign(om0)
    st = apply_contact_friction(c, solver, mu=mu, h=_H)
    v_np = solver.v.numpy().copy()
    om_np = solver.omega.numpy().copy()
    assert st.n_corners > 0, "no in-contact corners — scene not resting?"

    # device kernel
    d = _device_arrays(c, solver, v0, om0, mu, dev)
    f64 = wp.float64
    wp.launch(K.k_contact_friction, dim=1, device=dev, inputs=[
        d["x"], d["q"], d["v"], d["omega"], d["mass"], d["I"], d["counts"],
        d["body_ids"], d["row_body"], d["row_off"], d["row_U"], d["row_active"],
        d["q_s"], d["r"], f64(c.shelf_y_rest), f64(5.0e-3), f64(mu), f64(_H),
        f64(9.81), f64(1.0e-9), d["vf"], d["of"], d["fd"]])
    v_wp = d["v"].numpy()
    om_wp = d["omega"].numpy()

    fd = d["fd"].numpy()
    assert int(fd[0]) == st.n_corners, (int(fd[0]), st.n_corners)
    assert np.allclose(v_wp, v_np, atol=1e-5), np.abs(v_wp - v_np).max()
    assert np.allclose(om_wp, om_np, atol=1e-5), np.abs(om_wp - om_np).max()
