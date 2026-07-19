# Literature Gap Audit Findings

## 2026-07-18 MIG Short-Paper Panel Review

- Review artifact: `paper/main_short.pdf`.
- The review will use only evidence visible in that PDF; existing regular-paper and novelty-audit notes are background checks, not evidence credited to the submission.
- Artifact metadata: 4 pages, letter size, generated 2026-07-18 19:37 PDT; title is “How Much Energy Does a Modal Contact Row Inject? A Cross-Formulation Measurement and a Cumulative Storage Bound.”
- The abstract claims a matched 24-cell sweep across XPBD, AVBD, and implicit sequential impulse; worst modal/incident-energy ratios of about 1.2e5, 1.7, and <=1; a cumulative rigid-loss-funded modal-storage bound holding in 72 cells; and enforcement side effects up to 21.6 mm penetration and 8.7x corrective impulse.
- The framing is unusually explicit that the shared rigid/modal row and the general finite-iteration energy-injection observation are prior art. Claimed novelty is the quantitative cross-formulation measurement, the specific cumulative source-referenced storage bound, and explicit measurement of post-projection contact cost.
- The PDF openly limits the method to normal rows, e=0 for the position-level version, modal-storage energy only, CPU float64 enforcement, and one-machine/three-scene/one-contact-regime evidence; the device path monitors but does not enforce the governor.
- Visual pass, pp. 1–2: typesetting is clean and professional but extremely dense for four pages. Figure 1 is readable and immediately motivates the pathology, while the paper devotes substantial scarce space to defensive novelty framing.
- Equation (2) bounds net modal storage increase by cumulative positive rigid kinetic-energy loss, not the actual cumulative contact-port work into the modal subsystem. The paper needs a more operational definition of `Delta E_rig`, including translational/rotational terms, which bodies/rows are included, and how unrelated rigid damping, rigid-rigid collisions, or integrator loss are excluded; otherwise “contact has actually dissipated” and “source-referenced” may overstate what the ledger identifies.
- The PDF does not yet state the experimental value(s) of eta near the invariant/enforcement description. Because eta sets the permissible storage directly, omitting its value and sensitivity is a reproducibility and interpretation risk.
- The projection `(q,qdot) <- gamma(q,qdot)` is transparent and exactly enforces the scalar storage inequality, but it is an after-solve global modal-state scaling rather than a contact-consistent correction. The paper correctly admits that it moves the contact surface and quantifies the resulting gap/impulse costs.
- Central interpretation risk: the paper demonstrates a severe failure of a particular fixed-budget transcription/configuration and also shows convergence or the implicit realization removes it. Acceptance therefore depends on convincing reviewers that the tested XPBD/AVBD rows are representative, matched fairly, and cannot be repaired more locally/cheaply than by the proposed global clamp.
- Visual pass, pp. 3–4: Figures 2–3 are legible and information-dense, and Table 1 directly reports an uncomfortable tradeoff instead of hiding it. Page 4 has substantial unused space while pages 1–3 are crowded; layout could be rebalanced and a small scene/method schematic added, which would help a visual-computing audience understand what the shelf/ledge/table setups actually are.
- Figure 2's nominal “budget” changes both iterations and substeps (`4x1` through `32x8`), so it simultaneously changes iteration convergence, time discretization, and total work. Counts are also not automatically comparable across XPBD, AVBD, and impulse. The isolated K sweep in Figure 3 helps, but only for one shelf case.
- The text labels modal-energy/incident-impactor-KE ratio 1 as an “injection threshold” while also admitting that the ratio is not the enforced invariant. Without explicit initial energy and all external/internal sources, `peak E_mod / peak incident KE > 1` is not by itself a proof of numerical energy injection. The repeated “injects in N/24 cells” language therefore needs either a direct discrete energy-balance measurement or more careful terminology.
- Figure 3 compares XPBD against an impulse `K=500` reference, not clearly against converged XPBD. Near-agreement of one scalar ratio does not by itself establish that the XPBD amplification is solely a truncation artifact rather than a formulation/configuration interaction. A same-formulation convergence endpoint and state/contact-error comparison would make the claim much stronger.
- The cumulative sum of positive rigid-energy losses can double-count energy that cycles rigid -> modal -> rigid -> modal, and it never subtracts rigid gains. This supports a monotone storage ceiling but not a full passivity/energy-conservation guarantee; the paper should state this distinction prominently and avoid allowing the passivity keyword/prior-work discussion to imply more.
- The strongest evidence is diagnostic rather than visual/behavioral: no scene image, deformation sequence, or governed-vs-converged trajectory appears. For MIG, reviewers may want at least one compact qualitative panel or linked supplemental video showing whether the bounded result remains perceptually useful despite 21.6 mm penetration and large corrective impulses.
- Official MIG framing (2026 homepage plus current submission materials): short papers may use 4–6 content pages excluding references, and review emphasizes technical quality, novelty, significance, and clarity. The supplied PDF uses only four pages total including references, so it is not space-forced to leave the ledger definition, eta, solver matching, and qualitative evidence this compressed.
- The 2026 official homepage places the work squarely in scope (interactive systems/animation), but scope fit will not compensate for the technical distinction between a storage cap and a passivity guarantee.
- Independent novelty/fit lens: borderline/weak reject (3/5, confidence 4/5). It praised focus, candor, the memorable cross-formulation diagnostic, and explicit measurement of correction side effects, while flagging insufficient positioning against passivity observers/energy tanks/energy projection, non-local source accounting, conflated budgets, duplicate implicit cells, lack of a useful governed visual regime, and no device-side enforcement.
- Independent evaluation/presentation lens: weak reject (2/5, confidence 4/5). Its dominant concern is that the PDF omits enough solver/scene/ledger parameters that formulation-level attribution and reproduction are not possible; it also calls the guarantee experiment partly tautological and asks for physical/contact accuracy across all hosts rather than only selected XPBD cells.
- Concrete factual inconsistency: §3.1/Figure 2 report the implicit realization's worst ratio as 0.53, but the conclusion calls the three worst-case ratios `1.2e5, 1.7, and 1.0`. If these are all the same diagnostic, 1.0 is incorrect; if 1.0 means the threshold/bound, the sentence mislabels it as measured worst case.
- Cross-formulation interpretation needs cellwise care: on the two table 4x1 cells where AVBD exceeds 1 (1.18, 1.70), XPBD is actually below 1 (0.13, 0.37). The prose statement that AVBD is “three orders of magnitude better behaved than the position-based host at the same budget” is not true for the matched table cells and is unclear even as a global-worst comparison (the displayed worsts differ by nearly five orders). Report paired differences/win counts instead of comparing unrelated extrema.
- Enforcement-cost evidence is selective: Table 1 covers only XPBD on shelf/ledge at 4x1 and 8x2, omitting AVBD's table cells where enforcement is actually needed. It reports absolute penetration without support thickness/object scale and no governed full-FEM comparison.
- Timing text is not decision-grade: no base runtime or relative overhead is given for the 0.8–2.9 ms ledger cost, and the only device-path timing is for monitor-only operation. The opening “Apple M4, CPU only” statement also leaves “device-resident path” undefined, and a fourth `truck` scene appears only in timing.
- The method's global scaling erases quasi-static sag as well as spurious dynamic energy. Because gravity work is excluded from supply, a load-bearing modal equilibrium can be treated as unfunded; scaling deviations around a reference equilibrium or a contact-consistent projection would be more physically defensible than scaling `(q,qdot)` about zero.
- Independent technical lens: weak reject (2/5, confidence 4/5). It treats the diagnostic/invariant mismatch as the core defect: the abstract and results infer supply-bound violations from the incident-KE ratio even though §3.1 says that ratio is not the invariant. It also classifies Eq. (2) as a gross-loss cap rather than a proven physical supply/passivity law and requests same-formulation convergence, actual ledger traces, and complete solver definitions.
- Panel convergence is strong: all three independent lenses praise the relevance, compact visuals, striking diagnostic, and exceptional candor; all three identify the same acceptance risks—metric mismatch, ambiguous energy attribution, unmatched solver comparison, construction-tautological enforcement, and unproven usefulness at tolerable contact error.
- Independent practitioner lens: 3/5 borderline/weak accept, confidence 4/5. Its accept case is the severity and practical relevance of the failure, simplicity/inertness of the guard, and unusually candid reporting. Its blockers are lack of enforced device timing, unmatched claimed-vs-tested production budgets, and a storage-envelope guarantee that can reuse historical credit rather than bound cumulative transfer.
- Primary generalist/meta-review calibration: 3/5 borderline, confidence 4/5. Under a short-paper bar, the diagnostic result could be publishable, but the current abstract/results/conclusion overinterpret the plotted ratio and make the central claim unauditable. Panel scores are 2, 3, 2, 3, 3 (mean 2.6, median 3): borderline with a weak-reject lean in the submitted state.
- Highest-impact revision order: (1) make the diagnostic ratio and Eq. (2) ledger distinct everywhere and plot both; (2) rigorously define/rename the gross-loss ledger, eta, gamma, initial-state handling, and energy-source scope; (3) add matched solver definitions plus same-formulation convergence and separate iteration/timestep/equal-time comparisons; (4) demonstrate a governed regime that is physically/visually useful, including AVBD/table costs and governed FEM/contact error; (5) strengthen energy-control prior art and device/enforcement timing; (6) fix factual/presentation inconsistencies.


## 2026-07-18 Velocity-Impulse Native-Modal Check

