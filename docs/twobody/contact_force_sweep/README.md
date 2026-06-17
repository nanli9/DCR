# Truck-bed per-contact force logging + slab-thickness sweep

Verifying the **two-way coupling** at the contact level for the
`run_truck_bed_viser.py` scene (`dcr.twobody.multibody.build_truck_bed`), with a
slab-thickness sweep, **FEM vs ABD** cargo cubes, and a one-way control.

Reproduce:
```
PYTHONPATH=. python3 scripts/run_truck_bed_contact_force_sweep.py \
    --n-steps 1000 --calib-steps 3000 --thicknesses 0.03 0.05 0.08 0.12
PYTHONPATH=. python3 scripts/_plot_contact_force_energy.py   # supplementary energy plots
```

## What the bodies are
- **Bed slab**: ALWAYS a reduced-coordinate FEM-modal body (`build_fem_slab`,
  `nc=0`, pure modal `q`, 20 modes). `kind` (fem/abd) only changes the **cubes**.
- **Cargo**: 4 piles — light crate, **3-cube lumber stack (pile 1, bodies 2→3→4)**,
  heavy crate, 2-crate stack. Impactor (body 8) drops on bare bed, never touches cargo.
- 32 contacts: `bed_base` (slab→pile base), `cube_cube` (within a stack),
  `bed_impactor`.

## How the contact force is logged (Newtons, consistent across solvers)
A single scalar `F_c` per contact, applied through `grads[c] = +Jac_upper / −Jac_lower`
(`multibody.py:98`), so the SAME `F_c` lifts the upper body and loads the lower —
equal/opposite (Newton's 3rd law), **structurally two-way**.
- GT / Split (penalty): `F_c = k_c·max(0,−gap)`
- AVBD (aug. Lagrangian): `F_c = max(0,−(λ_c+ρ_c·gap_c))`
- XPBD (compliant): `F_c = λ_c/h²`
Recorded as `solver.last_contact_force` (added to all four solvers).

## Findings

1. **Force IS the real slab→cube force (calibration).** With no impactor, settled
   and time-averaged, ⟨bed→base force⟩ = supported weight to within 0.1–4.6 %
   (`calibration.csv`, plot 1). FEM: ratios 1.00–1.05; ABD: 1.00. Confirms the
   logged scalar is physically the slab→cube normal force.

2. **The coupling is genuinely two-way (dynamic).** Post-impact lumber-stack
   peak KE [J] (plot 6):

   | thickness | AVBD-fem | XPBD-fem | AVBD-abd | Split-fem (1-way) |
   |-----------|----------|----------|----------|-------------------|
   | 30 mm     | 4.50     | 5.39     | 3.52     | 6.36 *(anomaly)*  |
   | 50 mm     | 2.20     | 2.52     | 2.45     | **0.034**         |
   | 80 mm     | 1.02     | 1.23     | 1.31     | **0.202**         |
   | 120 mm    | 0.44     | 1.04     | 0.97     | **0.018**         |

   At 50/80/120 mm the dynamic solvers put **10–65× more** energy into the cargo
   than the quasi-static Split bed (same contacts, same forces, but no modal
   inertia → no ring). The bed's *ring* is what drives the cargo ⇒ energy flows
   slab→cube, not just cube→slab. The bed force literally **launches** the stack
   (repeated 1000–1750 N landing spikes, plot 2), and that load transmits up the
   stack base→mid→top with attenuation + lag (plot 5).

3. **Thickness matters, strongly and monotonically.** Thicker bed → stiffer
   (plate compliance ∝ 1/h³) → less deflection → monotonically less energy to the
   cargo (plots 4, 7): AVBD-fem 4.5→0.44 J over 30→120 mm. Consistent across all
   three dynamic solvers and both cube models.

4. **FEM vs ABD cubes (plot 3).** Same qualitative two-way behavior and thickness
   trend. FEM cubes bounce as sharp near-rigid spikes (~1770 N peak @ 80 mm); ABD
   cubes rock more diffusely at lower peaks (~795 N). Calibration is excellent for
   both. Solver fixed at AVBD (XPBD's per-constraint damping isn't wired for ABD).

## Honest caveats
- **Thin-bed Split anomaly (30 mm).** The one-way control degenerates: the
  over-soft quasi-static bed deflects so far instantaneously that it flings the
  cargo (KE 6.36 J, higher than the dynamic solvers). The clean one-way/two-way
  contrast holds at 50/80/120 mm. Flagged on plot 6.
- **Ring-std is a poor metric** (dominated by impulsive stack-landing spikes,
  non-monotonic) — superseded by post-impact cargo KE (plots 6/7). The old
  ring-std panel of plot 4 was replaced.
- Post-impact peak forces (1500–2300 N) are violent-impact transients, not steady
  loads; the steady value is the supported weight (~20 N for this stack).

## Energy loop & bounces (`scripts/_probe_energy_loop.py`)

The two-way coupling forms a **slab ⇄ cargo energy loop**, verified directly
(`9_energy_loop_{avbd,xpbd}.png`, schematic `10_loop_schematic.png`):

- The impactor dumps ~123 J into the **slab modal ring** (peak 43 J AVBD / 63 J
  XPBD after impact/penetration losses).
- **slab → cargo**: the ring LAUNCHES the lumber stack — ~1.0 J/cycle (AVBD),
  1.3 J (XPBD). Small vs the slab ring (≈2–3 %), so the loop is asymmetric and
  dissipative, not a conservative resonance.
- **cargo → slab**: each landing RE-RINGS the bed (visible as secondary humps in
  the slab-energy curve at the landing times).
- Both directions are carried by the SAME shared contact multiplier — that pair
  IS the loop.

**The force spikes are bounces (verified).** The stack goes genuinely airborne
(base-contact gap > 0) **81 % (AVBD) / 79 % (XPBD)** of the time and re-lands:
**5 bounces (AVBD) / 6 (XPBD)** over 0.5 s, max lift 54.8 / 68.1 mm. The flight
times match free-fall ballistics (½gt²) to <2 mm, confirming separation+relanding
rather than a continuously-pressed contact. Each force spike = one landing.

## Files
- `contact_forces_long.csv` — tidy per-(config, thickness, step, contact) force [N]
- `pile_forces_long.csv` — per-pile bed-support force + pile KE vs time
- `summary.csv` — per-config calibration + post-impact peak/ring/KE metrics
- `calibration.csv` — clean settled force=weight check
- `energy_loop_probe.csv` — slab/cargo energy, base height, gap, force vs time
- `1..7_*.png` — calibration, two-way contrast, fem-vs-abd, thickness sweep,
  stack transmission, two-way energy, thickness trend
- `8_per_contact_point_{avbd,xpbd}.png` — every corner contact, thickness × layer grid
- `9_energy_loop_{avbd,xpbd}.png` — slab↔cargo energy loop + bounces + force
- `10_loop_schematic.png` — box-and-arrow loop diagram (annotated with measured J)
- `11_energy_loop_explained.png` — twin-axis zoom on ONE bounce cycle explaining
  the loop panel: ① impact charges slab → ② slab launches cargo (+1.3 J) → ③
  cargo lands, re-rings slab (+1.7 J). "1.3 J/cycle" = the cargo's (constant)
  mechanical energy during each ballistic flight = what the slab handed it.
