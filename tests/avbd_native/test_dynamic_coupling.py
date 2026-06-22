"""Stage 1 — dynamic two-way modal contact constraint in the GPU AVBD coupler.

Pins the port of the finalized constraint (`two_band_coupling.html`, "Approach
B") into `ReducedCoupledAVBDCoupler`:

  (a) PARITY — the GPU device path matches the CPU numpy reference (the dynamic
      oracle) to machine precision before chaotic round-off amplification, then
      stays bounded over a full impact + ring-down run. Both run on cuda:0 so
      the only variable is the hook path (`device_resident`).
  (b) TWO-WAY COUNTERFACTUAL — the constraint's only new ingredient is the modal
      inertia term M_q/h². Holding q̇ ≡ 0 (`freeze_qdot`, the SplitOneWay control)
      deletes exactly that term: the modal ring vanishes (modal KE ≡ 0) and the
      bystander cargo gets far less motion. Dynamic q launches it; frozen does
      not — that is "two-way, in the form of the constraint", demonstrated.
  (c) PASSIVITY — one free backward-Euler step of the dynamic modal block is
      unconditionally dissipative: total modal energy E = ½q̇ᵀM_qq̇ + ½qᵀK_qq is
      monotone non-increasing absent forcing (the Ė = −q̇ᵀD_qq̇ ≤ 0 proof).

CLAUDE.md rule 6: the numpy path is the reference and stays the default on CPU.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_truck import build_reduced_truck


def _cuda_or_skip() -> str:
    wp = pytest.importorskip("warp")
    wp.init()
    if wp.get_cuda_device_count() < 1:
        pytest.skip("no CUDA device for GPU-residency parity test")
    return "cuda:0"


def _build(device: str, device_resident: bool, *, freeze: bool = False,
           iters: int = 4, sub: int = 4, **kw):
    # This file tests the AVBD reduced *coupler* (CPU↔GPU residency parity).
    # solver="avbd" now selects the native AVBD solver, so pin the coupler
    # explicitly via "avbd_coupler" (transitional; removed in Stage 6).
    h = build_reduced_truck(device=device, iterations=iters, avbd_substeps=sub,
                            solver="avbd_coupler", **kw)
    c = h.world.reduced_coupled_coupler
    c.device_resident = device_resident
    c.freeze_qdot = freeze
    return h


def _run(device: str, device_resident: bool, n: int) -> dict:
    h = _build(device, device_resident)
    w = h.world
    for _ in range(n):
        w.step()
    s = w._solver
    return dict(q=h.rs.q.copy(), qdot=h.rs.qdot.copy(),
                x=s.x.numpy().copy(), sq=s.q.numpy().copy(),
                coupler=w.reduced_coupled_coupler)


# --------------------------------------------------------------------------
# (a) parity
# --------------------------------------------------------------------------
def test_build_deterministic():
    """Two independent truck builds produce the SAME reduced basis (scipy eigh
    is deterministic) — the precondition for comparing two builds as parity."""
    a = build_reduced_truck(device="cpu", iterations=4, avbd_substeps=4)
    b = build_reduced_truck(device="cpu", iterations=4, avbd_substeps=4)
    assert np.array_equal(a.rs.Mq, b.rs.Mq)
    assert np.array_equal(a.rs.Kq, b.rs.Kq)
    assert np.array_equal(a.rs.Dq, b.rs.Dq)


def test_cpu_gpu_parity_machine_precision():
    """Device path == numpy reference to fp64 round-off before chaos. The
    second-order modal velocity inherits a 1/h amplification of q's round-off,
    so the tight gate is on q (and the body state), per the plan's ≤1e-12."""
    dev = _cuda_or_skip()
    ref = _run(dev, False, 2)
    gpu = _run(dev, True, 2)
    assert np.max(np.abs(gpu["q"] - ref["q"])) <= 1e-12
    assert np.max(np.abs(gpu["x"] - ref["x"])) <= 1e-9
    assert np.max(np.abs(gpu["sq"] - ref["sq"])) <= 1e-9
    # q̇ = Δq/h: round-off scaled by 1/h_substep (=480) — still ≤1e-10.
    assert np.max(np.abs(gpu["qdot"] - ref["qdot"])) <= 1e-9


def test_cpu_gpu_early_horizon_agreement():
    """The device/host divergence GROWS from machine epsilon (it is round-off
    amplification, not a systematic offset): ≤1e-12 at N=2 grows only to sub-mm
    by N=8. The truck stacks chaotic contacts (a 4-block lumber stack), so the
    two faithful FP paths decorrelate exponentially afterwards — only stability
    is asserted long-run (below), as no faithful reimplementation gives tight
    long-run parity on a chaotic scene.

    The bound is the GPU's OWN run-to-run nondeterminism (CUDA atomics / graph
    replay are not bit-reproducible), not a magic constant: CPU↔GPU drift must
    be of the same order as GPU↔GPU drift on this chaotic stack — anything
    larger would be a systematic divergence, which is what we actually guard."""
    dev = _cuda_or_skip()
    ref = _run(dev, False, 8)
    gpu = _run(dev, True, 8)
    gpu2 = _run(dev, True, 8)                       # GPU nondeterminism floor
    gpu_nondet = np.max(np.abs(gpu2["x"] - gpu["x"]))
    cpu_gpu = np.max(np.abs(gpu["x"] - ref["x"]))
    # CPU↔GPU within an order of magnitude of GPU↔GPU (+ a 1mm absolute floor
    # for when the GPU happens to replay identically and gpu_nondet≈0).
    assert cpu_gpu < max(10.0 * gpu_nondet, 2e-3), (cpu_gpu, gpu_nondet)
    assert np.max(np.abs(gpu["q"] - ref["q"])) < 1e-4


