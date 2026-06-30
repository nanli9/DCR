# Native solvers — two-way coupling + slab⇄object energy loop

Verifying, for the **current native solvers** (`Solver6DOF` = AVBD, `SolverXPBD`),
that the reduced-modal contact constraint is genuinely **two-way**: energy flows
in a circle — impactor KE → slab modal ring → the slab feeds back to the resting
object / impactor → it all decays to rest. This is the native-solver port of the
twobody verification (`docs/twobody/contact_force_sweep/README.md`); here the
"slab" is the reduced-modal **support surface** of each NON-cargo scene
(shelf / ledge / dinner table), with an impactor dropped on it and standing
"books" as the resting objects.

Reproduce:
```
.venv/bin/python scripts/run_native_energy_loop_verification.py
# probe internals + calibration: scripts/probe_native_energy_loop.py
```

## What is logged (per step), and how the contact force is defined

Per support-contact corner we log a scalar normal force `F_c` in Newtons. The
SAME multiplier enters the rigid-body gradient (lifts the body) and the modal
gradient (`∂C/∂q = −U_y`, deflects the slab) — Newton's 3rd law, so the loop's
two directions are one shared constraint.

| solver | `F_c` formula | source |
|--------|---------------|--------|
| XPBD   | `λ_c / h_sub²` (compliant multiplier)            | `_SupportContact.lam` |
| AVBD   | `max(0, −(λ_c + ρ_c·gap_c))` (aug.-Lagrangian)   | `c_lambda`, `c_penalty`, gap |

**Calibration (the force is real).** With the books at rest, the 4 load-bearing
corners of a 1 kg book sum to the supported weight to a few %:
AVBD 9.05→9.42 N, XPBD 9.6 N vs `m·g = 9.81 N` (`/tmp/calib_probe.py`). A box has
8 support rows; the bottom 4 carry the load, the top 4 read 0 — "the four contact
points." The 6 kg shelf impactor likewise settles to its own weight after impact
(4 corners × ~14.7 N ≈ 58.9 N = 6·g), with a large transient at the strike:
XPBD 569 N, AVBD 417 N peak (`loop_*`/`percontact_*` panel 1).

