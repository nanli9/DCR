# Publication Plan — "Modal Contact as a Native Dynamic Constraint"

> Planning document only (2026-07-04). No code changes prescribed until the PI signs off
> on scope + venue. Companion to `prompts/paper_experiments_execution_plan.md` (X0–X7)
> and `prompts/modal_contact_network_implementation_prompt.md` (N0–N6); this file sits
> ABOVE both: it says what a *submittable paper* still needs, in priority order.

---

## 1. Where the project stands (evidence inventory)

**The method (branch `native-dynamic-constraint`, HEAD 0e39d58).** Modal coordinates are
first-class solver DOFs co-solved with rigid state in one incremental-potential step, in
two independent solvers (AVBD `Solver6DOF`, XPBD `SolverXPBD`; coupler deleted). One
unilateral contact row spans every pairing:

```
C = C_rigid + (Ĝ_A·a_A − Ĝ_B·a_B),   Ĝ_X = n̂ᵀ R_X Φ_X
```

support row and box-box row are the two special cases of the same gap; the shared
multiplier gives two-way momentum consistency by construction. Shipped solve is the
engaged-gated block-GS (cross-term Schur implemented and *rejected*, documented).
Extras: enforced §15 passivity clamp (X1), GPU-resident support q-block (fp64 parity),
modal contact network N2 (stacks ring through box-box; AVBD host-only), rigid-ride
(N3-partial). 602 tests collect; OFF-paths bit-identical.

**Evidence already in hand (strong):**

| Claim | Evidence | Where |
|---|---|---|
| C2 passivity enforced | OFF injects up to 119,534×; ON 24/24 passive; long-horizon 5,292× lower; ≤1 ∀ε_r (vs paper-DCR → 2.65×) | X1/X6/X7, `benchmark` branch |
| C3 two-way correctness | full-FEM convergence: amplitude 0.56→1.02× as h→0, ring freq 0.4%, falloff = standing wave (no r^-β) | X3 |
| C1 head-to-head | response-vs-distance: native 2.3× DCR at the far object; curves cross (honest) | X2 (core) |
| Motivation | paper's forced-IIR violates the §15 bound 1.6–3.4× (up to 14 kJ); governed path ≤ budget to FP noise (106 runs) | B1–B7, `legacy/benchmark-suite` + local `benchmark/runs` |
| Physical accuracy | ring freq vs Euler-Bernoulli AND independent 3D FEM (1–9%); f ∝ √(E/ρ); 90-config robustness matrix (safe envelope: relax 0.7, ≥16×4) | `benchmarks/material_sweeps/` (working tree) |
| Network (new) | force ledger: every stack joint = weight above to ~1–2%; ring cascade base→mid→upper (0.58/0.73 attenuation); ON/OFF discriminator exact; freeze counterfactual 0.64×; ride cuts box-box force chatter 4.4–6.9×, stack stands at μ=0.4 | §N2 figures, `benchmark` branch `docs/network/` |
| Determinism/repro | pinned PAPER_CONFIG, bit-identical repeats, per-figure `.config.json` manifests | X0 |

**What does not exist yet:** any LaTeX, any MP4 (GIF-only; no ffmpeg dep), a related-work
survey (4 PDFs on hand), CI, a single branch containing method + evidence, N3's
go/no-go robustness gate for the network, N4–N6, and the X-suite gaps its own audit
scopes (X2 MP4s/drift, X4 impulse replay, X5 k/N/CUDA sweeps, X6 breadth scenes).

---

## 2. The paper story (recommendation — needs PI sign-off)

**One paper, three claims plus one capability:**

1. **C1 — Reformulation.** DCR's modal response becomes a *native dynamic constraint*:
   reduced coordinates are solver DOFs; one unilateral gap couples rigid↔modal and
   modal↔modal (body↔body) with a shared multiplier. Subsumes the paper's one-way
   IIR + kick pipeline; deletes its per-scene tuning (C/β/mode gains → relax + budget).
2. **C2 — Passive by construction + enforced bound.** Backward-Euler on the single
   incremental potential dissipates; on top, the §15 clamp gives a *per-step enforced*
   `ΔE_modal ≤ η·ΔE_rigid_loss` (the paper's Eq. 10 violates it; restitution
   double-counting eliminated).
3. **C3 — Two-way and correct.** Shared multiplier ⇒ momentum-consistent back-reaction;
   converges to full-FEM ground truth in amplitude/frequency/spatial profile.
4. **Capability demo — the modal contact network.** Stacks *ring through* box-box
   contacts and *ride* the ring with smoothed contact forces — structurally impossible
   in the original DCR (its response is per-object, post-solve). This is the teaser.

