# Passivity-cap cost: Step 1 (done) + deferred Steps 2 & 3

The §15 passive-energy clamp (`dcr/avbd/_solver/passivity.py`) runs a small
energy-accounting block per rigid substep: two rigid mechanical-energy sums, two
modal energy sums, a gravity-work term, and one scalar γ = √((E_m_old+budget)/E_m_new)
that scales (q, q̇). The intrinsic arithmetic is ~430 flops + one sqrt for the
shelf scene (6 bodies, 16 modes) — nanoseconds on a GPU. This note records what
the *measured* cost actually is, what Step 1 fixed, and the two follow-ups
deferred until a CUDA box is available.

## Step 1 — DONE: vectorize the accounting + hoist the constant inversion

`rigid_mechanical_energy` was the dominant chunk. It (a) looped over bodies in
Python and (b) re-inverted the **constant** 3×3 body inertia `inv(invIl)` on
**every** call. Fixed:

- vectorized over bodies — batched Rᵀω (`_quat_to_R_batch`) and the two quadratic
  forms via `np.einsum`;
- added an optional precomputed `Il` (body-local inertia); both solvers now
  compute it **once** (`local_inertia_from_invIl`, cached as `self._psv_Il`) and
  pass it every substep, so the inversion leaves the hot loop.
- the scalar reference is retained as `_rigid_mechanical_energy_loop` (CLAUDE.md
  rule 6) and is the **parity oracle** in
  `tests/avbd_native/test_passivity_energy_vectorized.py` (24 cases: KE, KE+grav
  PE, cached-Il == internal-inversion, static-body skip, singular-inertia
  angular-drop, degenerate-quat → identity).

**Measured (shelf, CPU host reference):**

| quantity | before | after |
|---|--:|--:|
| `rigid_mechanical_energy` / call | 55 µs | **38 µs** (1.5×; cached-Il hot path) |
| AVBD 4×4 end-to-end cap cost (OFF≡ON trajectory) | +10.3% | **+9.2%** |

Bit-parity: `self._psv_Il` = `inv(invIl)` (same LAPACK inv, one-time), so AVBD
ledger/monitor numbers are unchanged. All 17 existing passivity/network tests
pass.

## The honest cost picture (why Step 1 is modest, and where the cost really is)

The end-to-end numbers move only a little because **the arithmetic was never the
bottleneck**:

1. **Host read-backs dominate the AVBD path.** The device-resident 6-DOF solver
   does 8× `.numpy()` per substep (v, ω, q, x, twice) *purely to feed the host
   energy accounting*. Vectorizing the arithmetic doesn't touch these. They are
   removed only by a device-resident clamp → **Step 3**.
2. **XPBD "cost" percentages are trajectory-divergence artifacts.** When the
   clamp bites, OFF *blows up* and ON stays physical, so `(on−off)/off` compares
   two different simulations, not the cap's overhead. On a **non-injecting** XPBD
   config (safe region 16×4, OFF≡ON, E bit-identical, no readbacks) the ~320 µs
   of per-step accounting is **<1% of a 35–48 ms step and lost in measurement
   noise** (ON even times faster than OFF run-to-run). So the cap's *compute* is
   cheap at real budgets; the large percentages in `x1_blowup.md` are the
   blow-up, not the bill.

**Takeaway for the paper:** state the cap as O(n_bodies + n_modes) ≈ a few
hundred flops per substep with **no host synchronization required**; do not quote
a GPU cost until it is measured. The +9–10% AVBD reference figure is unvectorized
host read-back accounting, not the mechanism.

## Step 2 — DEFERRED (paper wording, no code): cost paragraph

Until a measured GPU number exists, the cost section should say:

> The passivity governor adds an O(n_bodies + n_modes) energy-accounting step per
> rigid substep — for our scenes a few hundred floating-point operations and one
> scalar projection, requiring no host↔device synchronization. In the CPU
> reference the clamp adds 9–10 % to step time, dominated by host read-backs used
> only for the accounting; the arithmetic itself is <1 % and, on a non-injecting
> trajectory, within measurement noise. On AVBD the governor is inert (bit-
> identical), so this is a monitoring cost, not a fidelity cost.

Do **not** claim "~1–4%" or "free" for the cap until Step 3 is measured.

## Step 3 — DEFERRED until CUDA: fully device-resident clamp

Port the accounting so nothing round-trips to host:

1. **Pre-substep reduction kernel** — per-body ½m‖v‖² + ½ω_localᵀI_localω_local
   (+ modal ½q̇ᵀMq̇ + ½qᵀKq) → 2 device scalars (`E_rig_pre`, `E_modal_pre`).
   I_local is a constant device array (upload once); use the **closed-form 3×3
   inverse** (cofactors + det guard) if inverting on device, so no LAPACK.
2. **Post-substep reduction kernel** — same, plus gravity work
   Σ m (g·Δx) from the already-device-resident `x` and `x_prev`.
3. **Single-block governor kernel** — thread 0: rigid_loss → `deposit` → γ against
   a device-side ledger (~8 scalars, sequential across substeps is fine — it lives
   on device); r threads scale q, q̇ in place. HUD/certificate reads the ledger
   once per frame, not per substep.

Expected cost: only kernel-launch overhead (~10–20 µs/substep uncaptured, **~1–2
µs inside a CUDA graph** — warp supports capture). Against a device substep that
is itself a 10–20-kernel pipeline dominated by contact solves, expect **low
single-digit %, <2% graph-captured**, shrinking on larger scenes (cap is
O(bodies+modes); solver is O(contacts×iters)).

**Warning (confirms the diagnosis):** a *naive* port that keeps the clamp on host
and calls `.numpy()` per substep would force ~2 syncs × 6 arrays/substep — each a
pipeline stall — plausibly reproducing today's overhead in PCIe form. "Fully
resident" is a **correctness requirement** of the port, not a nicety.

**Optional Step 2.5 (CPU, no CUDA needed):** a warp CPU kernel for the two
reductions would collapse the 38 µs `rigid_mechanical_energy` toward its ~1–2 µs
arithmetic floor (numpy is dispatch-bound at n≈6). Rule 6 now permits it (we have
a measured slowdown), but it does not remove the AVBD read-backs, so it is
strictly less valuable than Step 3 and is grouped with the deferred GPU work.

## Reproduce

```
.venv/bin/python -m pytest tests/avbd_native/test_passivity_energy_vectorized.py -q
```