**Logging fix (impactor force — corrected 2026-06-30).** The force/gap extractors
filter solver rows by SOLVER body index (`sc.bi` / `row.body_a`), but were being
queried with DCR body indices (`impactor_idx`, `probe_indices`). The two spaces
are offset (shelf: DCR k → solver k−1), so the resting-object panels read a
*neighbouring* body's rows and the impactor panel — whose DCR index exceeds every
solver index — matched nothing and read a **flat zero**. The impactor is in fact a
tracked modal-support body (8 support rows; it is placed at contact zone
`(0.22, 0.0)`), so its force was never zero — only mis-logged. Fixed in
`probe_native_energy_loop.py` (`_solver_body_idx`, DCR→solver translation); no
solver math touched. The energy/lift/two-way metrics were never affected (they
come from real body state, not the force extractor), so Verifications 1–3 below
are unchanged; only the per-corner force curves and the `bounces` counts (which
read the now-correct body's gap) moved.

Also logged: impactor KE `Eimp`, slab modal ring `Eslab = last_modal_KE+PE`,
resting-object total mech energy `Erest = KE + m·g·lift` (so the launch is visible
while airborne), object lift, min corner gap (>0 ⇒ airborne).

## Verification 1 — the energy circulates (temporal ordering)

From `loop_series.csv` (reference config iters=16, substeps=4), the events are
ordered, not simultaneous — energy flows around the loop:

| scene/solver | impactor dump | slab ring peak | object KE peak | object re-ring landings |
|--------------|---------------|----------------|----------------|--------------------------|
| shelf/xpbd   | 250 ms        | 250 ms         | **275 ms**     | 5 (258…508 ms)            |
| dinner/xpbd  | 250 ms        | 250 ms         | **258 ms**     | 7 (250…458 ms)            |
| shelf/avbd   | 250 ms        | 250 ms         | 267 ms         | 1 (weak)                  |

The slab peaks **before** the object (the ring drives the object, not vice-versa),
and the object re-lands repeatedly, each landing re-ringing the slab (secondary
humps in `Eslab`). Everything decays to rest: e.g. shelf/xpbd `Eslab` 3303 → 6 mJ
tail, object KE 387 → 0 mJ. → **the loop is closed and dissipative.** See
`loop_<scene>_<solver>.png` (4 panels: energies, object height+airborne, impactor
per-corner force, object per-corner force) and `schematic.png`.

## Verification 2 — the coupling is genuinely TWO-WAY (control)

Discriminating probe: freeze the modal velocity (`q̇≡0`) so the slab becomes a
quasi-static spring that deflects but **cannot ring or feed energy back**. If the
object launch is slab-ring-driven, freezing must kill it. Ratio = object-KE-peak
(two-way) / (one-way), at the reference iters=16, substeps=4:

| scene  | XPBD two-way ratio | AVBD two-way ratio |
|--------|--------------------|--------------------|
| shelf  | **29×**            | 1.0×               |
| ledge  | **246×** (208× @ s=8) | 1.2×            |
| dinner | **18×**            | 1.1×               |

**XPBD: strongly two-way** — freezing the ring collapses the object's KE by
1–2 orders of magnitude; the launch is unambiguously slab-ring-driven. See
`control_<scene>_<solver>.png`.

**AVBD: only marginally two-way at the reference config** — the slab still rings
(shelf `Eslab` 1390 mJ two-way vs 840 mJ one-way, so the inertial ring is real),
but that ring barely reaches the resting object; the object's small KE is mostly
quasi-static shelf tilt, present with or without the ring. AVBD's coupling
**emerges only at high convergence** (see sweep) — e.g. dinner 32 iters × 8
substeps reaches **42×**.

## Verification 3 — iterations × substeps sweep (`sweep_<scene>_<solver>.png`, `summary.csv`)

Robustness of the loop across solver settings. Trends (consistent across scenes):

- **Substeps strengthen the loop** for both solvers — more substeps resolve the
  ring better → more object launch and a higher two-way ratio. XPBD shelf two-way
  ratio: 16× (s=2) → 29× (s=4) → 75× (s=8). AVBD dinner: 3.4× → 7.7× → 42× at 32
  iters.
- **AVBD coupling grows with iterations+substeps** — weak/non-monotonic at low
  budgets (the under-relaxed, dissipative AVBD solve suppresses the feedback),
  strong only when well-converged.
- **XPBD is two-way at every budget** (ratio ≥ 16× wherever energy is bounded),
  but see the caveat below.

## Honest caveats

- **XPBD injects energy at low iterations (NOT energy-conserving there).** At 8
  iterations the slab ring exceeds the impactor's input by up to ~12–30× —
  shelf `Eslab` 352 J vs impactor 29 J (8×2); ledge 1138 J vs 385 J. This is the
  known under-convergence blow-up (cf. memory *parallel XPBD blow-up at high modal
  impedance*). Energy is **bounded only at iters ≥ 16** (shelf 8×2: 352 J → 16×2:
  7.4 J → 32×2: 2.3 J). The two-way *coupling* is real regardless; the *energy
  magnitude* at ≤8 iters is a solver artifact, flagged on the sweep heatmaps.
- **AVBD stays energy-bounded** (max slab ring < impactor KE in every config) but
  is too dissipative to show a strong loop except when well-converged.
- The two-way ratio in a near-zero-coupling regime (AVBD low budget) is noisy and
  occasionally < 1 (one-way's quasi-static tilt happens to transmit slightly more)
  — reported as-is, not cherry-picked.
- These are the reduced-modal **support** scenes only (non-cargo, per request).
  The symplectic modal step is the host path; runs are CPU.

## Files
- `loop_<scene>_<solver>.png` — 4-panel energy loop + bounces + per-corner forces
- `control_<scene>_<solver>.png` — two-way vs one-way (frozen q̇) overlay
- `percontact_<scene>_<solver>.png` — every corner force, impactor + resting object
- `sweep_<scene>_<solver>.png` — iters×substeps heatmaps (slab ring, object KE,
  bounces, two-way ratio)
- `schematic.png` — annotated box-and-arrow loop
- `summary.csv` — every (scene, solver, iters, substeps, coupling) metric
- `loop_series.csv` — per-step series for the reference (16,4) configs