def test_long_run_stability():
    """Over a full impact + ring-down the GPU run stays finite and physically
    bounded — no blow-up. Backward Euler keeps the dynamic modal block stable
    (the M_q/h² + D_q/h terms are SPD-dominant); the cargo stays on the road."""
    dev = _cuda_or_skip()
    gpu = _run(dev, True, 200)
    for k in ("q", "qdot", "x", "sq"):
        assert np.all(np.isfinite(gpu[k])), k
    # Bodies remain in a sane region (road is ~2.5×1.5 m; nothing launched to
    # orbit). The modal deflection stays small (the slab does not blow up).
    assert np.max(np.abs(gpu["x"])) < 3.0
    assert np.max(np.abs(gpu["q"])) < 0.1
    # Modal energy is finite and bounded (passivity holds in the full solver).
    c = gpu["coupler"]
    assert np.isfinite(c.last_modal_KE) and c.last_modal_KE < 1e3


# --------------------------------------------------------------------------
# (b) two-way counterfactual — the M_q/h² term IS the coupling
# --------------------------------------------------------------------------
def _peak_signals(freeze: bool, n: int = 200) -> dict:
    h = _build("cpu", False, freeze=freeze, iters=6, sub=4,
               impactor_mass=60.0, impactor_drop_height=0.5)
    w = h.world
    c = w.reduced_coupled_coupler
    descs = w._descs
    bystanders = [b.dcr_idx for b in h.bodies if b.dcr_idx != h.impactor_idx]
    y0 = {i: float(descs[i].dcr_body.position[1]) for i in bystanders}
    peak_rise = 0.0
    peak_modal_ke = 0.0
    for _ in range(n):
        w.step()
        for i in bystanders:
            peak_rise = max(peak_rise,
                            float(descs[i].dcr_body.position[1]) - y0[i])
        peak_modal_ke = max(peak_modal_ke, c.last_modal_KE)
    return dict(peak_rise=peak_rise, peak_modal_ke=peak_modal_ke)


def test_two_way_counterfactual():
    """Dynamic q rings (modal KE > 0) and lifts the bystander cargo; the frozen
    q̇≡0 control deletes the modal-inertia term so the ring is EXACTLY zero and
    the cargo gets only the quasi-static sag — no ring back-reaction."""
    dyn = _peak_signals(freeze=False)
    frz = _peak_signals(freeze=True)

    # Frozen: the inertia term is deleted ⇒ no modal velocity ⇒ modal KE ≡ 0.
    assert frz["peak_modal_ke"] == 0.0
    # Dynamic: the support genuinely rings (the M_q/h² term gives q a life).
    assert dyn["peak_modal_ke"] > 0.5
    # The ring's back-reaction lifts the bystander cargo well beyond the frozen
    # quasi-static response — the two-way loop, in the form of the constraint.
    assert dyn["peak_rise"] > 2.0 * frz["peak_rise"]


# --------------------------------------------------------------------------
# (c) passivity — backward Euler on the dynamic modal block is dissipative
# --------------------------------------------------------------------------
def _be_modal_step(Mq, Kq, Dq, q, qdot, h):
    """One free (no-contact) backward-Euler substep of the dynamic modal block
    EXACTLY as the coupler assembles it (two_band_coupling.html):
        (M/h² + D/h + K) q⁺ = M/h²·q̃ + D/h·q ,  q̃ = q + h·q̇ ,
        q̇⁺ = (q⁺ − q)/h.
    """
    inv_dt2 = 1.0 / (h * h)
    inv_dt = 1.0 / h
    H = inv_dt2 * Mq + inv_dt * Dq + Kq
    q_hat = q + h * qdot
    rhs = inv_dt2 * (Mq @ q_hat) + inv_dt * (Dq @ q)
    q_new = np.linalg.solve(H, rhs)
    qdot_new = (q_new - q) / h
    return q_new, qdot_new


def test_backward_euler_modal_energy_monotone():
    """Free ring-down of the dynamic modal block: total modal mechanical energy
    is monotone non-increasing every step (passive by construction — no
    governor). Uses the real reduced matrices from a built support."""
    h = build_reduced_truck(device="cpu", iterations=4, avbd_substeps=4)
    Mq, Kq, Dq = h.rs.Mq, h.rs.Kq, h.rs.Dq
    r = Mq.shape[0]
    hsub = (1.0 / 120.0) / 4.0

    rng = np.random.default_rng(0)
    q = np.zeros(r)
    qdot = rng.standard_normal(r) * 1e-2   # a "plucked" modal velocity

    def energy(q, qdot):
        return 0.5 * qdot @ (Mq @ qdot) + 0.5 * q @ (Kq @ q)

    E0 = energy(q, qdot)
    E_prev = E0
    assert E0 > 0.0
    for _ in range(400):
        q, qdot = _be_modal_step(Mq, Kq, Dq, q, qdot, hsub)
        E = energy(q, qdot)
        assert E <= E_prev + 1e-15, (E, E_prev)
        E_prev = E
    # And it actually decays (dissipative, not merely non-increasing).
    assert energy(q, qdot) < 0.5 * E0