**Positioning sentence** (the novelty defense — see §6 risk 1): the physics is classical
floating-frame/CMS flexible multibody; the contribution is realizing it as *compliant
unilateral constraints inside real-time position-based / augmented-Lagrangian rigid
solvers* (AVBD + XPBD, GPU-resident), with an enforced contact-energy passivity bound
and a validated equivalence to the DCR effect it replaces. Nearest neighbors to
differentiate: ABD/affine bodies (12-DOF affine vs modal elastic basis, no passivity
bound), CMS/component-mode multibody (bilateral, not game-solver-native), SCA'23
unified contact/shock-propagation (rigid-only), bounce maps / prescribed responses
(one-way, not energy-bounded).

**§14 wording discipline (binding):** claim "the modal injection step is energy-bounded
and passive" — never "the full solver is unconditionally stable"; whole-scene passivity
is NOT claimed while the host box-box stack issue stands; no h-invariance claim
(reduced sensitivity only); no audio claims (E6 stays out).

**Explicitly rejected alternative:** splitting into two papers (coupler+§15 short paper
now, native constraint later) self-scoops the passivity bound — the strongest single
result — and the B-suite baseline (`coevoet` arm) is itself the motivation for the
native paper. Keep one paper; the legacy-coupler §15 governor gets one sentence.

---

## 3. Work plan

Priorities: **P0** = blocks everything; **P1** = blocks submission (claim-critical);
**P2** = blocks a *good* submission (presentation); **P3** = strongly recommended.
Effort in focused days (single person + assistant).

### P0 — Consolidate the artifact (~1 week)

| # | Item | Detail | Accept | Effort |
|---|---|---|---|---|
| P0.1 | **One paper branch** | Merge `native-dynamic-constraint` + `benchmark`; recover the B-suite code/report/plots from `origin/legacy/benchmark-suite` (`scripts/benchmark/run_b*.py`, `dcr/benchmark/*`, `benchmark/RESULTS.md`, `benchmark/plots/B*/`); commit or tar-track the local raw `benchmark/runs+logs` so data is never divorced from generators again | one branch; every figure regenerates from its manifest at one SHA | 2–3 d |
| P0.2 | **Re-baseline X at HEAD** | X0–X7 numbers predate the (z,Q) box-box generalization. Re-run X0 + X1 (spot-check X3) at merged HEAD with network OFF; OFF-neutrality tests say bit-identical — verify and record | X tables reproduced at HEAD SHA | 1 d |
| P0.3 | **Hygiene** | Fix stale counts (README "141"/CONTRIBUTIONS "52" vs actual 108 avbd + 146 avbd_native); apply the B5 material-claim retraction to CONTRIBUTIONS.md; prune/complete dead stubs (tests/stageE5 empty, E6 unbuilt, stageDCR_projection orphaned pyc); add GitHub Actions pytest CI | docs match `pytest --collect-only`; CI green | 1 d |
| P0.4 | **Truck-lumber decision** | `test_truck_lumber_stack_rides_ring_and_holds` topples 180° (pre-existing, host box-box scene params). A stacks paper with a failing stack test is a reviewer landmine: fix params, or drop the scene, or move to documented-limitations. Decide, don't leave ambient | no unexplained red test on the paper branch | 0.5–2 d |

### P1 — Close the claim-critical evidence gaps (~3–4 weeks)

| # | Item | Detail | Accept | Effort |
|---|---|---|---|---|
| P1.1 | **N3 gate: passivity over augmented Q** | The clamp currently covers the non-cargo host q-block only. Extend the §15 clamp/monitor across `Q = [q_support; a_b0; …]` (network path) and run the X1-style robustness matrix on the network scene. This is the go/no-go your own N-plan defines for shipping the network in the paper | matrix all-passive with clamp ON; `docs/network/n3.md` written | 3–5 d |
| P1.2 | **Network ground truth (small)** | X3 covers support-only. Add a minimal 2-cube (or cube-on-slab-on-cube) FEM GT arm reusing `fem_modal_support.py` machinery: does the *transferred* ring match a full-FEM contact sim in amplitude/frequency as h→0? Even a 1D-vertical GT (X3-style honesty) answers "is the cascade physical?" | convergence plot for one box-box joint | 4–7 d |
| P1.3 | **X2 finish** | Side-by-side MP4s; dedicated N-drop drift trace; *stretch:* one solver-controlled arm (paper-DCR kick injected into the same native contact solver) to blunt "method-level comparison" criticism | X2 doc closes its own "remaining" list | 2–3 d (+3–4 stretch) |
| P1.4 | **X5 finish** | Mode-count k-sweep, body-count N-sweep (shares rockfall scene with P1.6), CPU↔CUDA crossover point. **Resource dependency: needs a CUDA box** — schedule around GPU access | one unified perf table: CPU-host symplectic vs device path (0.9–2.4 ms/step) with honest real-time statement | 1–2 d CPU + GPU session |
| P1.5 | **X4 close-or-descope** | Either do the impulse-train equivalence replay (needs per-substep support-impulse logging hook) or descope the solver-generality claim to exactly what X4 shows (divergence = transfer, not generation) | claim text matches evidence | 2–3 d or 0 d |
| P1.6 | **Breadth scenes** | Original paper shows 7 scenes; we have ~4 + network. Add 2–3: friction-mediated distant slide, scaffold two-level, rockfall N=50–100 (doubles as N-sweep), plus **N4 tower-on-slab** (full slab⇄base⇄stack loop — completes the network story) | each: scene + MP4 + one metric + manifest | 5–8 d |
| P1.7 | **Restitution knob (decide)** | Native XPBD contact is hardcoded e=0. Option A: implement Newton restitution (real solver change + parity tests) so X7's native arm is *measured*, not clamp-guaranteed. Option B: keep e=0, present clamp guarantee ∀ε_r and list e=0 as limitation. Recommend B for EG timeline, A for SCA | decision recorded; if A: X7 re-run | 0 d or 3–4 d |

