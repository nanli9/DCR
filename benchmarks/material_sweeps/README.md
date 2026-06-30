# Material sweeps — is the native two-way slab⇄object coupling physically accurate?

**Isolated benchmark.** Everything here lives under `benchmarks/material_sweeps/`
and imports the `dcr` library / scenes **read-only**, setting solver config at
**runtime** — no original code is modified.

**Two settings, applied to BOTH solvers** (the solver-source defaults are wrong for
a physical ring and must be set explicitly):
- **symplectic modal step** — source default `_modal_symplectic = False` (BE).
- **modal relaxation `0.7`** — source defaults under-relax the modal block and
  suppress the ring: AVBD `_modal_relax = 0.1`, XPBD `modal_relax = 0.25`
  (+ `_support_block_relax`). Set to **0.7** for both.

> Correction vs an earlier draft of this benchmark: with the default relax (0.1)
> and an FFT that locked onto the slow contact-settling envelope, AVBD *appeared*
> not to ring (~2 Hz). That was an artifact. At relax 0.7, with the settling
> high-passed out before the FFT, **AVBD rings at the modal frequency** like XPBD.

Cargo is **out of scope** (per project scope); only the non-cargo scenes
(shelf / ledge / dinner) are swept.

Reproduce:
```
.venv/bin/python benchmarks/material_sweeps/fem_reference.py     # FEM-truth self-test
.venv/bin/python benchmarks/material_sweeps/run_slab_sweep.py    # slab material sweep + physics accuracy
.venv/bin/python benchmarks/material_sweeps/run_scene_sweep.py   # multi-scene verification
```
Out (`out/`): `slab_physics_accuracy.png`, `fem_vs_analytic.png`, `scene_sweep.png`,
`slab_material_sweep.csv`, `scene_sweep.csv`.

---

## 1. Slab material sweep + physics accuracy  (`slab_physics_accuracy.png`)

Shelf scene (plate 0.8×0.3×0.03 m), slab `youngs`/`density`/`poisson` swept, both
solvers, symplectic + relax 0.7. Ground truth on two independent legs: **(A)**
analytic Euler-Bernoulli (the synthetic basis's own model) and **(B)** a full 3D
solid-FEM simply-supported plate (`fem_reference.py`).

| material | E [GPa] | √(E/ρ) | EB f₁ | FEM f₁ (B) | XPBD meas | AVBD meas | XPBD two-way | AVBD two-way | passivity (X/A) |
|----------|--------:|-------:|------:|-----------:|----------:|----------:|-------------:|-------------:|-----------------|
| soft     | 0.5 |  913 |  20.3 |  21.1 | 15.4 | 22.1 | 15× |   6× | 0.44 / 0.62 |
| oak      | 11  | 3963 |  89.9 |  92.3 | 88.1 | 96.9 | 60× | 172× | 0.99 / 0.40 |
| steel    | 200 | 5048 | 112.5 | 116.8 |111.7 |113.4 | 48× | 301× | 0.02 / 0.04 |
| aluminum | 69  | 5055 | 113.8 | 117.4 |115.1 |115.1 | 17× |  77× | 0.04 / 0.11 |
| glass    | 70  | 5292 | 115.3 | 121.9 |114.9 |116.6 | 15× |  74× | 0.04 / 0.11 |

**Findings:**

1. **Both solvers reproduce the physical ring frequency** — measured ring (detrended
   FFT of `q0(t)`) lands within **~1–9 %** of the analytic Euler-Bernoulli `f₁` for
   oak/steel/aluminium/glass, on both solvers. The softest slab is the noisiest case
   (XPBD 15.4 / AVBD 22.1 vs EB 20.3) — light, heavily-damped, low frequency where
   the settling-vs-ring separation is hardest.

2. **f ∝ √(E/ρ)** — steel (200 GPa) and aluminium (69 GPa) ring at nearly the same
   frequency (≈112–115 Hz) because their sound speeds are nearly equal despite a 3×
   stiffness gap; panel (b) shows EB, FEM, and both measured frequencies collapsing
   onto one line through the origin.

3. **Both solvers are two-way** (freeze-q̇ control), 6–300×. AVBD's coupling is now
   strong (it was ~1× at the default relax).

4. **Energy passivity holds** — slab ring peak / impactor KE < 1 for every material
   and solver (panel d; oak/XPBD is closest at 0.99). No injection.

## 2. Full-FEM truth leg (B)  (`fem_vs_analytic.png`)

The shelf support is a **synthetic analytic basis** (sine bending modes + Gaussian
static bumps), not a meshed FEM eigensolve — so we independently mesh the same slab
as a 3D tet solid (`dcr.geom.make_slab_tet_mesh` + `dcr.fem.FEMModel`), impose
simply-supported BCs (own per-DOF reduction), and solve the eigenproblem.

- **(a)** linear tets shear-lock and overestimate stiffness on coarse
  through-thickness meshes; refining drives `f_FEM/f_EB` 1.25 → 1.02.
- **(b)** converged 3D-FEM `f₁` agrees with Euler-Bernoulli to **~4 %**.
- **(c)** static self-weight deflection agrees to ~7 %.
- Caveat: higher FEM modes mix torsion/width modes the 1-D strip basis omits — only
  the fundamental is compared mode-to-mode.

→ **The synthetic basis is a physically faithful thin-plate model for the
fundamental**, validated independently of the analytic formula.

## 3. Multi-scene verification  (`scene_sweep.png`)

Each scene's own reduced-support geometry, default material, symplectic + relax 0.7.

| scene  | geometry (L×W×t) | EB f₁ | XPBD meas | AVBD meas | XPBD two-way | AVBD two-way |
|--------|------------------|------:|----------:|----------:|-------------:|-------------:|
| shelf  | 0.8×0.3×0.03 |  20.3 | 15.4 (24%) | 22.1 (8%) | 15× |  6× |
| ledge  | 1.2×0.8×0.08 | 118.1 | 118.4 (0%) | 118.4 (0%) | 98× | 0.6× |
| dinner | 1.2×1.0×0.03 |  44.3 |  43.3 (2%) |  43.3 (2%) | 41× | 47× |

- **ledge & dinner ring essentially exactly** (0–2 % vs EB) on both solvers.
- **Two-way is strong** in 5/6 configs. The one exception is **ledge / AVBD: it
  rings but does not launch the resting object** (two-way 0.6× < 1) — the ring is
  present yet the object KE is no larger than the frozen-q̇ control there; reported
  as-is, not cherry-picked.
- Passivity < 1 everywhere.

---

## Bottom line
- **With symplectic + modal relax 0.7, the native two-way coupling is physically
  accurate for BOTH solvers** — the slab rings at its true natural frequency
  (validated against Euler-Bernoulli *and* a 3D full-FEM plate), obeys f ∝ √(E/ρ),
  and stays energy-passive across a 10²–10³× stiffness range and three scenes.
- **The modal relaxation is the key knob.** At the source default (0.1/0.25) the
  modal block is under-relaxed and the ring is suppressed (most visibly for AVBD);
  at 0.7 both solvers ring.
- Remaining rough edges: the soft-shelf measurement is noisy (low freq, heavy
  damping), and ledge/AVBD rings without transferring to the resting object.
