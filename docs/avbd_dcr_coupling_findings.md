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
