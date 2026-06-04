# AVBD ↔ DCR coupling — session findings (2026-06-03, branch `AVBD`)

Working notes from a debugging/explanation session on the AVBD-native DCR
follow-up. Covers: the vendored-solver re-sync, three diagnosed coupling
issues (shelf, ledge, truck), the paper check on AVBD's force model, the
new viewer knobs, and how Phase A vs Phase B differ. All measurements were
produced headless on CPU via the `scripts/_diag_*.py` harnesses noted below.

---

## 1. Vendored AVBD solver re-synced to upstream

Re-synced `dcr/avbd/_solver/` from upstream <https://github.com/nanli9/AVBD>
at commit **`52d2483`** ("Default to paper-faithful 'jacobi' graph coloring").
Changes were confined to the 6-DOF rigid path:

- `solver_6dof.py`, `kernels_6dof.py` — copied verbatim from upstream.
- `__init__.py` — kept the DCR-customized one (it re-exports the contact-type
  constants `FLOOR_CONTACT_6DOF` etc. that upstream's package init drops);
  only updated the provenance note.
- `coloring.py`, `kernels.py`, `solver.py`, `deformable.py`, `scene.py` were
  already byte-identical to upstream → untouched.

What the perf pass brings: achieved-color-count primal bound (A0/A1),
speculative "jacobi" coloring now default (A2), stable-graph recolor skip
(A4), static half-extent re-upload skip (A5), the captured-graph `set_*()`
`.assign()` correctness fix, and `read_state_batched(include_rows=)` (B1).

Verification: 52/52 `tests/avbd/` pass; `jacobi` vs `jones_plassmann` give
bit-identical solves (only the partition differs, the AVBD solve is the same).

---

## 2. Shelf scene — low AVBD iterations starve the modal injection

**Report:** at `avbd_iterations=4` (esp. with high substeps) DCR "does
nothing", books barely move even at `eta=1`. **Confirmed.**

**Not** a budget problem — the rigid KE dissipated (`E_loss`, hence
`E_max = η·E_loss`) is ~46 J in every config. The injection collapses anyway:

| iters | sub | cum E_loss | **cum injected** | max book disp |
|------:|----:|-----------:|-----------------:|--------------:|
| 10 | 4 | 45.7 J | **13.7 J** | 10.2 mm |
| 4  | 4 | 46.5 J | **0.0 J**  | 1.0 mm |
| 10 | 6 | 45.6 J | **9.5 J**  | 4.6 mm |
| 4  | 5 | 47.2 J | **0.13 J** | 1.3 mm |
| 4  | 6 | 47.1 J | **0.001 J**| 1.0 mm |

**Root cause — temporal misalignment at the once-per-step sampling seam.**
The modal kick (`passive_dcr.py:483-501`) fires only for `is_new` contacts,
and its size is the projection of AVBD's dual `λ` (`lam`). DCR samples the
solver once per rigid step, at the end of the substep loop. For a kick to
land, three things must coincide in that one sample: (a) the contact is
`is_new`, (b) `λ` is converged, (c) `E_max` is large. With a **hard** solve
(iters=10) the impact resolves in one step and all three align. With a
**soft** solve (iters=4) AVBD smears the impact across substeps; the
end-of-step snapshot never flags the impacting contact `is_new` during the
high-`E_max` window — it slips several steps late, by which point the budget
has drained. Iterations is the dominant knob; substeps secondary.

Not a passivity violation (injecting 0 still satisfies `ΔE_modal ≤ η·ΔE_loss`)
— it's under-utilization. Harness: `scripts/_diag_substep_bug.py`,
`scripts/_diag_impact_window.py`.

---

## 3. PGS-vs-AVBD: why iterations matter (paper-checked)

Verified against *Augmented Vertex Block Descent*, SIGGRAPH 2025, §3.1:

- **Eq 8** energy `E_j = ½ k_j C_j² + λ_j C_j` — augmented Lagrangian = a
  stiffness/penalty term **plus** the multiplier.
- **Eq 9** force `f = −(k_j C_j + λ_j) ∂C/∂x` — both terms.
- **Eq 10** `λ_j^(0) = 0` (dual starts at zero); text after **Eq 11**: *"the
  stiffness variable merely determines how fast the dual variable grows over
  multiple iterations to provide the necessary force."*

So at low iteration counts the **stiffness term** carries the force while the
**dual `λ` lags**. Our coupler reads exactly that dual (`kernels_6dof.py:656`
is Eq 11 verbatim; `Solver6DOF.lambdas()` → `c_lambda` → `contact_extract.py`).
A PGS/LCP impulse, by contrast, *is* the momentum change, so it stays
consistent even under-converged. Correction to earlier wording: it's the
*augmentation/stiffness* term of the augmented Lagrangian, not a "penalty
method". The ledge's iters=4 *over*-injection is the paper's §3.6 "explosive
error correction" (under-converged hard constraints spike momentum a frame
late).