- Current branch commit `462b717` is titled `impulse: native dynamic modal constraint on the velocity-impulse solver (paper Eq. 2/3)` and adds/updates `solver_impulse.py`, `impulse_native_constraint.md`, and dedicated tests.
- The backend is a velocity-level Schur-complement BLCP solved by PGS, derived from the project's earlier rigid contact solver. It is neither XPBD nor AVBD, although it implements the same deformed-gap/shared-multiplier modal contact row.
- The support row augments the rigid Delassus operator with `G W_eff G^T`, where `W_eff=(M_q+hD_q+h^2K_q)^-1`; solved normal impulses update both rigid velocity and modal velocity. Thus the support contact is genuinely co-solved and two-way at the velocity/impulse level.
- Runtime support state is reduced/modal (`q,qdot` plus diagonal modal mass/stiffness/damping and sampled surface basis values), not a full volumetric FEM nodal state. However, saying the slab has “no internal state” would be false: it has internal deformation coordinates. The FEM mesh/eigenanalysis is used to build the reduced basis before/runtime scene setup, while contacts sample the boundary basis rather than solve internal nodes each timestep.
- More precise representation: in `SolverImpulse`, ordinary moving objects are 6-DOF rigid boxes, while the slab is registered as a fixed-rest support surface plus an `r`-DOF modal block. It is not represented as a freely moving 6-DOF rigid body inside the impulse solver, nor as a full nodal FEM body. Each body corner contacts `y_rest + U_y q`.
- Some scenes use a synthetic reduced plate basis; at least the dinner scene explicitly constructs a tetrahedral `FEMModel`, solves/builds a modal basis, then passes the reduced matrices/surface samples into the native solver. Thus “there are no FEM nodes in the timestep unknown vector” is correct; “the method has no FEM model/nodes anywhere” is scene-dependent and incorrect.
- Production-scene support detail: `build_support_and_attach` normally calls `make_debug_reduced_shelf_support`, which uses an analytic/synthetic sine-bending + Gaussian-bump basis and quadrature-built reduced matrices. The dinner viewer explicitly selects `support_basis="fem"`, constructs a tetrahedral slab, computes mass-normalized FEM eigenmodes, samples them on the top surface, and then discards full nodal dynamics from the per-step solve.
- `world.enable_reduced_modal_support` removes the tracked rigid bodies' ordinary floor registrations and replaces them with corner-to-live-support rows. The slab itself is therefore best called a **fixed-base reduced deformable support**. Calling it simply a “rigid body” obscures the actual model: it has no rigid 6-DOF block, but it does have deformable modal DOFs and compliance/inertia.
- The dedicated tests prove exact floor load, analytic one-mode sag, stack load paths, ON/OFF network excitation, ledger checks, and payload pre-sag. They do not yet establish matched physical accuracy, restitution, tangential deformation, deformed collision detection, full-network monolithic back-reaction, or velocity-impulse backend real-time performance.
- Local verification on 2026-07-18: `.venv/bin/python -m pytest tests/avbd_native/test_solver_impulse.py -q` passed all 6 tests in 13.21 s.
- Cross-backend behavior should be described as feature-level parity, not numerical equivalence. All three hosts use the same deformed support gap and route a shared normal multiplier to rigid/modal states; AVBD minimizes an augmented/implicit objective with a modal block, XPBD projects compliant positional constraints, and the new backend solves a velocity-level BLCP with PGS and an implicit modal Delassus contribution. Their damping, compliance, convergence, timestep response, multiplier meaning/scaling, restitution support, and failure modes differ.

### Fresh primary-literature screen for the velocity-impulse pivot

- The pivot removes one of the old claim's two surviving axes: “modal DOFs in a real-time AL/PBD host” no longer describes the new headline solver. The new velocity-level complementarity/impulse host is precisely the neighborhood occupied by older modal/reduced-contact work.
- Hauser, Shen, and O'Brien 2003 is a direct mechanism precedent. It represents objects by a rigid frame plus modal coordinates, writes the contact point as a linear function of modal coordinates, derives contact velocity/acceleration response to impulses/forces, and solves simultaneous nonnegative contact constraints; demonstrations include colliding/stacked modal objects at interactive rates. This is materially the same generalized-coordinate contact-Jacobian idea, though not the same PGS implementation or directional ledger.
- Zheng and James 2011 is also direct: modal vibration is resolved inside collision and frictional multibody contact, including energy exchange/chattering. It is a global Staggered-Projections/LCP/QP-style solver rather than the current local fixed-budget PGS, and has no inspected rigid-loss-funded modal ceiling.
- Miguel and Otaduy 2011 explicitly formulate rigid/deformable contact as an MLCP/LCP, take a Schur complement to a contact-space matrix, and connect it to iterative impulse-based solvers. It uses full deformable FE blocks rather than this small modal support retrofit, but it weakens any broad claim that extending a rigid contact-space impulse solve to deformable states is new.
- Manvelyan, Simeon, and Wever 2021/2022 reduce linear-elastic dynamic contact while preserving contact Lagrange multipliers and solving an LCP each timestep; again adjacent rather than an exact passivity-budget match.
- Barbič and James 2008 already runs reduced deformable contact at 1 kHz, including deformable-deformable action/reaction, but uses distributed penalty contact rather than shared complementarity impulses and has no directional ledger.
- Manvelyan et al.'s transient LCP has contact-space operator `h^2 C (M+h^2K)^-1 C^T` under implicit Euler. This is algebraically very close to the new solver's modal `G (M+hD+h^2K)^-1 G^T` contribution. Adding damping and rigid blocks is useful implementation work, but the modal effective-mass/Schur idea itself is not new.
- Sheth et al. 2015 is an even closer “impulse + rigid frame + reduced internal coordinates” precedent. It embeds a reduced deformable body in a rigid frame, derives an impulse formulation controlling nodal velocity, handles collision/contact/articulation, and conserves momentum. It precludes claims that a rigid-body impulse host augmented by reduced internal coordinates is novel in itself.
- ABD is only an analogy here. ABD uses affine internal/shape coordinates in an optimization/IPC family and targets stiff-material, intersection-free simulation. The current backend uses linear vibration/FEM modes in a velocity-level PGS complementarity solve, does not implement ABD's nonlinear affine internal energy, and explicitly routes ABD cargo back to AVBD.
- Rath 2008 and You et al. 2026 keep the energy-claim bar high: the former gives energy-stable real-time contacting modal objects, while the latter gives an energy-controllable integrator for elastodynamic contact. Neither inspected method uses the exact cumulative fractional ceiling funded by measured rigid contact loss.
- Full-text comparison strengthens the overlap assessment. Hauser's constraint method embeds modal dynamics in a rigid-body frame, writes `p_w=t+R U W z`, solves a velocity constraint for a nonnegative impulse, derives linear contact-point velocity change containing translation, rotation, and modal response, and handles relative velocity between two objects. This is the closest equation-level ancestor of the current generalized row.
- Zheng/James explicitly sets generalized positions/velocities to include rigid motion and linear modal deformation, constructs relative-velocity Jacobians, writes normal contact impulses as `N alpha`, discretizes the Euler-Lagrange equations at velocity level, and solves the dual contact/friction QPs. The paper itself notes iterative velocity-LCP methods trade accuracy/stability for performance. Therefore “we put modal columns into a rigid velocity impulse system” is a transcription/implementation claim, not a standalone novelty claim.
- Sheth et al. derive a combined rigid-plus-deformation impulse factor, state that the combined operator remains linear and can be solved as quickly as in the rigid case, and treat rigid behavior as the zero-internal-basis special case. Their interactive example runs about 7 fps with collision/contact/post-stabilization iteration counts set to one. This directly undermines both “zero-column rigid special case is new” and “fixed low iteration makes the coordinate augmentation new.”
- Rath's guarantee is whole-system nonincrease across piecewise-linear contact phase switches; its real-time 44.1 kHz example uses a point mass contacting a modal surface. It is not the same solver/contact law or the same directional storage/supply inequality, but it prevents broad `first energy-stable modal impulse contact` language.
- A fresh 2025--July 2026 query found no exact source-referenced rigid-loss-to-modal fractional budget in a velocity-impulse modal solver. Recent hits concern full-space/contact integrators, rigid-deformable MPM/peridynamics, or energy-targeted elastodynamics rather than this exact port ledger.
- Kaufman et al. 2008, *Staggered Projections for Frictional Contact in Multibody Systems*, is a foundational additional adversary: its primary paper explicitly targets rigid and reduced-deformable bodies with rigid modes and velocity-level frictional contact, and its evaluation compares against Projected-Gauss-Seidel LCP packages. Zheng/James builds directly on it. A paper centered only on modal/reduced coordinates inside velocity-level contact would therefore be clearly preempted.
- Full SP paper: the method defines arbitrary generalized coordinates `q`, point maps `x_i(q)`, point Jacobians, system block-diagonal mass, nonpenetration `N^T qdot >= 0`, and equal/opposite generalized impulses. It demonstrates hybrid reduced-StVK/rigid scenes at interactive/haptic rates and explicitly cites prior linear-modal LCP extensions. This is almost the abstract mathematical template of the new backend; swapping its QP/projection procedure for sequential PGS is not, alone, a novelty axis because PGS LCP solvers are themselves a comparison baseline in that paper.
- SP discusses contact algorithms' energy-gain artifacts but does not supply the inspected current method's cumulative contact-to-modal storage ceiling. Thus the new solver pivot leaves one primary research question: whether the exact **source-referenced directional modal-energy allocation/enforcement** is new, useful, and correctly guaranteed under a cheap underconverged PGS host.

### Current velocity-impulse passivity implementation caveats

- `SolverImpulse` contains the shared `PassivityLedger` and a full-state radial projection: after the PGS solve it computes a rigid-loss deposit, and if `_enforce_modal_passivity` is active, scales support/cargo `(q,qdot)` by one `gamma` so the modal-energy ceiling holds.
- Enforcement is **off by default**. The six dedicated impulse tests never turn it on; their passivity test verifies that one chosen trajectory is naturally within the ledger, not that the clamp activates and repairs an injecting velocity-impulse case. Its docstring says “enforced,” but the test setup does not exercise enforcement.
- The viewer's `_apply_passivity()` detects cargo through the solver's `_cargo_enabled` property, so an impulse scene with registered cargo can activate enforcement with `--passivity` (and uses monitor-only mode when the box is off). Support-only impulse scenes do not enter the viewer's support-enforcement branch because that branch additionally requires `_modal_symplectic=True`, while `SolverImpulse` defaults it to false. Thus the mechanism is exposed for cargo scenes but not the support-only impulse path, and the six dedicated impulse tests still do not force a clamp activation.
- The clamp is post-solve and scales `q` as well as `qdot` without re-solving the contact rows. It enforces the scalar modal-energy inequality by construction, but can alter the deformed gap after complementarity was solved. A paper must distinguish the scalar ledger certificate from simultaneous satisfaction of the contact law, momentum, and gap after projection.
- The funding signal is global rigid mechanical loss plus gravity work; it is not isolated contact-port work. Friction, numerical damping, stabilization/regularization, and other constraint losses can fund modal storage. This was already a proof/claim risk in the XPBD/AVBD version and remains in the impulse version.

### MIG 2026 fit/timing

- The official MIG 2026 site lists the long/short paper submission window as 2026-07-25 through 2026-08-07 (23:59 AoE), with the conference on 2026-12-11--13. The official venue framing covers interactive systems/simulation; physics-based animation, collision/deformation, haptics/sound are directly in scope based on the official/current and prior submission pages.
- Scope fit remains strong. Acceptance strength is a different question: a long paper cannot rely on the host pivot as novelty, and the only plausible surviving mechanism must be actively wired, adversarially exercised, proven carefully, and compared against the direct velocity-level modal-contact predecessors.
- The solver uses backward-Euler modal effective mass, exact unilateral normal rows, PGS, rigid-only friction columns, rigid broad/narrow-phase geometry, modal correction in the gap/Jacobian, and zero restitution. It is CPU/Numpy reference code; the July 17 note does not establish a velocity-impulse GPU real-time implementation.
- Important implementation qualification: support/slab rows carry full modal columns; box-box rows default to rigid-only solve with the same impulse driving modes open-loop. Fully monolithic box-box modal rows are opt-in because the documented unilateral-row rectification destabilizes off-center stacks. Therefore the whole network is not uniformly a full monolithic modal co-solve in the shipped default.
- The code explicitly rejects ABD cargo on this backend because nonlinear affine `V_perp` support is not implemented. “ABD-ish” is a useful coordinate-augmentation analogy, but the present implementation is not ABD.

### Current-paper compatibility and final verdict

