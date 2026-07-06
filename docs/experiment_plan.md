# Validation plan — scenes × metrics × baselines

Companion to the paper (`paper` branch, `sections/40_results.tex`,
Tables 2–3) and to the prior-art map (`docs/novelty_positioning.md`). This is the
**buildable** version: every metric cell maps to a scene builder, a measurement
harness, a reference baseline, and an acceptance threshold, with the honest
current status. It is the plan behind "wire the generalization for all the scenes,
not just cargo, and get a FEM ground truth for each."

> **Scope discipline.** Claims live in `docs/novelty_positioning.md` §"Do / don't"
> and CLAUDE.md / foundation §14. Lead with the passivity bound + real-time-AL
> embedding; the two-way *mechanism* is Zheng–James's, not ours.

---

## 0. Where the evidence lives (three branches)

| branch | holds | relevant paths |
|---|---|---|
| `native-dynamic-constraint` (code, HERE) | solver, scenes, passivity clamp, unit tests | `dcr/avbd/_solver/passivity.py`, `scenes/reduced_*.py`, `tests/avbd_native/` |
| `benchmark` (a.k.a. `stageX3-ground-truth`) | the **X-suite** X0–X7: already-run experiments + CSVs + figures + per-stage docs | `benchmarks/paper_eval/x*/`, `docs/paper_eval/x*.md`, `AUDIT_BRIEF.md`, `STATUS.md` |
| `paper` (orphan, code-free worktree `DCR/paper`) | the LaTeX write-up | `sections/`, `main.tex` |

**Key consequence:** most metrics are *already measured* on a reference slab /
cargo / dinner scene by the X-suite — but on the `benchmark` branch, and for a
**subset** of the five paper scenes. "Generalize to all scenes" = port/extend the
X2 (vs-DCR falloff) and X3 (FEM-GT) harnesses from the single slab operator to
road / dinner / ledge / stack. That is the gap in §5, not a from-scratch build.

---

## 1. Positioning matrix (mirror of paper Table 1)

Six axes; only the (**Passive**, **RT-AL**) pair is unoccupied by any prior row.
Do **not** claim the two-way mechanism as novel.

| Work | DOF | 2-way | Modal | Passive | RT-AL | Net |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **This project** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Zheng & James 2011 | ✅ | ✅ | ✅ | ❌ damping | ❌ offline/audio | ✅ |
| DCR (Coevoet 2020) | ❌ sep. IIR | ❌ | ✅ | ❌ | ✅ | ❌ |
| Sheth et al. 2015 | ✅ | ✅ | ✅ | ❌ momentum | ❌ | ~ |
| ABD (Lan 2022) | ✅ | ✅ | ❌ affine | ❌ | ❌ | ✅ |
| FFRF / energy–mom. (Betsch 2007) | ✅ | ✅ | ✅ | ❌ conserves | ❌ | ✅ |
| Port-Hamiltonian FMB (Brugnoli 2021) | ✅ | ✅ | ✅ | ~ genre | ❌ | ❌ |
| XPBD / AVBD / VBD | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ |
| DyRT (James & Pai 2002) | ✅ | ❌ display | ✅ | ❌ | ✅ | ❌ |

---

## 2. Scenes

All are DCR's own figure layouts re-simulated with the two-way modal constraint,
plus two network stress scenes. `n_g/n_ℓ` = global/local reduced modes per body
(builder defaults). Body counts for dinner/ledge/shelf are the measured X5 sizes.

| scene | builder | bodies | n_g/n_ℓ | what it tests |
|---|---|--:|:--:|---|
| Road (crate/cones/lumber) | `scenes/reduced_truck.py` | TODO | 12/16 | distant response, large slab |
| Dinner table | `scenes/reduced_dinner_table.py` | 17 | 10/14 | distant place-settings (DCR Fig.1) |
| Ledge (boulder→pillars) | `scenes/reduced_ledge.py` | 5 | 12/16 | strong-coupling topple |
| Cargo network / stack | `scenes/reduced_cargo_network.py` | 6 | 8/1 | two-way, box–box network |
| Shelf | `scenes/reduced_shelf.py` | 6 | 10/14 | support + stacked-cube network |
| FEM cargo | `scenes/reduced_fem_rigid_cargo.py` | 2 | 8/1 | full-FEM accuracy reference |

The X-suite's own reference scene is a `10×6×2` corner-fixed **slab + bystander
row** (`benchmarks/paper_eval/x3_ground_truth/scene_and_gt.py::build_fem`),
E=1.1 GPa, ν=0.3, ρ=770 — this is what X2/X3 currently measure.

---

## 3. Validation matrix (scenes × metrics × baselines)