---

## 4. Ledge scene — material stiffness, not solver knobs

**Report:** ledge barely responds for any iters/substeps. **Confirmed**, and
it's a material limit:

| scene | inject / E_loss | motion |
|-------|----------------:|-------:|
| shelf (E=0.5 GPa, ρ=600)  | 13.7/45.7 = **30%** | 8 mm |
| ledge (E=10 GPa, ρ=2500)  | 0.7/385  = **0.2%** | ~2 mm |

The ledge is 20× stiffer / 4× denser; the contact impulse barely projects
onto its (high-frequency, small-amplitude, mass-normalized) modes — `Φᵀj` is
tiny, so the budget is irrelevant. Geometry compounds it: the pillars rest on
a pedestal that rests on the ledge, so they're one rigid hop from the only
body DCR excites. No solver knob can change stiffness.
Harness: `scripts/_diag_ledge.py`.

---

## 5. Truck scene — runaway `E_modal` from a non-conservative back-reaction

**Report:** slab "vibrates as hell", `E_modal` never decays; is it AVBD
treating the slab as deformable?

- **The slab is a *static infinite-mass plane* in AVBD** (`world.add_floor`,
  `is_static=True`, `avbd_body=None`). AVBD never deforms it. The visible
  vibration is purely the DCR modal overlay `rest + Φ·q` drawn on top. So it
  is **not** "AVBD as a unified solver".

- The bounded passive kick is innocent: cumulative injection **2,725 J** ≤
  `η·E_loss` = 78,684 J (bound holds). Yet `E_modal` reaches **~125–196 kJ**
  and `q̇` is amplified ~45× the injected energy → energy is being *created*.

- The exact modal stepper (`homogeneous_stepper.py`) has spectral radius
  `e^{−ζωT} ≤ 1` → cannot create energy. The only other write to `q̇` is the
  **patch-mode modal back-reaction** at `passive_dcr.py:1006`:
  `self._stepper.qdot -= Phi_x.T @ lam_final`.

- That step is **not energy-conservative**: `ΔE = −q̇·(Φᵀλ) + ½‖Φᵀλ‖²`. The
  self-term `½‖Φᵀλ‖²` is always positive, and the patch impulse `λ` is
  geometric (not aligned to `q̇`), so it *pumps* instead of *drains*.

**Decisive test** (`scripts/_diag_truck_backreaction.py`) — disabling only
line 1006:

| config | peak E_modal | final E_modal | peak slab disp | final disp |
|--------|-------------:|--------------:|---------------:|-----------:|
| back-reaction ON (stock)  | 1.96e5 J | 3.0e4 J | 186.6 mm | 69.5 mm |
| back-reaction DISABLED    | 6.7e2 J  | **1.3e-6 J** | 8.9 mm | **0.005 mm** |

The faithful behaviour is the disabled row: a ~9 mm modal dip under impact
that damps to flat. **Status: diagnosed, not fixed.** Harness also:
`scripts/_diag_truck.py`.

### Is the rendered vibration "the modal reduction of the FEM mesh"?
Yes — `rest + Φ·q` is exactly the modal superposition `u(x)=Σ qᵢ φᵢ(x)`, and
a deforming elastic support *is* the intended DCR feature. What's wrong is the
*magnitude/persistence* (the back-reaction bug inflating `q`), not the
visualization. The geometry the bodies actually collide against stays a flat
plane; the deformed mesh is an overlay (so geometry and overlay can visually
disagree — the cost of "distant" response).

