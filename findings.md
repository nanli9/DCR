# Literature Gap Audit Findings

## 2026-07-19 MIG Teaser / Visual-Demo Design

- Existing paper evidence separates two kinds of failure that should not be conflated visually. The current shelf `8x2` paper cell is a strong **energy/spectrum** failure (1555.6 J OFF vs 29.26 J ON), but 99.6% of the OFF energy sits in 20.7–24.7 kHz modes that barely affect surface height; it may not look like a dramatic geometric explosion.
- `paper/NUMBERS.md` records older production-budget XPBD blow-up cells at `1x16`, `2x4`, and `1x8`: roughly 5.5e4, 9.2e6, and 3.0e6 J OFF versus 40.8, 36.0, and 42.3 J ON. These are promising visible-demo candidates, but their frozen CSV/config and current-code reproducibility must be checked before recommending one; they cannot be used merely because the scalar energy is large.
- The repository already has an activation-trace benchmark and paper plot but no obvious current OFF/ON scene capture. The current plan/progress explicitly says the R5.3 triptych is blocked on interactive browser capture because there is no offscreen render path.
- A scientifically honest teaser must use identical OFF/ON camera, state, solver budget, timestep, and visualization scale. Deformation magnification is acceptable only if labeled and paired with a true-scale view; rigid trajectories should never be render-exaggerated.
- The short-paper plan already selects the defensible paper comparison: synchronized shelf `8x2`, relax `0.7` frames for ungoverned XPBD, governed XPBD, and the converged reference. A 60--90 s supplementary video was planned around the same-budget OFF/ON contrast plus a reference overlay.
- The legacy production-budget logs make `2x4` the first video-only candidate to inspect (9.24 MJ OFF vs 36.0 J ON and lower logged overhead than `1x8`/`1x16`), but its generalized displacement is only about 4.1 mm. It is not yet evidence of objects visibly flying apart.
- Avoid the worst `4x1` projection cell as the hero visual: the cap bounds energy but permits roughly 21.6 mm penetration, about 72% of the board thickness, so the governed panel would visually advertise the method's largest contact-validity cost.
- The repository contains a purpose-built interactive preset in `scripts/run_native_scenes_viser.py`: `--inject-xpbd` selects the shelf/steel-board scene, symplectic XPBD, and the production `1 iter x 16 substeps` budget. Its own help text identifies this as the genuine ~55 kJ runaway in a ~1 J scene, with violent board ringing OFF and a physical ring ON. This is the best current *visual-demo* lead because it was designed to expose the same frozen `1x16` result, rather than relying on an arbitrary high-energy table cell.
- The nearby `--inject` preset is explicitly an AVBD ledger violation that remains visually stable; it is useful as a selectivity/monitoring secondary clip, not as the XPBD teaser hero.
- In the canonical shelf trace, the ungoverned `8x2`, relax `0.7` energy peak occurs at frame 34 / `t=0.283 s` (1555.56 J); the governed peak is frame 30 / `t=0.250 s` (29.26 J). A synchronized paper frame should therefore use approximately `0.283 s`, with a cursor on the energy plot, rather than independently cherry-picking each arm's maximum.
- The saved governed-accuracy artifact contains 100-frame deflection fields at 48 support sample rows for all four arms (`ungoverned`, `governed`, `xpbd_converged`, `oracle`), so a synchronized OFF/ON/reference surface render can be produced from frozen states without rerunning physics once a small mesh adapter is wired.
- For geometry, frame 31 / `t=0.258 s` is the stronger synchronized still: ungoverned reaches 24.12 mm peak support displacement, versus 5.93 mm governed, 20.48 mm converged XPBD, and 20.00 mm oracle (the latter three peak at frames 31--32). At this same frame the energy trace already separates clearly: 791.9 J OFF versus 28.7 J ON under a 29.6 J budget. Frame 34 is the scalar-energy maximum but the OFF displacement has already crossed near a smaller 2.56 mm magnitude, illustrating why independently choosing the energy peak would make a weak teaser.
- This visible comparison also exposes the method's cost: the governed surface is much flatter than either reference. The caption must say “bounds runaway energy” rather than implying that the cap restores the correct motion.
- The live MIG 2026 CFP does **not** require a teaser image or qualitative figure. It permits 4--6 content pages for short papers (references excluded) and “strongly encourage[s]” supplementary material such as video, up to 200 MB. Therefore an image is a review-communication choice, while a video is strongly recommended but not formally mandatory under the current 2026 wording.
- The 2026 review criteria explicitly include originality, technical quality, clarity, significance, reproducibility where applicable, and relevance. For this graphics/animation paper, synchronized visual evidence directly helps clarity and significance even though the format rules do not mandate it.
- The current short paper already labels the single-column activation-energy plot as `fig:teaser`; it is not missing a quantitative teaser, but it is missing a *scene-level visual*. The strongest revision is therefore to turn Figure 1 into a compact composite (synchronized OFF/ON/reference frames above, existing energy trace below), not to add an unrelated fourth figure.
- The current PDF is seven physical pages with the body ending on page 6 and references on page 7. A new full-width 3x3 image sequence would compete with an exactly full six-page body; the space-efficient paper choice is one synchronized timestamp across three columns, while the time sequence belongs in the supplementary video.
- Page 1 confirms that Figure 1 occupies a compact single-column block beside the abstract. The energy plot is readable, but the reader sees no shelf, impactor, contact state, or deformation. A replacement composite must fit essentially the same footprint: a shallow three-panel frame strip plus a shorter log-energy sparkline, with the caption shortened rather than expanded.
- The Viser demo exposes the needed live toggles and diagnostics (cap checkbox, true/render-only slab-deflection scale, full/static/ring-only view, modal energy, deflection, penetration, and clamp count), but it has no scripted camera or screenshot/recording path. Reproducible capture therefore requires manually locking one client camera or adding a small capture adapter; camera drift between OFF/ON runs would invalidate the comparison.
- The shelf scene is visually legible: a 0.8 x 0.3 x 0.03 m cantilever-like board, five upright books near the fixed side, and a heavy closed book dropped at the free end. The best camera is a locked low three-quarter side view that preserves the board profile and shows whether the standing books launch/topple; a top view would hide the displacement, and an extreme side view would obscure contact layout.
- Existing shelf artifacts are diagnostic plots only; no repository image already provides the required scene-level OFF/ON comparison.
- The dramatic `1x16` preset is not one of the current short paper's plotted 24 matrix cells; the paper only mentions `1x8`/`2x4` as representative production budgets. Therefore `1x16` is excellent for the supplementary video if its configuration/result is disclosed there, but using it as the paper's sole teaser would disconnect Figure 1 from the evaluated `8x2` evidence unless the caption or supplement explicitly bridges that provenance.
- The `--inject-xpbd` preset also changes the shelf material to steel (`E=200 GPa`, `rho=7850`) and relaxation to `1.0`, whereas the canonical paper shelf uses its default soft-board material and the main comparison uses relaxation `0.7`. This materially reinforces the rule: treat `1x16` steel as a separately specified stress/demo case, never as a visual rendering of the paper's `8x2` curve.
- For the paper reference panel, prefer the converged XPBD fixed point (`500x1`) rather than the implicit oracle. That keeps the visual comparison within the same formulation and isolates truncation/governing; the oracle can remain a numerical secondary reference in text/supplement.
- A fresh current-code reproduction of the exact `--inject-xpbd` physics (steel shelf, XPBD `1x16`, relax `1.0`, 100 logged frames) does **not** reproduce the stale help/CSV magnitude exactly: OFF peaks at 17,982 J and ON at 2.13 J. More importantly, true-scale peak support deflection is only 0.642 mm OFF versus 0.0115 mm ON on a 30 mm-thick, 0.8 m-long board. The energy failure is genuine, but the board itself is not a strong true-scale “explosion” still; the help text's “rings violently” likely depends on motion/video, downstream rigid-body response, or render magnification.
- Consequently, any `1x16` stress-case video must first inspect the books' rigid motion. If they do not launch/topple clearly, present this as high-frequency energy runaway using a fixed vibration/velocity color field and a labeled deformation inset, not as a geometric explosion.
- That downstream check succeeds decisively on current code. In the steel `1x16` run, all five resting books launch by 33.4--46.2 mm and move laterally by up to 12.3 mm with the cap OFF, peaking around simulation steps 48--50 (`0.41--0.43 s`). With the cap ON, their upward lift is 0.0 mm (only ~1.0 mm settling, <=0.018 mm horizontal drift). Thus the scientifically legible true-scale event is **spurious launch of the resting books**, not large board bending. Frame the demo around that causal downstream motion.
- The dropped book follows nearly the same 0.5 m descent in both arms, so it supplies a useful visual control: identical incident motion, radically different bystander response. This makes the case much stronger than coloring the board alone.
- The canonical paper `8x2`, relax `0.7` case is also visible downstream: resting-book lift is 15.3--22.9 mm OFF versus 1.6--8.2 mm ON. However, the converged same-host XPBD reference produces 7.7--30.9 mm lift depending on book, while its modal peak is only 8.22 J. This confirms the paper's negative accuracy result in visual terms: the cap suppresses the runaway, but it also suppresses legitimate low-frequency motion and does **not** reconstruct the reference trajectory.
- Therefore a two-panel paper image “OFF explodes / ON correct” would be misleading. The paper teaser should include the converged-reference third panel and use the takeaway “bounded emergency response” rather than “restored physics.” The stress-case video can still use OFF/ON as the dramatic opening, followed immediately by a reference panel/caveat.
- Recommended paper composite, within the current Figure 1 footprint: top strip = synchronized true-scale shelf frames at logged frame 42 / `t=0.350 s` (`XPBD 8x2 OFF`, `XPBD 8x2 + cap`, `XPBD 500x1 reference`), with faint initial-pose ghosts and one locked low three-quarter camera; bottom strip = the existing log-energy trace with a vertical cursor at the same time. At that cursor the trace reads 1102.7 J OFF versus 8.62 J ON under a 30.16 J running budget. Use orange/blue/gray consistently and label “same state, camera, time; true scale.”
- Recommended video opening: the separately labeled steel `1x16`, relax `1.0` stress case, split-screen OFF/ON from independently reset identical initial states. Freeze near `0.42 s`, when the OFF bystanders have launched 33--46 mm and ON remains grounded; then transition to the canonical `8x2` OFF/ON/reference comparison to disclose over-damping. Do not toggle the cap midway through one trajectory and present it as the paired experiment.
- Terminology: call the event “runaway modal energy causing spurious bystander launch” or “finite-budget instability,” not a numerical “explosion,” because the reproduced state remains finite and the support displacement itself is sub-millimeter in the steel case.

## 2026-07-18 MIG Short-Paper Panel Review

- **Supersession notice:** the bullets below were produced from a 4-page build generated at 19:37 PDT. The user-supplied path now resolves to a regenerated 6-page build generated at 23:06 PDT with SHA-256 `8d4b83f9663ded4b91f337577d9aef2f511a561086c1134d3bbdc37b676baa15`. Do not reuse the earlier score until the current artifact is re-audited.
- **Current 6-page rebuild, first text pass:** the manuscript now directly repairs several earlier blockers. It sets `eta=1`; defines modal storage and scene-wide translational/rotational rigid-energy accounting including gravity work; explicitly calls Eq. (2) a cumulative gross-loss-funded storage ceiling rather than contact-port passivity; separates the incident-KE diagnostic from the invariant and plots both; gives a formulation table; reports an equal-work iteration-vs-substep comparison; uses a same-code-path high-iteration impulse reference; corrects the implicit worst ratio to 0.53; and discloses governed contact error, FEM comparison, runtime limits, and scope limitations.
- The revised central result is stronger and more nuanced: XPBD violates the ledger in 8/24 cells, AVBD in 23/24 but usually by under 0.15 J (worst 15.1 J), and implicit impulse in 0/24; enforcement satisfies the printed inequality in all 72 cells, while the paper candidly reports up to 21.6 mm penetration and 8.7x corrective impulse.
- New/remaining technical concern: the text says Eq. (2) is the invariant, then discloses that the implementation's own test forgives one largest substep deposit, while reported violations use the stricter printed Eq. (2). The relationship between the reservoir update/projection and the exact cumulative inequality must be checked carefully; an enforcement mechanism that satisfies the inequality by radial scaling is a certificate by construction, so scientific value rests on physical usefulness, attribution of the gross-loss supply, and comparison with simpler/local alternatives.
- New/remaining evidence concern: the useful response/FEM evidence is for a selected ledge case, whereas the worst governed XPBD cell has visible 21.6 mm penetration. The device path remains monitor-only, and no unqualified real-time claim is made. This is acceptable candor but limits deployability and significance.
- The revised convergence section is materially stronger than the stale audit: it reports XPBD complementarity residual decay, shows self-convergence to a formulation-specific fixed point, and explicitly states that XPBD and the implicit oracle converge to different discrete solutions (including a 6.8 mm trajectory discrepancy). This supports a truncation-pathology claim without falsely claiming cross-formulation equality.
- The supply-recycling limitation is now measured rather than merely acknowledged: opposite-channel rigid gains are 0.4–27% for impulse, 3–32% for XPBD, and 102–118% for AVBD. Especially for AVBD, this makes the scalar gross-loss budget a loose upper envelope rather than a clean measure of contact-dissipated source energy; the abstract's phrase “measured against the energy contact actually dissipated” is therefore stronger than the paper's own §4 caveat supports.
- Eq. (2) enforcement remains CPU float64 only; the RTX 4090 path monitors rather than governs, and governed-vs-full-FEM validation remains future work. The manuscript accurately discloses this, but the core mitigation is not demonstrated in the performance regime or against the physical reference.
- **Current 6-page visual audit:** Figures 1–3 are clean and generally readable; the heatmap and convergence plot communicate the diagnostic well. The paper is nevertheless visually text-heavy for MIG: no scene image, contact-row schematic, governed/un-governed deformation sequence, or full-FEM overlay is shown. Page 2 is nearly all prose/equations, and Table 1 on page 3 is cramped enough that several mathematical entries and wrapped words are hard to parse at normal zoom.
- The title occupies three lines and the abstract is unusually long/dense. Figure captions are also near-paragraph length. Page 6 leaves ample unused space after only seven references, so the manuscript could trade some defensive prose for a small method/scene schematic and a more credible related-work treatment without exceeding the current length.
- The bibliography is notably thin for the breadth of the claim: seven entries, only one direct classic modal-contact reference and two 2026 energy-control preprints. A skeptical numerical-simulation reviewer is likely to ask about reduced/rigid contact formulations, energy-stable modal contact, passivity observers/energy tanks, and contact-consistent projection/optimization alternatives.
- Official MIG 2026 materials checked on 2026-07-18 confirm that the venue invites long and short papers for interactive systems and animation, with the official homepage listing the August 7 deadline. The paper is strongly in scope; acceptance should be calibrated primarily on originality, technical quality, clarity, significance, and reproducibility, not on venue mismatch.
- The official CFP says short papers are 4–6 pages **excluding references**, strongly encourages supplementary video, and names technical quality, novelty, significance, clarity, originality/reproducibility, and relevance as review criteria. The current PDF places references within page 6, so it is not actually using the full allowed content budget; moving references to page 7 would create room for a schematic/qualitative result and fuller definitions.
- Primary-source spot check confirms important omitted neighbors. Hauser–Shen–O'Brien (GI 2003) already demonstrates interactive modal deformation with collision/contact constraints; Kaufman et al. (TOG 2008) gives discrete velocity-level contact for rigid and reduced deformables, discusses iterative-solver energy gain and fixed-budget degradation; Rath (DAFx 2008) specifically targets energy-stable contact of modal objects; classic time-domain passivity-observer/controller work uses monitored energy budgets to stabilize contact. None of these obviously duplicates the exact cross-host measurement plus gross-loss-funded modal-storage ceiling, but omitting them makes the novelty context look selectively narrow.
- **Fresh technical-review issues on the 6-page build:** (i) §2 says the reservoir receives `Delta E_rig` “before the contact solve,” although Eq. (3) requires the substep's post-solve endpoint; the executable update order is therefore impossible or at least misstated and needs pseudocode; (ii) calling cross-substep warm starting “intrinsic to the formulation” is not defensible—reset/carry is a solver-policy choice and may materially drive the XPBD comparison; (iii) `K*S` equalizes row evaluations, not total work, because substeps regenerate contact and repeat integration; (iv) contact compliance/regularization is not matched across the XPBD-rigid, AVBD-penalty, and impulse-CFM rows.
- The paper proves truncation removal only for the position-based host. It does not show an AVBD iteration/convergence curve for the Eq. (2) margin, even though AVBD violates that margin in 23/24 cells. Abstract/conclusion wording that “the amplification is a truncation artifact” should be scoped to the measured XPBD catastrophe unless AVBD is also tested.
- The application argument cites typical deployed budgets near `1x8` or `2x4`, but the main sweep uses `4x1, 8x2, 16x4, 32x8`, and the performance paragraph uses 16x4. The exact claimed target regimes are not evaluated. This is a high-impact reviewer question because the safeguard must be useful, accurate, and affordable precisely where it is supposed to ship.
- The FEM section validates an ungoverned reduced response in one ledge regime, while §4 explicitly leaves governed-vs-FEM validation for future work. The claimed residual 10% mode-truncation error is not supported by a modal-rank sweep in the PDF. The mitigation's accuracy therefore remains the main evidence gap.
- Contribution (3) says “momentum” broadly, but §3.3 measures only instantaneous **rigid linear** momentum across a projection that writes no rigid state, making the zero change true by construction; total/generalized or angular momentum and contact-law satisfaction are not established.
- **Artifact lock:** `paper/main_short.tex` was modified at 23:24:56, after `paper/main_short.pdf` was generated at 23:06:36. The source now contains AVBD contact-validity rows and a governed-vs-converged accuracy analysis that are absent from the reviewed PDF. The panel review must not credit those source-only repairs; final output should name the reviewed PDF SHA-256 and warn the user to recompile before any follow-up review.
- **Fresh five-lens score calibration for the 23:06 PDF:** generalist/fit 3/5 (confidence 4), numerical soundness 2/5 (4), novelty/positioning 3/5 (4), evaluation/reproducibility 2/5 (4), practitioner/short-paper value 4/5 (3). Mean 2.8, median 3. Overall: borderline, leaning weak reject for the PDF as supplied; strong venue fit and a plausible short-paper contribution, but not yet a safely auditable or demonstrably useful mitigation.
- **Final 23:28 compiled build:** 7 physical pages, SHA-256 `e959b15d39d71546c2693bd30b03f104ed4ca7754340202936583bb32d1668cf`. It compiles the source-only repairs: AVBD clamp validity, governed-vs-converged energy/trajectory accuracy, spectral diagnosis of the XPBD high-frequency energy, and a more explicit statement that the projection is a safety envelope rather than an accuracy device. A delta against the 23:27 build is editorial/layout only.
- The new accuracy result is scientifically valuable but adverse to the method: on shelf `8x2`, the governor reduces energy error from 196x to 3.7x while increasing trajectory `L_inf` error from 33% to 71% of the reference peak. It removes the total energy but leaves 97.7% of the remaining energy above 10 kHz and reduces legitimate low-frequency sag. This strengthens the negative/diagnostic-paper framing and weakens any production-cure framing.
- New AVBD rows close the previous selectivity gap: its two `R>1` cells have only 1.4–3.1 mm worst gap violation and <=1.4x impulse/variance effects, materially gentler than XPBD. Governed-vs-full-FEM validation is still explicitly future work, and the claimed actual deployment budgets remain untested.
- **Latest visual/submission check:** page 5 is very dense but readable; page 6 is full; after compression, only the final three lines of the Conclusion spill onto page 7 before the references. Because the official six-page allowance excludes references but not body text, this remains a plausible format-compliance problem. End the complete body on page 6 and start references on page 7.
- The new build still uses only seven references and has no method/scene schematic or qualitative frame. The nearly empty lower 80% of page 7 can hold a much fuller bibliography, but body prose must first be shortened/moved so it remains within six content pages.
- **Recalibrated latest-build panel:** generalist/fit 3/5 (confidence 4), numerical soundness 2/5 (4), novelty/positioning 3/5 (4), evaluation/reproducibility 3/5 (4), practitioner/short-paper value 4/5 (3). Mean 3.0, median 3. Overall remains borderline with a slight weak-reject lean: the new evidence raises evaluation by one point but confirms the governor is an inaccurate emergency brake, while ledger attribution, algorithm ordering, comparison fairness, prior art, and page compliance remain unresolved.
- The most defensible paper identity is the **empirical/negative result**: identical-looking fixed-budget modal-contact rows can exhibit formulation-dependent energy pathologies, and incident-KE ratios can miss pervasive small ledger violations. The projection should be presented as a deliberately crude safety envelope whose contact/accuracy cost is itself part of the result, not as an accurate production cure.
- Acceptance-impact order: (1) correct gross-loss/contact-dissipation terminology and executable ledger ordering; (2) add the missing modal-contact/passivity/energy-projection ancestors; (3) test the actually claimed `1x8`/`2x4` deployment budgets and include governed-vs-reference state/contact error; (4) ablate warm-start/contact matching and rename `K*S` as equal row evaluations; (5) add a scene/row schematic and supplementary video; (6) report total CPU runtime/relative overhead and either enforce on device or keep the deployment claim explicitly monitor-only.
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

### R4 (plan §6.6) — the acceptance criterion FAILED, and that is the result

- **XPBD self-converges to a DIFFERENT fixed point than the oracle.** Plan §6.6
  expected |XPBD(500) − oracle| ≪ the K=32 gap of 2.7e-2. Measured improvement:
  **1.026×**. The ratio plateaus by K≈64 (0.3003 → 0.2996 over K=32..500) at a
  value 9.6% away from the oracle's 0.2735. It is a fixed point, not a tail.
- **The state metrics say the same thing, more strongly.** Peak deflection
  agrees to 2.4%, but the L∞ difference of the deflection trajectory is 6.8 mm
  = **34% of the oracle's own peak**, and flat from K=32 onward. So the two
  hosts agree on scale and disagree on shape/phase.
- **This is expected physics, not a bug, and it improves the paper.** The two
  hosts discretize the same continuous law differently — §1 already says the
  position-level row is one linearization step and an e=0 choice away from the
  velocity-level one. The sweep therefore separates two effects the original
  text conflated: a truncation pathology convergence REMOVES (2.96e4 → 0.30),
  sitting on a formulation difference convergence does NOT (residual 9.6%).
  §3.2 changed from "cured by convergence" to "largely cured ... removes the
  pathology outright", plus a new paragraph stating the plateau.
  A reviewer who ran K=500 themselves would have found this; better that we
  report it.
- **My ring-frequency metric was unreliable and is NOT reported.** The dominant
  FFT peak moved with window length (XPBD 15.6 Hz at 100 frames → 11.2 Hz at
  300). Cause: over these windows the deflection trace is dominated by the
  quasi-static sag, so the spectral peak is the settling envelope, not the
  elastic ring. Caught by re-running at 300 frames specifically to test window
  sensitivity — energy/peak/L∞ were identical to 4 s.f., the ring was not.
  The paper says why it is omitted and points at the resolved full-FEM ring
  comparison (78.0 vs 78.3 Hz) instead. **Lesson, same family as the R1 metric
  bug: verify a derived quantity is stable under a parameter it should not
  depend on, before reporting it.**

### R5 (plan §6.7) — the governed result is bounded, not accurate, and now we know why

- **The plan's headline arithmetic survived a real threat.** R4 had made "the
  converged reference" ambiguous (XPBD self-converges to 0.2996, the oracle sits
  at 0.2735), so R5's predicted "~200× → ~3.7×" could have collapsed. Measured:
  196.5× → 3.696× against the oracle and 189.2× → 3.558× against the
  position-based host's own fixed point. The claim survives under either
  denominator, which is a stronger position than the plan assumed — and the
  boot prompt was right to demand the re-derivation rather than trusting it.
- **THE GOVERNOR MAKES THE TRAJECTORY WORSE. Not anticipated anywhere.**
  Deflection L∞ against the reference goes from 6.5 mm (33% of reference peak)
  ungoverned to 14.3 mm (71%) governed, while the energy error falls ~50×. The
  plan expected a deflection "counterpart" to the energy improvement; it is a
  degradation. Reported as measured. This is the strongest available support for
  "safety envelope, not accuracy device" precisely because it cuts against us.
- **The mechanism, and it resolves an apparent contradiction.** A reviewer would
  immediately ask how the ungoverned run holds 196× the reference energy while
  its peak deflection is only 1.2× too large. Answer, measured at the
  peak-energy frame: the excess is not kinetic (0.3% of the total) and not
  low-frequency. The shelf spectrum is bimodal — ten bending modes at
  20.3 Hz…2.03 kHz, then six stiff modes at 20.7…24.7 kHz — and **99.6% of the
  ungoverned energy sits in the stiff cluster** (centroid 24.1 kHz) against
  **0.0%** for both converged references (centroids 25 and 30 Hz). The substep
  rate is 240 Hz, so that cluster is ~200× above what integrates it. Energy is
  quadratic in frequency; those modes barely move U_yᵀq. So an energy metric and
  a deflection metric measure genuinely different things — which retroactively
  explains R4's split verdict (peak agrees to 2.4%, L∞ differs by 34%).
  - I chose the 10 kHz threshold only after checking the spectrum is bimodal
    with a decade-wide gap (2033 → 20685 Hz), so any cut in 3–20 kHz gives the
    same number. Stated in the paper so it cannot read as a tuned knob. This is
    the third time this session a derived quantity needed a robustness check
    before I would report it, and the discipline paid again.
- **γ is a scalar, so it cannot fix the spectrum — only the total.** It takes
  1555.6 J → 29.26 J while leaving the character untouched (99.6% → 97.7% above
  10 kHz), scaling the legitimate low-frequency sag down along with the noise
  (peak deflection 24.1 → 5.9 mm against a reference 20.0 mm). That is the
  mechanism behind the L∞ degradation above, and it names the next mechanism
  (band-selective projection) without our having built it.
- **R5.4 reframes the penetration more starkly than the geometry did.** The
  21.6 mm worst case is 9–13× the unclamped resting sag (1.7–2.4 mm) and
  **1.05–1.08× the peak dynamic deflection the board ever reaches** (20.0–20.5
  mm). At its worst substep the projection does not reduce the sag, it removes
  all of it. "Resting sag" is defined as a late-window tail median so the
  definition is auditable; the impact transient is excluded deliberately.
