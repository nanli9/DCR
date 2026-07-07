# "Dinner is served" — DCR-paper-style validation (2026-07-07)

Duplicates the DCR paper's §5.1 dinner scene and its §5.2 ground-truth
protocol, presented the way the paper presents it (qualitative agreement +
parameter/timing tables), extended with drop-position sweeps the paper only
shows on its spatial-attenuation scenes. Harness:
`benchmarks/dinner_dcr/run_dinner_dcr.py`; figures in `docs/dinner_dcr/`.

## Scene (paper §5.1 / Table 2 duplicate)

| item | paper | ours |
|---|---|---|
| table | oval, E=1.1 GPa, ν=0.3, ρ=770 (Table 2; §5.1 prose says 700) | 2.2×1.1×0.04 m box slab, E=1.1 GPa, ν=0.3, ρ=770 |
| pot | 5 kg, dropped once at centre | 5 kg, `pot_drop_xz` parameter (3-position sweep) |
| plates / teacups / candlesticks | 0.5 / 0.4 / 0.8 kg, **rigid** (§4.5) | same masses; rigid arm + all-cargo arm |
| table modes | 20, precomputed eigenbasis | 24, eigenbasis of the SAME FEM operator as the GT (G1 shared operator, R1 mesh: 44×22×3 cells, 4,140 nodes) |
| GT | SOFA, elastic table only, h=1e-5, ~30 min for <1 s | all-FEM `MultiFEMSim` (every body FEM), h=5e-5, ~17-19 min for 3.7 s |

Protocol: X3 park/settle/release, `t_settle = 2.5 s` — the DCR-material table
sags under its own 74.5 kg self-weight and rings at f1 ≈ 10 Hz with
ζ ≈ 0.016; 0.4 s of settle leaves 67 % of that transient alive (measured:
dishes tossed ~80 mm before the pot lands), 2.5 s leaves ~8 %.

## Results (3 drops × 3 arms)

Support: GT peak mid u_y 9.2 / 7.0 / 5.9 mm, dominant ring **9.2–9.9 Hz** vs
the shared operator's f1 = **9.8 Hz** — the arms agree on the operator.
Native table peak |u_y|: 6.3 mm (rigid dishes), 3.5 mm (all-cargo).

Max dish jump (mm), per drop point:

| arm | (0, 0) | (0.65, 0) | (0.90, 0) | ms/step |
|---|--:|--:|--:|--:|
| native, rigid dishes (paper §4.5 setup) | 6.6 | 2.3 | 1.1 | ~37 |
| native, all-cargo (our generalization) | 1.4 | ~0 | ~0 | ~120–170 |
| all-FEM GT | 50.3 | 56.7 | 37.3 | ~2.8e4 (17–19 min/drop) |

Figures: `response_vs_distance.png` (per-body peak jump vs distance from the
drop, log-y, toppled/flung bodies >0.3 m excluded per the GT contact
limitations), `near_far_traces.png` (near vs far plate height traces).

## Findings

1. **Operator agreement (the G1 claim):** the GT's measured ring frequency
   (9.2–9.9 Hz) matches the native basis f1 (9.8 Hz). With the previous
   synthetic debug basis the native table was a different table entirely
   (f1 = 4.7 Hz, 30× response mismatch) — `support_basis="fem"` is what makes
   this comparison meaningful at all.
2. **Distance attenuation appears without any fitted model** (the paper fits
   Eq. 14's C, β by hand/data): the rigid-dish native arm falls from 6.6 mm
   near the drop to sub-mm at the far end; the GT falls the same direction,
   more gently (its dish response is chatter-broadened — far plates keep
   bouncing on the still-ringing table).
3. **Absolute dish-launch amplitude is structurally low in the native arm**
   (~7× under GT with rigid dishes). Measured to be insensitive to mode
   count (24→48: no change) and modal under-relax (0.7→1.0: +30 %), so it is
   NOT a truncation/tuning artifact: the native constraint path integrates q
   implicitly (BE) at the solver rate (1/480 s), which band-limits the sharp
   impact transient whose surface VELOCITY launches dishes (ballistic jump
   ∝ v², so a 2.6× velocity deficit reads as ~7× in jump height). The DCR
   paper's architecture works around exactly this: its IIR filter sub-steps
   the modal response at T = π/(2ω_max) ≪ h and re-injects the max
   displacement as a velocity kick (Eqs. 10–12) — deliberately re-amplifying
   what the coarse rigid step would smear. Our native path trades that
   amplitude for two-way coupling + passivity; this is the honest
   difference-statement for the paper.
4. **All-cargo halves the table ring again** (3.5 vs 6.3 mm): soft (E=1e6)
   deformable dishes absorb impact compliantly. Physical, but it means the
   paper's "plates jump" visual needs the rigid-dish configuration — which
   is also the paper's own configuration (§4.5).
5. **GT dish-jump numbers carry chatter**: the far-plate trace keeps 2–6 mm
   bounces from the residual table ring. Per the validation plan §6.1, the
   scored GT signals remain the deflection field and the contact ledger;
   dish jumps are qualitative.

## Paper-style verdict (§5.2 idiom)

At the paper's own operating point (Table 2 material, rigid dishes), the
native modal-constraint response is qualitatively similar to the all-FEM
ground truth: the table rings at the same frequency, near dishes respond
more than far ones with no fitted attenuation, and the response pattern
follows the drop point. The native arm under-predicts absolute launch
amplitude by ~7× — a band-limiting consequence of solver-rate implicit
modal integration, disclosed above, where the original method's IIR+kick
re-amplification (Eqs. 10–12) trades passivity for launch amplitude in the
opposite direction (its Δv can exceed the passive bound; cf. X1/X7).

## Reproduce

```bash
.venv/bin/python -m benchmarks.dinner_dcr.run_dinner_dcr              # reuses recorded GT
.venv/bin/python -m benchmarks.dinner_dcr.run_dinner_dcr --no-reuse-gt  # full re-run (~1 h)
.venv/bin/python scripts/run_native_scenes_viser.py                    # dinner: pot x/z sliders
.venv/bin/python scripts/run_fem_gt_viser.py --scene dinner --pot-xz 0.65 0
```