---

## 6. Phase A vs Phase B — both push objects, only B pays correctly

- **Phase A** (always-on base pipeline): inject impacts into modes
  (`q̇ += α·s`, bounded by `E_max`), push resting objects via patch kicks,
  and "pay" via the line-1006 back-reaction. But A's payment *is* the leak
  (§5), so A cannot settle the reservoir — its only drain creates energy.

- **Phase B** (opt-in moving-support pass, `_run_moving_support_pass` +
  `moving_support_solve.solve_one_contact`): also pushes resting objects, by
  treating each resting contact as a contact against a **moving support**
  whose velocity is `v_s = Φ(x̄)·q̇`. The impulse
  `J = −(1+e)·K_total⁻¹·(v_p − v_s)` (with `K_total = K_body + ΦΦᵀ`) is
  friction-cone clipped, then **γ-line-searched so work ≤ `β·E_modal`**
  (§11/§12, `passivity_scale_gamma`), then paid via `q̇ −= Φᵀ J`. Gated off on
  empty reservoir (§22 Inv 3), non-closing support (§13 causal), and modal
  cutoff (§14.3).

Because B's payment is budgeted, it can only *drain*, and the drain is
proportional to `E_modal` → it's a self-limiting valve. It does not touch the
geometry/contact point — only reads the surface **velocity** `Φ·q̇` (and, with
`--use-bj`, the surface normal tilt) at the fixed flat-plane contact, so no
penetration path is introduced.

**Measured (truck, `scripts/_diag_truck_phaseb.py`):**

| config | peak E_modal | final E_modal | peak slab disp | cum W_support | body travel |
|--------|-------------:|--------------:|---------------:|--------------:|------------:|
| Phase B OFF | 1.96e5 J | 3.0e4 J | 186.6 mm | 0 | **91.9 m** |
| Phase B ON  | 9.4e2 J  | **1.3e-6 J** | 9.8 mm | 71.9 J | **3.7 m** |

B drains the leaked energy into bounded object-pushing work and holds
`E_modal ≈ 0`, which also starves A's pump. **B masks the bug; it does not
fix it.** Phase B is the template for the fix.

---

## 7. Viewer change (shipped)

`scripts/run_scenes_avbd.py` — new "Visualization" GUI folder, two checkboxes:
- **render FEM vibration** (default **off**): off → slab drawn flat (rest
  pose), like a plain rigid body, and `Φ·q` is skipped; on → modal deformation.
- **FEM tet-mesh style** (default **off**): off → solid surface; on →
  tet-mesh wireframe (the FEM surface triangulation) via a second handle.

Both default off ⇒ default look is a plain solid flat slab. Verified: the
viewer launches clean (viser, no errors).

---

## 8. Phase-A back-reaction fix (applied)

Fixed the line-1006 leak with a **dissipativity guard** (one-shot γ, the
spec's §9 / Phase B's §12 pattern with budget 0). The §9.4 identity
`ΔE_total = −½λᵀK_totalλ ≤ 0` only holds for the raw `λ = K_total⁻¹·Δv_des`;
§9.5 cone projection + §9.6 scaling break it. The guard bounds the
back-reaction's **own** modal-energy change, measured on the **actual**
post-`step_n` `q̇` it mutates (not `Δv_des`/`v_f`, which are built from the
pre-`step_n` `_qdot_just_after_kick` — using those was a first wrong attempt
that came out γ≈1, a no-op):

```
j = Φ(x̄)ᵀ·lam_final
ΔE_modal(γ) = −γ·(q̇ᵀj) + ½γ²‖j‖²        # c_m = q̇ᵀj, a_m = ‖j‖² ≥ 0
γ = 0            if c_m ≤ 0              # kick can only add energy → reject
  = min(1, 2c_m/a_m)  otherwise
```

`γ` scales **both** the rigid kick and the back-reaction (transpose-
consistent). γ=1 when the kick already drains → well-behaved scenes
unchanged; γ<1 clamps the runaway. Carries `# DEVIATION:` / §15 cites in
`passive_dcr.py`. Diagnostic: `coupler.last_backreaction_gamma_min`.

