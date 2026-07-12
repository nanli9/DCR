# Stage E6 demo — offline impact-sound render (band-split modal bank)

*Scope change 2026-07-11 (user-approved, CLAUDE.md amended): E6 is the logged
sound-energy bound **plus this offline render demonstrating it**. Synthesis is
a standard technique (van den Doel & Pai 1998 modal IIR bank) and is NOT a
claimed contribution.*

## Architecture — the band split

The co-solved sim-rate modal band (the paper's contribution) is **untouched**.
It cannot carry sound: at the default 240 Hz substep rate its Nyquist is
120 Hz, and pushing kHz eigenmodes into the fixed-budget q-block is exactly
the stiff-row energy-injection failure mode the paper documents. So:

| band | modes | rate | coupling | role |
|---|---|---|---|---|
| dynamics (existing) | ~10, ≤ substep Nyquist | sim substep | two-way, ledger-clamped | trajectories, contact events, rattle timing |
| audio (`dcr/sound/`) | ~50–60/object, 150 Hz–20 kHz | 44.1 kHz offline | **open-loop** | timbre |

Both bands are excited by the same physical multiplier: the audio band replays
the per-substep engaged support force `F_n = −min(ρC + λ_eff, 0)` — the exact
force assembly the native q-block consumes (`solver_6dof._modal_qblock_solve`)
— logged by `dcr/sound/logger.py` via `substep_end_hook` (recording runs only;
zero cost otherwise). One-way is defensible up here: modal displacement per
unit impulse ∼ 1/ω, back-reaction energy ∼ 1/ω².

## Pipeline

1. **Log** (`logger.SoundImpulseLogger`): per substep, per SUPPORT row —
   engaged `F_n`, corner world (x, z), body v_y, and total rigid mechanical
   energy (same quantity the §15 sim ledger differences).
2. **Events** (`events.extract_impulses`): high-pass each row's force
   (mirrors the coupler's own overlay-HP deviation), burst-aggregate rises →
   one event per impact with `J = ΣΔF⁺·h_sub`; `j_floor = 1e-3 N·s` gates
   resting-load jitter (measured: 23k events at 1e-5, 1k at 1e-3; real
   impacts ≥ 5e-2). **Settle muting** (`events.settle_arm_index`, default
   on offline + live): scenes start with every body ~1 mm above the support,
   so t≈0 emits a burst of real-but-unwanted settle clinks (measured: 222
   events by t=0.15 s at v≈0.05 m/s, J ≤ 0.028 N·s, then a 192 ms silent gap
   before the pot at 0.333 s). Scene-agnostic arming, first rule wins:
   (1) a `settle_quiet=0.15 s` event-free window passes; (2) **prominence** —
   an event ≥ 5× the loudest muted clink breaks through immediately, so an
   impact landing INSIDE the settle window (low drops, launched impactors)
   is never swallowed (verified: 0.25 m drop arms at the impact, t=0.237 s);
   (3) the `settle_max=1.5 s` deadline. Muted events don't debit the ledger
   (a kick that never plays must not consume budget). All thresholds are
   parameters (`--settle-quiet/--settle-max/--settle-prominence` offline;
   `settle_quiet/settle_max/arm_prominence/arm_j_floor` live); nothing is
   scene-specific.
3. **Shaping** (`shaping.py`): Hertz τ ∝ v^(−1/5) (τ_ref per material pair),
   half-sine kernel with fractional-delay placement (no substep-grid comb).
4. **E6 cap** (`render.AudioLedger`): per substep, deposit
   `η_audio · max(−ΔE_rigid_mech, 0)`; per event, admit the **kernel-filtered
   effective kick** `½‖g·|Ĥ(ω;τ)|‖²` (what the bank actually receives — raw
   ½‖g‖² overcounts high modes and diverges with mode count), scale by
   γ = √(reservoir/E) when it binds (§6 quadratic form, §15 inequality).
5. **Bank** (`bank.py`): exact impulse-invariant biquads per mode (paper
   Eq. 8), lfilter fast path parity-tested against the per-sample exact
   propagator reference (CLAUDE.md rule 6).
6. **Bases** (`audio_basis.py`): table = k=64 eigsh of the SAME slab FEM
   recipe as the shared-operator arm, modes < 150 Hz dropped (crossover:
   sim band + poor radiators); bodies = free-free eigsh (negative-shift
   invert), 6 rigid modes dropped, **real-object thickness** for the audio
   mesh (5 mm porcelain, 3 mm steel — the 2 cm collision proxy is not the
   thing that rings).

## Demo result (dinner scene, defaults)

```
python scripts/render_sound.py --seconds 6 --out exports/sound/dinner_impact.wav
```

- 1440 substeps, 200 support rows, 1036 events, peak F = 514 N.
- Bases: table 53 modes 151–828 Hz (wood, Rayleigh ζ); plate 12 modes from
  3.0 kHz; pot 20 from 1.7 kHz; fork/knife 7 from 2.3 kHz; cup 2 at ~9.1 kHz.
- **E6 holds with headroom**: effective kick energy 11.5 J ≤ η·rigid loss
  25.69 J; ledger inert (0/1036 capped) — the physically-shaped excitation
  fits the budget, the cap is the safety bound.
- Artifacts: `exports/sound/dinner_impact.wav` (7.5 s),
  `…_spec.png` (spectrogram: settle clinks → 0.32 s crash → per-instrument
  ring lines → silence by ~1.6 s), `…_log.npz` (raw log).
- Tests: `tests/stageE6/test_sound_render.py` (7) — bank frequency/decay +
  lfilter↔reference parity, kernel impulse conservation, Hertz monotonicity,
  ledger cap/inequality, free-free basis sanity, end-to-end dinner smoke.

## Honesty list (binding, per findings.md discipline)

- **Impacts only.** Normal rows only — friction/scrape/rolling sounds are
  impossible in the current coupling and must not be implied.
- **e = 0 character**: single-hit thud/ring, no bounce clatter; rattle
  re-excitation comes from the two-way sim's event stream (that part is real).
- **Plausible, not measured**: coarse linear-tet meshes (locking shifts kHz
  eigenfrequencies), heuristic RMS radiation weights (no BEM/FFAT), lumped
  Hertz τ_ref, λ solved without audio-band compliance, body-frame ±ŷ normal
  assumption at corners, box proxies (a solid stub "cup" barely rings — its
  thin-shell replacement is a render instrument, disclosed).
- ~~**Offline render (Tier 0)**: the render is not real-time-demonstrated.~~
  **Superseded — Tier 1 live demo landed 2026-07-11** (see below). Device-path
  (CUDA-graph staging) readback remains a follow-up.
- **Box-box impacts unlogged** (support rows only) — follow-up.
- **Not a contribution**: the paper may cite this only as the E6 demo — "the
  soundtrack is funded by the same measured budget that bounds the visible
  response."

## Tier 1 — LIVE demo (landed 2026-07-11, `dcr/sound/live.py`)

```
python scripts/run_native_scenes_viser.py --scene dinner --solver avbd --sound
# open http://localhost:8192, watch AND hear the pot land
```

Dependency: `sounddevice` (PortAudio), justified in pyproject/CLAUDE.md for
this demo only; imported lazily, repo works without it.

Architecture: the sim thread's `substep_end_hook` samples the same engaged
forces as the offline logger (shared `logger.sample_substep`), runs a
STREAMING burst tracker (parity-tested against `extract_impulses`), runs the
same `AudioLedger`, and pushes γ-scaled kicks to a PortAudio callback. The
audio thread renders each voice in CLOSED FORM — damped complex phasors, the
exact Eq. 8 solution between kicks — so a block is one complex multiply per
voice, no per-sample Python. τ-shaping is applied SPECTRALLY live
(kick × |Ĥ(ω;τ)|, the same quantity the ledger admits — live excitation and
accounting agree by construction; offline keeps the time-domain kernel).

Verified (wall-paced 4 s dinner run on the M-series CPU, real output stream):
932 blocks, 1,930 kicks, **0 underruns, 0 clipped blocks**, E6 HOLDS live
with the same numbers as the offline render (11.5 J ≤ 25.7 J, 0/1036 capped);
worst callback 8.9 ms (GIL contention with the sim thread) < the 11.6 ms
block budget at the default `--sound-block 512`. Impact-to-sound latency ≈
burst-close lag (1–2 substeps) + one block ≈ 15–25 ms.

Honest notes: the sim thread briefly falls ~0.4 s behind wall clock during
the contact-heavy crash at speed 1.0 (audio stays coherent — both bands are
sim-clocked; the viser default speed 0.5 has 2× headroom); tap adds host
readbacks per substep (recording/demo runs only); dinner + AVBD host path
only (`--sound` prints a note and stays silent elsewhere); the E6 HUD row
shows the live inequality state, kick/cap counts, callback health.

Materials: bodies get per-kind instruments (`scripts/sound_voices.KIND_SPEC`
— porcelain plates/cups, cast-iron pot, steel utensils: own E/ν/ρ/ζ/τ_ref,
own free-free eigenmodes → distinct pitch, brightness, decay). The TABLE
follows the viewer's material knob twice over: E/ρ shift its eigenfrequencies
(already), and `_AUDIO_TABLE_ZETA` sets its ring character (wood = the sim's
Rayleigh thud; steel ζ=3e-4 rings; plastic 8e-3 dull; soft 2.5e-2 dead) — a
render-side constant-ζ override, DEVIATION-noted in audio_basis.py, since the
scene's single Rayleigh fit would make every material thud. Material/
thickness changes rebuild the table basis on first use (~10–20 s eigsh,
then cached).
Tests: `tests/stageE6/test_live_sound.py` — phasor synth ≡ reference bank,
streaming tracker ≡ offline extractor, live tap on the real scene (stub
engine, headless), real-stream smoke (skips sandboxed/CI).

## Render-quality pass (2026-07-11, second): radiation weights + contact choke

Two audible-realism fixes to the render layer (voices/mix only — excitation,
event extraction, band split, and the E6 ledger are untouched; the ledger
verifies bit-for-bit: 11.49 J ≤ 25.69 J, 0/814 capped, γ=1 throughout).

**Problem.** Every impact read as the same lightly-damped 1.5–3 kHz "ting":
(a) with mass-normalized modes the bare-rms listening weight made the light
body voices out-shout the 75 kg table by ~62 dB per unit impulse (measured:
pot mix amplitude 1281× the table's), burying the wood response entirely;
(b) the open-loop bank let bodies ring with free-air ζ *while resting loaded
on the table* — a physically wrong limit that sustained the ting.

**Fix 1 — radiation weight** (`audio_basis.radiation_weight`, DEVIATION):
per-mode weight is now `√(σ·S)·rms(Φ_y)` with S the radiator's plan area and
σ = (ka)²/(1+(ka)²) a compact-dipole short-circuit roll-off (a = √(S/π),
k = ω/c_air). Still a heuristic — no BEM/FFAT, directivity, or listener
distance. Cache key bumped (`radiation_v=2`); old `data/audio_basis/*.npz`
are orphaned and can be deleted.

**Fix 2 — contact choke** (`render._render_voice_phasor`,
`live.ComplexModalSynth`, DEVIATION): while a body's summed engaged support
force is ≥ 0.25·m·g (hysteresis, off < 0.10·m·g — `events.LoadedTracker`,
shared by both paths), its voice decays with ζ_i → max(ζ_i, ζ_contact = 0.08)
— a damping switch with the phasor state carried across, not a re-strike.
Free flight between bounces rings free; rest chokes. Table voice (the
permanent support) is never choked. Offline renders body voices through a
segmented damped-phasor path that is float-identical to the LTI lfilter path
when unchoked (tested), and identical to the live synth given the same
toggles (tested). Choking only *removes* modal energy faster, so the §15-form
bound is unaffected. Knobs: `--zeta-contact` (offline) /
`--sound-zeta-contact` (viser), 0 disables.

**Measured (same 6 s dinner run, `dinner_impact.wav` → `dinner_impact_v2.wav`):**

| metric | before | after |
|---|---|---|
| low-band (<800 Hz) energy fraction, impact window | 0.011 | 0.941 |
| spectral centroid of the pot impact | 1821 Hz | 361 Hz |
| low-band fraction, late tail [1–2 s] | 0.011 | 0.996 |
| ring residue at +400 ms (rel. to hit rms) | 12 % | 2.5 % |
| high-band (>1.2 kHz) fraction, first 25 ms of hit | — | 0.098 |

i.e. pot-on-wood is now a metallic clank *onset* (~10 % high-band for
~25 ms) handing over to the table's 151–828 Hz woody body — "lower and
dense" — instead of a quarter-second 1.7 kHz ping. Live master level drops a
few dB (body weights shrank); compensate with `--sound-gain` if needed.

Tests added: radiation-weight scaling, LoadedTracker hysteresis, phasor ≡
lfilter (unchoked), choke-shortens-ring + unchoke-resumes, live ≡ offline
choke parity, live tap pushes chokes on the real scene (19 pass / 1 hw skip).

## GPU sound architecture — Stage A/B landed (2026-07-12), 4090 validation pending

The sound tap now has a second, CUDA-compatible excitation source. Design
principle: the tap consumes the sim the way the *viewer* does — at frame
cadence from a device-staged buffer — instead of at substep cadence through a
host hook (which forces per-substep syncs and disqualifies both CUDA-graph
tiers, `solver_6dof.py` capture eligibility).

**Stage A — device staging** (`dcr/avbd/_solver/sound_stage_kernels.py`):
three fixed-shape kernels appended to the end of `_step_one_body` behind
`Solver6DOF.enable_sound_stage()` (flag is part of
`_current_graph_signature`, so toggling recaptures; OFF = zero cost). Per
substep they write into a fixed-capacity ring (default 4 frames deep):
per-support-row engaged force F = −min(ρC+λ_eff, 0) — the same assembly as
`k_modal_rowforce`/`sample_substep`, evaluated post-solve on the float32
`q_modal` mirror (fresh on both host and device q-block paths) — corner
world (x,z), per-body v_y, rigid mechanical energy (float64, passivity
form), then a head increment publishing the substep. Pure `wp.launch` — no
host interaction, no allocation — so on the resident CUDA path the whole
sequence folds into the full-substep captured graph.

**Stage B — frame drain** (`dcr.sound.logger.DeviceRingSource`): one bulk
copy per frame → `SubstepSample`s in substep order → the SAME consumer the
hook tap uses (`LiveExcitationTap._consume`: burst tracker, load gate,
ledger deposits/admits in sim order, kick+choke pushes). Overrun drops the
oldest substeps with a one-time warning (`.dropped`). Both
`LiveExcitationTap` and `SoundImpulseLogger` take `source="hook"|"ring"`;
ring callers call `.drain()` once per frame after `world.step()`.
`attach_live_sound(..., source=)` plumbs it; the viser `--sound` flag picks
hook on cpu, ring on cuda, and drains in the render loop;
`render_sound.py --device cuda:0` records offline via the ring.

**Parity (CPU device, tests/stageE6/test_device_ring.py — same kernels run
on CUDA):** staged F within 5e-2 N (f32-mirror-q vs f64-host-q, ρ-amplified;
impacts are 10² N), corners 1e-5, v_y bit-equal, e_mech 1e-9 rel; tap-level:
identical event/mute/choke counts, kick times and voices exact, kick g
within 1% on the quietest rattle kicks, ledger totals 1e-4 rel, §15 holds on
both. Guard split: the hook tap now *errors toward the ring tap* on a
resident q-block instead of dead-ending.

**4090 checklist (next compshare session):**
1. `pytest tests/stageE6/test_device_ring.py` on `--device cuda:0` variants
   (edit `_build_dinner` device or parametrize) — same tolerances.
2. `python scripts/render_sound.py --device cuda:0 --seconds 6` → WAV; diff
   band-split metrics vs the CPU render of the same scene.
3. Steady-state graph health: with `--sound` + ring on the resident path,
   assert zero recaptures after warmup (signature stable) and frame-time
   regression < 0.2 ms vs staging off (nsys with --cuda-graph-trace=node,
   per the graph-kernel profiling note).
4. Live viser on cuda: 0 underruns, HUD ledger HOLDS, AV latency subjectively
   ≤ hook path + one frame.

Still out of scope: XPBD-native staging, box-box (body-body) impact rows —
documented follow-ups.