Each metric is scored against a **baseline** (§4) by an **X-stage harness** (§0).
Status: **done** = measured + in a committed CSV/figure; **ref-only** = done on
the X-suite reference scene, pending generalization to this column;
**pending** = not yet measured; **n/a**.

| metric | baseline | harness (branch `benchmark`) | Road | Dinner | Ledge | Stack | FEM | acceptance |
|---|---|---|:--:|:--:|:--:|:--:|:--:|---|
| Modal displ. field `u_y` L2 error | F full-FEM | `x3_ground_truth/` | pending | ref-only | pending | pending | **done** | native/GT mid-deflection → 1.0 as h→0 |
| Distant-response fidelity (falloff) | F, D | `x2_vs_dcr/run_x2.py` | pending | pending | pending | n/a | **done** | gentler-than-DCR falloff, no `C·r^-β` fit |
| Contact-force ledger | A analytic `mg` | `network/report_sheldon_contact_forces.py` | pending | n/a | pending | **done** 0.06–1.9% | n/a | per-joint `Σλ = (stack-above)·mg`, <2% |
| Passivity invariant `ΔE_m ≤ η ΔE_r` | the bound | `x1_passivity/run_robustness_clamp.py` | pending | ref-only | pending | **done** | pending | ON: 24/24 cells passive (currently met) |
| Passivity ablation (blow-up) | clamp off/on | `x1_passivity/run_blowup_figure.py` | n/a | n/a | n/a | **done** 119,534× | n/a | OFF injects, ON passive, inert @ high budget |
| Two-way ring `|a|` | network off/on | `x1_network/run_network_clamp.py` | pending | pending | pending | **done** 1.1e-5/0 | n/a | `|a|`>0 on / ≡0 off (freeze-q̇ counterfactual) |
| Momentum drift (lin/ang) | 0 | **new probe** | pending | pending | pending | pending | pending | drift < solver tol over the run |
| Restitution–energy consistency | D | `x7_*/` | n/a | done | n/a | done | n/a | native ratio ≤ 1 ∀ε_r (DCR → 2.6×) |
| Runtime (ms/step, RT×) | R, D | `x5_perf/run_perf.py` | pending | **done** 58 ms | **done** 29 ms | pending | pending | see §6 real-time caveat |

Measured X-suite headline numbers (reference scene, `benchmark`):
- **Passivity (X1):** OFF injects in 12/24 budget×relax×scene cells, up to
  **119,534×**; **ON: 24/24 passive**, 0 clamps in the safe region.
- **Two-way vs DCR (X2):** peak distant-object KE (mJ) at 0.14/0.28/0.42/0.56 m —
  DCR 13.6/6.1/0.9/0.9 (steep, near-field); **native 9.8/4.9/3.2/2.0 (2.3× DCR at
  the far object)**; curves cross. Native falloff is the slab's low-mode
  **standing wave**, reached with **no `C·r^-β` fitting** — the Claim-2 evidence.
- **FEM-GT (X3):** native/GT mid-span deflection **0.56 → 0.75 → 0.89 → 1.02** as
  h = 1/120 → 1/960; ring freq **81.0 vs 80.7 Hz (0.4%)**.
- **Perf (X5):** clamp overhead **+1–2 ms (2–5%)**; AVBD 1.3–2.8× XPBD; dinner/avbd
  58 ms, ledge/avbd 29 ms — **not** real-time at 120 Hz on the CPU-host symplectic
  path (see §6).
- **Restitution (X7):** paper-DCR energy ratio → **2.6×** as ε_r→1 (double-counts);
  native **≤ 1 ∀ε_r**.

---

## 4. Baselines (the reference axis)

| key | baseline | how to produce |
|---|---|---|
| **F** | full-FEM (unreduced) ground truth | `CoupledFEMRigidSim` on the same `FEMModel` (`x3_ground_truth/scene_and_gt.py`). Score the **deflection field `u_y(x,t)`**, not launch KE (§6). Consider an IPC-grade contact reference for stiff contact. |
| **D** | DCR one-way | `DCRWorld` + `ModalDCRCoupler` (Eq. 10 forced-IIR + post-solve `Δv=d_max/h`) + `ConstraintSolver` (`x2_vs_dcr/run_x2.py`, arm `paper-DCR`). |
| **R** | rigid-only | `DCRWorld(dcr_enabled=False)` / modes-off — the two-way null and cost floor. |
| **A** | analytic static | closed form `Σλ = mg` per joint; the settled contact ledger. |
| off/on | internal toggles | passivity clamp `solver._enforce_modal_passivity`; modal network `network=` — the two claims that are ours alone; keep everything else fixed (PAPER_CONFIG: relax 0.7, 16×4, symplectic, h=1/120). |

---

## 5. The generalization gap — the actual work, prioritized