- The current abstract, introduction, method, results, and conclusion are still an XPBD/AVBD paper: they claim a position-level augmented-Lagrangian/PBD host, host-specific fixed-budget stabilization, a GPU-resident co-solved implementation, 120 Hz, and 512-body evidence. Those statements do not describe or validate the new CPU/Numpy velocity-impulse backend and cannot be transferred to it without new measurements and a manuscript rewrite.
- The former novelty intersection does not survive unchanged. In particular, the `modal DOFs + real-time fixed-budget AL/PBD host` axis disappears when the headline method becomes a classical velocity-level complementarity/impulse solver. Hauser 2003, Kaufman et al. 2008, Zheng/James 2011, Sheth et al. 2015, and reduced dynamic-contact LCP work already cover most of the rigid-plus-modal generalized-coordinate contact construction.
- No inspected source through 2026-07-18 used the exact cumulative fractional rule that funds positive modal-storage gain from measured rigid mechanical-energy loss in an underconverged sequential-impulse solve. That is a potentially novel, much narrower contribution, not evidence that the host embedding, shared multiplier, modal Delassus term, two-way contact, rigid-as-zero-internal-coordinate case, or energy-stable modal contact is new.
- As currently demonstrated, the velocity-impulse version has moderate-to-weak novelty, approximately **4/10**. It could plausibly reach **5--6/10** if the directional budget is correctly isolated, enabled across the intended impulse paths, forced to activate in adversarial tests, proven without invalidating complementarity/momentum, and evaluated against direct modal-contact and energy-projection/passive baselines. This is a research literature screen, not a legal/patent novelty opinion.
- MIG scope fit is strong, but the present impulse version is not yet a convincing long-paper package: cargo viewer wiring can activate the survivor, but the dedicated impulse tests do not exercise an activating clamp case; the support-only viewer path disables it; the default box--box network is not uniformly monolithic; and the existing GPU performance/validation evidence belongs to different backends. The honest PI/MIG positioning is: a true rigid sequential-impulse host augmented with reduced modal support coordinates, with novelty sought in the directional energy budget under truncation rather than in the coordinate augmentation itself.

## 2026-07-11 Demo Repositioning — Initial Local Context

- The repository already separates scientific evaluation from spectacle: passivity/eta/solver tests (`benchmarks/paper_eval/x1_passivity`), FEM convergence and spatial falloff (`x3_ground_truth`), and performance/device stress tests (`x5_perf`).
- Existing paper figures include restitution/DCR-adjacent response, passivity robustness, contact forces, ground-truth falloff, network/dinner response, solver comparison, and runtime. This means replacing a large-jump hero demo does not require replacing the paper's entire evidence structure.
- The repo contains several physically grounded candidate scenes/assets (slab/beam, ledge/shelf, dinnerware, cargo/truck, boulder/plate), plus FEM references and audio/modal bases. These can support a new demo centered on back-reaction, deformation fields, contact-network propagation, stability, and sound rather than ballistic jump height.

### What the current draft itself establishes

- The abstract/introduction do **not** define novelty as large visible launch. They define it as: (1) stable fixed-budget coupling of stiff modal DOFs in AL/PBD-class solvers, (2) a cumulative directional passivity bound, (3) extension across a body–body contact network, and (4) validation.
- The current results explicitly call bystander launch KE a secondary, harsh, and non-convergent observable; the trustworthy accuracy observable is the surface-deflection field and its modal frequency/shape. This is strong internal evidence that a DCR-like jump-height target is scientifically misaligned with the method.
- The manuscript already admits the causal tradeoff: DCR's forced-IIR path re-amplifies a sub-millisecond transient and can exceed the passive bound, while the native two-way path is band-limited by the rigid timestep and remains physically funded. Therefore, matching DCR's large jump without changing timestep/contact/restitution would conflict with the paper's own physical/passivity story.
- The DCR head-to-head is currently scoped to falloff *shape*, not absolute magnitude, and is unmatched in timestep/restitution. It is useful as context/ablation but too weak to be the paper's hero demonstration.
- Current stronger observables already exist: shared-multiplier contact-force balance, top-cube ring appearing only with the modal network enabled, smoother force ripple, FEM deflection convergence and frequency agreement, passivity stress tests, and runtime scaling.

### Existing planning evidence

- `docs/mig_submission_plan.md` had already made the correct metric decision: deflection field primary, launch amplitude secondary. The present concern is therefore a narrative/hero-demo mismatch, not evidence that the core method ceased to exist.
- `docs/proposal_modal_response_as_constraint.md` explicitly characterizes the accepted formulation as having no artistic gain/jump/exaggeration dial; the physical/numerical inputs are part of the model/solver. Returning to a DCR-like jump knob would contradict that positioning unless clearly labeled as visualization-only and excluded from quantitative claims.
- The planned supplementary video already includes clamp/passivity, network, accuracy, and scale shots; DCR-like dinner/road footage was only one part of the package, not the sole demonstration route.

### Current MIG facts (official page checked 2026-07-11)

- MIG 2026 explicitly describes itself as a platform for research in interactive systems and animation, invites original work on a broad range of topics, and offers long and short paper sessions. A physically based interactive simulation method is squarely within that stated scope.
- The official page lists the paper submission window as July 25–August 7, 2026, with the conference on December 11–13, 2026. The page contains apparent stale-year typos for notification/poster dates, so only dates consistently stated elsewhere on the same official page should be treated as reliable without confirmation.
- Venue scope does not impose a requirement for large-amplitude or artist-controlled motion. Review risk comes from significance, evidence completeness, and communication—not from the physical effect being millimeter-scale by itself.
- The full official CFP explicitly lists `Physics-based animation` and `Interactive simulation and virtual environments` as topics. Its review criteria are originality, technical quality, clarity, significance, reproducibility where applicable, and relevance.
- Long papers are described as mature, complete contributions; short papers as focused results, emerging ideas, or concise technical contributions. The current 2026 page still contains placeholder text for page limits/anonymity/template details, so category fit can be assessed now but exact formatting must be rechecked later.
- Supplementary videos/images/data are encouraged when they help reviewers understand the contribution. For subtle physical motion, that supports slow motion, overlays, split views, and clearly labeled visual magnification.
- Strong venue precedent exists: recent MIG programs include physics-simulation sessions, real-time soft/deformable-body work, and an XPBD constitutive-material simulation paper. Lack of artistic control is not a categorical mismatch.

### ABD versus modal headline

- The local publication decision is important: ABD is already a drop-in affine cargo basis using the same two-way contact network. It does not create the coupling contribution; it changes the reduced deformation basis. The current affine path also has unresolved slow secular buildup and is not covered by the modal passivity claim.
- Therefore, if `towards ABD fast deformable objects` means *application/demo flavor*, the current novelty survives. If it means *replacing the modal formulation and passivity-bounded modal path with ordinary ABD two-way contact*, then much of the claimed novelty collapses because ABD already supplies fast two-way reduced contact. A method-level pivot would require a fresh claim audit.
- Safest current framing: modal/passivity/fixed-budget AL mechanism is the paper; ABD is a generality demonstration or supported alternative basis only after it shares the same enforced energy controller and passes long-horizon stability/accuracy tests.

### Visual audit

- The existing network OFF/ON GIF communicates the causal toggle and labels its ×241 modal-flex magnification, but it is an analysis artifact rather than a polished teaser. It supports the concept of a scientific visualization, not a final hero shot.
- The ABD comparison correctly shows basis-independent static load balance and that both modal/affine bodies receive network excitation, but the affine trace visibly builds late in the run; this reinforces the current decision not to headline ABD stability.
- The strongest replacement teaser can reuse the same stack with polished rendering, true-scale and magnified panels, contact-force arrows, per-body modal-energy coloring, and a compact OFF/ON trace. This makes micrometer/millimeter motion legible without changing the simulated trajectory.

### Final replacement-demo recommendation

- Highest-value new hero scene: a **mass-loaded resonant plate**. Keep a payload in contact below lift-off, tap the plate remotely, sweep payload mass, and compare coupled vs one-way/prescribed replay vs full FEM. A mass-dependent resonance shift is a clean back-reaction signature: a one-way driver cannot let the payload alter the support dynamics.
- Existing supporting scenes form a coherent evidence ladder: contact-network tower ON/OFF (causality and force ledger), native/full-FEM deformation-field overlay (fidelity), passivity OFF/ON at a starved budget plus inertness at the production budget (necessity and noninterference), and the N-grid (scale).
- Visual treatment: always show true scale beside a labeled render-only deformation ghost/heat map (roughly 100–300×), use slow motion, and keep rigid trajectories unamplified. Audio may sonify the modal state but is qualitative support, not evidence.
- The current jump-centered dinner plot/shot should be demoted or removed from the hero position because it highlights the weakest, timestep-band-limited observable. DCR can remain a compact contextual baseline rather than the paper identity.
- Long-paper readiness is separate from demo amplitude. A credible long submission still needs one evaluated configuration combining the central enforcement, fidelity, and target performance; otherwise the official MIG short-paper category better matches a focused contribution.

## Local Claim Baseline

- Current draft claims: passivity-bounded two-way modal contact in a real-time augmented-Lagrangian / position-based solver.
- The paper itself correctly avoids claiming first two-way rigid-modal coupling.
- Existing local novelty note identifies Zheng & James 2011 as the main adversary: two-way modal contact with shared multipliers exists offline; DCR 2020 is real-time but one-way; the proposed open cell is real-time AL/PBD + two-way modal DOFs + enforced contact-to-modal passivity bound.

## Open Questions

- Has any work after the local novelty audit combined modal/reduced contact DOFs, two-way coupling, real-time PBD/XPBD/AL/VBD-style solve, and an explicit passivity or energy-transfer cap?
- Are there adjacent works in haptics, robotics, reduced FEM, or game physics that could undermine the energy-bound novelty even if not modal-contact graphics papers?

## Initial Web Search Notes

- Searches for `"passivity" "modal contact" simulation`, `"modal contact" "passivity" "energy"`, and related terms did not surface an obvious modal-contact paper combining two-way modal contact, real-time AL/PBD, and an explicit directional energy cap.
- Current adjacent work surfaced includes ABD follow-ups and GPU/distributed ABD variants through 2026. These strengthen the "reduced/affine contact DOF" prior-art neighborhood but do not appear to use vibration eigenmodes or a contact-to-modal passivity budget.
- A 2023 Drake/robotics result on convex rigid-deformable frictional contact is relevant as robust interactive contact with deformables, but it is not modal two-way contact with a passivity-bounded modal injection path.

## Novelty Agent Verdict

- No exact paper found combining all three axes: real-time AL/PBD-style solver, two-way modal/reduced contact DOFs as native contact variables, and enforced directional passivity cap `Delta E_modal <= eta * Delta E_rigid_loss`.
- Closest adversary remains Zheng & James 2011: two-way modal contact and modal energy exchange, but offline/global contact sound solver with damping, not a fixed-budget real-time AL/PBD host and not an explicit rigid-loss-to-modal cap.
- DCR 2020 is real-time and modal-response related, but one-way, not native modal contact DOFs, and no passivity cap.
- ABD / Embedded IPC / M-ABD / distributed ABD are strong reduced-contact prior art, but affine/subspace/IPC rather than modal vibration eigenmodes with a directional contact-to-modal energy budget.
- Port-Hamiltonian and haptic passivity work cover the passivity genre, but not this graphics modal-contact formulation or the per-step modal transfer cap.