**Verified** (`scripts/_diag_three_scenes.py`, `_diag_truck_backreaction.py`):

| scene | peak E_modal before | peak E_modal after | slab disp before→after |
|-------|--------------------:|-------------------:|------------------------|
| truck            | 1.96e5 J | **6.7e2 J** | 186 → 8.9 mm, decays to flat |
| ledge (light FEM)| 7.2e4 J  | **2.1e0 J** | runaway → flat |
| shelf            | 6.9e0 J  | 6.5e0 J     | unchanged (guard is a no-op) |

Stock (fixed) now matches the back-reaction-disabled baseline (~666 J peak,
→0 final). Shelf injection preserved (13.0 J; books move ~6.8 mm — slightly
less than the old 10.2 mm because that included leaked energy). Regression
test: `tests/avbd/test_patch_backreaction_passive.py`. 79 avbd+stageE tests
still pass.

Still open: the **shelf low-iteration injection starvation** (§2) — separate
bug (the `is_new`/`λ`/`E_max` sampling misalignment), addressed by the
effective-impulse source in `prompts/avbd_dcr_realtime_coupling_fix.md`,
not by this guard.

> The `scripts/_diag_*.py` files are throwaway diagnostic harnesses kept to
> back the numbers above and allow re-runs; safe to delete once consumed.

---

## 9. Effective-impulse source does **not** fix the §2 starvation (tested)

§8 closed by hoping the effective-impulse source from
`prompts/avbd_dcr_realtime_coupling_fix.md` §2 would cure the §2 low-iteration
starvation. **It does not.** Implemented all three sources behind a coupler
flag `impulse_source ∈ {lambda_only, augmented, delta_p}` and measured them
(`scripts/_diag_injection_iter_sensitivity.py`, shelf scene, 8 kg drop):

| source | iters=4 | 8 | 16 | 32 | CV(capped inj) |
|--------|-------:|----:|----:|----:|---:|
| lambda_only | 0.0 | 5.79 | 12.55 | 13.59 J | 0.689 |
| augmented   | 0.0 | 5.79 | 12.55 | 13.59 J | 0.689 |
| delta_p     | 0.0 | 5.79 | 12.55 | 13.59 J | 0.688 |

All three are **identical** and equally iteration-sensitive. Why:

1. **The cap, not the kick, sets the injection.** `passive_alpha` caps each
   step at `E_max = η·E_loss`; measured `α ≈ 0.3 < 1` whenever injection fires,
   so the cap is always binding. `delta_p`'s raw `‖s‖` is 5–7× smaller than
   `lambda_only`'s, yet the capped injection is the same — magnitude is moot.
2. **λ *is* under-grown at low iters** (probe: `max|λ_n|` = 0.16 @iters=4 vs
   4.16 @iters=8, ~25×) — the prompt's premise is literally true — **but it is
   harmless**, because the cap limits the injection before the under-grown
   magnitude could.
3. **The real lever is timing, as §2 said.** Total `E_loss` is
   iteration-*insensitive* (~45 J at every iter count); what collapses at low
   iters is the number of `is_new` steps that coincide with that `E_loss`
   (`n_inj` = 0 / 4 / 4 / 10 across iters=4/8/16/32). The injection is gated to
   `is_new` steps, and at low iters the impacting contact is never flagged
   `is_new` inside the high-`E_max` window.

**Decision:** default stays `impulse_source="lambda_only"` (zero behaviour
change; 263-test regression intact). `augmented`/`delta_p` kept as opt-in
ablations. The actual fix for §2 must target the **`is_new` × `E_max` timing
gate** (e.g. fund injection from an impact-window `E_loss` budget rather than
the single `is_new` step), not the impulse source. Plumbing added:
`solver.penalties()`, `extract_contacts` returns per-contact `k_N`, world
computes per-body `Δp`. Guard test: `tests/avbd/test_injection_impulse_source.py`.

---

## 10. Impact-window energy reservoir — partial fix (implemented + tested)