**G1 — FEM ground truth for every scene (highest; Claim 5).**
Extend the X3 pattern (`fem_modal_support.py` + `scene_and_gt.py`) from the slab to
dinner / ledge / road. Each needs: (a) one shared `FEMModel` for the deformable
support, (b) a native arm whose modal basis IS that operator's eigenmodes
(`Mq=I`, `Kq=diag(ω²)`), (c) a `CoupledFEMRigidSim` GT arm. `dinner_scene_gt.py`
already exists as the template. **Acceptance:** native/GT mid-deflection → 1.0 as
h→0, per scene. Report a per-scene convergence table like X3-B.

**G2 — distant-response falloff for every scene (Claim 2 across scenes).**
Generalize `x2_vs_dcr/run_x2.py` (three arms, response-vs-distance) to dinner
place-settings / ledge pillars / road cones. This is the honest test of "constraints
handle distance automatically": show the native falloff matches the FEM standing
wave with **no `C·r^-β` fit**, on each scene, and contrast DCR's steeper forced-IIR
decay. **Acceptance:** native falloff tracks GT within tolerance and beats DCR at
distance, per scene — *or* soften the "no attenuation path" claim to the regimes it
holds.

**G3 — real-time reconciliation (Claim 4; the biggest reviewer risk).**
X5 shows the **symplectic CPU-host** paper config is **not** real-time (6–35
steps/s). Real-time lives on the **non-symplectic device / warp-CPU** path
(0.9–2.4 ms/step, `docs/avbd_native/native_dual_solver.md`) — a *different* path
from the one X1/X3 validate. A reviewer will ask "are the passivity-validated path
and the real-time path the same method?" **Do one of:** (a) demonstrate the
passivity clamp + two-way coupling *on the device path* (needs CUDA — this is
exactly deferred Step 3 in `docs/avbd_native/passivity_cap_cost.md`); or (b) soften
"real-time" → "real-time-capable, validated on the correctness path." Until CUDA,
(b) is the honest wording.

**G4 — momentum-drift row (new, cheap).**
Add a linear/angular-momentum probe (Σ m v, Σ (I ω + x×mv)) logged per step across
all scenes — a standard conservation check reviewers expect. No solver change; a
read-only probe like the sheldon report.

**G5 — finish X4 / X6 across scenes (lower priority).**
X4 impulse-train equivalence replay (needs per-substep support-impulse logging);
X6 long-horizon passivity beyond the reference scene (currently holds ring 5,292×
below the un-clamped blow-up).

---

## 6. Honest caveats to bake into the paper (already discovered)

1. **GT signal = deflection field, not launch KE.** A bystander on a stiff penalty
   spring is a ~2 kHz oscillator the GT contact resolves poorly; its launch KE does
   NOT converge under GT refinement, but the modal **deflection field `u_y`** is
   rock-stable. Score `u_y`; report launch KE only as a contact-model-limited
   secondary. (X3.)
2. **Native falloff is the standing-wave modal profile, no fit.** The Claim-2
   strength (X2) — but it is the slab's *low modes*; confirm per scene in G2 before
   claiming generality. The paper's Limitations already keep the spatial-attenuation
   path as empirical / not energy-budgeted — do not silently upgrade that until G2.
3. **Real-time claim rests on the device path (G3).** State the split explicitly.
4. **Clamp is active on XPBD, monitor-only on AVBD** (AVBD empirically passive at
   PAPER_CONFIG). This is the descent-class vs stationarity-class dichotomy — see
   the passivity-generalization framing; frame the clamp as the safeguard the
   stationarity-class (XPBD) needs and the descent-class (AVBD) inherits for free.

---

## 7. Priority order for a submission

- **MIG (realistic):** G1 (FEM-GT across ≥3 scenes) + G2 (falloff across scenes) +
  G4 (momentum) + G3(b) honest real-time wording. The X-suite already supplies
  X1/X2/X3/X5/X7 on the reference scene; generalization + honest framing is the bar.
- **CGF/SCA (reach):** the above **plus** G3(a) — passivity + two-way demonstrated
  on the real-time device path — **plus** a deeper passivity treatment (the bound as
  the safeguarded-iteration member, §novelty_positioning) and an IPC-grade contact
  reference. Gating factor is validation depth + the real-time reconciliation, not
  the method.

## Reproduce (X-suite, on the `benchmark` branch)

```
git switch benchmark
python -m benchmarks.paper_eval.x1_passivity.run_blowup_figure     # passivity ablation
python -m benchmarks.paper_eval.x2_vs_dcr.run_x2                    # vs-DCR falloff
python -m benchmarks.paper_eval.x3_ground_truth.run_x3             # FEM-GT convergence
python -m benchmarks.paper_eval.x5_perf.run_perf                   # runtime
# docs: docs/paper_eval/{STATUS,AUDIT_BRIEF,x0..x7}.md
```
