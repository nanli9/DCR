# Modal Contact Network — every deformable participant in every contact row

> **Status (first pass landed):** N1(partial)+N2 modal-coupling half is
> implemented, tested, and rendered — see `docs/network/n2.md`. A stacked cargo
> cube's modes ring iff the box-box modal network is on (0 → nonzero), stable and
> OFF-parity-clean. The **rigid-ride** half (flex into the box-box primal gap) was
> implemented and reverted: it chatters an offset stack off its base — exactly the
> **N3 stability gate** below. N3 is the go/no-go before wiring the rigid ride and
> before any XPBD/device port (N5) or the full slab⇄base⇄stacked loop (N4).

> Staged build plan for generalizing the dynamic two-way modal constraint from
> "support rows only" to **all** contact rows, so that bodies carrying reduced
> modes (`fem_rigid` / `abd` / `fem` cargo) exchange ring energy with each other
> — not only with the slab. Read `CLAUDE.md` first, then this file top to
> bottom. Work happens on branch lineage of `benchmark` (where the native cargo
> machinery and the X0–X7 paper evidence live).
>
> **Relationship to the current paper:** this track is strictly additive and
> gated (see Hard Constraint 1). Paper-1 (X0–X7) claims and evidence must remain
> valid and re-runnable unchanged at every stage. The go/no-go decision for
> whether this becomes part of paper 1 or the core of paper 2 happens at the
> N3 gate — not before.

## Why this plan exists (context for the executing agent)

Current state of the native solvers (verified against code, 2026-07-03):

- The support's modal `q` couples two-way with **every** body's support
  contacts (impactor and resting objects identically; per-contact
  engaged/compressive gating only). Verified: `dcr/avbd/_solver/solver_6dof.py:2283-2301`,
  `solver_xpbd.py:1418-1442`, scenes track all bodies.
- Cargo bodies (a 6-DOF rigid box **plus** k body-frame elastic modes; the
  `rigid → fem_rigid → abd → fem` dropdown, `dcr/avbd/cargo/`) join the
  augmented modal vector `Q = [q_support; a_b0; a_b1; …]` with block-diagonal
  `M_Q/K_Q/D_Q`. Their **support** rows carry the co-rotated modal column
  `G_a = n̂ᵀ·R·Φ_c` and one shared multiplier loads support `q` (−U_y·f) and
  cube `a` (+G_a·f) — Newton's third law on `Q`. AVBD:
  `solver_6dof.py:716` (`add_cargo_native`), `:2581` (`_cargo_freeze_and_W`),
  `:2639-2643` (`_solve_q_block_cargo`). XPBD: `solver_xpbd.py:485`
  (`add_cargo`; the `_STAGE4` string at `:62` is stale — Stage 4 landed, see
  `tests/avbd_native/test_xpbd_cargo.py`).
- **The gap this plan closes:** the augmented gradient `W` is assembled over
  support rows ONLY (`W` is `(n_sup × R_tot)`, loop over `_support_row_cidx`,
  `solver_6dof.py:2587-2598`). `BOX_BOX_CONTACT_6DOF` rows carry **zero** modal
  columns — a body stacked on a ringing cargo cube feels only the cube's rigid
  pose, never its flex. Slab⇄cube exchange exists; cube⇄cube does not.

The target formulation is uniform and already implicit in the cargo design
(`two_band_coupling.html`): **every contact row's gap reads the deformed
contact points of both participants**,

```
C_row(z, Q) = n̂ · [ p_A(z_A, a_A) − p_B(z_B, a_B) ],
p_X = x_X + R_X (r̄_X + Φ_X(p) a_X)                    # deformed contact point
∂C/∂a_A = +n̂ᵀ R_A Φ_A(p)      ∂C/∂a_B = −n̂ᵀ R_B Φ_B(p)
```

with one clamped multiplier per row driving `z_A, z_B, a_A, a_B` together. The
slab is the degenerate participant: zero rigid DOFs, world-fixed field
`Φ(p)·q = U(x_c)·q · ŷ` — i.e. today's support row is the special case, and a
cube "is treated just like the slab."

## Hard constraints (binding for every stage)