The reservoir from `prompts/avbd_dcr_impact_reservoir_fix.md` targets the §9 root
cause directly: deposit `η·E_loss` every step into a short-lived
per-(rigid,support) budget (key = `(rigid_body, elastic_body_idx)`, window W=4,
ρ_B=0.65), and let the E1 injection spend it on any *near* contact — dropping the
brittle `is_new` gate. Wired behind `use_impact_reservoir` (default OFF;
bit-identical fallback). The patch channel, `passive_alpha` cap, and back-reaction
guard are untouched. No `world.py` change (the coupler already gets `E_max` and
`contacts`). Diagnostic: `scripts/_diag_impact_reservoir_iter_sensitivity.py`.

**Result (shelf, eta=0.5, cum injected modal energy J):**

| config | iters=4 | 8 | 16 | 32 | CV |
|--------|-------:|----:|----:|----:|---:|
| is_new (OFF), lambda_only | 0.0 | 5.79 | 12.55 | 13.59 | 0.689 |
| reservoir ON, lambda_only | 1.25 | 6.48 | 14.47 | 15.49 | 0.623 |
| reservoir ON, **delta_p** | 1.43 | 7.95 | **22.62** | **22.59** | 0.678 |

**What it fixes (acceptance §14.1/§14.4/§14.7 — PASS):**
- **Kills the zero-injection at iters=4** (0 → 1.4 J; `n_inj` 0 → 97). The timing
  starvation is gone.
- **delta_p + reservoir nearly doubles** mid/high-iter injection and reaches
  `fill = 0.997` (budget fully utilized) at iters=16/32.
- Globally passive: `Σ E_inj ≤ η·Σ E_loss` holds in every config.
- η=0 ⇒ no injection; flag OFF ⇒ reservoir inert. Test:
  `tests/avbd/test_impact_reservoir_passivity.py` (4 pass; 59 avbd + 27 stageE green).

**What it does NOT fix (acceptance §14.2 — FAIL): iteration-insensitivity.**
CV only moves 0.689 → 0.62–0.68 (target < 0.34). The spread stays huge
(iters=4: 1.4 J vs iters=32: 22.6 J). Root cause — measured, not the reservoir's
fault: at iters=4 the budget IS deposited (~23 J, iteration-insensitive) but only
**5–6 % is spent** (`fill≈0.05`); the rest decays. The injection is
**magnitude-limited, not budget-limited**: a soft low-iteration solve smears the
impact across ~97 small-impulse frames, and the injectable modal energy `½‖s‖²` is
**quadratic** in the per-frame impulse, so the same total Δp spread thin yields far
less vibration energy (Cauchy–Schwarz). This holds for `delta_p` too — its
per-frame `s` is also small when the impact is smeared. `passive_alpha` only
scales *down*, so a large reservoir budget cannot rescue a small `s`.

This residual is arguably **physical**: a mushy solve genuinely transfers less
energy to vibration than a sharp strike, the way a soft landing rings a bell less.
The reservoir removes the *artifact* (zero from timing); it cannot manufacture
vibration the soft solve never imparted.

**Decision:** keep `use_impact_reservoir=False` default (doesn't meet the CV bar,
changes behaviour), but it is the best low-iter option available and is
passivity-safe — recommend enabling it **with `impulse_source="delta_p"`** for
low-iteration interactive use. A true iteration-insensitive fix would need
*coherent impulse accumulation* (bank the impulse VECTOR `s` over the window and
inject `½‖Σsᵢ‖²`, whose positive cross-terms recover the energy that per-frame
projection loses), capped by the banked energy budget — a formulation beyond the
current spec. **§11 tests exactly this prediction — and refutes it.**

## 11. Coherent impact impulse bank — refuted (implemented + tested)

`prompts/coherent_impact_impulse_bank_fix.md` formalizes the §10 prediction: bank
each event's per-frame modal impulses into `S = Σsᵢ` over a short causal window
and inject the event-level `½‖S‖²` once, recovering the cross terms
`Σ_{i<j} sᵢᵀsⱼ` that per-frame `Σ½‖sᵢ‖²` discards. Implemented as a standalone
module `dcr/dcr/impact_bank.py` (`ImpactKey`/`ImpactEvent`/`ImpactBank`) wired
behind `use_coherent_impulse_bank` (default OFF). The bank **subsumes the
reservoir** — it owns the `η·E_loss` deposit so the budget is counted once (the
spec §15 config turns both on, which would double-count; the runtime dispatches
the bank branch first and the `__post_init__` guard forces the reservoir off).
`passive_alpha`, the patch channel, and the back-reaction guard are reused
unchanged. Diagnostic: `scripts/_diag_impact_bank_iter_sensitivity.py`.

