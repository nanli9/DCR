# Fresh-session prompt — energy-conserving (symplectic) modal integrator for the native AVBD support constraint

> Paste this into a new session on branch `avbd-native-dynamic-constraint`. Read `CLAUDE.md` first.

## Goal

Make the reduced-modal surface **ring** so it excites resting bodies, by replacing the **dissipative backward-Euler** time integration of the modal coordinate with an **energy-conserving (implicit-midpoint / trapezoidal, or exact-resonator) integrator** — while keeping the modal `q` **co-solved inside the native support constraint** (no decoupling, no coupler, no energy bookkeeping). Gate it behind a flag; keep BE as the default + parity reference.

**Apply it to BOTH solvers, consistently.** AVBD (`Solver6DOF._solve_q_block`) and XPBD (`SolverXPBD._project_modal_elastic`) both integrate the SAME modal subsystem (same diagonal eigenbasis `M_q=I`, `K_q=diag(ω²)`, `D_q=diag(2ζω)`) and both currently use backward Euler. They should use the **same symplectic modal step** — ideally a single shared helper both call — so the modal physics is identical across solvers. This also makes XPBD's ring a *genuine* modal ring (today it only rings as a rigid-contact-chatter artifact, see diagnosis #5) and gives a clean AVBD↔XPBD parity check: with the same symplectic modal stepper, the two solvers' modal `q(t)` response to the same impact should match closely, differing only in their rigid-contact handling.

## Verified diagnosis (do NOT re-derive these wrong — all probe-confirmed)

On `scenes/reduced_shelf.py` (drop a 6 kg book on a soft shelf with 5 resting books), AVBD's surface barely rings (~2–4 surface "rings", ~11–18 mJ resting-book KE) while XPBD rings ~43× and excites the books to ~125 mJ. Cause, established by probes:

1. **NOT the modal under-relax knob.** Matching `_modal_relax` (AVBD 0.1) to XPBD's 0.25 does not close the gap; the resting books plateau ~36 mJ. Even `relax=1` does not help.
2. **NOT the Rayleigh damping.** Book KE is insensitive to `modal_damping_scale` (1.0→0.05 leaves it at 36.51 mJ).
3. **NOT the contact stiffness.** AVBD rings the same regardless of penalty-escalation `beta`; XPBD rings the same regardless of `support_compliance`.
4. **The modal steppers are IDENTICAL.** Both AVBD `_solve_q_block` and XPBD `_project_modal_elastic` are **backward Euler** — they converge to `q^{n+1}=q̃/(1+ω²h²)` and dissipate ~100% of modal energy in free vibration (SDOF: a 20 Hz/ζ=0.012 mode keeps ~0% energy after 1 s under BE vs analytic ~4%).
5. **XPBD rings because its RIGID CONTACT chatters**, not because of a better modal stepper: the impactor rebounds ~17× in XPBD (under-damped position-based contact) vs ~1× in AVBD (augmented-Lagrangian lands & sticks). Each XPBD bounce re-kicks the shelf. This is a contact artifact, arguably *less* physical than a clean energy-faithful ring.
6. **Root cause of "AVBD looks dead": backward-Euler numerical dissipation** kills the modal ring even when fully converged.

See memory `xpbd-vs-avbd-modal-ring-mechanism.md`.

## Why symplectic (the chosen fix) and why NOT the decoupled IIR

- Integrator math: BE amplification `|λ| = 1/√(1+ω²h²) < 1` → energy decays every step. Implicit midpoint/trapezoidal has `det = 1` → energy conserved (undamped) and decays at the **physical** rate when damped.
- **Explicit symplectic is disqualified**: shelf modes span `ω = 128 … 155000 rad/s` and substep `h ≈ 2.08e-3 s`, so `ωh` up to ~322 ≫ 2 (explicit symplectic stability limit) → blows up on stiff modes.
- **SDOF validation (already done, `/tmp/sdof_symplectic.py`)**: implicit midpoint conserves energy on the low mode (E=1.0000 undamped, 0.0442 damped ≈ physical 0.0420) and **stays stable (A-stable) on the 24 kHz mode** (peak|q|=2.8e-6, no blow-up). Caveat: midpoint is not L-stable → stiff modes *chatter* at Nyquist (negligible amplitude here due to heavy damping). If that ever bites, use the **exact-resonator** form (`dcr/modal/exact_resonator.py`, `dynamic_compliance_step`), which kills stiff modes cleanly and is the same energy-faithful physics expressed as a compliance-to-force — the shape a constraint solve consumes.
- **Keep `q` co-solved (native).** The implicit constraint solve is passive *by construction* (body and `q` move together, momentum-conserving), so no η-bookkeeping is needed. This is the whole benefit of the native-constraint rewrite. The **decoupled standalone IIR** (where `q` is stepped by a recurrence outside the solve) gives back that passivity and re-introduces the coupler-era energy cap — it was prototyped here as `Solver6DOF._modal_iir` and it **blew up** (injected 1.3–18 J, flung the books) because the staggered forcing from the penalty load is non-passive. **Do not use the decoupled IIR.** The `_modal_iir` scaffold may be kept as a documented dead experiment or removed.

## The change to make