## Final Gap Assessment

- Gap still appears open as of 2026-07-07.
- Exact scoop risk: low-to-medium.
- Overall novelty risk: medium, because adjacent prior art is substantial and overclaiming would be punished.
- Strongest claim: enforced directional passivity cap for contact-to-modal transfer in a fixed-budget real-time AL/PBD-style modal contact solver.
- Weak/unsafe claims: first two-way modal contact, first modal contact DOFs, first modal contact network, first passivity method.

---

# MIG Regular-Paper Review Findings (2026-07-09)

## Scope

- Primary review artifact: `paper/main.pdf`, compiled 2026-07-09.
- Production demo is excluded at the user's request.
- Earlier literature-gap notes are background only; the acceptance decision will also weigh technical correctness, evaluation, clarity, reproducibility, significance, and MIG fit.

## Initial Manuscript Facts

- The compiled paper is 10 pages and visibly labeled `(working title - draft July 9, 2026)` on page 1.
- The paper claims: native modal compliant-constraint DOFs in XPBD/AVBD; shared unilateral multipliers for two-way rigid-modal coupling; an energy-transfer/passivity bound; modal propagation through contact networks; FEM/contact-force validation.
- The conclusion explicitly says the two-way mechanism is not novel; novelty rests on the real-time-AL embedding plus the passivity bound.
- The conclusion also discloses: the accuracy-validated symplectic CPU path runs at 16-34 ms/step; the faster device-resident co-solved path lacks the same deflection-field accuracy validation; native restitution is zero; road-scene accuracy is pending; and the affine-basis stability result is unfinished.
- The manuscript's own validation matrix contains several `pending` cells, including road fidelity, multiple momentum measurements, and some network/scene coverage.
- Build log has no unresolved citations/references, only underfull box warnings.

## Technical and Evidence Concerns

- Section 3 derives a per-step velocity-increment scale `alpha*` with modal displacement fixed. Section 4 says the shipped controller instead accumulates a reservoir and scales the full state `(a, adot)` by `gamma`. The paper asserts this is a generalization but does not derive equivalence or prove the advertised bound for this different state projection.
- On the device path, the ledger is explicitly read-only and never activates in 20 sampled cells. This is empirical evidence of passivity on those runs, not an enforced guarantee for unseen states; wording such as "the guarantee covers the device path" overstates what is shown.
- The rigid-loss budget is described inconsistently: Section 3 uses rigid kinetic energy lost during contact resolution, while results use `gravity work - Delta KE` per substep. The manuscript does not rigorously isolate contact work from damping, numerical dissipation, or other constraints in a multi-contact network.
- The abstract says linear and angular momentum are conserved by construction, but Section 4 reports host-solver impact drift of +47% at a shipped budget and +12% at a larger budget. Even if modal-on/off errors match, the unconditional abstract claim is false for the implemented algorithm.
- At the paper timestep, reduced/full-FEM peak-deflection ratios are only 0.56 (slab) and 0.38 (ledge). Dinner's median launch ratio is 0.016, despite prose/caption emphasizing roughly 7x lower near-field amplitude. Thus the interactive configuration is substantially under-responsive in important observables.
- The FEM reference itself uses penalty contact whose launch KE is non-convergent; the paper acknowledges an IPC-grade reference would be stronger. Shared-discrete-operator comparisons validate reduction/integration behavior but not broad physical accuracy.
- The fast device path lacks the deflection-field accuracy validation applied to the slower CPU path, so the paper does not yet demonstrate accuracy and target performance on the same algorithm/configuration.
- Multiple evaluation cells are visibly pending. The manuscript reads as an experiment tracker rather than a complete submission, especially for the road scene, cross-scene force/momentum tests, and some network discriminators.
- The main parameter `eta` is never assigned a numerical value, and no selection/sensitivity study is provided. This prevents interpretation or reproduction of the central bound.
- Page 3 contains unresolved internal prose references `(foundation Section 15)` and `(foundation Section 6)` with no corresponding manuscript section or citation.
- Page 4 says the momentum probe is pending, while page 7 reports momentum measurements and Table 3 mixes measured and pending momentum cells. This is a stale-state contradiction.
- The paper has no algorithm/pseudocode that specifies solver ordering, reservoir initialization/update, clamping order, or how contact-set changes enter the energy accounting.
- Runtime rows name rigid-only and DCR as references, but the reported timing tables contain only the proposed XPBD/AVBD variants. CPU hardware is unspecified and CPU timings are single-run.
- The DCR comparison uses each method at its "natural timestep" and compares only falloff shape; the restitution comparison varies DCR restitution while the native solver remains at `e=0`. Neither is a matched head-to-head comparison.
- The 10-page PDF includes only plots/tables and no scene images or qualitative deformation/contact-network result figure, which weakens communication for a graphics/MIG audience.
- The controller's main utility is not demonstrated in a successful target regime: on AVBD it never activates, while on XPBD it prevents blow-up but the paper says it over-damps and is not accurate. No experiment shows active enforcement plus accurate response.
- Table 3 labels peak-deflection ratios (`0.56 -> 1.03`, `0.38 -> 0.88`) as modal displacement `L2 error`; these are not error values and do not match the field-error metric discussed in prose.
- Figure 5 calls its plotted quantity a passivity ratio but defines it as peak ring energy divided by impactor KE, with clamp-ON cells up to 1.22. That plot is not the advertised ledger ratio and does not directly visualize the claimed invariant.
- DCR's own abstract says its response can traverse a contact graph, but Table 1 marks DCR's `Net` capability as no. The proposed network is two-way/native and stronger, yet the prior method should be marked partial rather than absent.
- The limitations mention an empirical spatial-attenuation path with no energy budget, but no such proposed path is specified in the method; elsewhere the paper emphasizes having no attenuation term. This appears to be a leftover or an omitted method component.

## Positive Evidence

- The problem is relevant to MIG: visually meaningful vibration/back-reaction in interactive rigid-body simulation.
- Positioning is unusually candid that two-way modal coupling is prior art and isolates the proposed novelty to the real-time AL embedding plus energy bound.
- The shared-operator FEM timestep ladders on slab and ledge are useful diagnostics and separate temporal band-limiting from modal truncation.
- The clamp OFF/ON budget-relaxation sweep covers three scenes and exposes a real severe instability; the contact-force ledger and network toggle are clean, understandable discriminators.
- Limitations are extensive and transparent, making it easier to identify what is and is not supported.

## Preliminary Calibration

- Novelty: moderate, likely 3/5. The exact combination appears open, but the network extension is nearly immediate and the actual governor is a simple global energy projection whose proof is incomplete.
- Technical soundness: weak, likely 2/5, because the advertised guarantee is not established for the evaluated controller/device path and momentum language conflicts with measurements.
- Evaluation: weak, likely 2/5. Several thoughtful experiments exist, but accuracy and speed are not jointly validated and comparisons are often unmatched.
- Clarity/presentation: 2/5 in the current draft due visible pending markers, stale statements, undefined internal references, dense result narration, and missing qualitative scene imagery.
- Likely recommendation in current form: Reject / major revision, with meaningful potential after the controller and evaluation are made internally consistent.

## Final Review Consensus

- Three independent review lenses (technical, evaluation, and novelty/presentation) converged on rejection of the current regular-paper draft.
- Recommended overall score: 2/5 (weak reject), confidence 4/5.
- The decision is not driven by the absent production demo. It follows from the manuscript itself: proof/implementation mismatch, empirical-vs-enforced guarantee language, accuracy/performance split, contradictory momentum claim, unmatched baselines, incomplete validation, and inadequate reproducibility.
- Accept-side case: strong MIG fit, a plausibly open exact combination, clean shared-multiplier concept, useful stress testing, and unusually candid limitations.
- Reject-side case dominates at the regular-paper bar because no evaluated configuration simultaneously demonstrates active enforcement, fidelity, and target performance.

---

# Novelty Re-Verification Findings (2026-07-09)

## Claim Axes

- A: modal/vibration eigenmode coordinates participate as native contact solver DOFs.
- B: coupling is two-way through a shared contact multiplier, including rigid back-reaction.
- C: host is interactive/real-time augmented-Lagrangian, XPBD/PBD, VBD/AVBD, or a closely equivalent fixed-budget local solver.
- D: an enforced directional energy/passivity condition explicitly bounds contact-to-modal transfer.
- E: body-to-body propagation occurs through a contact network.

The possible exact scoop must substantially occupy A+B+C+D. Axis E strengthens the application but is not sufficient novelty by itself.

## Fresh Search: Initial Candidates

- Manvelyan, Simeon, and Wever, *An Efficient Model Order Reduction Scheme for Dynamic Contact in Linear Elasticity* (2021/2022), uses a reduced displacement basis while explicitly preserving unilateral contact constraints and Lagrange multipliers, motivated by real-time-capable digital twins. It is an LCP/implicit-Euler structural-contact method, not an XPBD/AVBD host and has no directional passivity cap. Overlap: A/B partial, C no, D no.
- Lee et al., *Constrained Projective Dynamics: Real-time Simulation of Deformable Objects with Energy-Momentum Conservation* (SIGGRAPH 2021), adds position-based energy and momentum constraints to a real-time projective-dynamics solver. It is not modal-contact transfer and uses conservation rather than a contact-to-modal inequality, but it directly occupies the broader `real-time position-based + enforced energy property` neighborhood and should not be omitted.
- ABD (Lan et al. 2022) and 2026 follow-ups (Distributed ABD; M-ABD) provide compact native coordinates with globally coupled contact and strong convergence/non-penetration guarantees, but their coordinates are affine/near-rigid rather than vibration eigenmodes and they do not impose a contact-to-modal transfer budget.
- The exact A+B+C+D intersection remains unfilled after the initial query set.

## Fresh Search: Passivity Adversaries

- Hannaford and Ryu, *Time-Domain Passivity Control of Haptic Interfaces* (2002), defines a passivity observer that accumulates energy flow and a controller that absorbs exactly any net generated energy at each sample. This is structurally close to the paper's cumulative ledger/governor. It does not use modal contact DOFs, but it means the observer-reservoir-correction principle is established prior art and the manuscript must distinguish its particular port, budget, and projection precisely.
- Yoon, Hong, and Lee, *Passive Model Reduction and Switching for Fast Soft Object Simulation with Intermittent Contacts*, explicitly combines contact-mode reduced FEM models with passive integration, passive reduction, and passive switching for fast simulation under changing contacts. It is a potentially important adversary: passive reduced contact simulation is not new. Initial evidence suggests it does not use a shared rigid-modal contact multiplier in a fixed-budget XPBD/AVBD host or the proposed directional rigid-loss-to-modal cap, so it is adjacent rather than an exact scoop.
- Asynchronous Contact Mechanics (Harmon et al. 2009) guarantees nonpenetration, causality, momentum, and energy conservation for deformable contact, but is not reduced/modal or a real-time fixed-budget AL/PBD solver.
- Flexible-multibody/contact MOR literature (e.g. hybrid data-driven MOR with impact/friction; free-interface component-mode synthesis for moving contact) already covers two-way reduced flexible contact extensively, generally without the proposed directional transfer cap or graphics real-time local host.

