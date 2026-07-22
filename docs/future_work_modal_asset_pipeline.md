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
modes, frequencies, damping, radiation weights) feeds **three** consumers at
runtime, band-split by what each can represent:

| consumer | band | rate | coupling |
|---|---|---|---|
| visible motion | sub-Nyquist modes (≲ substep rate / 4) | sim rate (120–480 Hz) | one-way *or* two-way co-solve |
| audio | 20 Hz – 20 kHz | 44.1/48 kHz | open-loop from logged excitation |
| haptics | ~30–500 Hz | 1–3 kHz | open-loop from the same excitation |

The excitation stream is shared, so what you hear, see shake, and feel are the
same physical event. This is the E6 architecture (`dcr/sound/`) generalized: the
audio bank is a *renderer* of the contact-excitation stream exactly as the viewer
is a renderer of the displacement stream. **The band-split rule is the
correctness spine**: never co-solve a mode the substep rate cannot represent —
that is the documented stiff-row injection failure mode, and it is the subject of
the MIG short paper.

## 2. Why the visual tier is the hard/optional one

Industry does not two-way couple reduced modal models. Five stacked reasons, three
of which this repo has *measured*:

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

The governor's own cost — up to 21.6 mm of penetration where it is load-bearing —
is the practitioner's main objection to that fail-safe, and it now has a
measured successor: see `gap_preserving_projection.md` (same bound, penetration
down 4.4–12.8× on three of four cells, unchanged in the one cell where the
surface being preserved is itself the artifact).

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

## 5. Haptics — mostly easy, with one real step

The same excitation, band-passed to roughly 30–500 Hz, drives the actuator.

- **Wideband actuators** (DualSense voice coil, high-quality LRAs) can take the
  band-passed waveform almost directly.
- **Narrowband LRAs** (~170–250 Hz resonance) cannot reproduce a waveform: render
  the **amplitude envelope** of the band onto the actuator's resonance instead.
- **Perceptual mapping** matters: vibrotactile sensitivity peaks near 250 Hz, so
  level mapping should be perceptual, not linear in energy.
- Export targets: Apple AHAP, DualSense, Interhaptics/Razer, OpenXR haptics.

Precedent: event-based haptics work (Kuchenbecker et al.; VerroTouch) showed that
*measured transients* feel dramatically better than canned rumble. Audio→haptics
middleware exists (Lofelt → Meta, Interhaptics); **nothing shipped is
geometry+material-first**, which is the gap this pipeline would fill.

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