### P2 — Presentation assets (~1.5–2 weeks, overlaps P1)

| # | Item | Detail | Effort |
|---|---|---|---|
| P2.1 | **Video pipeline** | Add ffmpeg or imageio-ffmpeg (justify in writing — first new dep; GIFs don't cut it for a graphics venue). Batch headless viser capture exists (x3 dinner glTF proves it) | 1–2 d |
| P2.2 | **Supplementary video** | **OWNED BY USER** — modeled on the original DCR SCA2020 video (side-by-side rigid-only vs modal response across the scene suite, plus the new stacked-cube network teaser ON/OFF). My side reduces to: keep the headless-capture harness working (P2.1) and hand over regenerated scene renders + the ledger/ride/contact-force clips. Do NOT plan a from-scratch video edit here | (user) |
| P2.3 | **Figure set (8–10)** | (1) teaser render; (2) method/constraint-row schematic (redraw from `two_band_coupling.html` cards); (3) X3 convergence + falloff + field overlay; (4) X1 robustness + X6 long-horizon; (5) X7 restitution; (6) X2 response-vs-distance; (7) N2 force ledger + cascade; (8) ride chatter; (9) perf table; (10) 90-config matrix (supp.). **Contact-force ledger + per-corner + ABD figures already generated** (`docs/sheldon_report/`, 2026-07-04). All regenerated at the pinned config with one matplotlib style | 2–3 d |

### P3 — Writing (~3–4 weeks calendar, starts immediately in parallel)

| # | Item | Detail | Effort |
|---|---|---|---|
| P3.1 | **Skeleton now** | LaTeX (acmart for MIG/I3D/SCA-PACMCGIT; EG `cgf` class for EG/CGF). Port structure from `two_band_coupling.html` (method) + `AUDIT_BRIEF.md` (results skeleton + limitations). The proposal doc is *pre-monolithic* — use for framing history only, not method | 1–2 d |
| P3.2 | **Related work** | ~35–50 refs across: DCR + follow-ups; modal sound synthesis (van den Doel/Pai, O'Brien, James/Zheng — cited, not competed with); reduced deformables & deformed normals (Barbič–James 2008 on hand); CMS / floating-frame multibody (Craig–Bampton, Shabana); PBD→XPBD→VBD→AVBD lineage; ABD/IPC affine bodies; compliant/soft constraints (Servin, Tournier, Andrews); shock propagation (SCA'23 Chen–Ly–Wojtan on hand; Guendelman; Erleben); multirate/two-band coupling. Write the positioning table early — it IS the novelty defense | 3–5 d |
| P3.3 | **Claims audit** | Every claim sentence checked against foundation §13/§14 + AUDIT_BRIEF limitations. The honest-limitations section is a *feature* — budget half a page for it | 1 d |
| P3.4 | **Drafts** | Full draft → PI pass → revision ×2. PI is a DCR co-author: exploit for the "vs DCR" fairness framing and for what SCA/EG reviewers will poke | 2–3 wk calendar |

### P4 — Submission mechanics (~2–3 days)

Reproducibility package: tagged release, `regenerate_all.sh` walking every manifest,
README with one-command repro per figure, anonymized repo (or zip) per venue policy;
supplementary PDF with the 90-config matrix + B-suite tables; arXiv preprint once the
PI approves (all candidate venues allow it).

---

## 4. Venue ladder + timeline (today = 2026-07-04)

| Venue | Deadline | Gap | Fit | Verdict |
|---|---|---|---|---|
| **MIG 2026** (Charleston, Dec 11–13) | **Aug 7, 2026** (verified; window opens Jul 25) | 5 wk | very good (animation/games, stacking, interactive) | Only with hard scope cut: P0 + P1.1 + video + writing; drop P1.2/1.3-stretch/1.4-GPU/1.5/1.7-A. Writing quality is the casualty. Attempt only if PI explicitly wants fast + scoped |
| **Eurographics 2027 full papers → CGF** | ~early Oct 2026 (*verify when CFP posts*) | ~13 wk | strong; CGF = the original DCR journal (nice symmetry) | **Primary recommendation.** Fits P0–P3 minus P1.7-A/N5. Go/no-go checkpoint Sept 1 |
| **I3D 2027** | ~Nov–Dec 2026 (*verify*) | ~5 mo | good (interactive 3D, perf story wants the CUDA numbers) | Fallback #1 if EG slips; the extra 6–8 wk absorbs P1.4 GPU work + P1.7-A |
| **SCA 2027** | ~mid-Apr 2027 (SCA 2026 was Apr 17) | ~9 mo | the home community; PACMCGIT | Fallback #2 / the "everything done" target incl. N5 XPBD network port + N6 demos |
| CGF direct / C&G | rolling | — | — | Safety net |

Decision points: **Jul 11** — PI decides story scope + MIG yes/no. **Sept 1** — EG
go/no-go on evidence completeness. If MIG is attempted and rejected (notif late Sept),
the EG window has closed → I3D becomes primary.

---

## 5. Reviewer-objection map (pre-empt in text + experiments)

| # | Objection | Pre-emption |
|---|---|---|
| 1 | "Classical flexible multibody/CMS — what's new?" | Positioning table (P3.2); contributions = solver-native unilateral formulation + enforced passivity bound + DCR equivalence + network; never claim the physics is new |
| 2 | "relax 0.1 default suppresses the ring; you evaluate at 0.7" | One pinned PAPER_CONFIG everywhere (X0); present relax honestly as an accuracy/stability knob with the 90-config safe envelope |
| 3 | "DCR comparison unfair (own timestep/contact per arm)" | P1.3 stretch arm; else scope the claim to falloff *shape* + capability table (current X2 framing) |
| 4 | "Amplitude only 0.56× of FEM at practical h" | Convergence story (→1.02×), frequency/shape/falloff correct at every h; frame as temporal resolution of sub-ms impacts, future work: impact-window substepping |
| 5 | "Not real-time" | Honest split table (P1.4): CPU-host symplectic reference vs 0.9–2.4 ms/step device path; CUDA crossover plot |
| 6 | "XPBD e=0" | P1.7 decision; clamp guarantees bound ∀ε_r regardless (X7) |
| 7 | "Frictionless offset stacks tunnel with ride on" | Documented gate + friction-held envelope (μ≥…); ride default-off outside it; show the failure in the video's honesty section |
| 8 | "Whole-scene passivity unproven" | §14-compliant wording: bound claimed on the modal path; P1.1 extends coverage over Q |
| 9 | "Cherry-picked scenes/configs" | Manifests + determinism (X0), robustness matrices with DEAD/BLOWUP cells shown, B-suite 106/106 runs reported incl. the weakened B5 material claim |
| 10 | "Ring transfer through stacks might be numerical" | ON/OFF bit-identical discriminator + freeze counterfactual + force ledger ≈ static weights + P1.2 GT |

---

## 6. Open decisions for the PI (blocking, in order)

1. Venue/timeline: MIG sprint vs EG 2027 primary (recommended) vs SCA 2027.
2. Scope of network claims: modal↔modal transfer only, or including rigid-ride
   (honest-partial) — recommend both, ride labeled as bounded flex-scale effect.
3. XPBD network port (N5): in-paper or "AVBD-only, XPBD future work" (recommend the
   latter for EG; XPBD already carries the core (z,q) support path, so C1's two-solver
   claim stands without it).
4. P1.7 restitution: measured (A) vs clamp-guaranteed (B).
5. GPU story: device-path numbers in main paper vs supplementary (needs CUDA access —
   when?).
6. Authorship + whether to loop in the other original DCR authors.

## 7. ABD decision (resolved 2026-07-04 — for the PI's "would ABD help?" question)

Evidence in `docs/sheldon_report/` (contact-force + ring analysis, `report_sheldon_contact_forces.py`):
ABD is **already a drop-in cargo material** (`kind="abd"`, co-rotated affine 9-DOF
`F`; corner Jacobian `B_c` substitutes for the modal `Φ_c`) and couples two-way
through the **identical** box-box network. The settled contact-force ledger is
basis-independent (rigid / modal / affine all hit the m·g multiples). So ABD does
NOT change the coupling story — it is an alternative reduced basis for the cargo's
own deformation. **Recommendation:** keep the modal `Φ` basis as the headline (it is
the DCR object, captures bending/ring modes the affine subspace cannot, and is the
one with the passivity bound); mention ABD as a supported, interchangeable cargo
basis + future work (its affine flex showed slow secular growth in the stack demo —
would need the same §15 governor before any stability claim). Not a paper blocker.