## Major Adversary: Passive Midpoint Integration

- Kim, Lee, Lee, and Lee, *Haptic Rendering and Interactive Simulation Using Passive Midpoint Integration* (IJRR 2017), is much closer than the current related-work section acknowledges. It enforces discrete-time passivity while retaining real-time interactivity, works in maximal and generalized coordinates, incorporates constraints/compliance, and includes multi-point Coulomb-friction contact through a PMI-LCP. One example stably emulates vibration of a flexible beam.
- The 2019 Yoon et al. paper builds passive reduced-order FEM simulation with intermittent contact on top of PMI, explicitly preserving passivity of each reduced model plus model reduction/switching.
- These papers do not appear to use an XPBD/AVBD fixed-budget local solve, a native shared rigid-modal contact multiplier in the paper's specific sense, or a directional inequality `Delta E_modal <= eta Delta E_rigid_loss`. Therefore they do not exactly scoop A+B+C+D as narrowly defined.
- They do invalidate broad formulations such as `first passive real-time modal/reduced contact`, `prior passivity work is genre-only`, or a novelty table implying that no prior real-time contact solver carries an enforced energy/passivity property.
- The manuscript must compare against PMI directly and explain why the proposed transfer-budget governor is technically different and useful relative to a passivity-preserving integrator.

### PMI Axis Detail

- PMI's flexible-beam example uses three generalized vibration coordinates with natural frequencies and demonstrates conserved vibration energy; the beam is coupled to a rigid body and haptic device through passive spring/virtual coupling.
- PMI separately derives multi-point Coulomb-friction LCP contact in generalized coordinates. The paper does not clearly demonstrate direct LCP contact on the modal beam, but its formulation makes the combination close enough that a reviewer could reasonably ask whether the new paper is an AL/PBD adaptation rather than a new passivity concept.
- The safest distinction is not `passive real-time modal contact`; it is the specific *directional transfer budget tied to measured rigid contact loss under a truncated local AL/PBD solve*.

### PMI Full-Text Cross-check

- The published journal HTML confirms that PMI is explicitly non-iterative and real-time, enforces discrete-time passivity, handles maximal and generalized coordinates, and incorporates intermittent multi-point Coulomb friction through PMI-LCP in both coordinate settings.
- Its flexible-beam example uses three natural vibration coordinates with inertia/stiffness matrices and couples that generalized-coordinate beam to a rigid box and haptic device through a passive spring/virtual coupling. The paper separately derives generalized-coordinate point contact and states that its static-rigid-object derivation extends readily to multiple moving rigid objects.
- Axis classification should therefore be conservative: A is at least strong partial (modal generalized coordinates plus a generalized-contact formulation), B is partial/arguably implicit rather than demonstrated as the manuscript's shared multiplier on a modal beam, C is real-time but not AL/PBD, and D is full-system discrete passivity rather than the directional rigid-loss-to-modal inequality.
- PMI does not exactly duplicate A+B+C+D under the narrow host and supply-rate definitions. It does, however, destroy any broad `first passive real-time modal/reduced contact` framing and makes the paper look like a specialized AL/PBD adaptation unless the directional port constraint is proved and shown to provide a distinct benefit.

## Further Recent Adversaries

- Yoon et al., *Fast and Accurate Data-Driven Simulation Framework for Contact-Intensive Tight-Tolerance Robotic Assembly Tasks* (2022), combines PMI discrete-time passivity with fast contact solving, Coulomb friction, maximum energy dissipation, and contact nodes augmented with object mechanics. It is rigid/contact-intensive rather than modal vibration, but reinforces that passive real-time contact simulation is established.
- Wei et al., *Early-Terminable Energy-Safe Iterative Coupling for Parallel Simulation of Port-Hamiltonian Systems* (2026 preprint), addresses spurious energy from finite-iteration subsystem coupling and proves a discrete passivity certificate for any finite inner-iteration budget. It is not a contact/modal graphics method, but it is extremely close at the abstract solver-failure level and must temper claims that fixed-budget coupling energy injection/remediation is unique.
- AVBD itself (Giles et al. 2025) explicitly identifies energetic error from under-solving fixed-iteration position-based hard constraints and introduces stabilization/convergence machinery; it guarantees descent of the variational energy when line search is used. It does not add modal coordinates or a directional transfer cap, but the host-solver failure context is already documented.
- Projection-based dynamic-contact MOR (Balajewicz, Amsallem, Farhat 2015), reduced dynamic LCP contact (Manvelyan et al.), and force-dual/contact-tailored modes (Benchekroun et al. 2025) expand the prior reduced-contact neighborhood. None found so far uses the exact AL/PBD transfer budget.

## Further Sources Logged

- Contact-intensive PMI framework: https://arxiv.org/abs/2202.13098
- Energy-safe finite-iteration coupling: https://arxiv.org/abs/2603.16424
- AVBD primary paper: https://graphics.cs.utah.edu/research/projects/avbd/Augmented_VBD-SIGGRAPH25.pdf
- Projection-based contact MOR: https://arxiv.org/abs/1503.01000
- Force-Dual Modes: https://arxiv.org/abs/2505.23969

## Modal-Contact and DCR Citation-Chain Check

- Searches around Zheng and James 2011 found no later primary paper adding an AL/PBD host plus a directional modal-transfer cap. Zheng and James remains the closest native two-way modal-contact mechanism: coupled vibration, collision, and frictional contact with an asynchronous adaptive LCP-style solver, but no explicit transfer budget.
- Searches around DCR 2020 found no published two-way/passivity follow-up. DCR explicitly propagates response across the contact graph, so network propagation alone is prior art; the new distinction must be native two-way modal state/back-reaction through shared constraints.
- No exact scoop surfaced in the modal-sound or DCR citation-chain queries.

## Energy/Structure-Preserving Graphics Context

- Constrained Projective Dynamics (Kee et al. 2021) is real-time projective dynamics with explicit position-based energy and momentum constraints; available material indicates collision handling was implemented. It is not a modal-transfer controller, but it is another reason the `Passive + RT-AL` empty-cell argument is too broad.
- Structure-preserving MOR already preserves Hamiltonian/Lagrangian structure, energy, dissipation, and passivity in reduced systems. Most of that literature is not contact-specific, but the paper should avoid implying that energy-safe reduced dynamics itself is new.
- The contribution continues to survive only under a narrow application/mechanism description: a rigid-loss-funded directional cap for native modal contact inside a truncated AL/PBD host.

## Major Adversary: FEPR

- Dinev et al., *FEPR: Fast Energy Projection for Real-Time Simulation of Deformable Objects* (SIGGRAPH 2018), takes a conventional approximate step and projects the state back to a constant energy-momentum manifold. It is designed for real-time solvers including PBD and Projective Dynamics and explicitly prevents numerical explosions caused by approximate solves or large timesteps.
- This is structurally very close to the manuscript's *implemented* full-state modal projection. The new aspect is narrower: it uses a one-sided modal-energy ceiling funded by measured rigid contact loss rather than restoring global constant energy/momentum.
- FEPR does not itself provide native modal two-way contact or the directional rigid-to-modal budget, so it is not an exact scoop. However, omitting it would make the claimed projection/controller novelty indefensible.
- The paper must state that its governor is a contact-port-specific, one-sided energy projection related to FEPR and TDPA/energy tanks, then establish what new guarantee or behavior follows from the particular budget and modal-only projection.

## Major Adversary: Su, Schroeder, and Fedkiw 2009

- *Energy Stability and Fracture for Frame Rate Rigid Body Simulations* (SCA 2009) derives an analytic scale on equal-and-opposite linear/angular contact impulses. Because kinetic-energy change is quadratic in the impulse scale, it selects a scale that prevents collision/contact from increasing energy while retaining momentum symmetry.
- This is mathematically very close to the manuscript's Eq. 8-9 velocity-increment quadratic. The manuscript permits a nonzero budget `E_max = eta Delta E_rigid` and applies it to modal velocity rather than clamping total rigid contact energy to zero growth.
- Therefore the quadratic closed-form clamp is prior art. The defensible novelty is the *choice of subsystem port and supply rate* (contact-to-modal gain funded by rigid mechanical loss), plus integration into shared-multiplier modal AL/PBD; it is not the existence of an exact quadratic energy scale.
- Su et al. also target frame-rate large timesteps and explicitly discuss split-state contact accounting, making this a mandatory citation and conceptual baseline.

## Su et al. Source Logged

- Author-hosted primary paper: https://www.cs.ucr.edu/~craigs/papers/2009-energy/paper.pdf

## FEPR Source Logged

- Primary project/paper: https://users.cs.utah.edu/~ladislav/dinev18FEPR/dinev18FEPR.html

## Additional Primary Source

- Constrained Projective Dynamics: https://doi.org/10.1145/3450626.3459878

## 2026 Energy-Controllable Contact Adversary

- You, Zheng, and Li, *Energy-Controllable Time Integration for Elastodynamic Contact* (2026 preprint), is closer to the proposed controller than its abstract alone suggests. After an implicit IPC contact step, it keeps the new position fixed, expresses post-step Hamiltonian energy as an exact quadratic along a velocity-correction ray, solves analytically for a scale matching a prescribed energy target, and clips/applies that correction. With friction it estimates dissipated energy and updates a cumulative energy target.
- This establishes prior art for the combination `contact + cumulative dissipation accounting + prescribed energy target + analytic quadratic velocity correction`. It is full-space elastodynamics with IPC/barrier contact and a total-system target, not a shared rigid-modal transfer port or a directional ratio funded by rigid-body loss.
- Consequently, the manuscript's quadratic alpha construction is not independently novel. The surviving distinction is the source/storage partition and supply rate: modal-storage gain is limited relative to measured rigid mechanical-energy loss inside shared-multiplier modal contact.
- Primary record: https://arxiv.org/abs/2602.08094

## Exact-Phrase and Modal-Impact Follow-up

- Adversarial queries for `contact-to-modal`, `modal energy budget`, `directional energy contact`, rigid-flexible energy-transfer bounds, and modal contact passivity did not surface a paper enforcing the same rigid-loss-funded modal inequality.
- Gehr et al., *Computational and experimental analysis of the impact of a sphere on a beam and the resulting modal energy distribution* (2022), is relevant native modal-impact prior art. It uses component mode synthesis with a massless contact boundary, analyzes modal energy distribution after impact, and reports 3--4 orders of magnitude computational reduction while matching experiments. It does not present a fixed-budget AL/PBD host or an enforced directional passivity cap.
- Primary record: https://arxiv.org/abs/2207.00795
- The negative query result is supporting evidence only, not proof that no uncatalogued or differently worded work exists.

## Primary-Source Cross-check Notes

