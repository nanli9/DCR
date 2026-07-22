# Future work — the modal asset pipeline (sim + sound + haptics from one basis)

> Status: **design note, not a commitment.** Nothing here is in scope for the MIG
> 2026 short paper (deadline 2026-08-07) and nothing here is claimed as a
> contribution anywhere in `paper/`. Written 2026-07-22 from the session
> discussion so the reasoning is not lost.
>
> Repo scope reminder (CLAUDE.md): impact-sound synthesis is an **E6 demo**, the
> modal IIR bank is standard (van den Doel–Pai 1998), and it is *never* a claimed
> contribution. This document keeps that discipline: the pipeline's novelty, if
> any, would be in the **integration and the authoring flow**, not the synthesis.

## 1. The idea in one paragraph

One offline analysis per asset (tet mesh + material → generalized eigenproblem →
modes, frequencies, damping, radiation weights) produces one provenance-tracked
**modal asset**. One timestamped contact-excitation contract then feeds three
consumer-specific runtime states, selected by what each renderer and device can
represent:

| consumer | band | rate | coupling |
|---|---|---|---|
| visible motion | solver-feedback-eligible low modes | sim rate (120–480 Hz) | one-way *or* two-way co-solve |
| audio | audible modes selected by the acoustic renderer | 44.1/48 kHz | open-loop from logged excitation |
| haptics | modes selected through a target-device transfer profile | device/control rate (typically 1–3 kHz or higher internally) | open-loop from the same excitation |

The excitation stream is shared, so what you hear, see shake, and feel are the
same physical event. This is the E6 architecture (`dcr/sound/`) generalized: the
audio and haptic banks are separately clocked renderers of the event stream, not
consumers of one sim-rate modal state. Their selections may overlap—the same
physical mode can correctly be visible, audible, and tactile. The **strict split
is the solver-feedback gate**: never co-solve a mode the substep rate/integrator
cannot represent. That is the documented stiff-row injection failure mode and
the correctness spine of the proposed compiler.

## 2. Why the visual tier is the hard/optional one

Production engines rarely expose two-way coupled reduced modal models for ordinary
props. Five stacked reasons, three of which this repo has *measured*:

1. **Payoff asymmetry.** Stiff-prop vibration is millimetre-scale. One-way
   (detect contact → ring the modes, no back-reaction) captures nearly all the
   perceptual value at zero solver risk — hence Coevoet et al. 2020 as the
   real-time precedent. Cross-check from our own data: distant transfer in a
   realistic scene was ~0.1 % of ring energy (see
   `memory: stylization-features-rejected`).
2. **Stability / QA risk — measured here.** A shared stiff DOF in a truncated
   solver overdraws by up to 4.4×10⁷ J (paper §3.1). Add box–box rectification of
   a ring into net rigid torque (idle stacks topple; `memory:
   impulse-boxbox-ride-rectification`) and ARM/x86 divergence on chaotic stacks
   (breaks lockstep networking; `memory: arm-x86-chaotic-scenes`).
3. **Solver architecture mismatch.** Engines get their performance from island
   decomposition, graph coloring, warm starting and sleeping. A globally shared
   `q` touches every contact on the prop (the paper's "dense on the modes"
   observation), which merges islands, complicates the parallel solve, and
   prevents sleeping (a ringing support keeps waking its neighbours).
4. **Content pipeline cost.** Modal DOFs need a tet mesh, material parameters and
   an eigensolve per asset. Prop artists author render meshes and convex hulls;
   nobody currently owns `E, ν, ρ`, let alone damping.
5. **Where two-way matters, linear modal is the wrong model.** Gameplay-relevant
   deformation is large-amplitude / nonlinear / topology-changing, so the
   industry's two-way route went full-space GPU FEM (PhysX 5 softbody, Chaos
   Flesh). Linear modal's sweet spot — small-amplitude stiff ringing — is exactly
   where one-way suffices. Modal got squeezed out visually and thrived in audio,
   where small-amplitude linear vibration *is* the physics of the signal.

**Consequence for the pipeline:** ship one-way as the default visual tier; offer
the two-way co-solve only where the paper's operating guide says it is safe
(implicit modal weight, or converged iterations), with the governor as the
fail-safe. The MIG paper is, in effect, the safety datasheet for that tier.

The governor's own cost—up to 21.6 mm of penetration where it is load-bearing—is
the practitioner's main objection to that fail-safe, and it now has a measured
successor: see `gap_preserving_projection.md`. Reviewer-safe wording is important:
the successor preserves selected affordable **surface displacements**, not
contact velocity or complementarity, and cannot preserve a surface state whose
minimum elastic energy already exceeds the ledger ceiling.

## 3. Game audio today, and where modal synthesis fits

**The shipped pipeline is samples + middleware, event-driven:**

1. Physics raises a contact event (impulse magnitude, material pair, position,
   relative velocity, contact type — impact / slide / roll from manifold
   persistence).