1. **Strictly additive; default OFF; OFF ⇒ bit-identical.** All network
   behavior sits behind one flag (`modal_contact_network`, default `False`).
   With the flag off — or on but with no modal body-body pairs in the scene —
   every X0–X7 probe must reproduce its committed CSVs bit-identically (same
   gate as X0's determinism check). This is what keeps paper 1 shippable at
   every point of this plan. A stage that breaks OFF-parity fails, full stop.
2. **All CLAUDE.md rules apply**: cite the foundation section (§N) in every
   implementing docstring, `# DEVIATION:` for any divergence, naming discipline
   (`eps_r`/`restitution`, `eta`, `alpha` — never bare `eps`), CPU/numpy
   reference first, warp only after measured need, no new runtime dependencies
   (`playwright` + system Chrome remain rendering-tooling deps only, as in X3),
   test before claiming, one branch per stage (`stageN0-network-foundation`,
   `stageN1-full-normal`, …), 0 new test failures per stage (baseline: the 30
   documented pre-existing failures, incl. the truck lumber-stack host box-box
   topple — plan rule: never "fix" it silently here either).
3. **Engaged-gated block-GS is the shipped pattern.** `q`/`a` updates happen in
   the augmented q-block between colored primal sweeps, gathering only active
   compressive rows (`f = min(ρC + λ, 0); if f ≥ 0: skip`). Do NOT re-attempt
   the monolithic cross-term Schur — it was implemented and rejected for
   injecting energy without the Δz back-substitution
   (`docs/native_modal_support.md:76-149`, `dcr/avbd/modal_qblock.py` is the
   retained numpy oracle of that rejected form). Any revisit of that decision
   is out of scope for this plan.
4. **Normal-direction first.** Today's modal columns are normal-projected only
   (support rows: the y-row). This plan generalizes the projection to arbitrary
   `n̂` (N1) but does NOT add modal columns to friction/tangent rows — the
   tangential two-way question is open even on the support path (X6.1
   wrench-on-roof, unbuilt) and must be settled there first. One sentence in
   each stage doc; no tangent code.
5. **Conflict note vs the monolithic rewrite prompt.** 
   `prompts/monolithic_zq_solver_implementation_prompt.md` hard-constraint 4
   scopes `(z,q)` coupling to body↔support ("the foundation has no body↔body
   modal term"). That constraint tracks the CURRENT foundation; this plan's N0
   extends the foundation precisely so that scope can widen. Until N0 is
   written and reviewed, that older constraint stands. An executing agent must
   not treat the two prompts as contradictory: N0 is the amendment mechanism.
6. **Stepper scope stated per stage.** The cargo path runs the BE modal step
   (AVBD+cargo under `symplectic` raises `NotImplementedError`; X-plan rule 5).
   Every N-stage result states which stepper ran. Extending the symplectic
   stepper to cargo blocks is a separate follow-up, not assumed here.
7. **Honest reporting.** Dead/detuned cells, chatter, blow-ups, and any
   post-clamp violations go in the tables as-is. The N3 robustness matrix is
   the credibility anchor of this whole track, exactly as X1's was for C2.

## Stage N0 — Foundation extension (math first, no code)

**Goal:** the repo's discipline is math-foundation-before-code. Write
`prompts/modal_contact_network_foundation.md` covering:

1. **Unified gap + gradients** (the `C_row(z,Q)` block above), with the support
   row derived as the degenerate participant (zero rigid DOFs, world-fixed
   field) — one formulation, two special cases (support row, box-box row).
2. **Energy accounting on the augmented state.**
   `E_modal(Q) = ½ Q̇ᵀ M_Q Q̇ + ½ Qᵀ K_Q Q` (block-diagonal). Key structural
   point to state and prove at the ledger level: **body↔body modal exchange is
   internal to `Q`** — energy moving from the slab block to a cube block (or
   cube⇄cube) does not change `E_modal` totals except through the shared
   multipliers' work, so the existing §15 inequality generalizes as
   `ΔE_modal(Q) ≤ η · ΔE_rigid_loss` with the SAME rigid-side budget
   (`grav_work − ΔKE`). Define the work estimator over all modal-carrying rows:
   `W_c→m = Σ_rows (W_rᵀ j_r) · Q̇_mid`.
3. **Clamp generalization.** The X1 reservoir + full-state γ-projection
   (`dcr/avbd/_solver/passivity.py`) restated over `Q`; state whether γ scales
   the full augmented state (direct generalization — default) or per-block
   (refinement; discuss why per-block scaling can break third-law pairing
   mid-solve and leave it as an explicitly-marked option).
4. **Stability discussion (pre-registered hypotheses for N3):** two resonators
   through a unilateral on/off contact (chatter re-excitation), impedance /
   mass-ratio mismatch, gate flicker at grazing contact, block-GS spectral
   radius with both-sided columns, why engaged-gating + relax is expected to
   carry over — and what observable would falsify that.
5. **Claims-to-avoid list** (the §14 analogue): e.g. no "provably passive
   whole scene" while the host box-box friction instability exists; no
   wave-propagation-accuracy claims (k-mode truncation gives standing-wave
   fields per body, not traveling waves through a stack); no tangential-ring
   claims (Hard Constraint 4).

**Accept:** doc merged; every later stage's docstrings cite its §Ns.
**Deliverables:** `prompts/modal_contact_network_foundation.md`.

## Stage N1 — Full-normal modal columns on the EXISTING support rows

**Goal:** de-risk the projection generalization with a zero-behavior-change
stage. Replace the hardcoded y-row (`G_a = (R·Φ_c)[1,:]`, `U_y`) with the
general `n̂ᵀ(R·Φ_c)` / `n̂·Φ(x_c)` form, where support rows pass `n̂ = ŷ`.

**Steps:**
1. Thread a per-row normal through the modal-column assembly
   (`_cargo_freeze_and_W`, the XPBD `_SupportRow` fields, the device
   `modal_qblock_kernels.py` W upload). The anchor flex-bake becomes an offset
   along `n̂` (still a scalar per row).
2. Numpy reference first; device parity to fp64 roundoff (existing parity-test
   pattern).
3. New unit test: a synthetic TILTED support (rotate the mode field's frame)
   where the y-row form is provably wrong and the `n̂ᵀ` form matches a
   hand-integrated two-body reference.

**Accept:** (a) with `n̂ = ŷ` all X-scene probes bit-identical (Hard
Constraint 1 gate); (b) tilted-support unit test green; (c) parity green.
**Deliverables:** the projection generalization + `docs/network/n1.md`
(short — this stage is deliberately boring).

## Stage N2 — Box-box rows gain modal columns (CPU reference, AVBD first)

**Goal:** the actual feature. When `modal_contact_network=True` and either
participant of a `BOX_BOX_CONTACT_6DOF` row is a registered cargo body, the
row gets modal columns for each cargo participant: `+n̂ᵀR_AΦ_A(p)` in A's
a-block, `−n̂ᵀR_BΦ_B(p)` in B's a-block, and the gap reads both bodies'
deformed corners.

**Steps:**
1. **W over all rows.** Extend the augmented-gradient assembly from
   `(n_sup × R_tot)` to `(n_modal_rows × R_tot)` where `n_modal_rows` = support
   rows + box-box rows with ≥1 cargo participant. Box-box rows are stripped and
   re-emitted every step (`solver_6dof.py:326,398`) → the W rows and cargo
   tags must be rebuilt per step; support-row W stays cached as today.
   Multiplier warm-starting across re-emitted rows: reuse whatever the rigid
   box-box path does (do not invent a new scheme); state it in the doc.
2. **Modal sampling at SAT points.** Nearest-corner snap of `Φ_c` (the
   documented stage-3 deviation — box manifolds are corner/edge-generated, the
   modal field is smooth). `# DEVIATION:` citing N0 §(sampling) and stage-3's
   precedent. Surface interpolation is an explicitly-deferred refinement.
3. **q-block gather.** The augmented q-block already solves over `R_tot`; the
   change is gathering ±columns from box-box rows under the same engaged gate.
   Third-law check in code review: the SAME `f` must appear with opposite
   signs in the two a-blocks.
4. **Freeze counterfactual for a-blocks.** Mirror `_modal_freeze_qdot`
   (`solver_6dof.py:2189-2190`) with per-block `_freeze_adot[bi]` so N-stage
   metrics can ask "does the upper cube respond BECAUSE the lower one rings?"
   exactly the way X0's freeze-q̇ established the support loop.
5. **Minimal physics tests (no slab — isolate the body↔body path):**
   - *Third-law pair:* cargo cube A pressed on cargo cube B on a rigid floor;
     per-substep, the modal work into A's block equals the negative of B's
     through their shared rows (to roundoff), and total `E_modal` change ≤
     multiplier work (N0 §2 estimator).
   - *Ring transfer:* pre-excite A's fundamental mode (`a_A(0) ≠ 0`), B at
     rest on top; assert B's modal energy rises above a floor while
     `freeze_adot[A]` kills the effect (the discriminating counterfactual).
   - *OFF-parity:* same scenes, flag off ⇒ box-box behaves exactly as today.
   Friction guard: run these frictionless or at low μ first — the host box-box
   friction instability is a documented pre-existing issue and must not
   masquerade as (or mask) modal-transfer behavior; note μ in every test.

**Accept:** third-law + ring-transfer + OFF-parity tests green on the numpy
path; 0 new failures repo-wide; stage doc with the measured transfer numbers.
**Deliverables:** `docs/network/n2.md`,
`tests/avbd_native/test_network_boxbox.py`, the N2 scene builders in
`scenes/network_two_cube_transfer.py` (reused by N6's renders).

## Stage N3 — Stability + clamp coverage (THE go/no-go gate)

**Goal:** establish whether modal-modal chains have a safe operating region,
and make the §15 guarantee cover the augmented state. This is the stage with
genuine research risk — the simple support-only case already required
engaged-gating + relax 0.7 and a rejected monolithic solve; chains multiply
those feedback loops.

**Steps:**
1. **Clamp over `Q`.** Extend `PassivityLedger` + γ-projection to the
   augmented state per N0 §3 (this also closes the existing gap that the X1
   clamp is host **non-cargo** only — `solver_6dof.py:567`). Inertness
   requirement as in X1: zero clamps + unchanged transfer in the safe region.
2. **Robustness matrix** (the X1 money-figure pattern): scenes {2-cube stack,
   3-cube tower on rigid floor, 2-cube stack ON the slab} × budget
   {4×1, 8×2, 16×4, 32×8} × relax {0.7, 1.0} × mass ratio {0.1, 1, 10} ×
   cube stiffness ratio {soft/stiff}, clamp OFF vs ON. Flags: INJECT / BLOWUP /
   DEAD / DETUNE / gate-chatter rate, as-is per Hard Constraint 7.
3. **Characterize gate flicker** at grazing stacked contacts (count engaged
   toggles per row per second; correlate with any injection) — pre-registered
   in N0 §4.

**Accept (go):** clamp ON ⇒ 100% of cells satisfy the augmented invariant, AND
a nonempty safe region exists where the clamp is inert and transfer is alive
(the analogue of X1's 16×4 row). **No-go:** if every live-transfer cell needs
the clamp actively firing, the mechanism is not ready — stop, write the
honest doc, and the track becomes paper-2 research rather than a paper-1
section. Either outcome is a deliverable, not a failure of the plan.
**Deliverables:** `benchmarks/network/n3_robustness/` (CSV + heatmaps +
manifests, X-plan rule 8 style), `docs/network/n3.md` with the go/no-go call
written explicitly.

## Stage N4 — The full loop: slab ⇄ base cube ⇄ stacked cube

**Goal:** the scene this track exists for — "the stacked upper body feels the
ring." Slab rings → base cargo cube rides AND flexes → upper cube responds to
the base's flex (not just its rigid ride).

**Steps:**
1. Scene `scenes/network_tower_on_slab.py`: FEM-modal slab (X3 builder,
   `fem_modal_support.py`), 2–3 stacked cargo cubes off-impact, one rigid
   impactor dropped at distance (off-centre, X2 pattern).
2. **Metric — network two-way ratio:** upper-cube peak response with the
   network ON ÷ with `freeze_adot[base]` (rigid-ride-only control). This
   isolates the NEW channel: both arms keep the slab ring and the rigid stack
   ride; only the base cube's flex transfer differs. Report per budget cell
   from N3's safe region.
3. **Per-block energy ledger plot** (X-style 4-panel): E_slab-block, E_base,
   E_upper, rigid KE, cumulative multiplier work, clamp α/γ — the visual of
   "slab rings → cube rings → back," which is the user-facing story.
4. Wall-clock: `R_tot` scaling row into the X5-style table (dense `O(R_tot³)`
   q-block; e.g. r=16 + 3 cubes × k=6 → R_tot=34 — expected trivial; measure,
   don't assert).

**Accept:** network ratio measurably > 1 with a physical explanation and
ledger-clean energy flow in the safe region; penetration bounded; doc.
**Deliverables:** `docs/network/n4.md`, scene + driver + CSVs/manifests.

## Stage N5 — XPBD port + device parity (optional; do not block N6)

XPBD mirror (its Stage-4 cargo machinery + `_SupportRow.cargo_bi/pid` pattern
extended to box-box rows), then the device kernels for dynamic-row W. Parity
to fp64 roundoff against the numpy references, per repo rule. If time-boxed
out, state "AVBD-CPU is the N-track artifact" honestly in every doc — do not
half-port.

## Stage N6 — Viser demo scenes + evaluation renders

**Goal:** the same production render stack as X3 — viser WebGL server +
headless Chrome client (`client.get_render(...)`, playwright driving system
google-chrome, software WebGL), GIF/MP4 assembly — pointed at the network
scenes. Pattern source: `benchmarks/paper_eval/x3_ground_truth/make_dinner_viser_gif.py`
(server/client capture, side-by-side worlds, deformation-exaggeration
captions).

**Scenes (each: side-by-side network ON vs OFF, impact-aligned, exaggeration
captioned, manifest):**
1. **Two-cube ring transfer** (`network_two_cube_transfer.py`, from N2): cube A
   pre-excited/struck against resting cube B on a rigid floor — no slab, the
   pure body↔body channel. ON: B's surface visibly ripples and B twitches;
   OFF: B inert. The clearest didactic render.
2. **Tower on the slab** (`network_tower_on_slab.py`, from N4): distant
   impact; the ring climbs the tower. Overlay per-level modal-energy traces
   under the render (the N4 ledger panel as an animated strip).
3. **Dinner, stacked plates** (`network_dinner_stacked_plates.py`): the X3
   production dinner scene with plates stacked two-high near the pot drop —
   real glTF assets, table = FEM-modal support, plates = cargo cubes'
   coupling (plate bodies registered as cargo). ON vs OFF: the upper plate's
   extra kick from the lower plate's flex. This is the paper-facing beauty
   shot; quantitative claims stay on scenes 1–2.

**Accept:** three GIFs/MP4s under `docs/network/` regenerable from manifests;
each caption states stepper, h, exaggeration, μ, and clamp state.
**Deliverables:** `benchmarks/network/make_*_gif.py`, `docs/network/n6.md`.

## What NOT to do (scope guards)

- No friction/tangent modal columns (Hard Constraint 4).
- No host box-box friction fix inside this plan; low-μ isolation instead.
- No monolithic cross-term Schur revival (Hard Constraint 3).
- No symplectic-stepper extension to cargo blocks inside this plan.
- No surface-interpolated Φ sampling in N2 (corner-snap + deviation note;
  interpolation only if N3/N4 measurements show snap artifacts — then as its
  own commit with a test).
- No claims beyond N0 §5. In particular: "stacked bodies feel the ring
  through deformable interfaces, energy-bounded" — yes;
  "wave propagation through stacks" — no.

## Definition of done (claims → evidence map)

| Claim | Evidence | Stage |
|---|---|---|
| Unified constraint (slab = special case) | foundation doc + N1 bit-identical gate + N2 third-law tests | N0–N2 |
| Cube⇄cube two-way exchange exists | ring-transfer test + freeze-ȧ counterfactual | N2 |
| Energy-bounded on the augmented state | clamped robustness matrix, 100% invariant + inert safe region | N3 |
| Stacked body feels the ring (the loop) | network two-way ratio > 1 vs rigid-ride control + ledger | N4 |
| Solver generality / practicality | XPBD+device parity; R_tot timing row | N5 (optional) |
| Demo quality | three viser renders, ON/OFF side-by-side | N6 |

Every stage: `pytest tests/ -q` with 0 new failures, figures regenerable from
manifests, stage doc written, THEN move on. The N3 gate decision (paper-1
section vs paper-2 core) is recorded in `docs/network/n3.md` at the moment it
is made, with the matrix that justified it.