- Zheng and James's author page explicitly states that modal vibration is resolved during both collision and frictional contact, enabling vibrational energy exchange, and that the solver is an asynchronous modified Staggered Projections method. This confirms A+B while distinguishing its host from a fixed-budget XPBD/AVBD loop and confirming the absence of the claimed directional budget in its stated contributions.
- Yoon et al.'s institutional publication record explicitly describes fast reduced FEM simulation with changing contact modes, passive midpoint integration for each reduced model, and passive model reduction/switching. This confirms that `fast + reduced contact + passivity` is prior art even though native eigenmode contact coordinates and the rigid-loss-funded transfer inequality are not established there.
- FEPR's author page explicitly states post-step projection to a constant energy-momentum manifold, use with PBD/Projective Dynamics, prevention of approximate-solve/large-step explosions, and real-time suitability. This confirms that the manuscript cannot claim post-step energy projection in a PBD-like host as new.
- Su et al.'s Eurographics record explicitly describes a frame-rate technique for clamping contact/collision energy gain while conserving energy and momentum. The author paper supplies the analytic quadratic impulse scaling detail already logged.
- Wei et al. 2026 explicitly guarantees discrete passivity for any finite inner-iteration budget in partitioned subsystem coupling. It is not contact/modal graphics, but it directly weakens broad claims about uniquely addressing energy injection from truncated coupling iterations.

## Energy-Bounding Algorithm Precursor

- Kim and Ryu, *Robustly Stable Haptic Interaction Control using an Energy-bounding Algorithm* (IJRR 2010), explicitly limits energy generated by a sample-and-hold operator to energy consumable by effective physical damping, thereby enforcing passivity. This is a particularly close precursor to the abstract supply principle `an otherwise active update may spend only measured dissipative energy`.
- It has no modal contact state, shared rigid-modal multiplier, or AL/PBD host. It therefore does not exactly scoop the paper, but it makes the rigid-loss-funded controller principle look like a port-specific adaptation of established energy-bounding control rather than a new passivity concept.
- Primary publisher record: https://journals.sagepub.com/doi/10.1177/0278364909338770

## Interim Risk Calibration

- Exact all-axis scoop risk remains low-to-medium if axes A+B+C+D are defined narrowly and conjunctively; no inspected source duplicates the complete combination.
- Practical reviewer novelty risk is medium, because PMI nearly spans passive real-time generalized/modal mechanics plus contact, while Zheng/James supplies the exact two-way modal-contact mechanism and FEPR/Su/You/Kim-Ryu supply the controller mathematics and energy-accounting ideas.
- Controller/mechanism obviousness or incrementality risk is high. The paper needs more than an empty taxonomy cell: it must prove the actual cumulative controller and demonstrate a qualitative/quantitative benefit unique to the directional supply rate.

## Real-Time Reduced/Modal Contact and XPBD Precursors

- Barbi\v{c} and James, *Six-DoF Haptic Rendering of Contact Between Geometrically Complex Reduced Deformable Models* (IEEE ToH 2008), supports contact between rigid or reduced deformable models with complex geometry at hard real-time kilohertz rates. The method uses stiff penalty contact and reduced deformation; the detailed paper supports classic linear modal bases and applies opposite forces to both contacting bodies. It has no shared AL multiplier or directional energy budget. It invalidates a broad `first real-time two-way modal/reduced contact` claim.
- Primary DOI/record: https://doi.org/10.1109/TOH.2008.1 and https://pubmed.ncbi.nlm.nih.gov/27780152/
- Peng et al., *Soft robot fast simulation via reduced order extended position based dynamics* (Robotics and Autonomous Systems 2024), explicitly uses reduced XPBD with a subspace constructed from linear modes and modal derivatives. Its showcased soft-robot actuation setting does not establish shared rigid-modal unilateral contact or passivity, but it invalidates `first modal/reduced coordinates in XPBD` as a standalone claim.
- Publisher record: https://www.sciencedirect.com/science/article/pii/S0921889024000332 ; DOI: https://doi.org/10.1016/j.robot.2024.104650
- Brandt, Eisemann, and Hildebrandt, *Hyper-Reduced Projective Dynamics* (TOG 2018), already combines real-time reduced-space Projective Dynamics with collision constraints. Its sparse subspaces explicitly avoid modal analysis, so it is adjacent rather than an eigenmodal scoop.
- Primary institutional record: https://research.tudelft.nl/en/publications/hyper-reduced-projective-dynamics/ ; DOI: https://doi.org/10.1145/3197517.3201387
- Goury, Carrez, and Duriez, *Real-Time Simulation for Control of Soft Robots With Self-Collisions Using Model Order Reduction for Contact Forces* (RA-L 2021), supplies another real-time reduced-contact/LCP precedent. It has no rigid-modal network or directional passivity budget.
- Primary HAL identifier: https://hal.science/hal-03192762 ; DOI: https://doi.org/10.1109/LRA.2021.3064247

## Earlier Energy-Stable and Interactive Modal Contact

- Rath, *Energy-Stable Modelling of Contacting Modal Objects with Piece-Wise Linear Interaction Force* (DAFx 2008), explicitly addresses discrete-time contact between vibrating modal objects and exact preservation of system energy when switching between contact phases. It is intended for real-time interactive/audio scenarios. The interaction is a piecewise-linear force between modal resonators, not a fixed-budget AL/PBD unilateral contact solve or a directional rigid-loss-funded ceiling.
- Primary proceedings PDF: https://dafx.de/paper-archive/2008/papers/dafx08_27.pdf
- This directly invalidates the draft's broad contribution wording `passivity inequality ... absent from prior modal-contact work`. The safe distinction is the particular source-referenced directional inequality, not energy stability/passivity in modal contact generally.
- Hauser, Shen, and O'Brien, *Interactive Deformation Using Modal Analysis with Constraints* (Graphics Interface 2003), implements manipulation, collision, and environmental constraints inside a linear modal framework and demonstrates real-time/interactive examples. It establishes native interactive modal contact/backreaction well before the current work, although its penalty/constraint machinery is not the proposed AL/PBD directional-budget solver.
- Primary author page/PDF: https://graphics.berkeley.edu/papers/Hauser-IDU-2003-06/ and https://graphics.berkeley.edu/papers/Hauser-IDU-2003-06/Hauser-IDU-2003-06.pdf
- Bhalerao and Anderson, *Modeling intermittent contact for flexible multibody systems* (Nonlinear Dynamics 2010), formulates normal/friction complementarity for flexible multibody systems represented with local mode shapes. It is an important shared-contact/modal multibody precedent but not a demonstrated real-time graphics system or energy-bounded AL host.
- Primary publisher record: https://link.springer.com/article/10.1007/s11071-009-9580-2
- Ducceschi, Bilbao, and Webb, *Real-time modal synthesis of nonlinearly interconnected networks* (DAFx 2023), gives an energy-stable real-time algorithm for networks of nonlinearly connected modal resonators, including gap/rattle-like connections. It is an audio-rate modal-network method, not shared rigid-modal unilateral AL contact, but further removes energy-stable modal networks as a standalone novelty.
- Primary publisher PDF: https://www.pure.ed.ac.uk/ws/portalfiles/portal/377936620/Bilbao2023DAFxRealTime.pdf

### Rath Full-Paper Classification

- Rath begins with two dynamical systems coupled by an interaction force and assumes actio-reactio, `f1=f` and `f2=-f`. Its worked model couples a freely moving point mass to a vibrating modal object through a unilateral piecewise-linear spring/damper contact; the construction also states that the second object can use the same general dynamical form.
- The discrete switching rule offsets contact onset to a sample boundary so the no-contact-to-contact transition preserves energy exactly. Contact release can discard spring energy, so discrete artifacts can reduce but never increase total system energy.
- The demonstrated point mass repeatedly bounces on a three-mode surface under gravity. The paper explicitly states that each contact transfers energy from the free mass to the modal object and that total system energy decays monotonically. A separate implementation runs at 44.1 kHz with more than roughly 100 modes on an average notebook.
- Overlap is therefore A yes, B yes in a force/action-reaction sense, C real-time but not AL/PBD, D strong broader analogue (total-system nonincrease rather than `modal gain <= eta * rigid loss`), and E not demonstrated. This is a major mandatory citation and makes controller novelty substantially narrower.
- The exact survivor versus Rath is the *fractional directional allocation rule referenced to measured contact-side rigid loss, implemented as a cumulative post-solve projection for underconverged shared-row AL/PBD*, not energy stability, real-time modal contact, or two-way transfer themselves.

### Su Full-Paper Classification

- Su et al. explicitly scale equal-and-opposite contact/collision linear and angular impulses by a scalar epsilon. Because kinetic energy is quadratic, they derive the nontrivial exact root; `0<epsilon<1` scales an energy-injecting impulse, while negative values discard an infeasible impulse.
- Their clamp is independent of the particular contact algorithm so long as it produces an impulse, and targets frame-rate time steps. This is a direct mathematical precursor to the manuscript's increment-ray quadratic scale, although it caps total rigid kinetic-energy growth rather than funding modal gain with a nonzero directional budget.

## Revised Claim Risk After Citation-Chain Search

- Withdraw `the two-way coupling of Zheng and James brought from offline LCP/QP to real time`: Hauser 2003, Barbi\v{c}/James 2008, Rath 2008, and Sheth et al. 2015 already provide interactive/real-time two-way modal or modal-capable reduced contact.
- Withdraw `none of these hosts carry modal DOFs`: Peng 2024 supplies reduced XPBD built from linear modes/modal derivatives, and Hyper-Reduced PD supplies reduced collision coordinates in a real-time PD host.
- Withdraw `passivity inequality absent from prior modal-contact work`: Rath 2008 is explicitly energy-stable modal contact; PMI 2017 and Yoon 2019 establish broader passive modal/reduced simulation.
- Preserve only the conjunctive claim: a source-referenced directional fractional transfer budget in shared rigid/modal unilateral rows of a fixed-budget AL/PBD host, cumulatively enforced over changing contact graphs.
- Current broad-claim novelty risk is medium-to-high. With precise narrowing, exact-scoop risk is medium and overall idea novelty is moderate rather than strong.

## Full-Paper Checks: Hauser, Barbi\v{c}/James, and Sheth

- Hauser et al. represent each free object with a rigid-body frame plus modal coordinates. Object-object collision constraints use relative contact velocities/accelerations; the resulting linear program supplies nonnegative normal forces, and the force/impulse response includes translation, rotation, and modal terms. They demonstrate pairs of hybrid rigid/modal objects colliding and report interactive behavior, with penalty response reaching real-time rates and constraint response remaining interactive.
- This establishes A+B and interactive C in a non-AL host. It has no explicit energy/passivity controller. It is a direct precursor to native modal contact, not merely display-only deformation.
- Barbi\v{c}/James state that their framework accepts classic linear modal vibration models, reduced nonlinear FEM, and other low-dimensional models. Their implemented reduced FEM uses 15--20 deformation modes; the simulation, collision detection, and distributed penalty contact run together at 1,000 Hz. For deformable-deformable contact, each computed force is applied with opposite sign to both reduced objects.
- Thus Barbi\v{c}/James provides hard-real-time two-way modal-capable reduced contact. The missing pieces are a shared unilateral AL multiplier and any directional energy ledger; stability is handled through penalty/virtual-coupling design and damping.
- Sheth et al. use at most ten unconstrained eigenmodes per reduced body in their main examples. Their impulse formulation changes rigid translation/rotation and modal coordinates while conserving total linear/angular momentum. The Pachinko configuration runs at about 7 fps and explicitly sets collision, contact, and post-stabilization iterations to one.
- Sheth therefore supplies another A+B plus fixed-low-iteration interactive precedent, though not a real-time XPBD/AL host and with no energy-transfer cap.
- Primary sources: https://graphicsinterface.org/wp-content/uploads/gi2003-29.pdf ; https://graphics.cs.cmu.edu/projects/defoContact/BarbicJames-2008-IEEE-TOH.pdf ; https://physbam.stanford.edu/papers/stanford2015-05.pdf