2. Middleware (Wwise, FMOD) maps it to an *event*: a material-pair switch selects
   a sample pool; round-robin + random pitch/gain avoids repetition; an RTPC curve
   maps impulse → volume/filter; cooldowns and voice limits prevent
   machine-gunning.
3. Scrapes/rolls are looped or granular samples with speed-driven crossfades.
4. Spatialization/acoustics is a separate layer (attenuation, HRTF, reverb zones,
   or precomputed wave acoustics à la Project Acoustics).

Sound designers author everything; physics only *triggers*.

**Procedural modal synthesis has repeatedly knocked and stayed niche**: Phya
(Menzies), Audiokinetic SoundSeed Impact (modal resonators fit from *recordings*;
later retired), GameSynth, Nemisindo. Why it stalls: samples are cheap and sound
rich; pure linear modal sounds "ringy" without the broadband attack; the audio CPU
budget is small; and — the decisive one — designers demand authorial control, and
"the FEM says so" removes their knobs.

**The academic pipeline** (our E6 is a working instance): tet mesh + material →
`K, M` → eigensolve → (ω_i, damping, mode shapes) → impulses excite a van den
Doel–Pai IIR bank, per-mode gains from the mode shape at the contact point →
radiation weighting → mix.

## 4. The fidelity problem, and the known recipe

Raw FEM modal is the weakest part of the chain. Three fixes, each addressing a
different deficiency, in priority order:

1. **Attack residual (largest perceptual win).** The first ~10 ms of a real impact
   is broadband crunch, not modes. Layer a short recorded/granular attack per
   material class *under* the physically computed ring. This is the SoundSeed /
   Ren–Yeh–Lin (2013) recipe.
2. **Fit what FEM cannot predict; keep what it can.** Frequencies and mode shapes
   from geometry (FEM is good at these); **damping and per-mode output gains fit
   from a handful of recordings** (FEM is bad at these, and damping *is* the
   perceived material). This also answers the "plug in a real material" UX: a
   material preset is a fitted damping + radiation package, not a row in a
   handbook.
3. **Radiation.** Cheap per-mode weights `rho_i` for v1; precomputed acoustic
   transfer (Chadwick & James; KleinPAT/FFAT maps, Wang & James 2019) when
   spectral balance and spatial brightness matter.

**Scope honestly:** compact stiff props are in; thin shells (gongs, sheet metal,
cymbals) need nonlinear mode coupling and should be excluded from v1 rather than
shipped badly.

**Authoring stance that wins designers instead of threatening them:** physically
derived *defaults*, designer-overridable knobs (per-mode gain/damping curves,
material presets, an audition tool). The pitch is "no more authoring 40 impact
variations per prop," not "the simulation replaces you."

## 5. Haptics — reusable excitation, substantial device work

The same excitation can drive a haptic renderer, but a universal 30–500 Hz
band-pass is not a sufficient device model. The renderer should apply a measured
or vendor-supplied actuator transfer profile, then enforce amplitude, slew,
thermal/duty-cycle, latency, and comfort limits.

- **Wideband actuators** (voice coils and suitable broadband devices) can receive
  an equalized waveform within their measured operating envelope.
- **Narrowband LRAs** (~170–250 Hz resonance) cannot reproduce a waveform: render
  the **amplitude envelope** of the band onto the actuator's resonance instead.
- **Perceptual mapping** matters: vibrotactile sensitivity peaks near 250 Hz, so
  level mapping should be perceptual, not linear in energy.
- **Spatial mapping** matters: a modal response at the simulated contact must be
  mapped to the actuator location(s), not treated as a global scalar rumble.
- Export targets: Apple AHAP, DualSense, Interhaptics/Razer, OpenXR haptics.

This is a promising integration target, not an unoccupied research category.
The AHI already synchronized audio and haptics from one force profile; ACME
targeted automatically acquired visual/haptic/auditory object models; Hasti
generated synchronized tactile and modal-audio feedback from visual material
representations. The narrower gap here is a structural-modal, rate-certified,
device-calibrated authoring path—not “the first shared audio/haptic excitation.”

## 6. Suggested v1 scope (post-MIG)

Impacts only, one-way visual tier, audio + haptics from the shared excitation:

- **In:** offline analysis tool (mesh + material → modal package); one-way visual
  ringing; audio bank with attack residual + fitted damping presets; haptics
  export for one wideband and one narrowband target; an audition/authoring UI.