The modal subsystem is **diagonal eigenbasis** in both solvers: `M_q = I`, `K_q = diag(ω²)`, `D_q = diag(2ζω)`, 16 oscillator modes, no static modes (`rs.eigen_omegas / eigen_zetas` give per-mode `ω, ζ`). Because it's diagonal and shared, prefer a **single shared per-mode symplectic step** (a small helper that, given `(q, q̇)` and the modal generalized force/contact coupling, advances one trapezoidal/implicit-midpoint step) that both solvers call. Keep BE in both as the default + parity reference; gate the new path behind a flag, e.g. `_modal_symplectic`.

**AVBD — `dcr/avbd/_solver/solver_6dof.py`:**
- `_solve_q_block` (≈ line 2130) is the host (numpy) BE q-block. Replace the **inertial+damping discretization** — `H_q = M_q/h² + D_q/h + K_q`, `g_q` built against the predictor `q̃ = qⁿ + h·q̇ⁿ` (`_modal_predict`, ≈2116) — with the **trapezoidal / implicit-midpoint** discretization, **keeping the contact terms** `+ρ·U_yU_yᵀ` in `H_q` and `−U_y·f` in `g_q` so the contact stays implicitly coupled (this is what keeps it stable/passive). Reconstruct `q̇` consistently with the scheme (not the BE finite difference) in `_modal_commit` (≈2203). `self.dt` is the **substep** dt during the loop. Per-iteration q-block dispatch ≈ line 2096; substep-end commit dispatch ≈ line 1833.

**XPBD — `dcr/avbd/_solver/solver_xpbd.py`:**
- `_project_modal_elastic` (≈ line 1212) is the compliant modal-elastic constraint `C_i = q_i`, compliance `α=1/K_q[i,i]` — this is the modal **restoring**, and it's BE-equivalent (converges to `q̃/(1+ω²h²)`). Replace its BE character with the **same** energy-conserving modal advance, keeping the **support** contact (`_project_support`, ≈1234, and the block solve `_project_support_block`) as the coupling that links `q` to the rigid body. Predict at ≈ line 1002 (`_substep_cpu`), `q̇` reconstruction at ≈ line 1057. Use the shared helper.
- Device path: the XPBD modal-elastic kernel is `pk_modes_elastic` (`dcr/avbd/_solver/xpbd_kernels.py` ≈ 1694) and AVBD's device q-block is `_solve_q_block_device`. Port to device + parity tests only after both host paths pass.

CPU host path first for both (the shelf scene runs `device="cpu"`, non-cargo, non-resident → host paths).

## Acceptance test

1. **Resting-book probe** (recreate from this session's `/tmp/probe_resting_books.py` / `probe_ring2.py`): on `build_reduced_shelf(device="cpu", iterations=16, avbd_substeps=4)`, compare AVBD-symplectic, XPBD-symplectic, AVBD-BE, XPBD-BE. Target: **both** symplectic variants ring (surface rings in the tens) and reach comparable book KE (~100–125 mJ), **finite/stable**, no books flung (bounceY ≲ 15 mm, tilt ≲ a few deg).
2. **AVBD↔XPBD modal parity**: with the shared symplectic stepper, log `q(t)` (and `E_modal(t)`) for both solvers on the same impact; they should track closely (the modal physics is now identical; only rigid-contact handling differs). Confirm XPBD's ring no longer hinges on contact chatter (it should ring even when the impactor lands cleanly).
3. **Energy graph** (twobody / E-stage style). Primitives exist: `dcr/rigid/energy.py:rigid_kinetic_energy`, `dcr/modal/energy.py:modal_energy`, and `solver.last_modal_KE / last_modal_PE` each step. Mirror `scripts/run_coupled_energy_log.py` and `scripts/run_stageE3/E4/E5.py`. Plot `E_modal(t)` ringing and decaying at the **physical** rate (vs BE flatlining), and confirm **passivity** in both solvers: cumulative modal energy gained ≤ cumulative rigid energy lost (should hold by construction since `q` is co-solved — verify it does).
4. **Parity / regression**: keep BE default in both solvers; run `tests/avbd_native/` (device + modal suites) to confirm no regression on the BE paths.

## Project rules (from CLAUDE.md)
- Reference (numpy/CPU) path first; device kernels only after CPU passes, kept parity-tested.
- Every equation gets a `# DEVIATION:` comment if it diverges from the paper, citing the source. The modal stepper change is a deviation from the paper's forced-IIR (Eq. 10) toward an in-constraint symplectic step — document it.
- Test before claiming done: show the probe numbers + the energy plot.
- Be honest about the stiff-mode chatter caveat; flag the exact-resonator as the fallback.

## Useful context
- This session's diagnostic scripts were in `/tmp/` (sdof_symplectic.py, sdof_xpbd.py, probe_resting_books.py, probe_ring2.py, probe_contact.py, probe_bounce.py, probe_iir.py) — recreate as needed.
- `_modal_iir` scaffold (decoupled IIR, off by default) lives in `solver_6dof.py` (`_iir_modal_step`, `_ensure_iir_coeffs`) — reference only; the chosen path is symplectic-in-constraint, NOT this.
- The `--modal-relax` CLI + live GUI slider added to `scripts/run_native_scenes_viser.py` (uncommitted) tunes the under-relax knob; not the fix, but handy for A/B viewing.