## Broader Energy-Conserving Contact Acoustics

- Chatziioannou and van Walstijn, *Energy conserving schemes for the simulation of musical instrument contact dynamics* (JSV 2015), derives energy-conserving frictionless impact schemes from discrete Hamiltonian equations for point masses and distributed vibrating strings/beams against obstacles. It is generally implicit/Newton-based and not a rigid-modal AL graphics solver, but shows that energy-safe vibrating-contact algorithms are an established subfield.
- Primary preprint/record: https://arxiv.org/abs/1501.01493 ; DOI: https://doi.org/10.1016/j.jsv.2014.11.017
- Issanchou et al., *A modal-based approach to the nonlinear vibration of strings against a unilateral obstacle* (JSV 2017), combines a modal string representation, unilateral contact, and an energy-conserving integration adaptation. It is not a moving-rigid-body two-way AL contact network.
- Publisher record: https://www.sciencedirect.com/science/article/abs/pii/S0022460X16307623
- Ducceschi, Hamilton, and Russo, *Simulation of the Snare-Membrane Collision in Modal Form Using the Scalar Auxiliary Variable Method* (Forum Acusticum 2023), treats distributed modal-object collision in an energy-conserving framework. It further establishes modal collision plus energy stability, although the application/solver class differs.
- Su, Sheth, and Fedkiw, *Energy Conservation for the Simulation of Deformable Bodies* (TVCG 2013), supplies another general post-step energy-budget/conservation mechanism usable with a chosen integrator. It is not a directional rigid-to-modal contact allocation, but it belongs beside FEPR and Su 2009 in the controller ancestry.
- DOI: https://doi.org/10.1109/TVCG.2012.132
- These sources reinforce the same conclusion: the novelty cannot be `energy-safe modal contact`; it must be the particular directional supply rate and its integration with shared rigid/modal fixed-budget AL rows.

## Final Axis Matrix

| Work | Native/two-way modal contact | Interactive host | AL/PBD host | Enforced energy property | Same directional rigid-loss budget |
|---|---|---|---|---|---|
| Hauser et al. 2003 | Yes | Yes | No | No | No |
| Rath 2008 | Yes, point-mass/modal action-reaction | Yes, 44.1 kHz | No | Total energy never numerically increases | No |
| Barbi\v{c}/James 2008 | Yes/modal-capable reduced | Yes, 1 kHz | No, penalty | Stability/damping, not transfer ledger | No |
| Zheng/James 2011 | Yes | No, offline/audio solve | No | Contact damping | No |
| Sheth et al. 2015 | Yes | Partial, about 7 fps | No, impulse solver | Momentum conservation | No |
| PMI 2017 | Strong partial | Yes | No, LCP/midpoint | Whole-system discrete passivity | No |
| FEPR 2018 | No modal contact | Yes | PBD/PD | Post-step energy-momentum projection | No |
| Yoon et al. 2019 | Modal ROM contact input, not joint mate | Yes, 420 Hz | No | Passive integration/reduction/switching | No |
| Su et al. 2009 | No modal DOFs | Frame-rate | Contact-algorithm agnostic | Exact quadratic contact energy clamp | No |
| Peng et al. 2024 | Modal/reduced XPBD, no shown shared rigid-modal row | Yes | Yes | No | No |
| You et al. 2026 | Full-space elastodynamic contact | Not fixed-budget AL | No, IPC | Cumulative energy target plus analytic quadratic correction | No |
| Current paper | Yes | Claimed | Yes | Directional cumulative modal ceiling | Yes |

No inspected work occupies the final column. The empty final column is narrower than the manuscript's current `Passive + RT-AL` cell and is the only defensible novelty intersection.

## Final Novelty Verdict

- No exact A+B+C+D combination was found through 2026-07-09. Confidence is about 85%, not certainty; literature search cannot prove universal absence.
- Exact-scoop risk: **medium**. The exact fractional source/storage partition appears open, but terminology varies across graphics, haptics, acoustics, flexible multibody dynamics, and control.
- Overall idea novelty: **moderate, about 5/10**. Nearly every component is established in close combinations.
- Exact mechanism novelty: **about 6--7/10 only if** the implemented cumulative controller, contact-loss supply rate, and network invariant are rigorously derived and experimentally shown to matter. Without that, it looks like a combination of Hauser/Barbi\v{c}/Sheth + Peng + Rath/PMI/FEPR/Su/TDPA.
- Broad-claim risk: **very high**. Current statements at `paper/sections/10_introduction.tex:36`, `:38`, and `paper/sections/20_related_work.tex:42` are contradicted by prior work.
- Reviewer incrementality/obviousness risk: **high**. An empty taxonomy cell alone is not a sufficient contribution argument.

## Defensible Claim

Preferred wording:

> We introduce a cumulative post-solve modal-storage projection for shared rigid/modal unilateral contact rows in a fixed-budget XPBD/AVBD-style augmented-Lagrangian solver. Positive modal-storage gain is limited to a prescribed fraction of accumulated measured contact-associated rigid mechanical-energy loss, including across changing multi-body contact graphs.

If a priority statement is necessary:

> To our knowledge, prior work has not combined native vibration eigen-coordinates in shared two-way rigid-contact rows, fixed-budget local augmented-Lagrangian iterations, and a cumulative directional ledger limiting positive modal-storage gain to a prescribed fraction of measured contact-associated rigid mechanical-energy loss.

Use `directional energy-budgeted` rather than broad `passivity-bounded` unless the paper defines the external supply port and proves the corresponding discrete storage inequality for the shipped controller.

## Claims to Remove

- Remove `passivity inequality ... absent from prior modal-contact work`; Rath 2008 directly contradicts it.
- Remove `two-way coupling ... brought from offline LCP/QP to real time`; Hauser 2003 and Barbi\v{c}/James 2008 contradict it.
- Remove `none of these hosts carry modal DOFs`; Peng 2024 contradicts it.
- Do not claim the quadratic root, full-state energy projection, cumulative energy observer/reservoir, real-time passive reduced contact, or contact-network propagation as independently new.
- Change DCR's network entry from `no` to `yes/partial`.

## Minimum Related-Work Repair

- Mandatory direct comparisons: Rath 2008; Hauser 2003; Barbi\v{c}/James 2008; PMI 2017; Yoon 2019; Peng 2024; Su et al. 2009; FEPR 2018; You et al. 2026.
- Also retain Zheng/James and Sheth, and acknowledge the energy-conserving acoustic-contact line (Chatziioannou/van Walstijn 2015 and successors).
- Replace the binary positioning table with partial-overlap descriptions that distinguish whole-system passivity/conservation from the exact directional supply rate.

## MIG Implication

- The narrowed idea is still plausible for MIG, but it is not a merely under-polished strong-novelty paper. It is a solver/integration contribution with moderate novelty and high proof/evaluation burden.
- The current manuscript remains a weak reject for reasons independent of novelty. To become competitive, it must rigorously prove the implemented cumulative full-state controller, define contact-associated rigid loss, and demonstrate an accurate interactive regime where the controller activates and improves behavior relative to Rath/PMI/FEPR-like alternatives.

## Primary Sources Logged

- Zheng and James project/paper: https://www.cs.cornell.edu/projects/Sound/mc/
- DCR publisher page: https://doi.org/10.1111/cgf.14106

## PMI Sources Logged

- Primary IJRR paper/DOI: https://doi.org/10.1177/0278364917731821
- Author-hosted Yoon et al. PDF: https://50f23fad-e0b4-4694-b9a7-c25af4a3eeab.filesusr.com/ugd/313661_e69df8b58c0b4efc86575ec4d8697f45.pdf

## Additional Sources Logged

- Hannaford and Ryu DOI: https://doi.org/10.1109/70.988969
- Yoon et al. publication record: https://snu.elsevierpure.com/en/publications/passive-model-reduction-and-switching-for-fast-soft-object-simula
- Harmon et al. primary project/paper page: https://www.cs.columbia.edu/cg/ACM/
- Hybrid contact FMBS MOR DOI: https://doi.org/10.1016/j.mechmachtheory.2021.104649
- Free-interface CMS moving contact DOI: https://doi.org/10.1002/nme.6970

## Search Sources Logged

- Manvelyan et al. primary arXiv record: https://arxiv.org/abs/2102.03653
- Constrained Projective Dynamics DOI page: https://doi.org/10.1145/3450626.3459878
- ABD primary arXiv record: https://arxiv.org/abs/2201.10022
- Distributed ABD primary arXiv record: https://arxiv.org/abs/2605.15875
- M-ABD primary arXiv record: https://arxiv.org/abs/2603.08079

---

## 2026-07-18 MIG Short Paper Week 1 Findings

- Binding claim language is `docs/mig2026_short_paper_plan.md` §1. The row,
  gap/contact point, two-way coupling, modal contact DOFs, momentum consistency,
  and finite-iteration injection observation are not novelty claims.
- The invariant must be written cumulatively, and the 10^5-scale ratio must always
  be identified as peak modal energy divided by incident rigid kinetic energy in
  adversarial low-budget cells.
- Working branch and source starting commit: `impulse-native-constraint` at
  `b39c5d23a426b47d7534ab1060ac8f3773a8ff12`.
- The pre-existing worktree is dirty in unrelated sound/figure/log/export paths.
  Week 1 commits must stage explicit owned paths only.
- Sheth et al. 2015 is user-owned follow-up and remains pending by instruction.
- A0: `paper/sections/40_results.tex` explicitly reports 3 FEM-GT scenes:
  slab, ledge, and dinner. `benchmarks/fem_gt/run_gt.py::SCENES` supports 5:
  truck, ledge, shelf, dinner, and cargo.
- A0: the official MIG 2026 CFP gives 4–6 pages excluding references for short
  papers; `acmart` with `sigconf, screen, review, anonymous`; double-blind review;
  7 August 2026 at 23:59 AoE; and strongly encouraged supplementary material up
  to 200 MB. It gives no duration/codec/container requirement for video.
- A0: official pages are internally inconsistent only in two stale 2025 rows on
  the home page; the dedicated 2026 CFP gives 24 September 2026 notification and
  8 October 2026 camera-ready dates.
- E-S1: all 24 impulse executions were finite and passed both cumulative ledger
  verdicts; none exceeded peak modal energy / incident rigid KE = 1. The range
  was 0.0301514327–0.5314210975, and no governed rerun was required.
- E-S1: the benchmark branch's relaxation axis is not consumed by
  `SolverImpulse`; the two axis values are identical fresh runs. The matrix is
  therefore 24 executions but 12 unique impulse settings.
- E-S1 harness port: native-thin worlds do not synchronize the legacy DCR body
  mirror, so incident KE must be measured from authoritative solver arrays.
  This was a measurement-script correction, not a solver change.