- **Out (v1):** friction/scrape/roll excitation (our coupling is normal-only —
  a genuinely different excitation model, and the biggest functional gap); thin
  shells; the two-way visual tier (gated behind the paper's operating guide).
- **Risks, in order:** audio fidelity ceiling of linear modal (§4); damping data
  acquisition; designer adoption; audio CPU budget for many simultaneous props.

## 7. What already exists in this repo

- `dcr/sound/` — offline band-split modal IIR bank, ledger-capped, driven by the
  logged per-substep native-contact excitation (E6 demo). Tier-1 live path via
  `sounddevice` behind a lazy import.
- `dcr/modal/` — eigenproblem, steppers, energy accounting.
- The excitation stream itself (ledger-bounded native multiplier) — already the
  shared object the three consumers would read.
- `paper/main_short.tex` — the operating guide that gates the two-way visual tier.

Three of the pipeline's pieces are therefore already built; what is missing is the
authoring flow, the fidelity work of §4, and the haptics mapping of §5.

## 8. Novelty assessment — honest version

### What is established prior art

- Shared contact excitation for synchronized audio and haptics: DiFilippo and
  Pai, [The AHI (UIST 2000)](https://doi.org/10.1145/354401.354437).
- Automatically acquired visual, haptic, and auditory virtual-object models:
  Pai et al., [ACME / Scanning Physical Interaction Behavior](https://sensorimotor.cs.ubc.ca/2001/08/01/acme/).
- A unified representation used for visual dynamics, haptic display, and modal
  sound, including perceptual evaluation: Sterling and Lin,
  [Integrated multimodal interaction using texture representations](https://www.sciencedirect.com/science/article/pii/S0097849315001715).
- Low-rate scene contact expanded into a high-rate micro-contact process whose
  displacement drives touch and whose impulses drive modal audio: Chan, Tymms,
  and Colonnese, [Hasti (World Haptics 2021)](https://www.ncolonnese.com/research/Hasti/whc2021_sc_ct_nc_final.pdf).
- Automatic geometry/material-to-modal-audio analysis, including runtime LOD and
  asynchronous scheduling: Rausch, Hentschel, and Kuhlen,
  [Level-of-Detail Modal Analysis](https://diglib.eg.org/items/fa784fd2-78c9-400d-a376-2381c750bb33).

Therefore the broad claims “one asset feeds sight, sound, and touch,” “one event
feeds several rates,” and “geometry/material automatically produces modal audio”
are not novel.

### The defensible contribution

> A rate-aware structural-modal asset compiler that records physical provenance,
> certifies which modes may feed back into a low-rate dynamics solver, and emits
> separately clocked, calibrated visual, audio, and haptic render packages from
> one excitation semantics.

The potentially new part is the **executable safety and authoring contract**:

1. an explicit numerical eligibility test for the two-way band, motivated by the
   measured under-resolved shared-row failure;
2. automatic consumer manifests recording selection, rate, damping, units,
   transfer function, and fallback policy per mode;
3. one versioned excitation schema with deterministic timing and coordinate
   conventions across all renderers;
4. tests that reject an asset when an unrepresentable mode leaks into the
   coupled solver, instead of relying on an artist or integrator to notice;
5. designer-overridable material/fidelity controls that remain traceable to the
   generated physical defaults.

This is systems/tooling novelty, not a new eigensolver, modal synthesizer,
multirate architecture, or general multisensory principle.

## 9. Practitioner-value gates

The practitioner case is plausible but not yet demonstrated by the repository's
audio prototype alone. A credible v1 evaluation should pass all of these gates:

1. **Asset ingestion:** report success/failure and repair time on a varied set of
   real production meshes—open surfaces, bad topology, thin parts, composites,
   collision/render-mesh mismatches—not only clean tetrahedral examples.
2. **Authoring:** compare time and iteration count against a conventional
   sample/event workflow; include an audition UI, presets, overrides, and a clear
   fallback when the physical model is a poor fit.
3. **Dynamics:** naive all-mode co-solve versus certified feedback band versus
   one-way rendering; report stability, trajectory/contact error, and runtime.
4. **Audio:** measured or listener-rated comparison against recordings; separate
   modal ring, attack residual, radiation, and fitted damping ablations.
5. **Haptics:** at least one wideband and one narrowband target, each with measured
   transfer/equalization, saturation/latency logs, and a perceptual study.
6. **Cross-modal consistency:** synchronized versus deliberately mismatched
   excitation/material conditions, testing recognition, realism, and preference.
7. **Scalability:** simultaneous-asset/voice budgets, cache/build times, memory,
   deterministic rebuilds, and graceful LOD/fallback behavior.

Useful go/no-go evidence is not merely “all three outputs play.” It is measurable
authoring-time reduction without worse perceived quality, plus automatic
prevention of the unstable configuration documented by the MIG work.

## 10. Publication and product positioning

- Keep the MIG short paper focused on the coupling failure, operating envelope,
  and the governor evidence it actually validates; do not add the full pipeline
  claim to that paper.
- Develop this as a separate systems/demo or long-paper track. Lead with the
  compiler contract and workflow result, then treat the three renderers as its
  consumers.
- Say **one analyzed asset + one excitation contract**, not “one modal state
  shipped to three renderers.” Audio and haptics require their own clocks and
  states.
- Treat the gap-preserving governor as the safety mechanism for the optional
  two-way tier, not as evidence that every modal asset is safe to co-solve.