**Result (shelf, eta=0.5, cum injected modal energy J, `delta_p`):**

| config | iters=4 | 8 | 16 | 32 | CV | util@16 |
|--------|-------:|----:|----:|----:|---:|---:|
| reservoir ON (per-frame) | 1.43 | 7.95 | **22.62** | 22.59 | 0.678 | **0.997** |
| **bank ON** (end_of_window) | 0.35 | 2.13 | 4.55 | 4.12 | 0.602 | **0.203** |

**The bank injects LESS than the reservoir at every iteration count, and leaves
~80 % of the budget unspent** (utilization 0.203 vs the reservoir's 0.997). Three
findings, all from the diagnostic:

1. **Coherent deferral is strictly worse than per-frame spending.** Switching the
   bank to `inject_policy="every_frame"` (no coherent accumulation — `S` is reset
   each frame, degenerating to per-frame injection) *raises* iters=16 from 4.55 →
   14.46 J. The deferred `end_of_window` injection loses passive budget to the
   `λ_B` decay between deposit and the (later) spend; the reservoir spends each
   frame and stays ahead of the decay. **The cross-term gain (factor `R`) does not
   compensate for the budget lost by waiting.** Removing decay (`λ_B=1`) recovers
   more (every_frame → 19.65 J @16) but still trails the reservoir and stays
   capped at `fill≈0.05` (~1.1 J) at iters=4.

2. **A longer window makes it worse, not better.** Sweeping window ∈ {4,8,16,32}
   *decreases* injection at iters=16 (4.55 → 0.01 J): a longer accumulation defers
   the spend further, so more budget decays before it is used.

3. **`R_coherence ≈ 3.9 is flat across all iteration counts** (4/8/16/32). If
   low-iter AVBD were smearing one sharp impact, `R` would be large at iters=4 and
   ≈1 at iters=32. It is not — `R ≈` the window size at every iter count, i.e. the
   per-window coherence is an artifact of summing ~4 roughly-parallel samples, not
   a recoverable iteration-dependent smear. **The premise that a sharp impact is
   being smeared is not supported by the data.**

**Conclusion (spec §13/§18 — the honest outcome).** At iters=4 the injection
stays ~1 J no matter the policy, window, decay, or coherent summing. Low-iteration
AVBD produces a genuinely *softer* collision trajectory whose contact impulses —
even summed coherently over a window — carry intrinsically less vibration energy,
and there is no hidden coherence for banking to recover. Extraction from the
smeared solver output has reached its ceiling. The honest next step is the spec
**§14 sharp-impulse estimator**: reconstruct a sharp normal collision impulse
`Jₙ = −(1+e)·v_rel,n / Kₙ` from the *pre-impact* relative velocity and contact
effective mass, project it onto the modes, and still cap it by `η·E_loss`. That
synthesizes the impact the soft solve never resolved, rather than mining a trace
that does not contain it.

**Decision:** keep `use_coherent_impulse_bank=False` default. The bank is a
*refuted* ablation (like §9's `impulse_source`) — passivity-safe and retained for
the record, but it does **not** beat the reservoir. The reservoir + `delta_p`
remains the best extraction-based low-iter option. Tests:
`tests/avbd/test_coherent_impact_bank_passivity.py` (10 pass — cross-term
recovery, antiparallel rejection, passivity/depletion, expiry, η=0, flag-OFF
inert, global passivity, no-double-count; 96 avbd+stageE3+stageE4 green).
Honesty (foundation §14): we do **not** claim AVBD gives iteration-insensitive
modal excitation, nor that banking closes the gap — neither is true.

## 12. Energy-prescribed injection — the fix that works (implemented + tested)

§9-§11 all failed for the same reason: they derive the kick MAGNITUDE from the
contact impulse `s = Φ(x)ᵀJ`, which a soft low-iteration solve makes tiny, and
`passive_alpha` can only scale **down** (α∈[0,1]) — so the (iteration-insensitive)
`η·E_loss` budget sits unspent. The flaw is not the energy coupling; it is reading
the *magnitude* off the smeared impulse.

**Fix (option 1):** keep `s`'s **direction** (the spectral distribution from the
contact geometry — robust across iters, the normal barely moves) but set the
**magnitude** from the budget. `prescribed_alpha(s, q̇, E_target, α_max)`
(`dcr/modal/passive_inject.py`) returns the α ≥ 0 with `α·b + ½α²·a = E_target`,
scaling `s` **up or down** to deposit exactly `E_target = μ·(available budget)`.
Wired behind `injection_scaling="prescribed"` (default `"passive"` — bit-identical
fallback); pair with the impact reservoir so the budget is available every frame
(timing) and `prescribed_alpha` spends it (magnitude). One-line branch at the α
step in `process_step`, covering both the is_new and reservoir paths.

**Result (shelf, eta=0.5, E_rigid lost → E_modal injected, J):**

| iters | E_rigid lost | η·budget | is_new λ passive | reservoir δp passive | **reservoir δp PRESCRIBED** |
|------:|----:|----:|----:|----:|----:|
| 4  | 46.5 | 23.3 | 0.00 (fill 0.00) | 1.43 (0.06) | **23.8 (1.00)** |
| 8  | 44.7 | 22.4 | 5.79 (0.26) | 7.95 (0.35) | **22.8 (1.00)** |
| 16 | 45.2 | 22.6 | 12.55 (0.56) | 22.6 (1.00) | **22.7 (1.00)** |
| 32 | 45.3 | 22.6 | 13.59 (0.60) | 22.6 (1.00) | **22.6 (1.00)** |
| **CV** | | | **0.689** | **0.678** | **0.022** |

- **Iteration-insensitive:** CV(E_modal) across iters drops **0.69 → 0.022**;
  iters=4 rises **0 → 23.8 J** (full budget). The modal excitation at iters=4 now
  matches iters=32.
- **Still globally passive:** `fill = 1.000` at every iter count means it deposits
  exactly `η·E_loss` (the §15 bound) and never exceeds it. The realized ΔE is
  debited from the reservoir, which is bounded by `η·Σ E_loss`. Verified
  `cum_E_inj ≤ η·cum_E_loss` at iters ∈ {4,8,16}.
- **No noise amplification:** the `α_max` guard fired **0** times — the upscale was
  modest and finite (≈4× at iters=4, not unbounded), because `impulse_threshold`
  already rejects near-zero directions.
- Diagnostic: `scripts/_diag_prescribed_injection_iter_sensitivity.py`. Tests:
  `tests/avbd/test_prescribed_injection.py` (9 pass — prescribed_alpha hits the
  target / scales up where passive clamps / α_max clamp; scene passivity,
  iteration-insensitivity, η=0, passive-default-unchanged). 105 avbd+stageE3+E4 green.

**Honesty (foundation §14, the DEVIATION).** This uses the §15 inequality
`ΔE_modal ≤ η·E_rigid_loss` as a **target**, not a ceiling — it *synthesizes*
modal energy the literal contact impulse did not carry, re-sharpening the soft
low-iteration response. We do **not** claim this is the impulse's true modal
projection. The claim we *can* make: an **energy-bounded** modal excitation whose
magnitude is prescribed from the rigid energy loss and whose direction is the
contact-geometry mode mix — globally passive, iteration-insensitive, real-time.
This is the same "empirical, energy-budgeted" footing the spatial-attenuation /
patch channel already stands on (CLAUDE.md scope note).

**Decision / recommendation.** `injection_scaling="passive"` stays the default
(unchanged behavior, the strict §15 bound). For **low-iteration interactive use**,
enable `use_impact_reservoir=True, impulse_source="delta_p",
injection_scaling="prescribed"` — the timing fix (reservoir) + the magnitude fix
(prescribed) together give iteration-insensitive, passivity-safe modal coupling at
iters=4. `prescribed_mu ∈ (0,1]` dials the fraction of the budget spent (1.0 =
hit the η·E_loss bound; lower for a gentler response).