## 2026-07-18 — Review-response pass (plan §6)

- **R0.10 cannot be completed text-only.** Plan §6.2 item 10 asks for the
  21.6 mm worst penetration normalized by slab geometry *and* by "the unclamped
  static sag of the same cell". The geometry half is a scene constant
  (`scenes/reduced_shelf.py`: 0.03 m thick, 0.8 m span → 21.6 mm = 72% of
  thickness, 2.7% of span) and is now in the paper. The **static-sag half is
  frozen nowhere** and needs an instrumented run, which is outside R0's
  "text-only, pre-verified" scope. Plan §6.7 already assigns the normalized-
  penetration presentation to R5, so it is deferred there, not dropped.
- 72% of board thickness is a much starker framing than the bare "21.6 mm" and
  strengthens the Limitations paragraph rather than weakening it — worth
  keeping even after R5 adds the sag comparison.
- **The compshare pod is fresh, not merely restarted.** `~/DCR` and
  `~/dcr-venv` are both gone, so the 2026-07-13/07-18 "pod unreachable" note in
  plan §6.9 and `paper/NUMBERS.md` should become "pod re-provisioned; env
  rebuild required". R7b's cost is no longer "one command" — it is transfer +
  venv + warp install + one command, and the pod link runs ~200 kB/s, so the
  transfer dominates.
- **Transfer gotcha (cost me a wasted cycle):** `tar --exclude='benchmark/'`
  intended to drop the 254 MB top-level `benchmark/` also silently dropped
  **`dcr/benchmark/`** (4 files), because the pattern is matched against every
  path component, not anchored at the archive root. The device run then failed
  on an unrelated-looking import. Use `--exclude='./benchmark'` to anchor it.
  I initially misread the symptom as a truncated stream; it was an over-broad
  exclude. Verify transfers by diffing file LISTS, not counts — the counts
  differed for two independent reasons at once and masked each other.
- The repo is PUBLIC on GitHub while the submission is double-blind, so R7b's
  "push the branch to origin" step (plan §6.9 R7b.1) was replaced, with user
  approval, by a direct tar/scp to the pod. The plan step should be amended.

### R1 (plan §6.3) — measuring Eq. (2) itself

- **Design choice: run the solver's OWN ledger, don't replicate it.** The plan
  says "measurement-only wrappers ... that log per-substep rigid mechanical
  energy ... with the ledger's own formula replicated offline". Replicating it
  offline risks silent drift from the real formula. Instead the harness sets
  `_enforce_modal_passivity = True` (so `deposit()`/`commit()` run live) and
  patches the module-level `passivity_gamma` to return 1.0. In all three
  backends every state write in the ledger block is inside `if gamma < 1.0`
  (`solver_xpbd.py:1244`, `solver_6dof.py:2639`, `solver_impulse.py:1003`), so
  that branch is DEAD and the trajectory is bit-identical to clamp-OFF while
  the accounting is fully live. Non-perturbation is then structural, not
  argued — and it is confirmed empirically: all 8 frozen E-S1b XPBD cells and
  all 3 per-solver worst-over-cells values reproduce EXACTLY.
- **E-S1b caveat 1's "AVBD has no ledger object at all" is a lazy-init
  artifact, not an absence.** AVBD constructs its `PassivityLedger` on the
  first substep (`solver_6dof.py:2449` and `:3057`), whereas XPBD builds it at
  `set_modal_support`. Any harness that grabs `sol._psv_ledger` at setup time
  therefore finds `None` on AVBD and silently measures nothing. Because the
  lazy init is guarded `if self._psv_ledger is None`, pre-constructing the same
  object with the same η makes the solver adopt it. **This is why the AVBD
  Eq.-(2) column was missing, and it was fixable without touching solver
  source.** Anyone re-deriving these numbers must pre-construct the ledger.
- **RETRACTED AND CORRECTED — a bug in MY metric, not in the solver.** My
  first U definition was the plan's literal formula with a RUNNING denominator,
  `(E_mod^n − E_mod^0) / (η·Σ_{k≤n} max(ΔE_rig,0))`, maximised over n. In the
  opening substeps that denominator is ~0 while modal energy has already built,
  so a sub-joule in-transit lead inflates without bound. It reported "AVBD
  violates Eq. (2) in 23/24 cells, U up to 22" — for absolute overdrafts of
  0.01–0.15 J. AVBD shelf 0.7 32×8: raw running U = 20.3 for a 0.13 J overdraw.
  **That would have been a false and easily-destroyed claim.** Caught by
  noticing U = 21.9 in a cell whose peak modal energy (4.98 J) was FIVE TIMES
  SMALLER than its supply (25.3 J) — arithmetically impossible for a real
  overdraw. Two fixes:
    1. **Verdict** is now the ledger's own criterion, in absolute joules:
       `max_net_excess > max_deposit + tol` (passivity.py:287-293). The
       `max_deposit` allowance exists precisely because modal PE can spike in
       the same substep the rigid body is still delivering KE. It is also the
       test behind the paper's governed-run "all 72 cells satisfy Eq. (2)"
       claim, so the un-governed column is now adjudicated identically.
    2. **U** is now peak net modal storage over the run divided by the run's
       TOTAL funded supply — a stable denominator that the opening transient
       cannot inflate.
  Corrected result: AVBD violates in **2/24** cells (dinner 4×1, both relaxes),
  with **U = 1.18 / 1.68** against R = 1.18 / 1.70. So the abstract's original
  "exceeds ... marginally (1.7×)" turns out to be SUPPORTED once Eq. (2) is
  actually measured — the plan's "U > 1 branch". R and U agree closely here.
  **Lesson: a ratio whose denominator accumulates from zero is not a verdict.
  Sanity-check every ratio against the absolute joules before believing it.**
- **The return channel is far larger than the ≲1% plan §6.4 expected.**
  Σ max(−ΔE_rig, 0) / Σ max(+ΔE_rig, 0) measures 3.4–32.2% (XPBD) and
  0.4–27.1% (impulse) across cells, and **exceeds 100% on the AVBD dinner
  cells (109–111%)**, i.e. the gross rigid-energy *gain* there exceeds the
  gross loss. The recycling caveat cannot be waved off as negligible; R2 must
  report these ranges honestly. The AVBD >100% figure needs its own sentence —
  in that scene the rigid subsystem is not monotonically dissipating, which is
  the same family as the impulse box--box rectification already named in
  Limitations.

### R2 (plan §6.4) — pinning the ledger down

- **The paper printed one inequality and the code enforced another.** Eq. (2) as
  written is a strict cumulative net bound. The implementation's `passive()`
  additionally forgives one substep's largest deposit (`max_deposit`,
  `passivity.py:287-293`), which in these scenes is worth **7–389 J**. That is
  not a rounding tolerance; it is the entire difference between AVBD violating
  23/24 cells and 1/24. §2 now discloses it, and both the governed and
  un-governed columns are adjudicated by the strict reading (possible because
  the governed runs satisfy it with a 1.1e-13 J worst margin). This is panel
  blocker #2 in its sharpest form, and plan §6.4 had scoped R2 only to
  "state the ΔE_rig formula and η" — the real gap was larger.
- **`E_mod^0` has two conventions in this repo.** No solver assigns
  `e_modal_0`, so it stays 0 for every CPU number here, matching the paper.
  But two device-arm harnesses REBASE it to the post-first-step modal energy
  (`x5_perf/probe_device_passivity.py:97`, `x5_perf/run_stress_device.py:136`),
  which excludes the settling transient from the numerator instead of funding
  it — a strictly more lenient baseline. The device passivity rows in
  `paper/NUMBERS.md` §4.7/§4.8 ride on that convention. The short paper is
  safe (it claims only monitor-only on the device path, no verdict), but the
  long paper must not quote those rows as evidence for Eq. (2) as printed.
  Found while grep-verifying an anchor I had already written into the ledger;
  the ledger entry was corrected rather than left imprecise.
- **The recycling caveat now stands on data, and the data is worse than
  assumed.** Plan §6.4 guessed ≲1% for the modal→rigid return channel. Measured:
  0.4–27% (impulse), 3–32% (XPBD), **102–118% (AVBD)**. On AVBD the gross rigid
  *gain* exceeds gross loss in every cell, so the supply figure there is an
  upper envelope on genuinely dissipated energy rather than a measurement of it.
  Limitations says so, and attributes it to the same rigid-side energy creation
  as the impulse box–box rectification rather than to the bound.

### R3 (plan §6.5) — controlled comparison

- **Iterations and substeps are NOT interchangeable at equal work.** This is
  the sharpest new result of R3 and it was not anticipated by the plan. At a
  fixed 32 row-evaluations per frame on the shelf drop (same scene, relax and
  machine as E-S2, so the ladders overlay exactly): spent as iterations
  (K=32, S=1) the ratio is **0.300 and Eq. (2) holds**; spent as substeps
  (K=4, S=8) it is **3.13 with a +481 J overdraw**. Substep refinement alone
  does not buy convergence of the contact row.
  - Honest caveat, kept in the paper: the ordering is NOT uniform. At 8
    row-evals substeps are marginally ahead (213.9 vs 265.7); iterations only
    pull away from 16 upward (9.58 vs 68.05). Claiming a clean sweep would
    have been overreach.
- **The budget axis is steeper than its label.** K·S = 4, 16, 64, 256 — each
  rung QUADRUPLES the work and the axis spans ×64, not ×8. I first wrote "×8"
  in the paper and corrected it; plan §6.5's "×4 work ladder" is the per-rung
  factor, not the span. The paper now prints all four counts so the ambiguity
  cannot recur.
- **The energy decay really is constraint convergence.** The complementarity
  residual ‖min(C,λ)‖∞ falls monotonically 2.79e-2 → 3.56e-6 over K=1..128
  (7850×) and bottoms out by K=64 (K=128 agrees to 7 s.f., so the floor is the
  solve, not the budget). The E-S2 energy crossing at K≈24 coincides with the
  residual passing ~3e-5. This closes the "one scalar could shrink by
  coincidence" objection, which the K-convergence figure alone could not.
  - Measured on XPBD only, and the paper says so: AVBD's AL multiplier is not
    the same object and the impulse host is converged at K=2, so a per-host
    residual comparison would be the apples-to-oranges the item exists to fix.
- **Warm start differs between hosts and is intrinsic, not a knob.** XPBD zeroes
  λ every substep (`solver_xpbd.py:1119-1120`); AVBD carries λ AND its penalty
  across; impulse keeps a per-row λ cache. Worth flagging in T2 because a
  reviewer could otherwise read it as an unfair configuration choice.
- **Cross-platform test check (user-requested, NOT a paper number).**
  `test_box_falls_and_settles` fails identically on the ARM M4 and the x86 pod
  (box never leaves y=0.5), so it is PRE-EXISTING and not an x86 artifact —
  which also confirms the server environment is sound, and therefore that the
  R7b device timings are trustworthy. It cannot have been caused by this
  session: no solver source was touched. Distinct from the known ARM/x86
  chaotic-stack divergence, which produces small numerical differences rather
  than a body that never moves.