- **AVBD's projection is an order of magnitude gentler**, consistent with R1:
  its overdrafts are ≤15 J, so γ bottoms out at 0.60–0.73 and fires on a quarter
  of substeps. Worst violation 1.4/3.1 mm against XPBD's 21.6; corrective
  impulse and multiplier variance within 1.4× against 8.7×/58×. The *relative*
  effect is comparable (3.1/5.5× against 3.5–12.6×), so the hosts differ in the
  scale of the correction, not its character.
- **FOUR silent porting traps** moving E-S3 to the AVBD host, all logged in the
  ledger. The two worth repeating: `sol._q` on that host is the list of body
  QUATERNIONS, not the modal coordinate (E-S3's helper would have computed a gap
  from a quaternion); and **`c_lambda` is a FORCE in newtons**, validated by X1d
  against m·g, so the impulse is λ·h and not the λ/h of the position-based
  probe. I caught the latter by noticing a "steady impulse" of 5052 N·s — four
  orders of magnitude off. The reported quantity is a ratio and was therefore
  never wrong, but the absolute column would have been mislabelled in the CSV.
  **Unit conventions do not survive a port between hosts; re-derive them.**
- **R5.3 (triptych) is BLOCKED, not skipped.** It needs the same interactive
  browser session as the video: `docs/mig2026_submission_package.md` records
  that the viser scripts have no offscreen render path ("Video capture —
  requires an interactive browser session"). Plan §6.12 independently names the
  triptych as the second thing to demote to supplementary on page overflow, and
  the paper is over budget, so both the capability and the page budget point the
  same way. Recorded as a user-interactive TODO rather than quietly dropped.

### R6 (plan §6.8) — the governor's prior art was already half-cited

- **Two of the three works were already in `references.bib` and never cited.**
  `hannaford2002` (time-domain passivity control) and `dinev2018fepr` (FEPR)
  were sitting in the file unused, which means the "simple energy clamp without
  prior-art positioning" criticism was partly a citation-hygiene failure rather
  than a knowledge gap. Only the energy-tank line (`franken2011`) was genuinely
  missing.
- **The new reference was verified, not recalled.** Franken, Stramigioli, Misra,
  Secchi, Macchelli, IEEE T-RO 27(4):741–756, 2011, doi 10.1109/TRO.2011.2142430
  — checked against the University of Twente research record and the publisher
  DOI before it entered the bib. Given this repo's rule about verified
  references, citing a canonical paper from memory would have been the easy
  mistake.
- **The positioning that makes the transplant defensible** is two specific
  deviations, not a general resemblance: the tank is funded by measured gross
  rigid-side dissipation (energy removed *elsewhere*) rather than by the port it
  regulates, and the actuator scales realized *state* rather than modulating a
  force — because a fixed-budget solver has already committed its multipliers by
  the time the excess is observable. That second point is the same structural
  fact that R5.1c shows prevents a band-selective fix, so the related-work
  framing and the limitation now derive from one cause.

### R7 (plan §6.9) — the cost number was wrong twice, and I only found it by re-deriving it

- **The paper attributed an x86-server number to the Apple M4.** §3 states that
  every solver-behaviour number except the device timing was produced on the M4;
  the "+0.8–2.9 ms/step ... on the CPU host" came from
  `x5_perf/out/perf_reps_server.log`. `paper/NUMBERS.md` even carried a "Mac
  cross-check 3.5–4.6×" directly beneath it, so the contradiction was sitting in
  plain sight in our own provenance file. Undisclosed second machines are exactly
  what §3's opening sentence promises do not exist.
- **The headline upper bound was noise.** The 2.9 ms is `dinner xpbd: clamp
  +2.89 ± 2.76` — σ is 95% of μ over 10 repetitions. Re-measured on the M4 the
  same cell gives +1.35 ± 2.08: unresolved on both machines. We were quoting a
  measurement's error bar as its value. **Report σ next to μ, or an effect that
  does not exist will get a headline.**
- **The percentage is the portable quantity, and that is now demonstrated, not
  assumed.** Absolute step times differ 3.5–4.6× between the machines while the
  overhead percentages agree to within 0.02 points wherever both resolve (shelf
  xpbd 1.25% vs 1.23%; ledge xpbd 0.86% vs 0.84%). Plan §6.9 asked for a
  percentage; this is why that was the right request.
- **CPU baselines are 1.3–15× short of 120 Hz**, which reframes §3.5 honestly:
  host-side enforcement is not an interactive path at all, so the device
  paragraph is the motivation for the section rather than a competing claim.
- The defect is flagged in `paper/NUMBERS.md` because the **long** paper's §4.5
  inherits the same number.

### D9 red-team re-read against the five panel blockers (2026-07-19)

Required by the boot prompt's "done means". Verdict per blocker, after R0–R7.

1. **"The metric is not the invariant" (the central attack).** ANSWERED, and
   with the panel's own framing turned into a result. Eq. (2) is now measured
   un-governed on all three hosts (R1), R is explicitly demoted to a severity
   diagnostic in both §3.1 and the Fig. 2 caption, and the case where the two
   genuinely disagree — AVBD, 23/24 vs 2/24 — is reported as the finding rather
   than smoothed over. The abstract's "AVBD exceeds the supply bound (1.7×)",
   which had NO supporting measurement when the panel read it, now does.
   *Residual risk*: a reviewer may object that we report joules rather than a
   normalized quantity. Pre-empted in the caption, which states why every
   candidate denominator misleads.
2. **"The ledger is under-defined."** ANSWERED (R2): every term of Eq. (2) is
   stated in-paper with its code anchor in the ledger, and §2 now discloses that
   the implementation's own test is *weaker* than the printed inequality by one
   substep's largest deposit (7–389 J). We report the stricter reading for both
   columns. *Residual risk*: low — this is the item where we volunteered a
   discrepancy a reviewer would probably never have found.
3. **"Not apples-to-apples."** ANSWERED (R3): Table 1 sources every differing
   entry from the implementation, the two entries most open to a fairness
   challenge (inert relaxation on the impulse host, differing warm start) are
   called out in prose, and work is accounted in row evaluations rather than
   "iterations × substeps". *Residual risk*: the substep sweep moved to the
   supplement for space, so the equal-work claim now rests on one printed pair
   plus a pointer. Acceptable; the ladder is frozen in the ledger.
4. **"Truncation is asserted, not proven."** ANSWERED, and the answer is
   partly negative (R4): the residual is a fixed point, not a tail, and the
   paper says so. This is stronger than the original claim precisely because a
   reviewer running K=500 would have found the plateau themselves.
   *Residual risk*: low, and inverted — the risk was in the previous wording.
5. **"Is the governed result useful?"** ANSWERED (R5), and this is the one
   whose answer is least flattering: the energy error falls ~50× while the
   trajectory error doubles. We report both, name the mechanism (a scalar γ
   cannot deconcentrate energy sitting 200× above the substep rate), and point
   at the band-selective projection we did not build. *Residual risk*: a
   reviewer may read "worse trajectory" as fatal. Mitigation in text: the
   claim was never accuracy — it is boundedness for budgets that otherwise
   diverge, and §3.2 already concedes convergence is the better cure when
   affordable.

**Two blockers are answered with results that cut against us** (4 and 5). That
is the correct posture for a venue with no rebuttal: a reviewer who probes
either one finds we got there first and said so.

**What remains genuinely open**, and is stated as such in the paper: no
device-resident enforced γ; no validation of the *governed* path against
full-FEM; the reservoir is scalar, not per-interface, so the recycling exposure
(102–118% on AVBD) is bounded rather than eliminated; and the R8 mechanism
(deviation-referenced projection) is named as future work, not attempted.

### R8 pre-gate probe — I had the risk attributed to the wrong mechanism

- **The analytical caveat was right that a floor exists, and wrong about where
  it hurts.** I reasoned the γ-independent constant `c` was a risk for the
  panel's deviation-referenced proposal. Measured, it is a much larger risk for
  the **band-selective** variant that §3.3 originally named: infeasible in up to
  **37.8%** of clamp-active substeps (ledge 4×1) versus **0–1.2%** for
  deviation-referencing. Reasoning identified the right mechanism and the wrong
  magnitude; only measurement separated them.
- **The two floors are different physical objects, which is the whole story.**
  The deviation floor is the *settled* sag's strain energy (0.050–0.074 J). The
  band floor is the entire bending band *including its dynamic oscillation*
  (0.91–0.95 J) — 12–20× larger for the same scene. Once stated that way it is
  obvious; it was not obvious from the algebra, because both appear in
  `E(γ) = aγ² + bγ + c` as an undistinguished `c`.
- **The generalizable insight, and the one worth carrying forward**: the floor
  binds *not because the preserved energy is large but because the reservoir is
  nearly empty exactly where the governor matters*. Per-substep budget is
  0.020–0.167 J against modal energies of 137–1030 J. E_low is 0.03–1.0% of the
  modal energy and still exceeds the ceiling up to 38% of the time. **Any**
  floor-bearing projection is therefore most likely to fail in precisely the
  starved cells that justify having a governor.
- **R8a's safety margin is thin and rests on a proxy.** `q_eq` is the *resting*
  equilibrium (tail median of a converged run); a real implementation would use
  the *loaded* one, which is larger during impact, and `c ∝ q_eq²`. The critical
  factor s* = √(ceiling/c) has median **1.74** on shelf 8×2 — a merely 2× larger
  loaded equilibrium puts **60%** of substeps out of reach. So 0–1.2% is a lower
  bound on the true infeasibility rate, not an estimate of it. I only found this
  by asking what the estimate's own sensitivity was, which is now the third time
  this session that habit changed a conclusion.
- **The benefit is visible but I did not claim it.** Preserving a band retains
  most of the excursion the present γ destroys (1.44 → 0.25 mm under the current
  projection, 1.15 mm under band-selective). But the probe measures
  `max_i |U_y·q|`, an *unsigned* excursion, so it cannot tell "sag preserved"
  from "surface displaced the other way" — and the deviation-referenced number
  exceeding the pre-scale value hints at cancellation between `q_eq` and the
  scaled deviation. The claim needs the signed gap. Left unclaimed.
- **Net effect on the paper: none, and that is the useful outcome.** The
  Limitations sentence committed at `a74dfa6` names deviation-referencing (the
  safer variant) and states the floor caveat; both are now measurement-backed
  rather than argued. Had I written the §3.3 band-selective version into
  Limitations instead, the paper would be recommending the variant that breaks
  the guarantee a third of the time.

## 2026-07-19 — codex round 2 (C2–C7): four things worth remembering

**1. `grep` silently fails on the LaTeX log in this sandbox, and it made the
previous session's build claim false.** `grep -c Overfull build/main_short.log`
returns *nothing* — not "0", nothing — while `grep` on the same file for other
patterns also returns nothing and exits 1. The previous session recorded "0
overfull boxes" on that basis. Rebuilding `a74dfa6` proved otherwise: two
overfull hboxes (4.08 pt in T1's modal-weight cell, 1.98 pt in Limitations)
were present all along and are only now fixed. **Read the log with Python, not
grep.** Every gate check in this round used
`re.finditer(r'Overfull[^\n]*', open(log).read())`.

**2. The page budget is bound by float AREA, not word count — and prose cuts
get silently reabsorbed.** Five successive prose cuts (~12 column-lines) left
the overflow at *exactly* 2 lines each time. The mechanism: freeing text lets a
deferred float migrate up a page and consume precisely the space just freed, so
cutting words below the granularity of a float move accomplishes nothing
measurable. What actually moved the page break was reducing float area —
first `fig_s1_solver_matrix` to 0.92\textwidth, then removing two floats
outright (T3's table → prose, C3's algorithm block → an enumerate). Corollary
for the next round: **budget in floats, not words.** Seven floats in a six-page
body was already one per page-column, and the C3 addition alone displaced
Fig. 3 onto its own page.

**3. C6 measured two results that contradict sentences we had already
written** — the deployed budgets did not merely add data, they corrected the
paper:
- §3.5 concluded "host-side enforcement is not an interactive path" from 16×4
  timings. At 2×4, shelf (4.47 ms) and ledge (8.06 ms) fit a 120 Hz budget
  *with the governor on*. The general claim was false; it is now scoped.
- The ledger overhead is **negative and outside noise** on the table scene
  (−4.40 ± 0.50 ms at 1×8): the governed run is genuinely faster, because the
  projection suppresses the divergent deflection that was generating extra
  contact work. Reported as measured, with the mechanism named as a conjecture
  we did not isolate. This is a different phenomenon from the 16×4 table cell,
  where the spread merely exceeded the mean.
- Also: the projection is markedly *gentler* at deployed budgets (worst
  penetration 7.8–9.8 mm vs 21.6, corrective impulse 1.02–1.19× vs 8.7×). The
  headline 21.6 mm is an adversarial-corner number and the paper now says so.

**4. Concurrent benchmark runs corrupt wall-clock, and I nearly shipped it.**
I launched the 2×4 timing sweep while 1×8 was still measuring `dinner avbd`.
Both were killed, the partial CSVs deleted, and both re-run serially. Energy
sweeps are deterministic and unaffected; only timing is. The re-measured
`dinner xpbd` clamp figure (−4.40 ± 0.50) matched the contaminated run's
(−4.65 ± 0.38) closely enough to confirm the negative overhead is real rather
than contention — but that was luck, not method.

**Also worth flagging:** `run_governed_accuracy.py` prints "MISMATCH / FAIL"
for any cell other than 8×2, because its acceptance block compares against
hard-coded 8×2 constants. Running it at 1×8 (a C6 deliverable) therefore
*looks* like a failed measurement and is not. If that harness gains more cells,
the guard should take the expected values per cell rather than as module
constants.

### D-e red-team re-read against BOTH panels (2026-07-19)

Re-read the built PDF against the §6 five-lens set (R0–R8) and this round's
eight (C1–C8). Every blocker from both is answered in-paper **except** the
codex panel's #8 video, which is blocked on interactive capture.

Two gaps the re-read found, and what happened to each:

- **The abstract's "90 measured cells" was not reconstructable from the
  abstract.** It introduced the 24-cell sweep (72 cells over three hosts) and
  then claimed 90 without ever mentioning the 18 deployed cells, which first
  appear in §3.2. Fixed: the abstract now names the 1×8 / 2×4 budgets at the
  point the claim is made.
- **C6's deployed-budget ledger cost is measured but not in the paper.** §3.5
  reports only the 16×4 overhead. The deployed figures (6.6–34.3%, and negative
  beyond spread on the table scene) did not fit the page gate; the sentence was
  written, failed the rebuild, and was reverted rather than forced. It stays in
  E-C6 and belongs to the supplement. A reviewer asking "what does the governor
  cost at the budgets you motivate with?" gets a partial answer in-paper — a
  known, deliberate omission, not an oversight.

Residual exposure a reviewer can still press, all of it already conceded
in-text rather than hidden:

1. **AVBD's pervasive overdraft is measured but untraced.** The K-sweep
   demonstrates truncation for the position-based host only. C4 scoped every
   headline to match; the conclusion now says the augmented-Lagrangian
   overdraft "we measure but do not trace". Honest, but it is a hole.
2. **The governed trajectory is wrong, and the paper leads with that.** After
   C8 it is the first figure: governed sag 5.9 mm against the reference's 20.0.
   A reviewer who wants an accuracy method will reject on this. The paper's
   position is that it is a safety envelope, stated four times.
3. **The supply is an envelope, not a dissipation measurement.** C2 made every
   headline say so, and the recycling numbers (0.4–32%, and 102–118% on AVBD)
   are in Limitations. The AVBD case — gross gain exceeding gross loss in every
   cell — is the weakest point of the funding model and is stated as such.
4. **One machine, three scenes, one contact regime.** Unchanged, and named.

Nothing found in this pass contradicts a frozen number.
# 2026-07-19 Six-Reviewer MIG Short-Paper Review

- Review requested for `paper/main_short.pdf`; artifact hash, page count, and content audit pending.
- Panel design: six isolated AI reviewers use a shared rubric but cannot see one another's conclusions before synthesis.
- Artifact locked: SHA-256 `f36166def1214640a111b68ed89bfa4075381e9d5ff5b1b1036e23ddc7f5ea22`, generated 2026-07-19 05:23:18 PDT, 643,714 bytes, 7 letter-size pages, anonymous ACM/MIG metadata.
- Paper title: “How Much Energy Does a Modal Contact Row Inject? A Cross-Formulation Measurement and a Cumulative Storage Bound.” Page 7 contains references; the conclusion ends on page 6, so compliance depends on whether the current rule permits six content pages plus references.
- Claimed contributions: controlled 24-cell cross-formulation measurement (XPBD, AVBD, sequential impulse), iteration convergence diagnosis, gross-rigid-loss-funded cumulative modal-storage bound with state projection, and explicit measurement of the enforcement/contact-validity cost.
- Central empirical result: XPBD has rare catastrophic underconvergence, AVBD has near-universal but mostly tiny invariant overdraw, and the implicit sequential-impulse realization does not overdraw in the tested sweep. Governed runs satisfy the printed bound in all 90 measured cells.
- The manuscript is unusually explicit about negative results: the projection can reduce modal-energy error while worsening trajectory accuracy, causes up to 21.6 mm post-projection penetration (72% of board thickness), is a safety envelope rather than an accuracy mechanism, and has no device-resident enforcement implementation.
- Bound limitation: supply is scene-wide gross rigid kinetic loss corrected for gravity, not signed contact-port work; it can include unrelated rigid-contact losses and recycle returned/re-dissipated energy. The implementation test has a one-substep allowance although reported violations use the stricter printed inequality.
- Evidence scope: three scenes and one normal-only, zero-restitution regime; reduced/FEM comparison is for the ungoverned response, while validation of the governed path against full FEM remains future work.
- Runtime: CPU baselines are often outside 120 Hz; separate GPU monitor-only path reaches about 5.0–8.9 ms at 16×4 on four scenes, but no device-resident governor exists and the paper avoids an unqualified real-time claim.
- Visual audit: pages 1–6 contain all body text and the conclusion; page 7 is references only. No visible clipping, overlap, broken glyphs, or illegible body text was found at full-page inspection.
- Figure 1 is legible and candidly exposes the method's failure mode, but it is a small line-profile triptych rather than a compelling qualitative animation figure. Figures 2–3 and Tables 1–2 are dense but readable; Figure 2 efficiently carries the cross-formulation result.
- Presentation is highly compressed and qualifier-heavy. The writing is technically careful, but the amount of caveat/detail creates cognitive load for a six-page short paper and can obscure the simple takeaway.
- Page 7 has substantial unused space, but it contains references only; this is not itself a body-page overflow.
- Official MIG 2026 CFP checked 2026-07-19: short papers are 4–6 pages excluding references; long papers are up to 10 excluding references. Therefore the supplied six-content-page plus one-reference-page PDF is length-compliant.
- Official review criteria: originality, technical quality, clarity, significance, reproducibility where applicable, and relevance to motion, interaction, and games. Short papers are explicitly for focused results, emerging ideas, or concise technical contributions; physics-based animation and interactive simulation are listed topics, so venue/category fit is strong.
- Official review format is `\\documentclass[sigconf, screen, review, anonymous]{acmart}` and must include the assigned unique paper ID. The PDF visibly uses the correct anonymous review styling but no paper ID appears; add it before submission after EasyChair assigns it.
- Official submission encourages supplementary material, especially videos, up to 200 MB. This paper would benefit from a short side-by-side animation because Figure 1 shows profiles rather than motion/contact recovery.
- Primary-source spot check supports the manuscript's related-work distinctions: Wei et al. 2026 prove finite-iteration passivity for bilateral port-Hamiltonian subsystem coupling via wave-coordinate Douglas–Rachford splitting, not unilateral modal contact; You et al. 2026 target prescribed total energy in nonlinear barrier-contact elastodynamics; Rath 2008 gives energy-stable contacting modal objects; Kaufman et al. 2008 already covers velocity-level rigid/reduced-deformable frictional contact at interactive rates.
- Novelty therefore appears narrow but plausible: the established contact row, modal coupling, and energy-control genre are not new; the candidate contribution is the empirical cross-formulation truncation diagnosis plus this specific gross-rigid-loss-funded cumulative modal-storage ceiling and its measured failure tradeoff.
- Synthesis risk to watch: because the actuator is a closed-form post-hoc radial state scale and the supply is global gross loss rather than port work, some reviewers may view the bound as too weak/trivial to count as a useful method. Conversely, its candid negative evaluation and the 90-cell diagnostic study can meet a short-paper bar even if the governor is not a production solution.

## Isolated panel returns (sealed from remaining reviewers)

- Reviewer 1 (physics/modal technical): overall 3/7 weak reject, confidence 4/5. Strongly values the truncation diagnosis and candor; treats contact-invalid post-projection states, weak/global supply semantics, absence of governed FEM validation, and uncontrolled formulation differences as acceptance blockers.
- Reviewer 3 (novelty/significance): overall 4/7 borderline leaning accept, confidence 4/5. Finds the governor's ingredients incremental and physically weak, but judges the surprising measurement/diagnosis to narrowly meet the focused-emerging-result short-paper bar.
- Reviewer 2 (contact/numerics): overall 3/7 weak reject, confidence 4/5. Flags causal non-identifiability across unequal hosts, unclear strict-vs-weaker invariant wording, a dimensionally mixed complementarity residual, and contact destruction by the projection; still regards the empirical diagnosis as relevant and unusually candid.
- Early agreement: the empirical XPBD truncation result is the strongest contribution; venue fit and clarity are strong; the governor is not contact-consistent, not contact-port passivity, and should be framed as emergency containment rather than a physical solution.
- Reviewer 4 (evaluation/reproducibility): overall 3/7 weak reject, confidence 4/5. Finds the iteration/spectral diagnosis credible but the per-row injection interpretation, cross-host causal attribution, governed physical validity, and standalone reproducibility insufficient.
- Reviewer 5 (clarity/MIG generalist): overall 3/7 weak reject, confidence 4/5. Finds the paper relevant and the central plots effective, but the constructive contribution replaces blow-up with a visibly invalid state and the dense narrative/ambiguous “one row” framing weakens impact.
- Reviewer 6 (senior PC generalist): overall 5/7 weak accept, confidence 4/5. Explicitly judges the negative diagnostic result alone narrowly publishable at the short-paper bar, provided every formulation-level claim is narrowed to the tested implementations and the governor is described as a diagnostic fail-safe rather than a production method.

## Panel synthesis

- Overall scores: 3, 3, 4, 3, 3, 5; mean 3.50/7, median 3/7. Votes: four weak reject, one borderline/lean accept, one weak accept. Every reviewer reported confidence 4/5. Consensus recommendation: weak reject as currently framed, with a credible path to borderline/accept as a focused diagnostic paper.
- Mean criterion scores: originality 3.00/5, technical quality 3.00/5, clarity 3.83/5, significance 3.00/5, reproducibility 2.50/5, MIG relevance 4.83/5.
- Unanimous or near-unanimous positives: direct MIG fit; short-paper-sized focus; surprising and useful XPBD truncation result; strong iteration/convergence evidence; valuable distinction between ratio severity and invariant margin; unusually honest reporting of failures and runtime limits.
- Unanimous or near-unanimous blockers: post-contact radial state scaling does not preserve complementarity and can cause 21.6 mm penetration/suppressed sag; the gross scene-wide reservoir is not per-contact work or passivity and can cross-fund/recycle energy; the three-host comparison confounds formulation with policy/discretization differences; the governed path lacks full-FEM validation; the PDF alone underspecifies the catastrophic benchmark.
- Panel disagreement is narrow: Reviewers 3 and 6 believe the empirical negative result alone clears or nearly clears MIG's focused short-paper bar. Reviewers 1, 2, 4, and 5 regard the current title/abstract/contribution structure as a method paper whose proposed method is not yet physically usable.
- Fastest acceptance-oriented revision: reframe the paper around the measurement and truncation diagnosis, call the governor an intentionally crude fail-safe/negative baseline, and scope every conclusion to the three tested implementations. Stronger but larger revision: introduce contact-consistent enforcement (joint constrained projection or corrective contact re-solve), prove the exact invariant, and validate the governed trajectory.
- Mandatory technical cleanup: reconcile strict Eq. (2) with the implementation's one-deposit allowance; replace or nondimensionalize `||min(C, lambda)||_inf`; clarify that “one row” means one row law instantiated at many contacts; rename the implicit K=500 and XPBD fixed-point references; add baseline algorithm citations and a minimal self-contained benchmark specification.
- High-value evidence: controlled warm-start/compliance/timestep/modal-cutoff/rank ablations or an independent minimal reproduction; governed-versus-FEM comparison; long-horizon recycling and unrelated-contact stress tests; scale-aware analysis of tiny AVBD margins; attached command/data ledger and a short scene/video overview.

## Current-artifact rerun (17:43 PDT build)

- The PDF changed after the sealed panel: current SHA-256 is `103ac0e1c527f0c4dae9067b7bc1f3185d196f15e441314ee9c7f7d4f54b0033`, modified 2026-07-19 17:43:50 PDT, 686,140 bytes, seven letter-size pages.
- All earlier panel scores are stale until the changed artifact is re-audited; venue-rule findings from the same day may be reused only after a live source check.
- Text extraction confirms the same title and a seven-page anonymous ACM/MIG build. The abstract now foregrounds the strict Eq. (2) overdraw (XPBD up to `4.4e7 J`, AVBD 23/24 cells but at most `15 J`, impulse 0/24) and states that the governed result costs up to `21.6 mm` post-projection penetration.
- Figure 1 is materially stronger than in the stale panel: it presents a synchronized true-scale ungoverned/governed/converged-reference shelf comparison, reports `+93 mm`, `+19 mm`, and peak modal energies, and explicitly admits that the governor removes both spurious launch and some legitimate motion.
- The current method text is unusually explicit that the supply is scene-wide gross rigid kinetic loss rather than contact-port work, can count unrelated rigid-contact loss and recycled energy, and that the implementation enforces a one-substep-weaker test while the paper reports the strict printed invariant.
- The 24-cell result is now presented with two distinct diagnostics: incident-energy ratio and the signed strict-invariant margin in joules. This makes the AVBD result interpretable as 23/24 formal overdrafts but 21/23 below `0.15 J`, while XPBD has 8/24 catastrophic failures up to `4.4e7 J`.
- The iteration study is a strong causal diagnostic within the XPBD implementation: with substeps fixed, the ratio decreases monotonically from `2.96e4` at `K=1` to about `0.300` at `K=32`, near a different-formulation implicit reference of `0.2735`; the XPBD self-fixed point remains about `0.2996`. The manuscript correctly separates truncation removal from formulation-level fixed-point disagreement.
- The constructive mechanism remains scientifically limited. The radial `(q,qdot)` projection is post-contact and does not re-solve constraints; in load-bearing cells it opens up to `21.6 mm` penetration, produces up to `8.7x` corrective impulse and `58x` multiplier variance, can worsen trajectory error, and leaves the high-frequency spectral character largely unchanged.
- The ungoverned reduced model has useful full-FEM evidence (frequency within `0.4%`, far-field Spearman `rho=0.89`, timestep convergence), but the governed trajectory itself still has no full-FEM validation. Runtime evidence separates CPU enforcement from an RTX 4090 monitor-only path and avoids claiming device-resident governed real time.
- Potential technical/presentation concerns to test with reviewers: (i) the paper names Eq. (2) as the bound although the implemented enforcement test is explicitly weaker; (ii) `||min(C, lambda)||_inf` mixes quantities with different units unless normalized; (iii) the cross-host sweep holds scenes/settings fixed but not contact policy/discretization/warm-start, limiting causal formulation claims; (iv) the supply is an upper envelope with measured recycling as high as `118%` in AVBD.
- Visual audit pages 1–4: the ACM review layout is clean with no overlap/clipping and expected red line numbers. Figure 1 now communicates the failure and tradeoff much better than the stale build, although its three scene thumbnails and energy trace are small at full-page scale. Figure 2 is an effective, readable six-heatmap summary. Table 1 is information-dense with tight wrapping but legible when zoomed.
- The PDF visibly lacks an assigned paper-ID line. Its auto-generated reference format says “7 pages,” which is total PDF length rather than six content pages; this is not a scientific defect but should be checked against the submission template/metadata.
- Visual audit pages 5–7: Figure 3 and Table 2 are clear, though the plot still labels `R=1` as “injection threshold” while the paper carefully distinguishes that ratio from the actual invariant. Page 6 is dense but clean.
- Crucial format finding: the conclusion does **not** end on page 6. Four lines of conclusion appear at the top of page 7 before the references. If MIG's “4–6 pages excluding references” means all non-reference content must fit within six pages, the current artifact is over length. This is easily repairable because page 7 has large unused space, but it must be fixed before submission.
- All seven pages render without clipping, overlap, broken glyphs, or unreadable text. The reference list is complete-looking but unusually short (14 entries) for the breadth of adjacent passivity/contact work; novelty reviewers may ask whether the positioning is sufficiently comprehensive.
- Live-source check: the official MIG 2026 site is `https://mig.siggraph.org/2026/`, confirms the 2026 venue/dates and paper window. The first domain-restricted query returned no indexed results; a broader search found the official site. The exact papers subpage still needs to be opened for the authoritative page-limit/rubric wording.
- Official MIG 2026 CFP verified live at `https://mig.siggraph.org/2026/papers.htm`: short papers are 4–6 pages excluding references; the page explicitly says content should fit the six-page limit. Because current page 7 contains conclusion text before the references, the supplied build is noncompliant as rendered.
- The official review rubric is technical quality, novelty/originality, significance, clarity, reproducibility where applicable, and relevance. Short papers are framed as focused results, emerging ideas, or concise technical contributions; physics-based animation and interactive simulation are explicit topics, so category/venue fit is direct.
- The official review command matches the manuscript's `sigconf, screen, review, anonymous` appearance, but the CFP also requires the unique paper ID assigned by EasyChair. No such ID is visible in the current PDF.
- PDF packaging check: all listed fonts are embedded/subsetted and text extraction works. There are no embedded file attachments. `qpdf` is unavailable, but Poppler rendered every page without structural/rendering errors.

### Fresh isolated panel returns (hash `103ac0e...`)

- Reviewer 3 (novelty/significance): **5/7 weak accept**, confidence **4/5**; criteria originality 3, technical 4, clarity 4, significance 3, reproducibility 3, MIG relevance 5. Judges the controlled measurement and convergence evidence narrowly sufficient for a focused short paper despite an incremental/crude governor. Flags the global recyclable supply, implementation-level confounds, narrow spectrum/contact coverage, missing governed FEM/device validation, incomplete standalone setup, page-7 body spill, and missing paper ID.
- Reviewer 1 (physics/energy): **3/7 weak reject**, confidence **4/5**; criteria originality 3, technical 3, clarity 4, significance 3, reproducibility 2, MIG relevance 5. Values the direct invariant measurement, XPBD self-convergence evidence, and unusually candid failure accounting. Treats the nonlocal/recyclable reservoir, mechanically inconsistent post-contact projection, dimensionally mixed residual, under-resolved high-frequency spectrum, uncalibrated tiny AVBD margins, missing governed FEM validation, page overflow, and paper-ID omission as decisive in the current form.
- Reviewer 2 (contact/numerics): **3/7 weak reject**, confidence **4/5**; criteria originality 3, technical 3, clarity 4, significance 3, reproducibility 2, MIG relevance 5. Adds two important numerical concerns: gross positive rigid loss is substep-partition dependent, while the reservoir's positive-increment debit is stricter than Eq. (2), so the measured correction cost is not necessarily intrinsic to the stated bound. Also rejects per-row/causal formulation language without matched controls, numerical-drift calibration, normalized KKT residuals, and reproducible setup detail.
- Reviewer 4 (evaluation/reproducibility): **4/7 borderline**, confidence **4/5**; criteria originality 3, technical 4, clarity 4, significance 3, reproducibility 3, MIG relevance 5. Leans weak accept on scientific merit because of the diagnostic breadth and candid negative evaluation, but rejects the current upload if format rules are enforced. Requests convergence on the worst ledge/deployed cells, matched-cost and competing-mitigation baselines, robustness/tolerance studies, long-horizon reservoir tests, governed FEM validation, and a complete submitted artifact.
- Reviewer 5 (clarity/MIG practitioner): **3/7 weak reject**, confidence **4/5**; criteria originality 3, technical 3, clarity 4, significance 3, reproducibility 3, MIG relevance 5. Finds Figures 1 and 3 effective and the failure diagnosis useful to practitioners, but regards the governor as a blunt emergency limiter. Flags dense prose/Table 1, ambiguous dual reference terminology, missing immediate coupled-momentum/velocity-complementarity analysis, unexplained AVBD behavior, narrow scope, untagged PDF accessibility, and both submission-rule violations.
- Reviewer 6 (senior PC): **3/7 weak reject**, confidence **4/5**; criteria originality 3, technical 3, clarity 4, significance 3, reproducibility 2, MIG relevance 5. Says the empirical diagnostic alone could be publishable if the governor is explicitly a crude fail-safe and claims stay implementation-specific. Its stated blockers were the missing paper ID, self-contained reproducibility, and an alleged Eq. (1) sign inconsistency.

### Factual reconciliation

- Current artifact hash rechecked after all six reviews and remains `103ac0e...`.
- Reviewer 6's alleged Eq. (1) sign inconsistency is a false positive caused by the small rendered parentheses/text extraction. The PDF renders `C = y_c - (y_rest + U_y^T q)`, so `dC/dq = -U_y` is consistent; the TeX source confirms the same. This concern is excluded from the consensus blockers and does not affect the panel score.

### Fresh-panel synthesis

- Overall scores in reviewer order: `3, 3, 5, 4, 3, 3`; mean `3.50/7`, median `3/7`. Vote split: four weak rejects, one borderline, one weak accept. All six confidence scores are `4/5`. Consensus is **weak reject for the current PDF**, with the scientific case near the accept/reject boundary once format defects are fixed.
- Mean criterion scores: originality `3.00/5`, technical quality `3.33/5`, clarity `4.00/5`, significance `3.00/5`, reproducibility `2.50/5`, MIG relevance `5.00/5`.
- Unanimous/near-unanimous strengths: excellent MIG fit; a focused short-paper-sized question; valuable separation of catastrophic XPBD failures from tiny AVBD overdrafts; strong within-XPBD iteration/self-convergence evidence; effective new Figure 1; unusually honest measurement of failure, accuracy, runtime, and recycling costs.
- Unanimous/near-unanimous scientific concerns: the reservoir is a global, recyclable upper envelope rather than contact-local work/passivity; the radial post-contact projection can destroy complementarity and legitimate sag; cross-host differences prevent formulation-class causal claims; the governed path lacks full-FEM/device validation; and the PDF alone is not independently reproducible.
- Additional high-value numerical concerns: the positive-loss supply is substep-partition dependent; tiny AVBD margins need drift/tolerance/precision controls; `||min(C,lambda)||` needs unit-consistent normalization; and the printed invariant, stricter positive-increment ledger policy, and one-deposit-forgiving test need one aligned statement/proof.
- Administrative verdict is unambiguous: do not upload this exact PDF. Four conclusion lines occupy page 7 despite the six-content-page limit, and the required EasyChair paper ID is missing. The stale `injection threshold` label in Figure 3 should also be corrected to avoid contradicting the ratio-vs-invariant distinction.
- Fastest acceptance path: make the measurement/truncation diagnosis the primary contribution; describe the governor as a deliberately crude emergency fail-safe or negative baseline; rename “one row” as a row law instantiated across contacts; restrict claims to the three tested implementations; and add a minimal reproduction package plus targeted controls (worst-cell convergence, supply partition/long-horizon recycling, AVBD drift tolerance, and modal-cutoff/rank sensitivity).
- Stronger but slower method path: contact-local signed accounting plus a contact-consistent correction/re-solve, followed by governed full-FEM and device-resident validation. This is not necessary if the submission is honestly positioned as a diagnostic short paper.

## Current PDF + video-supplement review

- Review opened for the exact current PDF and supplied MP4.
- PDF lock: SHA-256 `627a14ed87af9588a49afebd70ed2c8e4c009251bfa272180db9569c4a131914`, generated 2026-07-19 20:39:46 PDT, 730,379 bytes, seven letter-size pages, untagged but structurally parseable.
- Video lock: SHA-256 `6dcd9042f57bce0faf213d4e5e690bb7ef989a2d138bfa6c0ce107a60f51fd8a`, modified 2026-07-19 17:43:00 PDT, 44.77 s, 1920x1080, H.264/YUV420p at 30 fps, video-only stream, 1.39 MB.
- The PDF hash differs from the previously reviewed `103ac0e...`, so all prior scores are stale. Full content and visual delta remain pending.
- First visual audit: all seven pages render cleanly with no visible clipping, overlap, broken glyphs, or unreadable body text. The conclusion now ends on page 6 and page 7 is references only, fixing the earlier body-page overflow. The bibliography has expanded to 18 entries. The PDF still visibly shows only anonymous/`Anon.` metadata and no assigned paper ID.
- The paper's current visual story is coherent: Figure 1 contrasts ungoverned, governed, and converged-reference behavior; Figure 2 gives the cross-host 24-cell diagnostics; Figure 3 provides within-XPBD budget convergence; Table 2 explicitly reports contact-validity costs. Density remains high, especially Table 1 and pages 3–6.
- Video sheet 1 (ordered 2-second samples, approximately 0–22 s) is legible and scientifically candid. It introduces the question, then shows identical-camera/true-scale steel-board ungoverned versus governed runs and a K=500 reference. The ungoverned launch is visibly obvious, while the governed state is close to the reference in the steel case. It then transitions to a soft-board case with the explicit warning that the bound can suppress legitimate motion.
- Video sheet 2 (approximately 24–44.8 s) completes the counterexample rather than hiding it: the soft-board governor removes the spurious launch but also under-moves the books relative to K=500; the title states “bounded, but not faithful.” It then plots the invariant and closes with “Boundedness, not trajectory recovery,” the 90-cell claim, measured contact-validity cost, and the CPU-host-side/no-unqualified-real-time disclaimer. The supplement therefore materially improves qualitative understanding and claim honesty, but it cannot cure the missing contact-consistent/accuracy validation.
- Current abstract/contributions are more defensible than the stale build: the governor is explicitly a “deliberately minimal fail-safe,” not a constructive contact method; the paper distinguishes the scene-wide gravity-corrected gross rigid loss from per-contact dissipation; and it reports 90 measured cells / 78 distinct configurations including deployed 1x8 and 2x4 budgets.
- Central headline evidence remains: XPBD has catastrophic starved-budget cells (up to 4.4e7 J invariant overdraw and 1.2e5 incident-energy ratio), AVBD formally violates in 23/24 cells but by at most 15 J, and the tested impulse realization violates in 0/24. Within-XPBD iteration convergence closes the gap to an implicit K=500 reference by six orders of magnitude.
- Method audit: Eq. (2) is explicitly scoped as a cumulative gross-loss-funded modal-storage ceiling, not contact-port passivity or signed interface work. The enforced recursion is acknowledged to forgive one substep's largest deposit (7–389 J); Proposition 2.1 proves only that weaker recursion, while strict Eq. (2) is empirically observed in all governed cells (worst margin 1.1e-13 J). This honesty improves clarity but leaves a real theorem/implementation/claimed-invariant mismatch.
- The comparison is explicitly “as deployed, not compliance-matched”: XPBD resets multipliers, AVBD carries dual/penalty state, and the impulse host warm-starts rows. That is appropriate for an implementation survey but prevents strong formulation-class causal claims. Equal `K*S` also does not mean equal runtime or algorithmic work; the paper now says so.
- Robustness evidence is materially stronger: 24/24 perturbations around the two worst cells still violate Eq. (2) across timestep, compliance, rank, and damping; removing the stiff modal cluster reduces severity by 286x/36x but leaves positive overdraw; the worst ledge cell converges from `R=8.5e5` to `0.165` over `K=1..32`.
- Evaluation remains double-edged. The governor reduces a representative energy error from 196x to 3.7x, yet worsens trajectory error from 6.5 mm to 14.3 mm; at deployed 1x8 it improves trajectory only from 108% to 96% of reference peak. The mechanism largely rescales rather than fixes the spectrum (99.6% stiff-band energy becomes 97.7%) and reduces legitimate sag.
- Contact validity is a major scientific limitation, not a hidden implementation detail: post-projection scaling can open 21.6 mm penetration, require up to 8.69x next-step corrective impulse, and increase multiplier variance up to 58x because contact is not re-solved.
- Full-results/limitations audit: ungoverned reduced-vs-full-FEM validation is respectable (frequency within 0.4%, far-field Spearman `rho=0.89`, timestep convergence toward a residual ~10% rank-truncation gap), but governed-vs-FEM validation is explicitly future work. Runtime is carefully scoped: CPU ledger overhead is typically 0.9–3.4%; a separate RTX 4090 path is monitor-only at 5.0–8.9 ms, with no device-resident enforced governor and no unqualified real-time claim.
- Supply weaknesses remain central: returned modal energy can be re-credited (measured opposite channel 3–32% for XPBD, 0.4–27% impulse, 102–118% AVBD), the scene-wide gross sum can cross-fund unrelated losses, and the positive-loss rectification depends on substep partition. The paper states all three limitations clearly.
- Submission packaging check: all fonts are embedded/subsetted; text extraction succeeds; no embedded attachments exist. Page 7 is references only. The PDF is untagged (minor accessibility/readiness issue) and no paper-ID text is present. The visual `ACM Reference Format` reports “7 pages,” which is total PDF pages and not itself a length violation.
- Live official MIG 2026 rubric confirmed: short papers are 4–6 pages excluding references and are intended for focused results, emerging ideas, or concise technical contributions; physics-based animation and interactive simulation are explicit topics. Reviews consider originality, technical quality, clarity, significance, reproducibility where applicable, and MIG relevance.
- Current submission-format status: six body pages plus a references-only seventh page is compliant; anonymous `sigconf, screen, review, anonymous` styling appears compliant. The official call requires the EasyChair-assigned unique paper ID, which is absent from this PDF and must be added before submission. The 1.39 MB video is comfortably under the 200 MB supplement allowance and is exactly the sort of motion evidence the call encourages.
- Video integrity check decoded all 1,343 frames without error. Page-1 close inspection confirms Figure 1 is readable and provides an immediate true-scale visual claim, though its thumbnails/trace are necessarily small; the video is therefore not redundant and materially improves perceptual legibility.
- Close inspection of pages 5–6 found no layout or legibility defect. Figure 3 and Table 2 are clear at page scale, and the limitations/conclusion are unusually direct. The tradeoff is compression: pages 5–6 carry convergence, robustness, contact validity, FEM comparison, runtime, and four major limitation classes in dense prose, so readers may miss the measurement-first narrative despite good local writing.
- Supplement anonymity check: MP4 metadata contains only generic `VideoHandler` and FFmpeg/libx264 encoder tags; no author, creator, title, or identifying comment was found.

### Fresh six-reviewer returns (PDF `627a14e...`, MP4 `6dcd904...`)

- Reviewer 1, physics/modal energy: `5/7` weak accept, confidence `4/5`. Accepts the narrow empirical diagnostic; flags the Eq. (2)/Proposition mismatch, non-port scene-wide supply, inconsistent reference naming, and absent reproducibility ledger.
- Reviewer 2, contact numerics: `3/7` weak reject, confidence `4/5`. Finds the within-XPBD convergence evidence strong but treats proof/indexing ambiguity, post-projection contact invalidity, cross-host confounds, and per-row framing as blockers.
- Reviewer 3, novelty/significance: `4/7` borderline leaning reject, confidence `4/5`. Finds the measurement close to the short-paper bar but wants an isolated/matched causal experiment; judges the fail-safe incremental relative to energy projection/passivity/modal-contact prior work.
- Reviewer 4, evaluation/reproducibility: `3/7` weak reject, confidence `4/5`. Values the controls and candor but finds solver-class attribution, strict-bound framing, usefulness baselines, governed validation, and standalone reproducibility insufficient.
- Reviewer 5, clarity/MIG practitioner: `5/7` weak accept, confidence `4/5`. Finds the empirical warning, limitations discipline, and video sufficient for a focused short paper; requests guarantee reconciliation, full artifacts, narrower cross-host language, and consistent reference terminology.
- Reviewer 6, senior-PC generalist: `5/7` weak accept, confidence `4/5`. Judges the diagnostic alone publishable at the short-paper bar; the governor is acceptable only as a crude audited emergency envelope.

### Reconciled panel

- Scores: `5, 3, 4, 3, 5, 5`; mean `4.17/7`, median `4.5/7`. Numerical split: three weak accepts, one borderline, two weak rejects; advice split: three accept versus three reject/lean-reject. All confidence scores are `4/5`.
- Mean criteria: originality `3.17/5`, technical quality `2.67/5`, clarity `4.00/5`, significance `3.33/5`, reproducibility `2.00/5`, MIG relevance `5.00/5`.
- Unanimous/near-unanimous strengths: exact MIG fit; compelling within-XPBD iteration/convergence diagnosis; useful separation of incident-energy severity from the joule-valued inequality; strong negative-result candor; clear six-page presentation; video communicates success and failure honestly.
- Unanimous concerns: strict Eq. (2) is observed while Proposition 2.1 guarantees the one-deposit-relaxed property; the supply is scene-wide/recyclable/schedule-dependent rather than contact-port work; host differences block solver-class causality; post-contact radial scaling can invalidate constraints and fidelity; the governed path lacks FEM/device validation; the claimed ledger/code/data are absent from the supplied supplement.
- Important terminology defect: Figure 1/video call the XPBD `K=500` self-fixed point the “converged reference,” while §3.2 uses “converged reference” for the implicit `K=500` realization and separately names the XPBD fixed point.
- Supplement verdict: strong positive effect on clarity and qualitative credibility, but only for the XPBD shelf case. It does not visualize penetration or support the cross-host, FEM, runtime, or reproducibility claims.
- Area-chair calibration: scientifically borderline, leaning weak accept under the focused short-paper bar because the diagnostic can carry the paper independently of the crude governor. It would be a reject if evaluated as a validated contact-control method. This is not a safe accept.
- Highest-priority pre-submission work: (1) reconcile/prove or rename the exact invariant; (2) attach the referenced anonymous ledger, commands, configs, raw plot data, hashes, and code/data snapshot; (3) use “three tested implementations”/“row law” consistently and standardize reference names; (4) add the assigned EasyChair paper ID; (5) if one experiment is possible, add an isolated or physics-matched contact control/matched-residual comparison. A video penetration close-up is useful but secondary.
- Final hash recheck after all reviews matched both frozen artifacts exactly.

## 2026-07-20 current-artifact panel

- PDF lock: SHA-256 `276cc3750e33d44bf668061c295c9e348d76c5e6d43ae95a18176fe3e1a53fc5`, generated 2026-07-20 00:05:58 PDT, 732,900 bytes, seven letter-size pages.
- Video lock: SHA-256 `30a862facd530dd31741e41ef1774582f2d46d42ad3043ce5bc56f5a267a5d54`, modified 2026-07-20 00:02:12 PDT, 44.77 s, 1920x1080, H.264 at 30 fps, video-only.
- Both hashes differ from the 2026-07-19 reviewed artifacts (`627a14e...` and `6dcd904...`), so the earlier 4.17/7 panel is stale and will not be reused.
- Current paper framing is unusually explicit: the shared modal contact row is established prior art; the new contribution is a cross-implementation fixed-budget measurement plus a deliberately minimal gross-loss-funded storage governor.
- The strict storage ceiling Eq. (2) and the guaranteed one-deposit relaxation Eq. (4) are now clearly separated. Proposition 2.1 claims only Eq. (4), while strict Eq. (2) is empirical in all 90 governed cells; the maximum one-deposit allowance is reported as 7–389 J.
- Central evidence remains strong as a diagnostic: XPBD violates the gross-loss invariant in 8/24 cells with a catastrophic worst case; AVBD violates in 23/24 by small absolute amounts (worst 15.1 J); the tested implicit sequential-impulse implementation violates in 0/24. A within-XPBD K sweep links the catastrophic case to truncation and also shows a residual discrete-solution difference.
- The paper candidly measures the governor's failure modes: trajectory error can worsen, legitimate sag and motion are suppressed, stiff-spectrum content is rescaled rather than repaired, and post-projection contact can open up to 21.6 mm penetration with up to 8.69x corrective impulse and 58x multiplier variance.
- Claim scope is careful but the core scientific limitation remains: the supply is a scene-wide rectified rigid kinetic loss, not signed contact-port work; it can cross-fund unrelated losses, recycle returned energy, and vary with substep partition. The governed path is not validated against full FEM or enforced on the device-resident implementation.
- The PDF says every number is frozen in a supplemental ledger, but the user supplied only the MP4 for this review; absent a separate artifact, those commands/data/hashes cannot be credited as reviewer-accessible reproducibility evidence.
- Live official MIG 2026 CFP rechecked 2026-07-20 at `https://mig.siggraph.org/2026/papers.htm`: short papers are 4–6 content pages excluding references; the current six-body-page plus references-only page 7 layout complies. Physics-based animation and interactive simulation are explicit topics, so venue relevance is strong.
- The official review criteria are originality, technical quality, clarity, significance, reproducibility where applicable, and MIG relevance. The review PDF must be anonymous and include the EasyChair-assigned unique paper ID; no paper ID is visible in this artifact, so it is not upload-ready unless the ID has not yet been assigned.
- Visual PDF audit: all seven pages render cleanly, no body text spills onto page 7, figures/tables are legible at page scale, and there is no clipping or overlap. Pages 2–6 are dense but professionally laid out. Figure 1 communicates the principal success/failure tradeoff immediately.
- Complete video audit: all 1,343 frames decode without error; the 44.77 s supplement has no audio stream and no identifying metadata beyond generic FFmpeg/libx264 tags. Ordered two-second samples cover the entire runtime with no missing segment.
- The video is a strong, candid qualitative supplement. It first shows a steel-board case where the ungoverned 1x8 XPBD run launches books while the high-iteration self-reference barely moves, then a soft-board case where the reference legitimately moves and the governor suppresses that motion. It closes with the measured budget plot and the explicit message "Boundedness, not trajectory recovery."
- The revised video consistently labels the high-iteration comparator `XPBD self-reference (500x1)`, states three independent runs/true scale, identifies the CPU float64 host, reports the 90-cell coverage, and disclaims an unqualified real-time claim. This fixes the previous comparator-label ambiguity.
- Supplement impact is positive for clarity and reviewer trust, but narrow: it visualizes one XPBD shelf family and does not show the worst post-projection penetration, AVBD/impulse behavior, full-FEM comparison, or device-resident results.
- Packaging audit: all PDF fonts are embedded/subsetted, text extraction succeeds, and the PDF contains no embedded files. Artifact hashes remained unchanged through the complete primary audit.

### Isolated reviewer returns (in arrival order)

- Reviewer 3 (novelty/significance): `5/7` weak accept, confidence `4/5`. Finds the carefully scoped diagnostic sufficient for a focused short paper, while rating the governor incremental, cross-host evidence implementation-level, generality narrow, and practical utility preliminary. Most important revision: a controlled fixed-schedule/second-implementation ablation isolating the cause.
- Reviewer 1 (physics/energy): `5/7` weak accept, confidence `4/5`. Values the truncation evidence and candor but identifies a central internal inconsistency: the written credit/project/debit recursion appears to imply strict Eq. (2), not merely relaxed Eq. (4). Most important revision: precisely index the reservoir chronology and make theorem, pseudocode, and reported guarantee agree.
- Both reviewers independently derived the same strict-bound concern: with same-substep credit and post-projection debit, nonnegative `B` appears to imply cumulative positive modal increments cannot exceed cumulative credited supply. This is now a likely technical correction, not a stylistic preference.
- Reviewer 2 (contact numerics): `4/7` borderline, lean reject, confidence `4/5`. Praises the diagnostic and candor but considers the `1x8` versus `500x1` reference schedule confounded given the paper's own substep-partition dependence, the cross-host comparison implementation-level, and the post-projection contact damage too large for a production mechanism. Most important revision: schedule-matched converged references and a fuller `K x S` control matrix.
- Reviewer 2 independently repeats the strict-Eq.-(2) derivation concern. All first three reviewers therefore agree that the theorem/indexing language must be corrected before submission.
- Reviewer 4 (evaluation/reproducibility): `3/7` weak reject, confidence `4/5`. The decisive issue is that the PDF repeatedly delegates commands, raw rows, source anchors, configurations, and timing factors to a supplemental ledger, while the review packet supplied here contains only the MP4. Also flags implementation confounds, no governed-path independent validation, weak long-horizon supply semantics, and no equal-wall-clock alternative. Most important revision: attach a complete executable reproduction package.
- Reviewer 4 becomes the fourth of four returns to independently identify the Eq. (2)/Eq. (4) indexing issue. Its rejection is materially conditional: the score could change if the promised anonymous ledger/code/data archive is actually submitted alongside the video.
- Reviewer 5 (clarity/practitioner): `5/7` weak accept, confidence `4/5`. Finds the empirical diagnosis and honest audit useful to MIG practitioners, but says the target/guarantee/observation taxonomy is still too easy to misread, solver labels invite class-level generalization, the title overstates row-local measurement, and practical eta guidance is absent. Most important revision: explicitly separate Eq. (2) as the desired budget, Eq. (4) as the claimed formal guarantee, and Eq. (2)'s observed satisfaction.
- Reviewer 6 (senior generalist): `5/7` weak accept, confidence `4/5`. Judges the narrow diagnostic sufficiently substantiated for a focused short paper, provided conclusions remain implementation-specific and the governor is treated only as a safety envelope. Most important revision: controlled attribution ablations or uniformly narrower cross-formulation language.

### Reconciled 2026-07-20 panel

- Overall scores in reviewer order: `5, 4, 5, 3, 5, 5`; mean `4.50/7`, median `5/7`. Votes: four weak accepts, one borderline/lean reject, one weak reject. All confidence scores are `4/5`.
- Mean criteria: originality `3.25/5`, technical quality `3.33/5`, clarity `3.92/5`, significance `3.42/5`, reproducibility `2.42/5`, MIG relevance `4.75/5`.
- Unanimous strengths: direct MIG fit; memorable and well-supported XPBD truncation pathology; useful separation of incident-energy severity from the joule-valued budget; unusually candid limitation analysis; clean six-page presentation; and a video that honestly demonstrates both the success case and lost legitimate motion.
- Unanimous or near-unanimous concerns: Eq. (2)/Eq. (4) guarantee/indexing inconsistency; implementation rather than formulation-level cross-host evidence; scene-wide recyclable and schedule-dependent supply rather than contact-port work; large post-projection contact/fidelity costs; no governed full-FEM/device validation; and absent reviewer-accessible ledger/code/data in the specified packet.
- Area-chair calibration: **borderline weak accept as a focused empirical diagnostic**, not as a validated contact-control method. The governor alone would not clear the bar. The score is not a safe accept because the theorem language and artifact packet can trigger technically justified rejects.
- Highest-impact fixes before upload: (1) formally resolve the reservoir indexing—the written recursion appears to prove strict Eq. (2), otherwise show why not; (2) submit the promised anonymous ledger/code/data archive; (3) add schedule-matched high-iteration references such as converged `K x 8` for the deployed `1 x 8` case, or explicitly scope the current comparisons; (4) narrow every host/class claim; (5) add the EasyChair paper ID once assigned. A penetration close-up in the video is useful but secondary.
- Supplement conclusion: strong positive clarity/credibility effect, but it supports selected XPBD shelf cases only and cannot validate the cross-host sweep, contact cost, FEM/runtime claims, or reproducibility.

## 2026-07-20 20:05 current-PDF audit

- New PDF lock: SHA-256 `4aea9e00e9975021cbf48bfb97c1f262b6b4d3f687d02bf8875c0976fa923eef`, generated 2026-07-20 20:05:00 PDT, 732,947 bytes, seven letter-size pages.
- Video lock remains SHA-256 `30a862facd530dd31741e41ef1774582f2d46d42ad3043ce5bc56f5a267a5d54`, 44.77 s, 1920x1080 H.264 at 30 fps, video-only.
- The PDF differs from the previously reviewed `276cc375...` artifact, so that panel's scores are stale. The unchanged video may be revalidated, but it cannot make the paper delta irrelevant.
- Structural audit: seven letter-size pages, approximately 7,483 extracted words, six body pages plus a references-only page 7. Every font is embedded/subsetted; the pages render without visible clipping, overlap, or body-text spill onto the reference page.
- Visual audit at contact-sheet scale: professional anonymous ACM/MIG layout, one teaser figure on page 1, method equations on pages 2–3, dense quantitative figures/tables on pages 3–5, and limitations/runtime/conclusion on page 6. The main presentation risk is density, not a rendering failure.
- Current central claims: across an identical 24-cell sweep, XPBD violates the gross-loss-funded storage budget in 9/24 cells (up to roughly `4.4e7 J`; its separate incident-energy diagnostic exceeds one in 8/24 and reaches `1.2e5`), AVBD violates the budget in 3/24 by at most `6.7 J` (versus 2/24 under the ratio), and the tested implicit sequential-impulse implementation violates neither metric in 0/24. The paper explicitly frames these as implementation-level observations, not solver-class theorems.
- The current manuscript now states Proposition 2.1 as an unconditional proof of strict Eq. (2), using same-substep credit before projection and a nonnegative reservoir debit. It reports a worst governed margin of `1.1e-13 J` across 90 cells (78 distinct configurations), resolving the earlier artifact's Eq. (2)/Eq. (4) target-versus-guarantee ambiguity on its face.
- The method is deliberately a fail-safe rather than trajectory repair. The abstract and Figure 1 foreground both the successful prevention of a spurious 93 mm launch and the suppression of legitimate 19 mm self-reference motion; worst post-projection penetration is reported as 21.6 mm at an adversarial `4x1` corner and 9.8 mm at deployed budgets.
- Experimental positives: identical scene/relaxation/budget grids across three implementations; a `K`-only XPBD convergence sweep showing six orders of gap closure; direct gap and separated-row multiplier residuals; a 24-configuration sensitivity sweep; deployed `1x8`/`2x4` cells; accuracy against both an implicit reference and XPBD self-reference; a separate unreduced-FEM comparison; contact-validity instrumentation; and CPU/device runtime scope stated without an unqualified real-time claim.
- Key control caveats remain explicit rather than hidden: equal `K*S` row counts do not equal equal work or schedule; warm-start/compliance/unknown choices remain host-constitutive rather than matched; `500x1` is iteration-converged but not schedule-matched to governed `S>1` runs; each formulation has only one implementation; and the enforced device path plus governed full-FEM validation do not exist.
- The gross scene-wide kinetic-loss supply is the method's main conceptual weakness. It is neither signed contact-port work nor per-interface dissipation, can cross-fund unrelated contacts, credits returned-and-re-dissipated energy twice, and changes with substep partition. Reported opposite-channel fractions reach `102–118%` for AVBD, reinforcing that this is a conservative exposure envelope rather than a physical transfer identity.
- Enforcement improves energy magnitude dramatically but not necessarily state accuracy: at the moderate shelf cell, energy error improves from `196x` to `3.7x` while trajectory error worsens from 33% to 71% of reference peak. The scalar projection retains the stiff spectral character (`99.6%` to `97.7%` in the high cluster) and reduces legitimate sag.
- Reproducibility is conditional on packaging: the PDF repeatedly promises a supplemental ledger with commands, commit hashes, source anchors, and full rows, but the user-specified review packet contains only the PDF and MP4. Reviewers cannot credit that material unless it is actually submitted as an anonymous supplemental artifact.
- Page-level visual audit, pp. 1–2: the teaser, abstract, contribution list, equations, and related-work positioning are crisp and legible with no overlap or clipping. The title page remains anonymous but shows no visible submission/paper ID; whether that is a defect depends on the live submission instructions and assignment status.
- Page-level visual audit, pp. 3–4: the enforcement chronology, Proposition 2.1 proof, host-comparison table, and two-metric heatmap are all rendered cleanly. The proof's same-substep credit/project/debit order is internally consistent with strict Eq. (2); Figure 2 clearly distinguishes diagnostic-ratio flags (`8/24, 2/24, 0/24`) from actual invariant violations (`9/24, 3/24, 0/24`). Table 1 is dense but readable at full page resolution.
- Page-level visual audit, pp. 5–6: convergence, contact-cost, accuracy, FEM-reference, timing, limitation, and conclusion material all fit cleanly. Figure 3 and Table 2 are legible, and the manuscript visibly gives high-cost failures comparable prominence to successes; no body content spills onto page 7.
- Page-level visual audit, p. 7: references only, cleanly rendered, with 18 cited works spanning the contact law, XPBD/AVBD, modal contact, iterative coupling/passivity, energy tanks, and projection. This confirms compliance with a six-content-page rule if references are excluded.
- Video revalidation: all 1,343 frames decode at 30 fps over 44.77 s. A complete two-second contact sheet confirms a coherent sequence: question/setup; steel-board `1x8` launch pathology; three-run ungoverned/governed/`XPBD self-reference (500x1)` comparison; soft-board case showing legitimate reference motion suppressed by the governor; invariant plot; and the closing claim “Boundedness, not trajectory recovery.” It is legible, true-scale, candid, and narrow to the XPBD shelf family.
- Live MIG 2026 CFP verified from the official site on 2026-07-20: short papers may use 4–6 content pages excluding references; supplements up to 200 MB are strongly encouraged; physics-based animation and interactive simulation are explicit topics; review criteria are originality, technical quality, clarity, significance, reproducibility where applicable, and MIG relevance. The current six-body-page plus references-only page 7 structure complies and venue fit is strong.
- Upload-readiness issue: the official double-blind instructions require the unique paper ID assigned by EasyChair. None is visible in the current PDF. This is administrative rather than scientific and becomes actionable once a submission record/ID exists.
- Packaging/anonymity audit: the PDF has zero embedded attachments; its visible/XMP summary fields expose no author identity, only generic LaTeX/acmart/pdfTeX producer information. The MP4 carries only generic FFmpeg/libx264 container tags and no audio stream or identifying author metadata. Both hashes remained stable through the primary audit.
- **Acceptance-critical internal data mismatch:** Figure 2's lower heatmap is inconsistent with the surrounding text and abstract. Counting positive cells under the caption's own rule (`>0` violates), the printed heatmap shows XPBD `8/24`, AVBD `23/24`, impulse `0/24`, with AVBD maximum `+15 J`; the body/abstract instead report invariant violations `9/24`, `3/24`, `0/24` and AVBD maximum `6.7 J`. The discrepancy is not rounding: it reverses the AVBD story from pervasive small positive margins to three localized violations, and the figure's XPBD count also differs by one.
- A second numerical wording error accompanies the new values: `4.4e7 J / 6.7 J` is about `6.6e6` (roughly 6.8 orders), yet the paper says the former is “five orders past” the latter. Five orders is appropriate for the separate incident-energy ratios (`1.2e5` vs `1.70`), not the stated joule margins.
- Table 1 contains a separate technical-clarity problem: the XPBD modal weight is printed as `1/(H_ii h^2 - 1)`, but `H_ii` is never defined in the visible paper and the sign/parenthesization is suspicious enough that a reviewer cannot reconstruct or sanity-check the transcription. The sequential-impulse weight `(M+hD+h^2K)^-1` is also not reconciled in the paper with the separately stated implicit-midpoint stepper. These may be notation/compression defects rather than code defects, but they undermine the claim that the three discrete rows are verifiable from the paper/video packet.

### Isolated reviewer returns so far (current hash `4aea9e00...`)

- Reviewer 1, formal physics: `3/7` weak reject, confidence `4/5`. Accepts Proposition 2.1's narrow endpoint algebra, but rejects the physical interpretation of the gross-loss supply and flags the undefined/suspicious Table 1 weights.
- Reviewer 2, contact numerics: `3/7` weak reject, confidence `4/5`. Finds the XPBD truncation diagnosis persuasive but the exact accounting guarantee insufficient evidence of useful governed solutions; requests contact-local work, schedule matching, and governed validation.
- Reviewer 3, novelty/significance: `3/7` weak reject, confidence `4/5`. Values the empirical diagnosis but rates the governor incremental and the scene-wide reservoir too weak semantically for the claimed practical role.
- Reviewer 4, evaluation/reproducibility: `3/7` weak reject, confidence `4/5`. Focuses on formulation confounds, incomplete governed baselines, unresolved interactive cost, and the absent promised ledger/raw artifact.
- Reviewer 5, practitioner/clarity: `5/7` weak accept, confidence `4/5`. Judges the focused diagnosis and candid failure accounting sufficient for a short paper if the governor is read only as an emergency envelope, while still requesting per-island accounting and an `eta` tradeoff study.
- Reviewer 6, senior generalist: `2/7` reject, confidence `4/5`. Independently caught and enumerated the Figure 2/prose contradiction, judging it fatal to the current comparative empirical record even though the theorem and XPBD diagnosis remain credible.
- None of the first five isolated reports independently noticed the stale Figure 2/new-prose contradiction; reviewer 6 did. The area-chair synthesis must apply that verified artifact defect rather than pretending the panel evaluated a consistent central dataset.

### Reconciled current-hash panel

- Scores in reviewer order: `3, 3, 3, 3, 5, 2`; mean `3.17/7`, median `3/7`; votes are five reject versus one weak accept. All confidence scores are `4/5`.
- Mean criteria: originality `3.00/5`, technical quality `2.83/5`, clarity `3.83/5`, significance `3.00/5`, reproducibility `2.50/5`, MIG relevance `5.00/5`.
- Consensus strengths: excellent MIG fit; a visually memorable and well-controlled within-XPBD truncation diagnosis; a now internally coherent narrow endpoint-bound proof; unusually candid measurement of accuracy, spectral, contact, and runtime costs; professional six-page presentation; and a supplement that shows both stabilization and lost legitimate motion.
- Consensus concerns even before the figure defect: scene-wide rectified loss is not signed/contact-local work and can recycle/cross-fund; the scalar projection is an emergency envelope rather than an accurate contact method; cross-host comparisons are implementation-confounded; `K*S` is not a matched schedule/cost axis; governed full-FEM/device validation is absent; the tight-budget overhead is substantial; and the promised ledger/raw reproduction package is missing from the supplied artifacts.
- Area-chair recommendation: **reject the current PDF**. The immediate reason is the irreconcilable central-data mismatch, not a demonstrated algebraic failure of Proposition 2.1. After regenerating all dependent claims from one audited table, defining/correcting Table 1's discrete weights, and attaching the promised anonymous artifact, the focused empirical diagnosis could return to borderline/weak-accept territory; the governor should remain framed only as a coarse safety envelope.
- Highest-priority repair order: (1) rebuild Figure 2, abstract, counts, maxima, and AVBD discussion from one authoritative per-cell table; (2) define `H_ii`, correct the printed XPBD weight if needed, and reconcile the implicit operator with midpoint; (3) attach the anonymous ledger/raw CSVs/commands/code and add the EasyChair paper ID; (4) add a signed/per-interface or adversarial cross-funding audit plus an `eta`/contact-quality tradeoff; (5) strengthen schedule-/cost-matched controls and governed validation; (6) add the worst penetration and an AVBD/impulse example to the video.

## P-round (plan §8) — 2026-07-19

### P7 prep found a Table 1 error: the printed modal rank is the REQUESTED
### mode count, not the realized one (shelf 24→16, ledge 28→16)

Found while choosing the E-C9 rank-axis points, which required knowing where
the stiff cluster sits in the realized basis.

`scenes/reduced_scene_common.py:242` clamps the local-mode count to the number
of *distinct* contact zones:

```python
n_modes_local = min(int(n_modes_local), len(distinct_zones))
```

(zones deduped within 15 mm, because coincident Gaussian bumps make `Mq`
singular and break the eigenbasis projection). So the builder kwargs are a
request, not the delivered rank:

| scene | requested `n_global + n_local` | Table 1 prints | realized rank | measured spectrum |
|---|---|---|---|---|
| shelf | 10 + 14 = 24 | **24** | **16** | 10 modes 20.3 Hz–2.03 kHz, 6 stiff 20.7–24.7 kHz |
| ledge | 12 + 16 = 28 | **28** | **16** | 12 modes 118 Hz–17.0 kHz, 4 stiff 170–191 kHz |
| table | 12 + 12 = 24 | 24 | 24 | 24 modes 4.7 Hz–5.20 kHz (no clamp: enough zones) |

Measured by reading `sol._kq` / `sol._mq` straight after `build_reduced_*`
(the same source `run_governed_accuracy.py:141` uses for its spectral split).

**The paper already contradicts itself on this, which is how it is
falsifiable without re-running anything.** §3.3 describes the shelf spectrum as
"ten bending modes below $2.1$~kHz, six stiff ones above $20$~kHz" — sixteen
modes, i.e. the *realized* basis — while Table 1 prints $r=24$ for the same
scene. The §3.3 sentence is right and Table 1's is wrong.

**No measured result changes.** Every E-S1b / E-C6 / R-round number was produced
by these builders at these settings; only the *description* of the model was
wrong. This is a corrected description, not a re-measurement, so the frozen
matrix stays frozen.

**§3.4's "$k{=}24$ mode truncation" is NOT affected — do not "fix" it.** That
sentence is about the ledge full-FEM comparison, whose arm is built by
`benchmarks/paper_eval/x3_ground_truth/ledge_scene_gt.py:284`
(`make_fem_modal_support(fem, num_modes=24)`) — a genuine 24-mode FEM
eigenbasis, a different construction from `build_reduced_ledge`. Verified
separately; it is correct as printed.

Bearing on E-C9: the rank axis is defined against the realized basis. Shelf
base is 16 = 10 global + 6 local, so "below the stiff cluster" is
`n_modes_local=0` (rank 10) and "above" is `n_modes_global=16` (rank 22);
ledge base is 16 = 12 + 4.

### P-round red-team re-read against BOTH panels' blocker lists (2026-07-20)

Build audited: `b2b179a` (paper worktree). Gate v2 green — body ends p. 6,
7 pages total, 0 overfull, 0 undefined, 18 references. Every new number
re-verified against its CSV (15/15) before this read.

#### Blockers now closed

| # | Blocker (panel) | Status in this build |
|---|---|---|
| 1 | Body spills to p. 7 — submission-critical (A+B) | **Closed.** P0; gate v2 is now scripted and per-commit. |
| 2 | No `\acmSubmissionID` (B) | **Closed** as a placeholder; fill at EasyChair registration. |
| 3 | Fig. 3 says "injection threshold" (A+B) | **Closed.** P0.2, re-rendered from the frozen CSV, verified label-text-only. |
| 4 | Eq. (2) vs the stricter enforced policy — "one consistent definition and proof" (A+B) | **Closed.** P3: one block defining three objects + Proposition with induction sketch; strict Eq. (2) is stated as *observed*, not implied. |
| 5 | Is the amplification a knife-edge artifact? (A+B) | **Closed.** P7/E-C9: 24/24 configurations still violate with R>1 across h, compliance, rank, damping. |
| 6 | Reproducibility 2.5/5 — no scene spec, no bundle (B) | **Closed.** P8: scene spec generated from code, anonymized bundle with 20 artifacts + ledger excerpts. |
| 7 | Supply depends on the substep partition (B numerics) | **Closed and quantified.** P6(b) + E-C9c: ratio 1.000–1.083, ≤7.7% rectified. Panel B was right; the effect is real and small. |
| 8 | Causal / per-row overinterpretation (B numerics) | **Closed.** P1 scoping sweep; grep-audited, 6 survivors all axis labels or the disclaimer itself. |
| 9 | XPBD/AVBD/sequential-impulse uncited (A) | **Closed.** P4, incl. a Catto citation verified against the author-hosted PDF. |
| 10 | Abstract ends on the adversarial maximum alone (A+B) | **Closed.** P5: the deployed-budget counterpart sits beside 21.6 mm. |
| 11 | "one row" ambiguous (A) | **Closed.** P2: one row *law*, per-scene instantiation counts. |
| 12 | Eq. (1) sign error (B senior PC) | **Correctly excluded** — ∂C/∂q = −U_y. Re-checked independently. No action. |

#### What the panels did NOT catch, and this round did

- **Table 1's modal rank was wrong** (24/28 → 16/16). The paper contradicted
  itself: §3.3 describes sixteen shelf modes. See the entry above.
- **The complementarity residual was dimensionally mixed *and* numerically just
  penetration in metres**, and "the complementarity conditions begin to hold"
  at K≈24 was unsupported — only the gap side converges there. Both fixed.
- **P6(a)'s anticipated "10²–10³× the accounting floor" was wrong** (2–274×).
  Printed as measured, per the D5 rule.

#### Still open — what a reviewer can still reject on, stated plainly

1. **No video.** P8.d needs the user's interactive capture session. For a
   graphics venue this remains the weakest presentational point; the teaser
   carries three arms as stills, which is not the same thing.
2. **The governor is still not contact-consistent.** Enforcement costs up to
   21.6 mm of penetration and moves the trajectory *away* from the reference.
   The paper concedes this in the abstract, §3.3 and Limitations. R8's NO-GO
   evidence stands (deviation-referencing measured NOT to collapse 21.6 → 19.89;
   band-selective unenforceable in up to 37.8% of clamp substeps). A reviewer
   who wants the constructive method will still say so — that is the long-paper
   track, and no text fix changes it.
3. **The governed path is not validated against full FEM.** §3.4 validates the
   *reduced response*, not the *governed* one. Conceded in Limitations.
4. **Three implementations are not three formulation classes.** P1 scopes every
   claim, but the sweep's breadth is what it is: n=3 hosts, 3 scenes, one
   contact regime.
5. **The AVBD overdraft is measured and unexplained.** Now bounded away from
   accounting noise (2–274× the floor), which makes the absence of a mechanism
   *more* conspicuous, not less.
6. **E-C9 sharpens rather than removes the stiff-tail question.** Excluding the
   stiff cluster cuts R by 286× on the shelf. The violation survives, so the
   claim holds — but a reviewer may reasonably read "the amplification is
   mostly a stiff-mode phenomenon" and ask why a rank-10 basis is not simply the
   recommendation. The paper does not answer that.

#### Page-budget honesty note

The P-round's content did not fit the 6-page limit alongside the existing
evidence. Beyond §8.2's named ladder (teaser caption, Fig. 2 caption,
forgiveness compression, Table 2's AVBD rows) this round also shrank Fig. 2
(0.92 → 0.80 textwidth) and Fig. 3, set the 7-step loop inline, and tightened
nine paragraphs. **Detail moved to the supplement, and a reader loses it from
the paper:** per-K self-convergence plateau values, per-scene device real-time
factors, and the AVBD post-projection validity rows. No claim and no frozen
number was dropped from the argument — but this is the point at which further
P-items would cost evidence, not words.

## Q-round (plan §9) — 2026-07-20

### Q0: "verify the paper worktree is clean" does not hold literally, and the
### honest check is disjointness, not cleanliness

§9.2 asks for a paper worktree "clean at the P-round head". It is not: nine
files are modified there (`main.tex`, `sections/00`–`50`, and two figure PDFs
`fig_x2_falloff`, `fig_x7_restitution`). None of it is Q-round dirt — it is the
**long paper**, carrying the 2026-07-13 standalone-repositioning edits, which
lives in the same worktree as a separate document and was deliberately left
alone by the P-round too (progress.md, P-round headline 6).

The check that actually matters is therefore disjointness, and it holds:
`main_short.tex`, `NUMBERS.md`, `references.bib` and `latexmkrc` are unmodified,
and the short paper `\includegraphics` exactly `fig_teaser.pdf`,
`fig_s1_solver_matrix.pdf`, `fig_s2_kconvergence.pdf` — none of which is among
the two modified figures. Rebuilding the short paper cannot pick up long-paper
state. Corroboration: the forced full rebuild produced **730,379 bytes**, the
byte count findings.md records for the reviewed PDF `627a14e…`.

Consequence for the round: every later gate check must be read the same way —
"clean" means *the short paper's inputs are unmodified*, and `git status` in the
paper worktree will keep showing nine unrelated modified files. Do not "tidy"
them; do not commit them on a Q-item commit. Check with
`git status --short main_short.tex NUMBERS.md references.bib latexmkrc`.

### Q0 incidental: the 21.6 mm penetration cell is shelf 4×1 (needed by Q5)

Located while spot-checking frozen numbers, ahead of Q5's own search: the
worst-case post-projection penetration the abstract and §4 print as 21.6 mm is
the **shelf $4{\times}1$** row of Table 2 (`main_short.tex:547`), which pairs it
with 107/108 clamped substeps and no corrective-impulse/variance entry; the
8.69× corrective impulse and 58× multiplier variance are a *different* row,
**ledge $8{\times}2$** (`:550`). Q5's overlay must not attach 8.69× to the
21.6 mm cell — they are different cells, and the paper never claims otherwise
(§4 prints them as separate worst-cases at `:85` and `:603`).

### Q1: the anonymity scan's first run found a real deanonymization the P8 scan
### would have shipped

`dcr/avbd/_solver/__init__.py:3` reads *"Vendored from the upstream port at
`https://github.com/<author-account>/AVBD`"* — the author's own GitHub account,
in a module docstring, in the one directory a code snapshot cannot omit. Three
upstream commit hashes follow in the same docstring, searchable in that same
account's repository.

The P8 DEANON list (home paths, `compshare`) would not have caught any of it,
and P8 shipped no code, so the exposure only became reachable the moment Q1
added the snapshot. The lesson generalizes past this one line: **the scan's
pattern list has to grow with what the bundle contains**, and a repo URL is not
automatically a leak — `github.com/savant117/avbd-demo2d` in the sibling file is
a citation of someone else's public demo and must stay. So URLs are adjudicated
one at a time against an allowlist rather than pattern-matched, and the
assembler refuses on any unadjudicated one.

Also learned the hard way: the assembler must exclude *itself* from the
snapshot. `make_supplement.py` holds the DEANON pattern list, which spells the
author's name, username and institution in plain text — shipping the scanner
would have shipped exactly what it scans for.

### Q1: `verify_paper_numbers.py` had been failing for two rounds and nobody ran it

It exits 1 on the P-round paper. Two of its checks assert that Table 2's AVBD
clamp counts (`27/108`, `25/108`) appear in `main_short.tex`; the P-round page
squeeze deleted Table 2's AVBD rows (progress.md records the deletion), so the
checks have been red since. The paper is fine — the *checker* went stale, in
the direction that makes a green tool useless rather than a red one noisy.

The repair matters more than the bug. Extending the checker to the numbers it
had never covered immediately found a **real error in the paper**: §3.3 printed
the post-projection penetration increase as `3.5`–`12.6×` at two sites, where
`3.5` is E-S3's shelf-only floor (ledge 4×1 is `3.12`). E-S3 computed it
shelf-only and said so; R5.2 then re-quoted it as "XPBD's 3.5–12.6×", host-wide;
the tex inherited R5.2's scope. Corrected to `3.1`–`12.6×` everywhere. It does
not weaken the claim — the second site calls the AVBD host's 3.1× and 5.5×
"comparable" to the XPBD range, which a floor of 3.1 supports more strongly than
3.5 does.

Two process points worth carrying to Q8: a verifier that nobody runs is worse
than none, so it now runs from the bundle itself; and a *scope-narrowing* clause
in a ledger entry ("shelf 4×1 … shelf 8×2") is exactly what gets dropped when
the number is re-quoted elsewhere. When a ledger range is scoped, the scope
belongs in the number's own row, not in the prose around it.

### Q1: a printed Table 1 quantity had no ledger entry at all

The claim-index self-check refused to build because `scene_spec.csv` — which
backs Table 1's realized modal rank (16/16/24) and §2's support-row counts
(48/40/200) — had **no entry in `mig2026_results_ledger.md`**. NUMBERS.md
recorded it; the ledger, which §3 of the paper explicitly points readers at
("every number is frozen with its generating command and commit hash in the
supplemental ledger"), did not. Frozen as **E-C9e**. The artifact and its
command had existed since P8; only the freeze record was missing, which is the
failure mode a mechanical index catches and a human read does not.

### Q1: bundle scope decisions worth not relitigating

- **Data extended 20 → 26 artifacts.** The P8 bundle covered §3.1–§3.3 and §4
  but not §3.1's substep sweep, §3.4's FEM comparison or §3.5's runtime, all of
  which the paper prints. Every results section now has its CSV present. What
  is still *not* re-derivable is stated in CLAIMS_INDEX rather than left
  implicit: device timings need an RTX 4090, the FEM reference needs hours, and
  the video's traces are large binaries.
- **`scripts/` and `benchmarks/paper_fig/` are not snapshotted.** No paper_eval
  harness imports either (checked with `git grep`), and paper_fig/data holds
  large frozen artifacts from other suites.
- **The snapshot is built from `git show HEAD:`**, never the working tree, so
  uncommitted WIP (the sound workstream, the R8 probes) cannot leak into a
  bundle. The consequence is an ordering constraint the plan already anticipated:
  the assembler must run *after* the round's final commit, or the snapshot
  ships the previous state. It bit once here — the first bundle carried the
  unrepaired verifier — and Q8 re-runs it last for exactly this reason.
- **`governed_accuracy.csv`'s working-tree drift was benign and is now
  committed.** The re-run differed from HEAD only in wall-clock timings and the
  manifest's sha/timestamp; every physical quantity was bit-identical. That is
  an unintentional reproducibility datum: the same measurement at a different
  commit reproduced exactly.

### Q2 audit table — every `enforc|guarante|certif|observ` site adjudicated

Vocabulary map (binding, §9.4): *guarantees / certifies* → the relaxed display
`\eqref{eq:budgeted}` ONLY; *observed* → strict `\eqref{eq:invariant}`;
*limits / contains / maintains* → safe descriptive language for the governor.
Line numbers are post-edit. `certif` has zero hits in the source, before and
after.

| site | before | verdict | after |
|---|---|---|---|
| abstract (:81,:83) | "**enforced** by a reservoir ledger… It holds in all 90 measured cells" | **CHANGED** — the panel's named site; "enforced" read as a strict guarantee | "**maintained** by a reservoir ledger… The loop **guarantees** a one-deposit relaxation of that bound; the strict form is **observed** in all 90 measured cells" |
| contribution bullet (:158,:161) | "**enforced** by a reservoir ledger… it satisfies the prescribed inequality in all 90" | **CHANGED** — same defect | "**maintained** by… guaranteeing `\eqref{eq:budgeted}`, a one-deposit relaxation; the strict form is *observed* in all 90" |
| Prop. 2.1 (:327) | "maintains $B\ge0$ and **enforces** (iii)" | **CHANGED** — "(iii)" was a prose pointer; now a numbered object | "maintains $B\ge0$ and **guarantees** `\eqref{eq:budgeted}`" |
| sketch (:336) | "exactly~(iii)" | **CHANGED** | "exactly~`\eqref{eq:budgeted}`" |
| sketch (:337–339) | "Strict … is not implied; it is *observed*, in all 90 governed cells, worst margin 1.1e-13 J" | **KEEP** — already exactly the map's *observed* form | unchanged |
| §2 item (ii) (:281) | "The **enforced** recursion" | **KEEP** — names the loop, claims nothing | unchanged |
| §2 item (iii) (:282) | "The implementation's own test additionally forgives…" | **CHANGED** — reframed as the guaranteed object, formula promoted to eq. (4) | "The bound the loop actually **guarantees** relaxes `\eqref{eq:invariant}` by one substep's largest deposit" |
| §1 contributions (:171) | "The cost of **enforcement**" | **KEEP** — names the measured cost | unchanged |
| §1 related work (:184) | "**enforced** by scaling realized modal state" | **KEEP** — mechanism description of ours, in contrast to prior work | unchanged |
| §1 related work (:177,:180) | wei2026 "**guarantee** discrete passivity" | **KEEP** — third party's claim, correctly attributed | unchanged |
| §1 related work (:196) | rath2008 "**enforces** exact per-interface energy stability" | **KEEP** — third party | unchanged |
| §1 related work (:193–194) | hannaford/franken "energy **observer**" | **KEEP** — the control-theory term of art | unchanged |
| §3.1 (:437) | "every state write in the **enforcement** path is guarded by $\gamma<1$" | **KEEP** — mechanism | unchanged |
| §3.1 (:450) | "With **enforcement** enabled, all 72 cells *of this sweep* satisfy" | **KEEP** — an observation, already scoped to the sweep | unchanged |
| §3.3 head (:539) | "The cost of **enforcement**" | **KEEP** | unchanged |
| §3.5 (:649,:653) | device path "carrying the ledger read-only rather than **enforcing** it"; "a device-resident **enforced** $\gamma$ does not exist in this work" | **KEEP** — both are scope disclosures, and the second is protected candor | unchanged |
| abstract (:67), §1 (:143), §2 (:292), §3.1 (:433) | "we **observe** behaviour", "an **observation** that predates this work", "not **observable** until the velocity solve", "before the excess is **observable**" | **KEEP** — ordinary usage, no bound claimed | unchanged |

**"Enforced up to X" phrasings: zero.** The relaxation is always named as an
object (`eq:budgeted`, "a one-deposit relaxation") rather than as a qualifier
on "enforced", which is what §9.4 warns reads as approximately-strict.

### Q3 audit table — every `converg` site, arm identity derived from data

Term A = **"implicit high-iteration reference (K=500)"**, handle *the implicit
reference*. Term B = **"XPBD high-iteration self-reference (500×1)"**, handle
*the XPBD self-reference*. "Converged" is RESERVED for statements a checked
criterion backs.

Arm identities, established before any rename — from the generating artifacts,
never from prose:

- `teaser_canonical.manifest.json`, `teaser_deployed.manifest.json`,
  `teaser_steel.manifest.json` **all** record `"solver": "xpbd"`,
  `"converged": "500x1"`, and `peaks.ref.e_mod_peak_J = 8.223580660384274`.
- `governed_accuracy.csv` gives `arm:xpbd_converged → 8.223580660384274` and
  `arm:oracle → 7.917553786483392`. The teaser's ref peak matches
  `arm:xpbd_converged` to all 16 digits.
- ⇒ **every teaser and video reference arm is Term B**, and the §3.3 site
  printing 7.92 J is Term A while the one printing 8.22 J is Term B.

| site | before | arm (source) | verdict |
|---|---|---|---|
| abstract (:77) | "a **converged reference** computed in the same code path" | **A** — "same code path" = the implicit realization | → "an implicit high-iteration reference" |
| Fig. 1 caption (:111) | "the host's own **converged solution** ($K{=}500$)" | **B** — manifest `xpbd`/`500x1` | → "the host's own high-iteration self-reference ($500{\times}1$)" — **the panel's exact catch** |
| contributions (:161) | "against a **converged reference**" | **A** | → "an implicit high-iteration reference" |
| Fig. 3 caption (:468) | "decays monotonically toward the **converged reference**" | **A** — caption names it two lines later | → "the implicit reference" |
| Fig. 3 caption (:472–474) | "the same code path run **to convergence**… already **converged** at $K{=}2$" | **A** | "to convergence" dropped as redundant; "already converged at $K{=}2$" **KEPT** — backed by the checked 4.9e-4 spread over K=2…500 |
| §3.2 definition block (:479–482) | "*the converged reference* is the implicit realization…, *the host's own fixed point* is the position-based host run to $K{=}500$ against itself" | **A and B** | rewritten to define *the implicit reference* and *the XPBD self-reference*; the block was already correct, only the names change |
| §3.2 (:484) | "approaching the **converged reference** $0.2735$" | **A** — `selfconvergence.csv` `impulse,500,is_oracle=True,0.27348…` | → "the implicit reference" |
| §3.2 (:503) | "the implicit realization is **converged** at $K{=}2$" | **A** | **KEEP** — same checked criterion |
| §3.3 (:567) | "against the **converged reference's** $7.92$~J" | **A** — `arm:oracle` = 7.9176 | → "the implicit reference's" — was already the right arm, now verified |
| §3.3 (:569) | "against the **host's own fixed point** ($8.22$~J)" | **B** — `arm:xpbd_converged` = 8.2236 | → "the XPBD self-reference" (name standardized) |
| §3.3 (:598) | "against the unclamped scene at a **converged budget**" | **neither** — the sag range 1.7–2.4 mm spans BOTH reference arms | → "at either reference". This site named no arm at all and would have been renamed wrongly by a blind sweep |
| Limitations (:663) | "moves the trajectory away from the **converged reference**" | **A** — the 6.5→14.3 mm figures are `accuracy:oracle` | → "the implicit reference" |
| §1 (:139), §3.1 (:422), §3.2 (:490,:498,:510,:512,:516,:518), Limits (:665), Concl. (:710,:711) | "solve to convergence", "does not converge the row", "**convergence** removes it", … | process, not an arm name | **KEEP** — 11 sites, unchanged |

**Residual `converged` in the source: 2 sites, both Term A at $K{=}2$, both
backed by the stated 4.9e-4 spread.** The two-meanings defect is gone by
removing the word from arm names, not by relabelling one of them.

Render scripts (label-text-only, the P0.2 precedent): `fig_teaser.py:54`
`"converged reference"` → `"XPBD self-reference"`; `make_teaser_video.py:61`
`"converged reference (K=500)"` → `"XPBD self-reference (500x1)"`, plus one
beat message and one beat subtitle. Figure re-render verified by text
extraction: **exactly one changed line**, `-converged reference` /
`+XPBD self-reference`.

### Q4 audit table — `formulation` and the row law

Rule: `formulation` survives only where it introduces the three families paired
with "one implementation each", or names a third party's object.

| site | verdict |
|---|---|
| title (:54) "A Cross-**Formulation** Measurement" | **KEEP** — plan §8.3 P1 adjudicated this in the P-round ("Title stays"); it names what the comparison ranges over, not a causal claim, and the abstract scopes it two sentences later |
| abstract (:64) "three fixed-budget solver **formulations** --- position-based (XPBD), augmented-Lagrangian (AVBD), and an implicit sequential-impulse realization" | **KEEP** — the family-introducing site, paired at :67–68 with "the three tested **implementations**" |
| contributions (:159) | **CHANGED** → "implementations" |
| §3.1 head (:351) "One row, three **formulations**" | **CHANGED** → "three implementations" |
| Fig. 2 caption (:357) | **CHANGED** → "implementations" |
| Limitations closer (:696) "Three **formulations**, three scenes" | **CHANGED** → "Three formulations, **one implementation of each**; three scenes" — the pairing made explicit at the coverage statement, which is where it does the most work |
| §1 (:188) "energy-tank **formulations**~\citep{franken2011}" | **KEEP** — third party, different sense entirely |

`row law` needed no change: **P2 already standardized it.** The source law is
"a velocity-level complementarity law" (:60) and "an established rigid–modal
contact law" (:708, prior work's object); ours is defined once as "one row
*law*, instantiated at every support contact every substep" (:217) and is "the
row" at every later mention (:422, :674). No second-mention drift exists to
fix — recorded so a future round does not re-open it.

### Q7: dropped, and the page budget is now genuinely exhausted

Q2's display equation cost a full page. Recovered in plan §9.13's prescribed
order — (iii)'s prose shrank as its formula moved out, the abstract and
contribution sentences were tightened, then plan §8.2's named ladder rung
(Fig. 2's candidate-denominator sentence, whose reasoning survives in §3.1's
"the ratio is not the invariant" paragraph) and the hatched-rows sentence,
which duplicated the body's own explanation.

**Q7's clause then did not fit at either length**, full (28 words) or
compressed (19). Per §9.9 it is the first thing to drop when the gate is red,
and §9.13 ranks it *below* making further cuts, so it was dropped rather than
funded. Logged as a decision, not an oversight: the paper already signals
future work twice (the device-resident governor and governed-vs-FEM validation
in Coverage; the deviation-scaling mechanism in "Stability is not accuracy"),
so what is lost is a direction pointer, not a disclosure.

The practical reading for Q8 and any later round: **at 6 pages this paper can
no longer absorb a display equation without losing prose that carries
argument.** The P-round already recorded "further P-items would cost evidence,
not words"; the Q-round confirms it — the two sentences cut here were the last
two that were genuinely redundant with the body.

### Q5: the fast path is unavailable, and the reason is structural

§9.7's fast path needs frozen body poses for the cell that prints 21.6 mm.
That cell is **shelf 4×1** (Q0's incidental finding). Inventory of every trace
in the tree:

| trace | scene / budget | body poses? |
|---|---|---|
| `teaser_canonical.npz` | shelf 8×2 | **yes** (off/on/ref) |
| `teaser_deployed.npz` | shelf 1×8 | **yes** (off/on/ref) |
| `teaser_steel.npz` | shelf 1×8, steel | **yes** (off/on/ref) |
| `governed_accuracy_traces.npz`, `governed_accuracy_1x8_traces.npz` | shelf 8×2 / 1×8 | no — deflection fields only |
| `selfconvergence_traces.npz`, `selfconvergence_long_traces.npz` | shelf, K ladder | no — deflection fields only |

**No trace carries 4×1 poses at all.** §9.7 anticipated half of this (it knew
`governed_accuracy_1x8_traces.npz` was fields-only); the other half is that the
three pose-carrying traces are all deployed-or-canonical budgets, because the
teaser was built to show a *production-like* cell, not the adversarial corner.
The 4×1 corner is the one the paper uses precisely because it is not
production-like, so the artifact that would visualize it was never recorded.

The boot prompt scopes this session to "Q5 fast path only", so Q5 ships nothing
and the round ships the Q3-relabelled 44.8 s cut — which §9.7 explicitly
permits and the panel already scored positively.

**One feasible alternative, for the user to decide at hand-off, not built
here.** The deployed 1×8 trace has poses, and the paper prints a worst
penetration of **9.8 mm** at the deployed budgets (§3.2). A close-up there
would be scientifically honest and matched to a printed number — it simply is
not the 21.6 mm headline, so the on-screen figure would be 9.8 mm. Building it
needs no new physics. Getting the 21.6 mm cell itself needs the §9.7 slow path:
one serial ARM replay of shelf 4×1 with pose capture, frozen as E-C11, whose
non-perturbation check is that it reproduces 21.6 mm to printed precision.

### Q8 red-team re-read of the final build against this panel's six risks

Read against the final PDF (clean rebuild, body p. 6, 0 overfull, 732,900 B)
and the rebuilt bundle. Scored honestly: "closed" means a reviewer repeating
the objection would now be wrong on the facts; "narrowed" means the objection
survives but a weaker version of it; "open" means untouched.

| # | panel risk | item | verdict |
|---|---|---|---|
| 1 | Prop. 2.1 guarantees only the one-deposit-relaxed bound; strict Eq. (2) is merely observed | Q2 | **narrowed, not closed** |
| 2 | Supply is scene-wide / recyclable / schedule-dependent, not contact-port work | Q1 | **narrowed** |
| 3 | Post-projection cost: 21.6 mm penetration, 8.7× impulse, worse trajectories | Q5 | **open, by decision** |
| 4 | Three hosts are implementations, not formulation classes | Q4 | **narrowed** |
| 5 | Ledger / commands / code / data absent from the supplement | Q1 | **closed** |
| 6 | Fig. 1 and the video call the XPBD K=500 self-fixed point "the converged reference" | Q3 | **closed** |

**1 — narrowed.** Every claim site now says which bound it means, and the
guaranteed one is equation (4) rather than a prose pointer. What did *not*
change is the underlying fact: the loop still guarantees only the relaxed
bound, and the paper still headlines the strict one. A reviewer who wants
strict Eq. (2) *proved* remains unsatisfied, and correctly so — that needs a
different loop (§10). The defensible position is that the paper no longer
anywhere implies otherwise, and it never did in §2; the defect was at the
abstract and contribution bullet, and those are fixed.

**2 — narrowed.** The partition and recycling measurements (E-C9c ≤ 7.7%
rectified; E-C9d flat over a 10× horizon) are now in the bundle with their
commands, so "you assert this without evidence" is no longer available. "This
is the wrong quantity to budget against" still is, and the paper concedes it in
§4 ("Tightening the envelope needs the signed or per-interface accounting this
scalar reservoir avoids"). Packaging cannot close a conceptual objection.

**3 — open, by decision.** No frozen trace carries poses for the 4×1 cell, so
§9.7's fast path did not exist and the boot prompt barred the slow path. The
cost remains disclosed in four places (abstract, §3.3, Table 2, Limitations) and
the panel itself ranked the close-up "useful but secondary". This is the round's
largest deliberate gap and the PI should know it is deliberate.

**4 — narrowed.** Four sites changed and the Limitations coverage statement now
carries the explicit pairing. The title keeps "Cross-Formulation" per plan §8.3
P1, so a reviewer who reads only the title still meets the broader framing —
a known, adjudicated residual, not an oversight.

**5 — closed.** Runnable snapshot, claim index, pinned versions, smoke test,
checksums, video, anonymized, verified from a clean unpack. The two things a
reviewer still cannot re-derive (device timings, the full-FEM reference) are
named in `CLAIMS_INDEX.md` with reasons rather than left to be discovered.

**6 — closed.** Both arms have fixed names, "converged" survives only where a
checked criterion backs it, and the figure and video were re-rendered
label-only with the specs verified identical. One consequence to carry to
submission: **the video the panel reviewed is not the video we ship** — same
frames, same cut, three different label strings, new SHA-256 `30a862fa…`
frozen as E-C9f.

#### What this round introduced that a fresh reviewer might catch

Adversarial pass over our own changes, not the panel's list:

- **A vocabulary seam between the caption and §3.2.** Fig. 1's caption says
  "the host's own high-iteration self-reference (500×1)" while §3.2's
  definition block and the video legend say "the XPBD self-reference". Same
  object, two surface forms, three pages apart. Judged acceptable: the caption
  is self-explanatory standalone and deliberately avoids naming a host before
  §3.1 introduces the three. Flagged rather than churned.
- **Fig. 2's caption now points at its own section** ("bit-identical by
  construction (§3.1)"). Slightly circular on the page where the float lands
  with its text, useful when it floats away. Kept.
- **The "why joules, not a second ratio" justification now lives only in the
  body.** Cutting it from Fig. 2's caption was the plan's own named cut rung
  and §3.1's "the ratio is not the invariant" paragraph carries the argument —
  but a reviewer who reads figures first will now meet the joules axis before
  the reason for it.
- **`eq:budgeted` is cited before it is displayed.** The contribution bullet on
  page 1 references equation (4), which appears on page 3. Standard practice
  and hyperlinked, but it is a forward reference the P-round build did not have.

Nothing found in this pass contradicts a frozen number, and
`verify_paper_numbers.py` passes 38/38 against the final tex.

---

## R4 round: two panels combined → solid-accept plan (2026-07-20)

Plan: `prompts/mig_short_r4_solid_accept_plan.md`. Inputs: Opus 4.8 panel
(pre-Q, mean 4.50 "borderline weak accept") + Fable panel on the Q8 build
(mean 4.33 "publishable, not safe"). Both deduped into one ledger S1–S12.

### P0 — provability gate: PASSED, verified in code

Reviewer 1's argument (strict Eq. (2) is provable) is **correct against the
implementation**, and the Q8 record's "needs a different loop (§10)" was wrong.
Confirmed all four ledger sites share the order credit → test → project →
debit-on-post-projection-state:

| site | credit | test | project | debit |
|---|---|---|---|---|
| `solver_impulse.py` `_psv_commit` | 998 | 1001 | 1003–11 | 1012 |
| `solver_xpbd.py` `_substep_cpu` | 1241 | 1242 | 1244–50 | 1251–52 |
| `solver_6dof.py` `_modal_commit` | 2630 | 2631 | 2639–46 | 2647 |
| `solver_6dof.py` network §N2 | 3300 | 3301 | 3305–09 | 3310 |

Ledger internals (`passivity.py`): `deposit` credits `c_k=η·max(ΔErig,0)` and
returns `B_{k-1}+c_k`; `passivity_gamma` caps `γ²E⁺ ≤ E⁻+B_{k-1}+c_k` (exactly
when binding, `+tol` when inert); `commit` debits `max(ΔE,0)` and floors B at 0.
Carry two invariants `B_k≥0` and `(E_m^k−E_m^0)+B_k ≤ Σ_{j≤k}c_j`; both hold at
k=0 and are preserved in all branches (inert / binding / reservoir-floored, the
last one covered by the projection cap `ΔE≤B_{k-1}+c_k`). Since `B_n≥0`,
`E_m^n−E_m^0 ≤ Σc_k` = **strict Eq. (2)**, up to `n·ε` (per-test tol 1e-12).
The ledger's own `max_net_excess` (passivity.py:282) measures exactly that
slack, and the paper already reports it at the 1.1e-13 J roundoff floor — the
`n·ε` tolerance in numbers. The old "one-deposit" (Eq. 4) slack was
over-conservative: the pre-test credit already accounts the in-substep deposit.

### P1 — theorem upgrade shipped (LaTeX + supplement, no re-run)

Four paper sites rewritten; build clean (7 pp, 0 overfull):
- Abstract (was "guarantees a one-deposit relaxation … strict form observed") →
  guarantees the bound unconditionally up to a stated tolerance, margins at the
  1.1e-13 J roundoff floor.
- Contribution bullet: `eqref{eq:budgeted}` → `eqref{eq:invariant}`, same upgrade.
- "Three objects" → "Two objects": deleted object (iii), the `eq:budgeted`
  display (former Eq. 4), and the "7–389 J slack … 1 of 24, not 23" sentence.
  Object (ii) now states the loop maintains Eq. (invariant) exactly.
- Prop. 2.1 restated (unconditional Eq. (invariant) up to `nε`); the sketch is
  now a full inductive **proof** matching the code.
- Supplement: `CLAIMS_INDEX.md` note that the `_allow`/`max_deposit` columns are
  the retired one-deposit reading, not a paper object; read `max_net_excess`.
- No dangling refs (grep clean: no `eq:budgeted`, no literal "(4)", no
  "reading (i)"). Net a space saving (one display equation removed).

P2–P5 tracked in the plan; P2 (trapezoidal `W_g` + re-run) is the long pole and
the only code work.

### P2 — code done, re-run done, and it changed the thesis (2026-07-20)

Code: trapezoidal `W_g = ½ m g·(v⁻+v⁺) h` at all four ledger sites (impulse,
xpbd, both 6dof commits), each with a `# DEVIATION` note; `v_prev`/`_psv_v_pre`
snapshotted at substep start. New test `test_gravity_supply_trapezoidal.py`
(18 cases: formula-level free-fall = 0 over a 64× h sweep; live xpbd/impulse
free-fall supply < 1e-4; 6dof white-box deposit matches trapezoidal to 1e-9).
Full `avbd_native` regression 202 passed / 30 skipped. One network-injection
torture fixture retuned (drop 0.02→0.05, E 3e6→1e7) because its old marginal
"injection" was itself the removed artifact.

**Re-run (`run_eq2_utilization.py --check-frozen`), the pivotal result:**
- Frozen **ratios all reproduce** — trajectory bit-identical, fix is ledger-only.
- **impulse: 0/24, worst margin now exactly 0.0 J** (was −5.7e-4) — the
  converged reference is provably clean; the old −5.7e-4 was pure artifact.
- **XPBD: 9/24** (was 8/24), worst 4.4e7 J unchanged — catastrophic injection
  untouched, one more cell caught by the tighter accounting.
- **AVBD: 3/24** (was **23/24**), worst +6.7 J (was 15.1). The 3: dinner 1.0
  4×1 (+6.74 J, R=1.70, the starved corner the paper already highlights) +
  ledge 8×2 at both relaxes (+0.005 J, tiny). The other 20 now hold (margins
  ~−1e-3). **The "pervasive but negligible" AVBD overdraft was ~87% integrator
  artifact.**

Why it's correct, not a bug: displacement `W_g = m g·(x⁺−x⁻)` is the exact
discrete mechanical-energy loss, but symplectic Euler drains a staggered-grid
½mh²g²/substep during free flight — real in the discrete energy, but a
discretization artifact, not contact dissipation. Trapezoidal removes it. The
impulse→exactly-0 result is the smoking gun. Telescoping check: Σ(disp−trap) =
½h Σ_b m_b g·(v_final−v_init) ≈ 0 for rest-to-rest, so total supply barely
moves; the margin (a peak-relative quantity) shifts because the timing of the
credit differs across the impact transient.

**Consequence — this reshaped Contribution 1.** User chose "adopt + reframe
honestly" (2026-07-20). The old punchline "pervasive but negligible (AVBD)
beside rare but catastrophic (XPBD), only the invariant distinguishes them" lost
its "pervasive AVBD" leg; reframed around **magnitude ordering** — catastrophic
truncation (XPBD 4.4e7 J) / small-localized (AVBD 6.7 J, one starved corner) /
none (impulse exactly 0) — with "neither metric subsumes the other" (each flags
a cell the other misses: XPBD shelf 16×4 Eq2-only, AVBD ledge 8×2 Eq2-only vs
dinner 0.7 4×1 R-only).

**Reframe executed across every affected site:** abstract (3/24, 6.7 J),
§3.1 ratio-is-not-invariant paragraph, §3.2 deployed (AVBD 5/6→1/6, ≤0.011 J),
§3.3 accuracy (governed peak 29.26→29.56 J, +1%), §3.3 AVBD projection (only
dinner 1.0 4×1 clamps: 1.8 mm; the R>1 0.7 cell holds), §4 Coverage, Table 2
(settling-cell clamp pattern shifted: shelf 8×2 impulse 6.90→3.68×, λvar 26→5.6×;
ledge 8×2 8.69→8.92×, 58→62×), prose 8.7→8.9× / 58→62×, range 3.1-12.6→3.1-12.5.
Governed matrix numbers **unchanged** (1.22/0.87 worst ratio; Prop 1.1e-13;
projection 21.6 mm held exactly — catastrophic injection dominates).

**Bundle frozen & self-consistent:** `verify_paper_numbers.py` 32/32 (AVBD block
rewritten for the reframe; ~15 constants updated); `smoke_test.py` PASS (impulse
margin assertion `≥0`→`>1e-9` since it's now exactly 0); CLAIMS_INDEX 29/29
anchors; `make_supplement.py` scan PASS (0 deanon), code_snapshot has the fix,
zip 1.93 MiB; `LEDGER_EXCERPTS.md` carries an R4 supersession header; NUMBERS.md
reconciled. Paper builds 7 pp, 0 overfull, 735,857 B. New test
`test_gravity_supply_trapezoidal.py` (18) + full `avbd_native` 202 pass.

**Only open item: EasyChair paper ID** (S11 — needs the user; insert in the
anonymous build). Deferred user decisions: E-C11 4×1 pose close-up (S9) and a
clean-room re-panel (S12).

## 2026-07-21 current-artifact review freeze

- Frozen PDF: `paper/main_short.pdf`, SHA-256 `6907a3bbc25fcb93d1eda2b6c117b9f4bc75f5068b19105f5a07111e5e388b43`, 732,389 bytes, generated 2026-07-21 00:57:29 PDT.
- PDF structural pass: 7 US-letter pages, 7,412 extracted words; all listed fonts embedded; no encryption, JavaScript, form, or structural-suspect flag.
- Frozen video: `benchmarks/paper_fig/out/teaser_video.mp4`, SHA-256 `30a862facd530dd31741e41ef1774582f2d46d42ad3043ce5bc56f5a267a5d54`, 44.766667 s, 1920x1080, H.264/yuv420p at 30 fps, 1,343 frames.
- Full FFmpeg decode completed with no reported error. The MP4 has one video stream and no audio stream; generic FFmpeg encoder/handler tags expose no author identity.
- The PDF changed after the prior panel; the MP4 hash matches the prior reviewed supplement. All prior paper scores are stale.
- The live official MIG 2026 homepage confirms the venue, 11–13 December dates, 7 August 23:59 AoE paper deadline, long/short paper track, and submission window. Its Call for Papers link targets the official `papers.htm` page but the browser cache missed it, so the exact page is being retrieved directly from the same official domain.
- The fetched official CFP states: short papers are 4–6 content pages excluding references; supplements such as video are strongly encouraged up to 200 MB; review criteria are originality, technical quality, clarity, significance, applicable reproducibility, and MIG relevance; submissions must be anonymous and include the system-assigned unique paper ID.
- Common panel scale frozen as 1 strong reject, 2 reject, 3 weak reject, 4 borderline, 5 weak accept, 6 accept, 7 strong accept; confidence uses 1–5. Every reviewer must separate scientific merit from fixable submission-readiness defects and state the video's effect on the score.

### Primary text audit (before panel synthesis)

- Core contribution is deliberately narrow: the rigid–modal row is established prior art and the energy-governor idea is transplanted from passivity/tank/projection controls. Claimed novelty is (i) a controlled 24-cell comparison of one XPBD, one AVBD, and one implicit sequential-impulse implementation, (ii) quantitative diagnosis of finite-budget modal-energy injection, and (iii) a host-agnostic scene-level cumulative modal-storage cap with an explicit contact-validity audit.
- The revised Figure 2 and prose are internally consistent on the main counts: incident-energy diagnostic flags XPBD/AVBD/impulse in 8/2/0 of 24; strict Eq. (2) margins flag 9/3/0. The AVBD maximum overdraw is 6.74 J, and the XPBD maximum is about 4.4e7 J.
- Proposition 2.1's credit–project–debit induction is plausible on its stated scalar accounting: same-substep credit is available before testing; quadratic scaling caps positive modal-energy gain by the reservoir; debiting positive realized gain preserves nonnegative balance and the cumulative storage ceiling. It does not prove contact-port passivity, total-energy stability, or contact validity, and the paper states those exclusions.
- Strong evidence/candor: equal scene/budget matrix; iteration-only and equal-row-evaluation comparisons; direct complementarity diagnostics; two independently named references; explicit self-convergence plateau; deployed-budget cells; one-at-a-time robustness; spectrum diagnosis; post-projection penetration/impulse/variance; limited full-FEM reduced-response check; runtime variance and negative results; unusually explicit limitations.
- Central scientific limitation: formulation labels remain confounded with one particular implementation each, including warm start, compliance/penalty/CFM, update variable, and contact treatment. The paper now says “one implementation of each” and “as-deployed, not compliance-matched,” which narrows but does not remove the attribution problem.
- Practical limitation is severe but disclosed: the scalar post-solve projection can cause up to 21.6 mm penetration (72% of board thickness), 8.9x corrective impulse, and 62x multiplier variance; governed trajectories can move farther from a reference. This makes it an emergency fail-safe, not a generally faithful contact method.
- Evaluation gaps: no governed-path validation against full FEM; the full-FEM check tests the reduced response rather than the governed contact path; no friction/restitution beyond normal-only e=0; three scenes and one machine for solver behavior; the AVBD overdraft mechanism remains unexplained; the device path monitors but does not enforce; comparisons are deterministic rather than replicated except timings.
- A notable conclusion inconsistency remains: the paper recommends the implicit or augmented-Lagrangian hosts “which stay within budget,” although it reports AVBD violations in 3/24 main cells and 1/6 deployed cells. This should be rewritten as an empirical degree-of-violation statement, not a categorical property.
- The submitted packet supplied for this review contains only the PDF and MP4. The PDF repeatedly relies on a supplemental ledger/commands/full rows/per-scene factors, but those materials are not in the supplied review packet; if omitted from the real submission, reproducibility claims are not reviewable.
- Submission-readiness: six content pages plus a references-only seventh page complies with the live 4–6-page rule. The PDF is anonymous, but no unique paper ID is visible; because the portal has not yet assigned one, this is a pre-upload fix rather than a scientific defect.
- Visual pages 1–2: clean ACM review rendering, crisp fonts/line numbers, anonymous author, and no clipping or overlap. Figure 1 is legible at normal page scale and honestly labels true scale, independent runs, energy peaks, and the lost legitimate motion. The title/abstract are very dense, and the running header shows only “Anon.” rather than a paper ID.
- Visual pages 3–4: equations, Proposition 2.1, Table 1, and Figure 2 render cleanly with no overlap. The table and heatmap carry unusually high information density but remain readable at full-page zoom. Figure 2 now visibly supports the prose counts (including the small positive AVBD margins and the additional XPBD/AVBD invariant-only cells).
- Visual pages 5–6: Figure 3 and Table 2 are clean and readable; the six-page body ends exactly on page 6 with no clipping or overflow. These pages are prose-heavy but well organized. The categorical conclusion phrase that AVBD and impulse “stay within budget” is visibly inconsistent with the nearby disclosed 3/24 AVBD violations.
- Visual page 7: references alone occupy page 7 with ample whitespace; citations and DOIs render cleanly. This confirms formal page-count compliance rather than a hidden seventh content page.
- Video contact-sheet pass: polished, anonymous, and legible scientific storytelling. It contrasts a stiff steel-board case, a soft-board case with legitimate motion, ungoverned/governed/XPBD-self-reference runs, energy curves, and an explicit “bounded, but not faithful” conclusion. It is unusually candid about the governor suppressing legitimate motion. Its evidentiary scope is narrow: only XPBD shelf cases are visualized; AVBD, sequential impulse, the 21.6 mm penetration/corrective-contact artifact, and cross-scene behavior are not shown.
- Video 1 fps audit, first 18 seconds: title/setup pacing is clear; the steel-board split-screen keeps camera, state, time marker, and scale aligned while energy values/curves update; the later three-way still makes the spurious launch relative to the XPBD self-reference immediately visible. Small grey explanatory text is readable at 1080p but likely marginal in a reduced embedded player.
- Video 1 fps audit, seconds 18–36: the soft-board sequence clearly demonstrates the key tradeoff—reference motion is legitimate, ungoverned motion is excessive, and the governor suppresses both. The cut explicitly discloses that the ungoverned run later drives a book through the board and that the renderer cannot depth-order it honestly. The “bounded, but not faithful” triptych and moving time cursor support the paper's cautious interpretation rather than hiding failure.
- Video 1 fps audit, seconds 36–44.77: the moving-cursor invariant plot makes the budget crossing/containment clear, followed by a concise final card: boundedness rather than trajectory recovery, all 90 measured cells, contact-validity cost measured, CPU-side enforcement, and no unqualified real-time claim. No hidden end credits, identity cues, audio, or extra claims appear.
- Phase-23 artifact verdict: both files are technically valid, anonymous, and submission-sized; all seven PDF pages and the complete 44.77-second video have been inspected. The video adds meaningful qualitative evidence but cannot validate the paper's cross-formulation or worst penetration claims by itself.
- PDF packaging/anonymity follow-up: zero embedded files; XMP creator is exactly “Anonymous Author(s)” and source is the generic `main_short.tex`; no author identity was found. The supplied PDF therefore does not itself contain the repeatedly promised supplemental ledger.

### Isolated reviewer reports (sealed from other reviewers)

- R3 (novelty/significance): **4/7 borderline leaning reject, confidence 4/5**. Praises striking/candid empirical evidence, useful iteration-vs-substep result, plausible proof, and strong MIG fit. Main concerns: known ingredients make mechanism novelty thin; implementation confounds prevent solver-class attribution; safeguard is practically unfaithful; extreme spectrum is partly under-resolved; promised reproducibility materials are absent. Video raises clarity/confidence but not generality.
- R2 (contact/numerics): **3/7 weak reject, confidence 4/5**. Finds the algebraic invariant sound and the negative-result disclosure excellent. Blocking concerns: implementation confounds, row-evaluation count mislabeled as “equal cost” in the abstract, accounting ceiling weaker than physical stability/passivity, severe contact invalidity, and missing promised artifact. Also independently catches the categorical AVBD conclusion contradiction. Video is a modest positive but omits cross-host/contact-validity evidence.

### Cross-check prompted by returned reports

- R2's wording catch is factual: the abstract says “at equal cost,” while §3.1 explicitly states that equal `K*S` means equal row evaluations and that substeps repeat contact generation/integration, so the refinements are “not ... equally priced.” This is a high-value, one-phrase repair: say “at equal row-evaluation count.”
- Attribution should be harmonized: the abstract still says injection is “formulation-dependent” and calls the three paths “formulations,” whereas the evidence/table/limitations establish one non-compliance-matched implementation of each. “Implementation-dependent in this sweep” is the defensible wording.
- R1 (physics/energy): **3/7 weak reject, confidence 4/5**. Finds no algebraic fatal error and judges the quadratic scaling/proposition sound for the computed ledger. Blocking concerns are discrete gravity-work exactness/definition, the potentially unbounded recycled supply versus the word “boundedness,” missing reproducibility material, and implementation confounds. Independently catches the AVBD conclusion and equal-cost contradictions; video is moderately positive but narrow.
- Adjudication note on R1's gravity concern: Table 1 states an implicit-midpoint stepper, for which constant-gravity work equals the endpoint kinetic-energy change if rigid translation actually uses the midpoint update. Thus R1 has identified an under-explained/under-reproducible premise, not a demonstrated sign or algebra error. The final meta-review should ask for the one-body discrete derivation/test rather than assert that Eq. (3) is wrong.
- R5 (presentation/practitioner): **5/7 weak accept, confidence 4/5**. Views the diagnostic result as publishable under a short-paper bar, praising the within-host truncation evidence, candor, practical iteration-vs-substep lesson, figures, and video. Conditions acceptance on narrowing to tested implementations and presenting the governor strictly as an emergency bound. Calls for a penetration visual and clearer/less dense prose.
- R4 (evaluation/reproducibility): **3/7 weak reject, confidence 4/5**. Praises internal controls, metric separation, ablations, candid limits, and apparent proof soundness. Reject drivers: missing promised supplement, implementation confounds, schedule-mismatched accuracy references/no governed FEM, limited robustness, and monitor-only GPU evidence. Independently confirms both key wording contradictions.
- R6 (senior generalist): **5/7 weak accept, confidence 4/5**. Judges the empirical diagnosis sufficiently original, credible, and focused for a MIG short paper despite modest mechanism novelty. Conditions acceptance on implementation-specific claims and fail-safe framing; flags nonlocal/recyclable supply, contact destruction, under-resolved stiff modes, and absent reproducibility material. Video materially strengthens the phenomenon but not generality.

### Six-reviewer reconciliation and final advice

- Scores in reviewer order R1–R6: `3, 3, 4, 3, 5, 5`; mean `3.83/7`, median `3.5/7`; all confidence `4/5`. Vote characterization: three weak rejects, one borderline leaning reject, two weak accepts.
- Area-chair-style recommendation for the exact supplied packet: **weak reject / borderline**. The reject side has the majority, but the disagreement is principled: R5/R6 believe the unusually careful empirical diagnosis alone clears a focused short-paper bar, while R1/R2/R4 and borderline R3 require stronger causal/reproducibility/practical evidence.
- Unanimous or near-unanimous positives: strong MIG fit; striking and useful finite-budget failure; internally plausible scalar proof; strong within-XPBD truncation evidence; unusually honest measurement of negative effects; polished figures; video improves qualitative understanding.
- Unanimous or near-unanimous concerns: only one unmatched implementation per solver class; the observer ceiling is not passivity/total-system stability; the clamp is not contact/trajectory faithful; promised ledger/code/data are absent from the supplied packet; video omits AVBD/impulse and penetration; presentation is dense.
- Adjudicated nonfatal technical issue: no reviewer found an algebraic error in Proposition 2.1. The discrete gravity-work concern should be resolved by explicitly connecting the stated implicit-midpoint update to exact constant-gravity work (and providing a one-body numerical check), not presented as a proven flaw.
- Highest-impact immediate repairs: (1) attach the promised reproducibility archive; (2) change “equal cost” to “equal row-evaluation count,” “formulation-dependent” to implementation-specific wording, and remove the claim that AVBD stays within budget; (3) add the assigned paper ID; (4) state that the right-hand-side supply may grow and use “cumulative storage ceiling” rather than unqualified long-horizon “boundedness.”
- Highest-impact scientific addition: a full representable-band/band-limited sweep plus one wall-time- or parameter-matched control would directly answer the strongest generality objection. Schedule-matched governed reference/full-FEM evidence is the next priority.
- Video verdict: technically clean and scientifically candid; a net positive but not score-changing for most reviewers. Best revision is a governed-contact close-up showing the reported penetration, followed by one brief AVBD/implicit comparison; enlarge secondary grey text for reduced-player viewing.
- Final hashes rechecked after all reports and unchanged: PDF `6907a3bb...`; MP4 `30a862fa...`.

## 2026-07-21 immediate rerun artifact delta

- New PDF SHA-256: `32f2951dd14467085c942302a38f7b42e32fe30b051ba1f8890e2bceef30d861`, 732,408 bytes, generated 2026-07-21 02:19:23 PDT. It supersedes the previous panel's `6907a3bb...` build.
- Video remains byte-identical at SHA-256 `30a862facd530dd31741e41ef1774582f2d46d42ad3043ce5bc56f5a267a5d54`; a fresh full decode completed without error.
- PDF remains 7 pages (six content plus references), anonymous, unencrypted, and structurally clean. Extracted text is 7,411 words.
- Material PDF changes already visible in the text delta: the abstract now says results vary across the three implementations rather than being formulation-dependent; “equal cost” is corrected to “equal row-evaluation count”; a warm-start control is added (same 8/24 footprint, same worst ratio, worse 4x1); and the conclusion no longer falsely says AVBD stays within budget, instead quantifying its small 3/24 overdraws against XPBD.
- The video did not change, so its prior visual facts remain applicable, but every new reviewer will independently inspect it and will not receive earlier conclusions.
- New substantive controls in §3.1–3.2: warm-starting XPBD leaves the same 8/24 incident-ratio footprint and the same worst ratio, while worsening the 4x1 result by 3.1x; removing the stiff modal cluster now covers the full injecting subset, with 6/8 cells still overdrawing and a remaining worst overdraw of 1.24e6 J. These additions directly weaken the prior “warm-start confound” and “headline is only unrepresentable modes” objections.
- The revised conclusion quantifies AVBD as at most 6.7 J in 3/24 cells against XPBD's 1e7 J scale. It is factually consistent, although “prefer ... AVBD” remains an empirical recommendation from one implementation and the AVBD mechanism remains unexplained.
- Unchanged major limitations visible in the new text: one implementation per host and unmatched compliance; global/recyclable schedule-dependent supply rather than port work; contact/trajectory degradation; no governed full-FEM validation; monitor-only device path; and reliance on a supplemental ledger not present in the two files the user supplied for this panel.
- New visual pages 1–2: clean, anonymous, and unclipped. The revised abstract preserves the same evidence while visibly fixing the implementation attribution and row-count language; Figure 1 and the invariant definition remain legible. No paper ID is visible yet.
- New visual pages 3–4: proof, Table 1, heatmaps, and all labels remain clean. The warm-start control fits naturally beneath Table 1 and explicitly narrows that confound without crowding the page beyond the already-high information density.
- New visual pages 5–6: the added band-limiting result is clearly legible and directly adjacent to the robustness argument; the revised conclusion is factually consistent about AVBD's nonzero overdraft. Six content pages still fit without clipping. Remaining wording risk: “prefer ... AVBD” remains broader than a one-implementation empirical study, and the shorthand “the position-based host's 10^7 J” is less precise than the 4.4e7 J stated in the abstract.
- New page 7 remains references-only and clean. The unchanged video was revalidated against its contact sheet and full decode: polished and candid, still XPBD-shelf-only, still omitting a direct view of the 21.6 mm penetration and cross-host behavior.
- Phase-27 verdict: the new PDF is a material scientific/claim-calibration improvement, not a timestamp-only rebuild. All pages and the full unchanged MP4 have been revalidated; no new layout, anonymity, or count inconsistency was found.
### Rerun panel — sealed reports received

- Reviewer 1 (energy/passivity audit): **4/7 borderline**, confidence **4/5**. The reviewer found the catastrophic XPBD diagnosis convincing and Proposition 2.1 algebraically valid under its stated update order, while praising the paper's candor about contact invalidity. The central reservation was that the scene-wide rectified rigid-energy-loss supply is not interface work or passivity: discrete gravity conservation and omitted compliance/penalty/dual reservoirs could matter, especially for the small AVBD overdrafts, and one implementation per host does not justify a solver-class preference.
- Reviewer 2 (contact/numerics): **4/7 borderline**, confidence **4/5**. The reviewer credited the warm-start, iteration-versus-substep, band-limit, perturbation, residual, reference, and inactive-path controls, and found the accounting proposition plausible. Remaining blockers were causal fairness across unmatched host implementations, lack of contact-port/physical validity in the scalar governor, limited worst-case convergence evidence, and the need to narrow solver-level recommendations.
- Reviewer 3 (novelty/significance): **5/7 weak accept**, confidence **4/5**. The reviewer found the XPBD failure mode striking and relevant, the evaluation unusually extensive for a short paper, and the paper candid about limitations. Reservations were modest mitigation novelty, one implementation per host, schedule-dependent rather than physical-energy guarantees, substantial distortion under governance, and lack of governed GPU/full-FEM evidence.
- Reviewer 4 (evaluation/reproducibility): **4/7 borderline**, confidence **4/5**. The reviewer praised the unusually strong internal controls and candid adverse-result reporting, but found the cross-host study causally unmatched, the governor insufficiently compared with practical alternatives, long-horizon/whole-system stability untested, and the supplied PDF/video packet insufficient for numerical reproduction without its referenced ledger.
- Reviewer 5 (presentation/practitioner): **5/7 weak accept**, confidence **4/5**. The reviewer regarded the work as a valuable, highly relevant, unusually honest short-paper warning whose diagnostic contribution and video clear a weak-accept bar. The governor itself was judged an emergency guardrail rather than a production remedy, with solver-family generality, practical accuracy, cost matching, and governed FEM/GPU evidence remaining limited.
- Reviewer 6 (senior/generalist): **5/7 weak accept**, confidence **4/5**. The reviewer judged the careful empirical diagnosis sufficient for the focused MIG short-paper bar, while treating the one-implementation-per-formulation scope, weak scene-wide accounting guarantee, severe contact side effects, absent governed physical validation, and missing supplied ledger as the limits on a stronger score.
- All six reports were produced independently from the locked PDF and video only. No reviewer saw planning notes, sources, data, prior reports, or another reviewer’s judgment.

### Immediate rerun reconciliation

- Scores in reviewer order R1–R6: `4, 4, 5, 4, 5, 5`; mean **4.50/7**, median **4.5/7**; all confidence **4/5**. Vote characterization: three borderline and three weak accept, with no reject score.
- Area-chair-style recommendation for the exact packet: **borderline / weak accept, leaning accept under the focused short-paper bar**. This is not a secure accept: half the panel still wants tighter causal attribution or more complete evidence.
- Relative to the immediately prior panel (`3, 3, 4, 3, 5, 5`, mean 3.83), the new build improves by **+0.67 points in mean score** and removes all reject votes. Reviewers explicitly credited the corrected implementation-specific/equal-row-evaluation wording and the new warm-start and band-limit controls.
- No reviewer found a fatal mathematical error. The consensus is that Proposition 2.1 correctly enforces the printed scalar ledger invariant, while that invariant is neither contact-port passivity, total-system energy stability, nor trajectory/contact accuracy.
- Strongest remaining acceptance risk: the conclusion still says to prefer implicit/AVBD despite testing one unmatched implementation of each host. Restrict every recommendation to the tested implementations unless a compliance- and wall-clock-matched comparison is added.
- Strongest artifact risk: the PDF repeatedly relies on a supplemental ledger that was not among the two reviewed artifacts. This criticism is conditional—if the actual review bundle includes the ledger/code/data and it contains the promised commands, commits, configurations, and raw rows, the reproducibility objection drops substantially.
- Energy-audit request: add a gravity-only/no-contact discrete check and explain how compliance, penalty/dual, or CFM-related stored energy enters—or is intentionally excluded from—the accounting. This matters most for interpreting the small AVBD overdrafts, not for the visibly catastrophic XPBD cases.
- The new band-limit result is valuable, but it is a diagnostic ablation rather than a cost-, contact-, and accuracy-matched mitigation comparison. A small matched comparison among extra iterations, band-limiting, and the governor would most efficiently strengthen practical significance.
- Video consensus: a material positive for the visible XPBD phenomenon and for the candid “bounded, but not faithful” tradeoff; it remains narrow because it omits AVBD/impulse behavior and the reported 21.6 mm penetration. Best addition: a true-scale contact close-up, followed by one brief cross-host view.
- Final hashes rechecked and unchanged: PDF `32f2951dd14467085c942302a38f7b42e32fe30b051ba1f8890e2bceef30d861`; MP4 `30a862facd530dd31741e41ef1774582f2d46d42ad3043ce5bc56f5a267a5d54`.

## 2026-07-21 rewrite-planning premise

- The strongest current story is not a generally necessary energy-control method. It is a practitioner-facing warning and operating guide for adding a small, globally shared modal state to an existing fixed-budget XPBD rigid-body/contact host.
- Modes and full-space nodal/tetrahedral XPBD occupy different operating points: the former trades nonlinear/local deformation for a precomputed state of roughly 10–24 global coordinates, while the latter carries many local nodal coordinates and internal constraints. The rewrite must make this tradeoff explicit in the opening motivation.
- AVBD and the implicit sequential-impulse realization should become controls, not co-equal target methods. The evidence-backed recommendation order is: implicit modal block when architecture permits; band-limit and allocate local iterations when XPBD is fixed; cumulative governor only as a disclosed emergency containment layer.
- A strong method-paper route remains possible only with substantive new evidence such as a hybrid XPBD-rigid/implicit-modal baseline at matched wall-clock cost or a contact-preserving adaptive safeguard. Merely promoting the current radial state scaling would strengthen the reviewer objection that the paper's own implicit baseline is preferable.

### Current short-paper architecture relevant to the rewrite

- `paper/main_short.tex` is a single 727-line, approximately 5,506-source-word manuscript. The six-page body currently allocates an abstract, teaser, introduction, a large standalone bound/proof section, three results subsections, full-FEM/runtime paragraphs, limitations, and conclusion.
- Current visual budget: one teaser figure, one two-column three-solver heatmap, one convergence figure, and two tables (solver differences and post-projection contact validity). This is enough visual real estate for the new story if the heatmap and solver table become secondary controls and the teaser becomes an explicit practitioner decision/failure figure.
- The present structure gives the governor/proof an entire major section before the empirical XPBD failure. The rewrite should reverse that order: establish the practitioner workflow and failure first, derive actionable solver guidance second, and introduce the bound only after the reader understands the fixed-host corner where it is relevant.
- The strongest already-compiled evidence for the new thesis is concentrated in the 24-cell implementation comparison, the iteration-only convergence ladder, equal row-evaluation iteration-versus-substep contrast, warm-start control, and representable-band control. The weakest material for the new thesis is the broad three-host recommendation, monitor-only GPU timing, and governed-path claims not validated against FEM.

### Opening/ending claim diagnosis

- The abstract currently starts from the classical velocity-level law rather than the practitioner decision. It names three solver formulations before explaining why a developer would retain XPBD, then asserts that convergence is unaffordable without first comparing the obvious implicit/hybrid alternative. This creates the user's “why not just use the working impulse realization?” reaction.
- The current introduction spends substantial space disclaiming novelty and comparing energy-control literature before it establishes the concrete workflow: extend an existing XPBD rigid solver with roughly 16–24 modal coordinates instead of converting a stiff prop to a full nodal/tet deformable. The rewrite should put that workflow, benefit, and numerical trap in the first two paragraphs.
- The current contribution list makes the storage bound contribution #2 and devotes a full early section to its proof. Under the new thesis, contribution #1 should be the practitioner-relevant failure characterization and causal controls; #2 the actionable operating envelope; #3 the audited last-resort guardrail and its failure cost.
- The conclusion's order is also backwards for the new story. It should first give the solver-choice decision tree, then state the implementation-specific measurements, and end with the warning that the radial governor guarantees only the scalar storage accounting and can destroy contact fidelity.
- Existing precise language worth preserving: the row is established rather than novel; the three paths are tested implementations rather than solver-class theorems; the governor is a minimal audited fail-safe rather than a constructive contact method; boundedness is not faithfulness.

### Rewrite assets and hard constraints

- The current artifact is exactly seven letter pages: six content plus one references page. Any restructuring must keep the existing `scripts/check_page_gate.py` gate and rebuild after every meaningful prose/figure change.
- All three essential existing visuals are reproducibly generated (`fig_teaser.py`, `fig_s1_solver_matrix.py`, `fig_s2_kconvergence.py`). A dramatic narrative rewrite does not require discarding the measurement pipeline; the likely figure work is recomposition/relabeling rather than new simulation.
- The repository also contains candidate visuals for contact forces, full-FEM comparison, runtime, robustness, activation, and sequences. Because the short paper can carry only about three major visuals, inclusion must be decided by the new claim hierarchy rather than by availability.
- Recommended visual priority: (1) “tempting XPBD extension → visible failure → decision path” teaser; (2) XPBD operating-envelope/convergence figure including iteration-vs-substep, warm-start, and band-limit takeaways; (3) compact cross-implementation control plus guardrail contact-cost evidence. Full host-difference details and complete heatmaps should move to the supplied reproducibility artifact if page pressure requires it.

### Motivation evidence and experiment scope

- The current short paper already validates that 16–24 retained modes reproduce the low-frequency ledge response against the same unreduced discrete FEM operator (frequency within 0.4%, spatial falloff Spearman 0.89). This supports using a compact modal state for stiff, small-displacement response, although it does not currently quantify its speedup versus full-space XPBD/FEM.
- A separate long-paper experiment reports a 13.6× reduced/full-FEM wall-clock difference and a refinement ladder up to 67k nodes, but it is a different scene/configuration and must not be imported into the short paper without a configuration-level audit. The rewrite plan should use the current same-operator fidelity result as the scientific justification and treat a direct modal-versus-full-space cost measurement as optional high-value evidence.
- The repository already contains a native implicit sequential-impulse implementation and extensive XPBD/AVBD infrastructure. The minimum diagnostic rewrite needs no new solver. The decisive method-paper experiment would be a hybrid fixed-XPBD host with only the rigid–modal block solved implicitly, plus matched-cost comparison; that is new scientific work and belongs behind a stop/go gate rather than on the critical rewrite path.
- DOF count alone is not the numerical story: each of the small number of modal coordinates is globally shared by many contact rows, whereas nodal/tet constraints are numerous but local. The rewrite should make this dense-global-versus-large-local tradeoff the intuitive explanation for why a 16-mode extension can still be difficult for truncated Gauss–Seidel.

### Current page allocation and rewrite opportunity

- Current pages 1–2 are dominated by the dense abstract/teaser, novelty disclaimers, related energy-control work, and the start of the bound; the empirical result does not formally begin until page 3. This delays the paper's strongest evidence and practitioner relevance.
- Page 3 completes the proof and host table before starting results; page 4 is largely the three-host heatmap; page 5 carries the convergence figure and contact-validity table; page 6 compresses FEM, runtime, limitations, and conclusion.
- Target allocation should invert this: page 1 audience/problem/visual failure; page 2 exact row plus why a dense shared modal block is difficult and the experimental protocol; pages 3–4 operating-envelope evidence and controls; page 5 guardrail definition/proof/cost; page 6 decision guide, scope, reproducibility, and conclusion.
- This reallocation can be achieved mostly by moving and compressing existing material. The bound proof should be reduced to the minimum induction needed for auditability; extended passivity-control positioning, full host table rows, complete heatmaps, and detailed runtime cells belong in the supplemental ledger.

### Mechanism depth needed to avoid a “blog-post warning” review

- Existing engineering notes identify the structural intuition: every support contact row touches the same small modal vector, making the constraint graph dense on `q`; ordinary graph coloring cannot recover locality, while primal/block methods can gather the rows into a small dense modal solve. This is a strong explanatory direction for the rewrite.
- Those notes also contain a spectral-radius failure for a separate averaged-Jacobi device path. It must not be imported as evidence for the current serial-GS XPBD experiment. If the rewrite claims a convergence mechanism, it needs a new linearized iteration-matrix audit for the exact current XPBD host.
- Best scientific upgrade for the diagnostic route: build the fixed-contact linearized XPBD iteration matrix at representative cells, measure its convergence factor/spectral radius, and test whether it predicts the observed iteration ladder. A successful correlation would turn “XPBD sometimes injects” into a mechanism-level explanation of why a small dense modal block is hard for a fixed local budget.
- Best practitioner upgrade: replace the current one-shot “remove stiff cluster” ablation with a frequency-cutoff ladder across `K`. The existing cutoff still retains modes up to roughly 2 kHz (shelf) and 17 kHz (ledge) at a 120 Hz frame rate, so it is evidence that one coarse truncation is insufficient, not yet a safe band-selection rule.
- Both upgrades should be gated: retain them in the paper only if they reproduce across at least shelf and ledge and yield a stable rule. Otherwise report residual/complementarity-based convergence diagnostics and describe band selection as something users must verify rather than a guaranteed formula.

### Citation/build readiness

- The bibliography already contains the exact practitioner anchor `mueller2020xpbd`, the original XPBD paper, modal-contact precedent, and reduced-order XPBD (`peng2024reduced`). The rewrite can establish the intended audience without adding a new literature-search dependency, although the incomplete Peng author list must be corrected before camera-ready.
- The existing build process supports the rewrite safely: `latexmk -pdf main_short.tex` writes auxiliaries under `paper/build`, and `scripts/check_page_gate.py` verifies body page ≤6, total pages, and zero overfull boxes. These should be mandatory gates after each page-level milestone, followed by number/citation and PDF visual checks.

## 2026-07-21 review of user amendments to rewrite plan

- The user retained sections 1–14 and appended a substantive section 15 with four changes: require perturbation/variance evidence (`E1b`), move a minimal XPBD-host/implicit-modal ablation (`E6a`) onto the diagnostic path, impose deadline priorities plus a frozen fallback artifact, and preserve the 8/24 incident-ratio versus 9/24 ledger-margin distinction.
- Initial assessment: the fallback/deadline discipline and count distinction are unequivocally good. The perturbation item addresses a real weakness, but should be specified as a deterministic perturbation/contact-order ensemble rather than “seeds” unless the simulation actually contains controlled randomness.
- The proposed `E6a` is scientifically high-value but is the amendment requiring the most scrutiny. An implicit modal weight already existing in another host does not make its transplantation into the XPBD position solve automatically cheap, matched, or single-variable. The ablation must keep the rigid/contact pipeline, row ordering, compliance, warm start, and local budget fixed and define exactly which modal operator changes.
- A one-scene/one-budget `E6a` can establish a local causal ablation, but cannot by itself justify a general recommendation to use implicit modal blocks. Either retain implementation- and case-specific recommendation language or require replication across at least a second scene/budget before treating it as the decision rule's causal license.
- The section-15 characterization of the earlier committee report is accurate: that panel was 5/5/5 versus 3/3/3 (mean/median 4.0), explicitly called the modal-weight ablation and replication/variance the non-negotiable soundness pair, and criticized five- to six-digit single-trajectory maxima on chaotic dynamics.
- The new deadline ordering correctly converts the original plan from an all-at-once wish list into an executable priority menu. Retaining the frozen 4.50 build as a fallback and requiring the rewrite to outperform it in one comparative re-review cycle is strong risk management, with the caveat that simulated-panel mean is calibration evidence rather than a true acceptance probability.
- The relevant implementations are local (`dcr/avbd/_solver/solver_xpbd.py` and `solver_impulse.py`), so `E6a` is inspectable rather than hypothetical. Feasibility and single-variable validity still require a line-level comparison of their modal updates before labeling it “minimal.”
- The line-level map shows that `E6a` is currently ambiguous, not merely underspecified. `SolverXPBD` already contains two separate experimental switches: `_modal_symplectic` for an implicit-midpoint modal restoring step and `_support_block` for exact condensation/solve of the dense shared support-modal rows. `SolverImpulse` instead uses backward-Euler modal effective mass `(M+hD+h²K)^{-1}` inside a velocity-level PGS row.
- Therefore “give XPBD an implicit modal block” could mean at least three materially different interventions: change the free modal integrator, change the contact-row effective modal mass, or block-solve cross-row support coupling. The plan must choose one and name the invariant parts; otherwise a positive result cannot identify the cause.
- The existing XPBD block-solve path suggests a minimal implementation may be feasible, but it is not automatically the clean counterfactual requested by the committee. It changes cross-row coupling and possibly scheduling, while the impulse arm also differs in time discretization and velocity-level contact semantics.
- The paper configuration explicitly sets `_modal_symplectic=True`; baseline XPBD therefore already uses an implicit-midpoint modal restoring step. The amendment's proposed conclusion “explicit modal-block integration under truncation” would be factually misleading for the current experiment.
- A clean E6a should be renamed and decomposed around the actual variable. Candidate A: keep the current symplectic XPBD free/restoring step and substitute only the stiffness-aware contact effective modal weight. Candidate B: keep the current modal weight and replace serial row-wise support coupling with the existing exact shared-block condensation. Running both as a small 2×2 ablation would distinguish temporal modal weighting from cross-row convergence more cleanly than the present single hybrid label.
- The existing `_support_block` documentation says it preserves the active-row compliant fixed point but uses a diagonal body block and a different convergence path. That makes it a useful ablation, not a behavior-identical implementation detail; those deviations must be disclosed.
- Exact amendment locations: replication/variance is lines 642–658; ambiguous minimal hybrid is lines 660–679; fallback priority is lines 681–705; count safeguard is lines 707–711. Sections 1–14 remain internally coherent with the new addition.
- Overall verdict after full read: the modified plan is materially better and execution-ready after one required correction to Amendment 2 and one protocol clarification to Amendment 1. The deadline/fallback amendment should be retained unchanged except to describe the 4.50 simulated mean as a calibration result, not acceptance evidence.

## 2026-07-21 integration targets locked

- The amendment currently conflicts with the main plan at Sections 2, 5, 9, 11, and 13: the body gives a generic implicit-block recommendation while E6 is wholly method-gated, and Section 15 incorrectly proposes an “explicit modal-block integration” conclusion even though the configured XPBD restoring step is already implicit midpoint.
- Integration will define E6a-1 as the controlled shared-row block-condensation ablation, put any stiffness-aware contact-weight change behind a discrete-equation feasibility gate as E6a-2, and reserve E6b for the replicated method-paper route.
- E1b will be a deterministic neighborhood-robustness ensemble (initial-condition and row-order perturbations shared across compared schedules), not a seed sweep. Its role is robustness of headline cases, not population inference.
- The frozen 4.50/7 simulated panel remains a comparative fallback calibration only. The final plan must say that a major rewrite should outperform it on motivation clarity and scientific quality after one full review cycle.
- Integration is now reflected in the main plan rather than an override appendix. Verification found four remaining generic “implicit block” phrases in reader-facing guidance; they were narrowed to the tested stiffness-aware velocity path or an E6a-validated shared-block path.
- Section 14 now explicitly defines the scope correctly: the expected PDF is a major narrative and structural rewrite, while the contact equations, core sweep, convergence ladder, controls, proof, and contact-cost evidence remain reusable.

## 2026-07-21 EXECUTION — Stage A (claim sheet frozen)

- Authority is `docs/mig2026_practitioner_diagnostic_rewrite_plan.md`; this
  session executes it. Branch/worktree layout confirmed: 3-host sweep harness on
  `impulse-native-constraint` under `benchmarks/paper_eval/x1_passivity/`; paper
  on orphan worktree `paper/` (`c15457c`). Fallback PDF `32f2951dd1446708…`
  matches, committed at `c15457c`, snapshotted to scratchpad.
- **Claim sheet** `docs/mig2026_claim_sheet.md`: 16 sub-claims across C1–C5 each
  bound to one frozen CSV/figure/ledger-§. Every headline number has a real
  source file that exists in `out/` (verified by `ls`).
- **E6a-1 is buildable, E1 and E1b are not (yet).** `SolverXPBD` carries
  `_modal_symplectic` (implicit-midpoint modal restoring step, ON in paper
  config → nonclaim 9 is real) and `_support_block` (exact shared support-modal
  condensation). So E6a-1 = serial support-row vs `_support_block`, both in the
  same host — directly runnable. But `run_schur_vs_blockgs.py` is an **AVBD**
  experiment (Schur crossterm vs block-GS on AVBD's q-block), NOT the XPBD
  E6a-1; and `run_static_ledger.py` is a static Σλ=mg weight check, NOT E1's
  gravity/no-contact accounting-residual audit. Both E1 and E1b need new
  harnesses.
- **Terminology baseline (Stage A gate).** Current draft is already mostly
  compliant: all 6 "passiv" prose uses are literature or explicitly negated
  ("neither port passivity…", "…not a theorem"); 8/24 (incident-ratio, R>1) and
  9/24 (strict Eq. 2 margin) already kept distinct at every site; "DCR" absent
  from prose; "real-time" only as prior-art label + the explicit no-claim
  disclaimer. Residuals → Stage E: (1) Fig. caption L354 "XPBD exceeds 1 in
  8/24" is a bare-family attribution, qualify to "our tested XPBD
  implementation"; (2) keyword "passivity" L94 reconsider under the diagnostic
  framing; (3) Table 1 L377 "modal weight: explicit" must be locked as the
  *contact weight* (variable 2), never read as explicit *integration* — the
  stepper row L385 already says implicit midpoint for all three hosts.
- Gate verdict: **PASS as far as Stage A owns it** — rules frozen, baseline
  audited, prose residuals are Stage-D/E enforcement (the caption is recomposed
  in Stage C anyway, so fixing it now would be premature churn).

## Stage-F supplementary video — no new claim (2026-07-21)

`mig_short_video.mp4` (six §12 beats, `make_short_video.py`) **introduces no
claim not already in the frozen claim sheet**: every on-screen number is read
live from the frozen Stage-B CSVs (`k_convergence`, `substep_sweep`,
`band_limit_sweep`, `projection_validity*`) and the teaser pose manifests. It
obeys the same terminology gate — the scalar bound is "storage bound /
containment", never "passivity"; the modal step is never called "explicit"; the
implicit/velocity path is the *observed control* (one implementation), not a
solver-class ranking. It ends on the operating-guide decision rule, not the
guardrail (§12: "no longer end as if the governor were the main product"). The
video is a visualization of the evidence, not a contribution.

## 2026-07-21 Stage G — frozen current paper/video review

### Artifact lock and initial paper reconstruction

- PDF: `paper/main_short.pdf`, SHA-256 `51b436f1c1c20069051487056e5f07820194e91c1448de04eb48ab0fc65826eb`, 734,737 bytes, generated 2026-07-21 22:03:38 PDT, seven letter-size pages, all fonts embedded. The ACM metadata says “7 pages”; the visible body runs through page 6 and references occupy page 7.
- Video: `benchmarks/paper_fig/out/mig_short_video.mp4`, SHA-256 `97035c0c08b0ffdd326b0eea7ec860ec0b8c31cf1266f24b13072cbd8f59632e`, 53.2667 s, 1,598 frames at 30 fps, 1920×1080 H.264/yuv420p, 1,451,244 bytes, no audio stream and no title/author/comment metadata reported by `ffprobe`.
- The paper is explicitly a diagnostic/operating-guide short paper, not a claim that the two-way rigid–modal row is new. Its central empirical claim is that one tested fixed-budget XPBD implementation catastrophically overdraws a scene-wide gross rigid-side energy-loss envelope in certain shared-modal contact configurations, while one AVBD and one stiffness-aware implicit implementation are milder controls.
- Evidence visible so far includes: three scenes × two relaxations × four schedules; direct invariant margins as well as incident-energy ratios; same-path iteration and self-convergence ladders; equal-row-count iteration-vs-substep allocation; warm-start, modal-band, deterministic perturbation, and serial-vs-block-condensation ablations; complementarity diagnostics; and a post-hoc scalar governor with quantified contact/trajectory harm.
- The guardrail proposition appears deliberately narrow: it maintains the printed scalar storage ledger by construction, but the paper expressly disclaims contact-port passivity, whole-system stability, contact accuracy, and a production-ready cure. Reported governed contact damage reaches 21.6 mm penetration (72% of board thickness), so the guardrail is framed as containment only.
- Initial review risks to test independently: causal generalization from one implementation per formulation with unmatched compliance/cost/warm start; whether gross scene-wide rectified rigid loss is a physically meaningful supply; whether the diagnostic contribution is novel/significant enough without a new contact method; whether a 500-iteration self-reference is an adequate accuracy reference; and whether the packet is reproducible without the separately mentioned ledger/data supplement.

### Initial visual audit

- All seven PDF pages render cleanly with no visible clipping, broken glyphs, overlap, or blank content. Pages 1–6 contain the paper body; page 7 contains only references, consistent with a six-content-page short-paper layout if MIG excludes references from the limit. Page 4 is the densest and Figure 3 uses small annotations, but the main visual hierarchy remains coherent at full-page viewing.
- Figure 1 works as a candid teaser: identical-view ungoverned/governed/XPBD-self-reference panels are paired with a modal-energy trace and explicitly show that containment also suppresses legitimate motion. Figures 2–3 carry substantial quantitative evidence but demand close reading.
- The 53.3-second video has six clear beats: two-way modal-row schematic; animated steel-board failure against a 500×1 XPBD self-reference; equal-cost iterations-vs-substeps curve; band-limit necessary-but-insufficient panel; animated ungoverned/governed/self-reference containment plus a 21.6 mm penetration cross-section; and a three-branch operating guide ending “The governor is a safety net, not the product.”
- The supplement is scientifically candid and directly reinforces the paper’s diagnostic framing. It is silent/no-audio and relies on small secondary text and plot labels that may be hard to read in a reduced conference-review player; its value is primarily comprehension, not new validation.

### Live MIG 2026 rubric (official site checked 2026-07-21)

- The official MIG 2026 call defines short papers as focused results, emerging ideas, or concise technical contributions and lists physics-based animation plus interactive simulation as in scope.
- The official format is 4–6 pages excluding references. The current packet’s six body pages plus one references page is compliant on length.
- The official criteria are originality, technical quality, clarity, significance, reproducibility where applicable, and MIG relevance. Supplementary video is encouraged up to 200 MB; the 1.45 MB video is compliant.
- Review copies must be anonymous and contain the unique submission ID assigned by EasyChair. The PDF is anonymous but currently has no visible paper ID. Because the official submission window opens 2026-07-25, this is a mandatory pre-upload fix rather than a scientific rejection reason at the current 2026-07-21 stage.

### High-resolution page audit, pages 1–2

- Page 1 is visually polished and unusually candid for a short paper, but the abstract is dense and number-heavy. The teaser is legible at full-page size; its smaller schematic labels and trace annotations will require zoom in many review interfaces.
- Page 2 cleanly distinguishes the adopted two-way row from the paper’s contribution and states the three claimed contributions. The rendered gap equation is `C = y_c - (y_rest + U_y^T q)`, so the printed derivative `∂C/∂q = -U_y` is consistent; any sign-error complaint based on text extraction would be a reviewer misread.
- The paper repeatedly and visibly narrows the invariant: scene-wide gross rigid-side kinetic loss corrected for gravity, not dissipation, not signed interface work, not contact-port passivity. This candor strengthens clarity but also makes the physical significance of the bound the central judgment call.

### High-resolution page audit, pages 3–4

- Page 3 is text-dense but readable. It openly discloses that the three implementations differ in unknown, modal contact weight, warm start, and relaxation, and calls the cross-host comparison “as-deployed rather than compliance-matched.” That prevents an unfair universal solver-ranking claim, but it also limits causal attribution.
- A 400-dpi check confirms that the printed XPBD contact-weight expression is literally `1/(H_ii h^2 - 1)`. It is not self-contained: `H_ii` is not defined in the visible paper and the denominator/sign are difficult to sanity-check. The complete host/parameter table is deferred to an unprovided supplement, making this a likely technical-clarity/reproducibility question rather than a demonstrated code error.
- Page 4’s heatmaps/control strip and three-part operating-envelope figure are visually clean at full resolution and support the headline narrative. The captions are very long and repeat much of the body, while several plot annotations require zoom; this is density, not a rendering defect.
- The same-path XPBD evidence is much stronger causally than the cross-host strip: iterations reduce energy ratio and gap error, complementarity clears later, warm start does not help, equal row counts allocated to substeps can still inject, and block condensation follows a distinct worse path. The paper appropriately avoids claiming convergence to the implicit discretization, noting a nonzero XPBD fixed-point gap.

### High-resolution page audit, pages 5–6

- The scalar projection and Proposition 4.1 are readable and internally coherent at the level printed: crediting nonnegative supply before the test, scaling the quadratic modal state to `E_mod^- + B`, and debiting only positive realized storage changes maintains a nonnegative reservoir and telescopes to Eq. (2). This establishes only the stated storage ceiling; it does not repair the physical meaning of the supply or contact validity.
- Table 1 is a strong negative-result inclusion: it exposes clamp frequency, median/max post-projection gap, corrective impulse, and multiplier variance instead of presenting the governor as a clean fix. The table covers only two starved budgets in two scenes, so the worst-case cost is clear but broader governed-path behavior is not.
- The FEM paragraph validates the reduced representation rather than the governed contact algorithm: it reports timestep convergence, frequency agreement, and spatial falloff against an unreduced reference, while the Limitations section explicitly leaves governed-path FEM validation for future work.
- Runtime reporting is honest but not a real-time demonstration: CPU overhead is 0.23–0.41 ms at 16×4 and proportionally much larger at deployed low budgets; the paper explicitly disclaims an enforced device-resident implementation and unqualified real-time claims.
- The conclusion gives a useful ordered operating guide and keeps the implicit-host observation implementation-specific. Overall presentation is dense but coherent, with the main residual reproducibility dependency being the unseen supplemental ledger/host table rather than a visible formatting problem.

### High-resolution audit, page 7 and animated comparison

- Page 7 contains references only and has substantial whitespace, but all 18 entries are readable and the bibliography covers the closest modal-contact, XPBD/AVBD, energy-projection, energy-tank, and recent energy-safe/contact work named by the paper. The page is not a content overflow.
- The animated “bounded, but not faithful” video comparison is effective at full resolution: three identical-view runs, current modal energies/book motion, shared trace, true-scale disclaimer, and a direct warning that legitimate motion is suppressed. The visual makes the contact/trajectory tradeoff harder to miss than the paper alone.

### High-resolution video audit, beats 1–3

- The opening schematic makes the target workflow and shared-row bottleneck understandable without narration. Its final question precisely matches the paper rather than overselling a new solver.
- The steel-board animation uses identical reset states and true scale, labels the ungoverned and 500×1 self-reference runs, and shows the entire energy trace. It is strong qualitative corroboration of the severe shelf failure, although it remains one scene family and a self-reference rather than external physical ground truth.
- The equal-row-count curve clearly explains the most actionable result: at 32 row evaluations, 32×1 iterations reaches `R=0.30` while 4×8 substeps remains at `R=3.13` and +481 J. This materially improves practitioner comprehension and is probably the supplement’s strongest decision-oriented frame.

### High-resolution video audit, beats 4–6

- The band-limit panel clearly shows paired full-basis and truncated-basis values for all eight injecting cells. Its message is appropriately nuanced: removing the stiff cluster reduces the ratio by 2–3 orders but leaves 6/8 cells overdrawn, so it is necessary in this setup but not sufficient.
- The final operating-guide card is exceptionally aligned with the paper: implicit/velocity control if architecture is flexible; audit and favor iterations/band limiting if XPBD is fixed; scalar storage projection only for a hard containment guarantee. It explicitly says “not a solver ranking, not a governor method” and ends “The governor is a safety net, not the product.”
- The video therefore strengthens clarity and significance but does not close the main scientific gaps: it adds no compliance- or wall-clock-matched baseline, independent physical validation, multi-machine replication, or reviewer-accessible numerical ledger.

### Video-specific fact check

- The true-scale penetration cross-section is clear and candid: 21.6 mm versus a 30 mm board, with the deployed 9.8 mm value also marked. It directly supports the “containment, not a fix” interpretation.
- One fixable wording inconsistency is visible in the equal-row beat: the video subtitle calls iterations versus substeps “at equal cost” and its held note says “Equal cost,” while the paper explicitly says equal `K·S` row evaluations are **not** equally costly because substeps repeat contact generation and integration. Relabel this “equal contact-row evaluations” or “equal row budget” before submission; the plotted experiment itself remains valid.

### Targeted novelty cross-check (primary sources)

- Hauser, Shen, and O’Brien (Graphics Interface 2003) already put contact/manipulation constraints directly into an interactive modal framework and derived rigid-plus-modal contact response. This confirms the manuscript’s correct choice not to claim the two-way modal row itself as new.
- Wei et al. (arXiv 2026) address the broader phenomenon that finite-iteration partitioned coupling can inject energy and provide an any-budget passivity certificate for bilateral port-Hamiltonian coupling; You et al. (arXiv 2026) provide energy-controllable integration for full elastodynamic contact. These raise the novelty bar for broad “energy-safe finite-budget coupling” claims, but neither inspected abstract targets this paper’s exact fixed-budget unilateral XPBD/shared-modal-row diagnostic and operating guide.
- A targeted current search found no exact duplicate of the manuscript’s empirical question or its specific scene-wide modal-storage ledger. Absence of a search hit is not proof of novelty; the defensible novelty is the measured failure map/mechanism/operating guide, not modal contact, energy tanks, or energy control in general.

### Isolated Stage G reviewer returns (sealed from remaining reviewers)

- R3, novelty/significance: **5/7 weak accept**, confidence **4/5**. Comprehension checks passed. The reviewer found the carefully isolated shared-row failure and actionable operating guide sufficiently original/significant for a focused MIG short paper, while stressing that novelty is an empirical case study rather than a new row, solver, or energy-control principle. Main limits: one unmatched implementation per host, gross rather than port-level supply, narrow normal-only regime, no governed FEM/device validation, incomplete two-file reproducibility, and potential overgeneralization of the tested block approximation. Video impact: modestly raises the score by making the failure and guardrail cost unmistakable.
- R1, physics/energy accounting: **5/7 weak accept**, confidence **4/5**. Comprehension checks passed. The reviewer independently verified the gap sign, gravity-work sign, radial projection, and Proposition 4.1 induction, finding no fatal theorem error. The main technical risk is incomplete energy closure: the ledger omits compliance/constraint/stabilization reservoirs, so `4.4×10^7 J` convincingly shows catastrophic ledger overdraw but the mild AVBD `6.7 J` should be called measured-ledger overdraw unless omitted contact energy is bounded. Other limits: unresolved high-frequency basis, approximate block ablation, unmatched hosts, missing numerical supplement, and no governed FEM. Video impact: slight raise.
- R5, presentation/practitioner/video: **6/7 accept**, confidence **4/5**. Comprehension checks passed. The reviewer found no acceptance-critical flaw and judged the diagnostic exceptionally actionable and well-supported for a short paper. It independently caught the video’s “equal cost” error against the paper’s explicit not-equally-costly statement, and also flagged dense page-4/abstract presentation, silent text-heavy pacing, categorical video wording, lack of a portable residual stopping rule, and the “production-like” label versus 11–126 ms baselines. Video impact: raises the score despite those fixable issues.
- R4, evaluation/reproducibility: **5/7 weak accept**, confidence **4/5**. Comprehension checks passed. The reviewer found the within-XPBD causal evidence convincing and no fatal flaw, but treated the absent ledger/commands/complete parameter table/full heatmap/perturbation definitions as acceptance-critical reproducibility material. Further concerns: unmatched cross-host controls, no port/total-energy claim, ambiguous `h=1/120` under substeps, no wall-clock matching, under-resolved modal spectrum, limited FEM/governed validation, and single-machine precision. Video impact: no score change because it animates existing shelf results without filling those gaps.
- R6, senior/generalist: **5/7 weak accept**, confidence **4/5**. Comprehension checks passed and no fatal contradiction was found. The reviewer judged the focused diagnosis and operating guide valuable, conditional on the promised numerical ledger being supplied and the modal-basis/timestep-fidelity concern being clarified. Decision-critical risks: Eq. (2) is a chosen scene-wide accounting policy rather than physical passivity, the deployed-timestep FEM ratio is only 0.38, and 99.6% of one excess case lies above 20 kHz; the paper still needs a decisive timestep-resolved basis case. Other limits are unmatched hosts, narrow contact regime, equilibrium-destroying projection, and CPU-only runtime. Video impact: slight raise.
- R2, contact/numerics: **5/7 weak accept**, confidence **4/5**. Comprehension checks passed. The reviewer found the within-XPBD finite-budget diagnosis convincing and no fatal flaw, while limiting the cross-host recommendation. Main issues: ambiguous `h=1/120` semantics and compliance rescaling under `K×S`; Figure 3(b) plots only primal gaps while the dual residual is prose-only; one-scene convergence ladder; high-frequency-basis dependence; approximate rather than exact block solve; no wall-clock matching; gross/nonlocal supply; and missing reproducibility details. Video impact: slight raise.

### Stage G reconciliation and area-chair calibration

- Final scores in reviewer order R1–R6: `5, 5, 5, 5, 6, 5`; mean **5.17/7**, median **5/7**. Vote characterization: five weak accepts and one accept; every confidence score is **4/5**. All comprehension checks were accurate and all six reviewers independently inspected the complete frozen PDF/video pair.
- Unanimous scientific verdict: no reviewer found a fatal algebraic or factual contradiction in the narrow result. Equation (1)’s sign is correct, and Proposition 4.1 enforces the printed scalar modal-storage ledger under the stated update order. The paper’s strongest evidence is the same-path iteration/complementarity ladder plus the 32×1-versus-4×8 equal-row-budget inversion, not the unmatched three-host strip.
- Area-chair recommendation: **weak accept / lean accept under the focused MIG short-paper bar**, not a secure accept. The contribution clears that bar as a carefully controlled negative result and operating guide, not as a new contact row, solver, passivity theorem, or accurate governor.
- Consensus acceptance risks, in priority order: (1) incomplete contact-run energy closure makes “real injection” and “energy-safe” too broad, especially for the 6.7 J AVBD margin; (2) the numerical ledger/commands/full host table/full heatmaps are not in the supplied two-file packet; (3) the decisive practical claim should be repeated or foregrounded with a timestep-resolved/FEM-faithful retained basis, because one excess is 99.6% above 20 kHz and deployment-step FEM amplitude is only 0.38; (4) cross-host controls are unmatched and support implementation observations only; (5) `h=1/120` and compliance scaling under substeps are ambiguous; (6) the tested block condensation uses a diagonal rigid-body approximation and cannot rule out exact coupled blocks.
- Verified fixable artifact defects: the video says “equal cost” although only row evaluations are equal; the paper leaves `H_ii` undefined in the printed `1/(H_ii h^2 - 1)` contact weight; Figure 3(b) does not plot the prose-reported inactive-row multiplier residual; the review copy lacks its future EasyChair paper ID; and the abstract/page-4 captions are overly dense.
- Video consensus: net positive for comprehension and significance (four reviewers explicitly raised or slightly raised, one no-change, none lowered). It makes the true-scale failure and 21.6 mm guardrail cost credible, but does not add independent validation or replace the numerical supplement.
- Cautious fallback comparison: the prior `32f2951d` simulated panel averaged 4.50/7, while this clean current panel averages 5.17/7 (+0.67). Because the artifacts, framing, video, and reviewer instances differ, this is directional calibration rather than a statistically meaningful acceptance gain.

## 2026-07-22 Split-state governor + unified multimodal pipeline audit

### Initial algebra verdict

- With `Λ ≻ 0`, `d = U_c q`, and a fixed selected row set, the proposed quasi-static component is mathematically sound: `q_qs = Λ⁻¹ U_cᵀ(U_cΛ⁻¹U_cᵀ)^+d`; `q_⊥ = q-q_qs` lies in `ker U_c`; and `q_qsᵀΛq_⊥ = 0`, so potential energy splits exactly.
- Rung 1 is the radial projection in the **energy-whitened metric** on the affine displacement-preserving subspace, provided that this proximal objective is stated explicitly. It is not the unique “proper KKT projection” without specifying a metric/objective.
- Rung 1 preserves `U_c q` for the selected rows, hence adds zero **projection-induced position-gap change** there. It does not preserve `U_c qdot`, contact impulses, complementarity, or rows omitted/misclassified by the active set; “contact-height preserving” is accurate, while “contact-valid” is not yet justified.
- If `E_qs > Ebar`, preserving the full displacement vector is infeasible. Rung 2 (`β q_qs`, zero velocity) is always energy-feasible and `β ≥ γ` because `E⁺ ≥ E_qs`; it therefore preserves a larger common fraction of the selected surface displacement than whole-state radial scaling. But it is a separate lexicographic policy (maximize a common displacement scale), not the solution of the same hard-height KKT problem.
- The formula after `q_qs` is closed form, but obtaining `q_qs` is active-set-dependent dense rank-revealing linear algebra. With 16–24 modes and up to hundreds of rows this should be implemented in modal/rank space via QR/SVD/eigendecomposition, not as a fresh `m×m` pseudoinverse; runtime, rank tolerance, and active-set churn are first-order engineering questions.

### Repository context located

- The repository already contains the current radial ledger in `dcr/avbd/_solver/passivity.py`, a prior R8 feasibility probe in `benchmarks/paper_eval/x1_passivity/probe_r8_feasibility.py`, a parked contact-consistent-governor track in `docs/mig2026_short_paper_plan.md`, and an explicit future multimodal asset-pipeline document in `docs/future_work_modal_asset_pipeline.md`.
- Audio is not merely aspirational: `dcr/sound/` contains analysis, event logging, modal banks, live/render paths and tests; numerous frozen `data/audio_basis/*.npz` assets exist. The novelty question is therefore about the automated cross-consumer contract, band/rate policy, and validation—not about first adding modal audio to the repository.

### Implementation discovery

- `dcr/avbd/_solver/passivity.py` already contains `quasi_static_split` and `gap_preserving_projection` implementing the proposed two-rung policy. The legacy `passivity_gamma` is still present, so the next audit question is wiring/default behavior rather than derivation alone.
- The implementation currently forms the redundant `m×m` Schur matrix and calls `np.linalg.lstsq`; this is mathematically serviceable for consistent rows but potentially the wrong hot-path shape when `m=200` and `r=24`. A rank-space factorization and measured overhead are needed before calling the runtime cost negligible.
- The existing `probe_r8_feasibility.py` addresses earlier deviation-referenced and band-selective floors, not the new contact-row minimum-energy split. Its prior infeasibility concern is exactly what Rung 2 resolves by relaxing heights; it does not answer how often the new Rung 1 is feasible on the actual altered trajectory.

### Implementation wiring audit

- The split-state governor is implemented, but it is opt-in: `solver_xpbd.py` initializes `_psv_gap_preserving = False`. The shipped/default path therefore remains the radial governor unless a benchmark or caller flips the private flag.
- The two-rung implementation matches the stated formulas and retains radial scaling only as a numerical fallback. It reports an energy-equivalent `gamma_eff`, not a literal common state scale on rung 1.
- The current quasi-static solve constructs `S = U_c K^{-1} U_c^T` and calls `lstsq` on the resulting `m × m` matrix. Since `rank(S) ≤ r` and the paper reaches roughly `m=200, r=24`, this is avoidably expensive and potentially tolerance-sensitive; a rank-space solve/weighted pseudoinverse should be benchmarked before calling the runtime cost “two closed-form lines.”
- The implementation comment “β ≥ γ, so penetration ≤ radial” is valid only for the selected linear displacement rows under the common-scale interpretation. It does not establish total geometric penetration, contact complementarity, or next-step impulse behavior.
- A dedicated test file and a `probe_gap_preserving.py` benchmark already exist. The next question is empirical coverage: how often rung 1 versus rung 2/fallback occurs on the four paper trajectories, and what it does to gap, trajectory, impulses, and runtime.

### Solver integration and test coverage

- The XPBD host extracts only support rows whose accumulated normal multiplier satisfies `lam > tol`, after the velocity solve, then projects the modal state. This is a reasonable definition of “load-bearing” for the prototype, but the multiplier is reset each substep by default, so row-set churn and threshold sensitivity are plausible trajectory-level effects.
- The code measures maximum penetration before applying the modal projection. Any reported `_last_max_penetration` therefore cannot by itself verify the governor’s post-projection gap claim; the comparison probe must recompute the post-projection geometry explicitly.
- Unit tests establish empty-set equivalence, `K`-orthogonality, selected-row displacement preservation, two-rung energy feasibility, rank-deficient synthetic rows, and inertness. They do not yet test full-solver active-set extraction, post-projection geometric gaps, contact velocity, complementarity/next-step corrective impulse, row churn, float32/device parity, zero/near-zero modes, or runtime.
- The test phrase “rung 2 is never worse than radial” should remain narrowly scoped to the selected linear displacement vector. A larger preserved `|U_c q|` can be better or worse geometrically depending on sign, pre-existing penetration, rigid-body motion, and omitted rows.

### Existing full-trajectory A/B evidence

- `out/gap_preserving.csv` is already a four-cell, full-trajectory comparison rather than a frozen-trajectory counterfactual. Both radial and split-state arms satisfy the repository’s scalar ledger checks in all four cells.
- Shelf `4×1`: worst post-projection violation falls from **21.59 mm to 7.93 mm** (about 2.7×); rung 1 occurs 53/102 clamps (52%), rung 2 49/102.
- Shelf `8×2`: **6.43 mm to 2.14 mm** (about 3.0×); rung 1 occurs 178/190 clamps (94%), rung 2 11, numerical fallback 1.
- Ledge `4×1`: **21.19 mm to 20.15 mm** (only about 1.05×); rung 1 occurs 44/102 clamps (43%), rung 2 58. This is the clearest counterexample to describing the method as eliminating the governor artifact under severely starved budgets.
- Ledge `8×2`: **4.08 mm to 0.931 mm** (about 4.4×); rung 1 occurs 152/153 clamps (99%), rung 2 once, and maximum clamp-induced violation is only about 0.0028 mm.
- Practical interpretation: the method is effective when the budget can afford the quasi-static contact component, and its own rung histogram is a useful health signal. If rung 2 is frequent, the method is chiefly a less-damaging fallback rather than a contact-preserving projection.
- The current probe still lacks trajectory error against a trusted reference, `U_c qdot` change, complementarity/next-step impulse, active-set stability, per-step factorization time, and device/runtime results. Peak modal energy alone is not an accuracy metric.
- Verification on the current repository head (`6044b1b`) passed all **29** dedicated gap-preserving tests. The frozen A/B manifest records the same head, so the inspected CSV corresponds to the implementation reviewed here.

### Unified-pipeline design-note audit

- The proposal is more precise than “one modal state”: it is one offline modal asset plus a shared contact-excitation/event stream, with **consumer-specific runtime states and rates**. Audio cannot literally consume a 120–480 Hz state for 20 kHz output; it must run its own high-rate resonator bank. Haptics likewise uses a higher control/update loop than its useful vibration band.
- The repository plan correctly treats one-way visual ringing as the v1/default tier and two-way co-simulation as optional. This keeps the pipeline idea separate from the risky shared-row mechanism diagnosed by the short paper.
- Implemented pieces are substantial but incomplete: modal analysis/steppers, contact excitation logging, an audio resonator/render path, and paper-derived rate guidance exist. Missing practitioner-critical pieces include a robust import/compiler contract, material/damping presets, radiation/attack modeling, actuator transfer/calibration, haptic export, authoring/audition UI, performance budgets, and cross-modal validation.
- The strongest potentially publishable claim is therefore not “modes drive graphics, sound, and haptics”; it is a reproducible **rate-aware asset compiler and runtime contract** that automatically partitions a provenance-tracked modal asset, prevents unrepresentable modes from entering a two-way solver, and emits calibrated consumer packages from one excitation semantics.
- Several categorical claims in the design note require literature/product verification before publication, especially “industry does not two-way couple reduced modal models” and “nothing shipped is geometry+material-first.” They are not needed for a strong systems pitch.

### Repository modality inventory

- The sound path is compact but concrete: `audio_basis.py`, event/logger modules, modal bank, shaping, offline render, live output, documentation, and Stage-E6 tests are present.
- No haptic renderer/export subsystem appears in the corresponding file inventory. The repository does contain prior haptic literature references in deformed-normal code, so haptics is a proposed third consumer, not an implemented “small final step.”
- A broad text search was polluted by an embedded base64 HTML artifact; follow-up searches must exclude generated HTML/media to avoid treating encoded payloads as repository evidence.

### Implemented audio path versus pipeline claim

- Stage E6 already enforces the key architectural separation: a low, sim-representable co-solved band and a 44.1 kHz open-loop audio bank driven by logged contact excitation. It has offline and live paths, event aggregation, basis caching, damping/radiation heuristics, attack shaping, ledgering, and CPU/device staging tests.
- The audio code itself repeatedly labels modal synthesis as standard and its fidelity as plausible rather than measured. This is the right novelty discipline for a future paper.
- The band cutoff is currently partly hand-set (`fmin_hz`, e.g. 150 Hz) and the audio assets use consumer-specific approximations/material overrides. A truly unified compiler must make the split rule explicit from actual simulation substep/integration limits, record why each mode went to each consumer, and either share or deliberately version material/provenance fields.
- The present audio pipeline demonstrates feasibility, but not yet the promised “material in, analysis automatic” experience: shape-class-specific builders, collision-proxy corrections, per-kind constants, radiation heuristics, contact choke, doublet detuning, and shell formulas contain substantial expert-authored logic. That is valuable engineering, but the automation claim should be evaluated against this hidden authoring cost.

### Haptics implementation delta

- A source-only search confirms that the only haptics-related implementation references are deformed-normal evaluation inspired by Barbič–James; there is no AHAP/OpenXR/DualSense/actuator rendering code or haptic test suite.
- Calling haptics “mostly easy” understates the work. The shared excitation is reusable, but a practitioner-ready path still needs actuator identification/equalization, saturation and slew limits, signal/envelope choice per actuator, latency scheduling, handle/contact spatial mapping, safety/comfort limits, device-specific exports, and perceptual validation.
- The sound subsystem’s API/test inventory is mature enough to serve as a template for a haptic consumer, which is a favorable engineering fact; it does not make the third modality scientifically validated yet.

### Primary-literature novelty check — first pass

- The broad “unified visual/audio/haptic pipeline” idea is not new. Sterling and Lin’s 2015/2016 integrated multimodal system used normal/relief maps as one representation for visual rigid-body behavior, haptic display, and modal sound, with user studies on multimodal cohesion (`doi:10.1016/j.cag.2015.10.010`).
- Hasti (Chan, Tymms, Colonnese, IEEE World Haptics 2021) is especially close at the architecture level: conventional visual material/geometry maps feed a real-time micro-contact simulation; its displacements drive vibrotactile actuators and its impulse stream drives modal sound synthesis. It also includes an exploratory perceptual study. This directly precludes novelty for “same event/material representation produces synchronized touch and sound.”
- Rausch, Hentschel, and Kuhlen (VRIPHYS 2015) already compute modal sound data from object geometry and material at runtime, with level-of-detail geometry and asynchronous prioritization. Therefore “automatic material/geometry to modal audio asset” is established prior art.
- Older primary work separately establishes modal constrained visual deformation (Hauser–Shen–O’Brien 2003), reduced-deformable haptic contact (Barbič–James 2008), and sound generated from physically based deformable motion (O’Brien–Cook–Essl 2001). The ingredients and most pairwise bridges are mature.
- The surviving novelty opportunity is narrower: structural-mode **rate partitioning across three consumers**, grounded by a measured failure of co-solving under-resolved modes, plus an end-to-end compiler/runtime contract and evaluation. The search so far found no exact match for that combined rule, but absence of a hit is not proof.

### Rate separation, practitioner evidence, and current novelty pressure

- Multi-rate multimodal architecture itself is established: haptic literature has long run graphics/physics and haptic loops at different rates, and Hasti explicitly converts 60–200 Hz macro contact positions into a 44.1 kHz micro-contact simulation whose displacements and impulses drive touch and sound. Therefore “different consumer rates from one interaction” is not a novelty claim.
- Hasti’s eight-participant exploratory study averaged over 85% texture identification and performed best in the combined audio+haptic condition. Sterling–Lin likewise report improved task ease/cohesion from a unified multimodal representation. These are encouraging evidence that coherent multisensory rendering can be useful, though neither proves production workflow value.
- Hasti also exposes why the proposed haptic band cannot be a universal fixed range: tested voice-coil and LRA devices produced perceptually distinct results, and the paper names uncompensated actuator frequency response as a limitation. The compiler should consume a measured/device-profile transfer function rather than assume every target reproduces 30–500 Hz directly.
- Recent object-centric work such as ObjectFolder already packages visual, auditory, and tactile representations into a uniform asset, while modern geometry/material-to-sound datasets and modal pipelines further crowd the broad asset-unification claim. The differentiator must be executable correctness and workflow evidence, not simply bundling modalities.
- Exclusive “mode ownership” is not required across senses: the same physical mode may appropriately be visible, audible, and tactile. The strict partition is specifically between modes allowed to **feed back into the low-rate dynamics** and modes rendered open-loop. Each sensory renderer should apply its own overlapping transfer/selection function.

### Quasi-static solve microbenchmark

- A local current-head microbenchmark confirms that the formula is cheap only after choosing the right factorization. The existing `m×m` normal/Schur solve took about **1.40 ms** at `m=200,r=24`; solving the whitened thin system `A = U_c Λ^{-1/2}`, `x=A^+d`, `q_qs=Λ^{-1/2}x` took about **0.071 ms**—roughly **20× faster** on this machine. At 40–48 rows and 16 modes the direct form was about 2× faster (roughly 0.024–0.026 ms).
- The thin solve is also numerically better because the current `S=A A^T` construction squares the condition number. In a 200-row/24-mode duplicated-row stress case, current relative displacement residual was about `1e-8` versus `7e-15` for the direct whitened least-squares solve, with otherwise matching states.
- Recommendation: formulate and implement the solver in whitened modal space with a thin rank-revealing SVD/QR or `lstsq(A,d)`. Then the runtime claim can honestly be “one small rank-space solve plus closed-form scaling,” not “two closed-form lines.”

### Concurrent worktree change detected

- During a read-only instrumentation attempt, `passivity.py`, `solver_xpbd.py`, and the benchmark changed relative to the implementation first inspected: the current call now passes per-row multiplier priorities and the benchmark accepts extra keyword arguments. New `gap_preserving_v2` outputs also appeared.
- These are pre-existing/concurrent user changes, so they will not be modified or reverted. Earlier v1 algebra and frozen `gap_preserving.csv` observations remain valid for that snapshot, but the final implementation verdict must inspect the new priority-prefix policy and v2 results before citing current behavior.

### Priority-prefix v2 audit

- The concurrent v2 adds a third policy: when the full selected displacement vector is unaffordable, sort rows by descending current multiplier and preserve the largest affordable prefix. This eliminates almost all rung-2 use in the frozen v2 runs and materially improves shelf `4×1` (worst gap **21.59→4.86 mm**, versus 7.93 mm in v1). It does not rescue ledge `4×1` (**21.19→20.08 mm**).
- Other v2 worst-gap results are strong: shelf `8×2` **6.43→0.501 mm** and ledge `8×2` **4.08→0.931 mm**. The policy therefore makes the well-resolved shelf cell substantially better than v1 while leaving the already-good ledge `8×2` essentially unchanged.
- Rung 1b is not the KKT solution of the original all-height constraint; it is a **lexicographic active-row selection heuristic**. Its defensible statement is “preserve the largest affordable multiplier-prioritized prefix,” not “contact-height preserving” globally or “penetration optimal.” Omitted rows can move non-radially.
- Multiplier magnitude is a plausible load priority but can inherit solver ordering, compliance, warm-start, and active-set noise. A weighted geometric/impulse objective or ablation over priority definitions is needed before elevating this heuristic to a general method.
- The v2 shelf `4×1` CSV reports `passive=True` but `holds=False`. Even if this is only cumulative-accounting roundoff and a later uncommitted micro-scale addresses it, the frozen result does not yet support an unconditional “all ledger checks pass” claim. It must be regenerated and independently verified.
- Prefix bisection calls the current ill-conditioned `m×m` split repeatedly. This strengthens, rather than weakens, the need for a thin whitened factorization and measured end-to-end overhead.
- The current expanded test suite passes **31/31** tests and now includes one synthetic prefix-priority case plus a strict ceiling-roundoff test. It still does not cover full-trajectory velocity/complementarity/impulse behavior, alternative row priorities, prefix numerical monotonicity under ill-conditioning, or runtime.

### Current in-memory v2 verification

- Re-running the four gap-preserving arms in memory after the strict micro-scale change makes both ledger checks pass in all four cells, while reproducing the frozen v2 gap numbers. The earlier shelf `4×1 holds=False` was therefore fixed in current code, but the on-disk v2 CSV remains stale and should not be cited until regenerated.
- Actual clamp-time active sets are much smaller than the 200 support-row worst case: shelf median about 20–22, max 24; ledge median 4–8, max 8. Measured projection cost on this CPU was modest: median **0.032–0.094 ms**, p95 **0.068–0.157 ms**, maximum 0.325 ms across these runs.
- This corrects the runtime risk calibration: the current factorization is not a blocker on the tested trajectories. The thin whitened solve remains the cleaner and more robust formulation—especially for future larger active sets and prefix repetition—but optimization is a hardening task, not a prerequisite for demonstrating value here.
- Median preserved-row fraction on clamp calls was about 80% for shelf `4×1`, 50% for ledge `4×1`, and 100% in both `8×2` cells. This aligns exactly with the outcome: the method is strong when nearly all loaded rows are affordable and weak when half the ledge rows must be sacrificed.

### Earlier synchronized multisensory precedents

- DiFilippo and Pai’s AHI (UIST 2000) already rendered tightly synchronized haptic and auditory stimuli from the **same contact-force profile**, with a latency study. Shared excitation is therefore a foundational design pattern, not a new contribution.
- Pai et al.’s ACME/“Scanning Physical Interaction Behavior of 3D Objects” (SIGGRAPH 2001) explicitly targeted automatically acquired models for visual, haptic, and auditory virtual-object feedback. It is data-driven rather than the proposed material/FEM compiler, but makes a broad “automatic multisensory object asset” novelty claim untenable.
- These precedents sharpen the positioning: the pipeline can still be a useful and potentially publishable engineering system, but only if it claims a specific new contract—structural modal provenance, solver-safe feedback gating, overlapping calibrated sensory transfer functions, and an end-to-end authoring/runtime evaluation.

### Final advisory verdict

- **Governor:** mathematically sound and empirically useful as a less-destructive admissible projection. It is not a contact solve and does not justify “zero penetration,” “contact valid,” or “word-for-word proof” language. The exact claim is zero projection-induced displacement change on selected affordable rows; the scalar ledger induction carries over after replacing the projection-feasibility lemma.
- The original clean two-rung method gives meaningful but regime-dependent improvement; the concurrent priority-prefix version improves the shelf cases further, at the cost of a heuristic row-selection policy. The starved ledge `4×1` cell remains a hard negative result. This should be presented as a health-monitored safety governor, with preserved-row/rung statistics exposed.
- **Pipeline:** the broad architecture is not genuinely novel—automatic multisensory assets, shared contact excitation, modal audio, multimodal visual/haptic/audio systems, and multi-rate loops all have direct precedents. A narrower contribution may be novel: a rate-aware structural-modal compiler whose explicit safety contract determines which modes may feed back into dynamics and emits calibrated, separately clocked sensory renderers from one provenance/event model.
- **Practitioner value:** potentially high, because it can reduce duplicate authoring and sensory mismatch, but the current repository proves audio architecture rather than a production pipeline. Adoption evidence must include import success on messy assets, authoring-time reduction, designer override/audition workflow, device calibration, runtime budgets, failure diagnostics, and a multisensory user study.
- Recommended scope separation: keep the MIG short paper focused on the diagnosed coupling failure and containment lesson; treat the governor as a validated follow-up or compact extension only if contact/trajectory evidence fits, and develop the unified pipeline as a separate systems/demo/long-paper contribution.
