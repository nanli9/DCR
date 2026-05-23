# CLAUDE.md — Project Guide

> Read this file at the start of every session before touching code.

## What this project is

A **from-scratch Python reproduction** of the SCA 2020 paper:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

The paper PDF is at `reference/DCR_SCA2020_preprint.pdf`. The detailed staged build plan is in `prompts/dcr_implementation_prompt.md`. **Read that file before you write a line of code.**

The first end goal of this repo is to reproduce the **core DCR method**: modal-path response for small objects, spatial-attenuation path for large objects, and a qualitative ground-truth comparison.

After the DCR core completes, this repo extends into a **follow-up project of our own** — a passive, energy-bounded modal injection mechanism. See the next section.

## What this project is NOT

- Not a fork or extension of *other people's* follow-up papers. No bounce maps, no contact sounds, no anisotropic friction, no GPU port.
- Not a production physics engine. Numerical robustness comes second to readability and faithfulness to the paper.
- Not real-time yet. Get correctness first.

If a user asks for any of the items in this list, the answer is "out of scope for this repo — let's finish DCR core (and the energy-injection follow-up) first."

## Follow-up: Passive Modal Energy Injection

After the DCR core (Stages 1–7 of `prompts/dcr_implementation_prompt.md`) reaches acceptance, this project extends with a follow-up of our own design. The math foundation lives in `prompts/passive_modal_energy_injection_foundation.md`. The staged build plan lives in `prompts/passive_energy_injection_implementation_prompt.md`.

The follow-up reframes the impulse → modal coupling as a *velocity-level kick* to `q̇` funded by the rigid-body kinetic energy lost during contact resolution, scaled by a transfer efficiency `η ∈ [0, 1]`, and capped by a quadratic passivity bound so that

```
ΔE_modal  ≤  η · ΔE_rigid_loss
```

holds every rigid step, globally across all contacts. This deviates from the paper's forced-IIR formulation (Eq. 10) — every change to the modal stepper must carry a `# DEVIATION:` comment citing §15 of the foundation document.

Stage order for the follow-up: **E0 → E1 → E2 → E3 → E4 → E5 → E6 (optional stretch)**. Each stage has acceptance criteria that must be demonstrated (test passing + plot / MP4) before the next begins. Same rules as DCR core.

Important scope clarifications for the follow-up:
- **Stage E6 is a logged scalar energy bound, not audio synthesis.** It does not contradict the "no contact sounds" line above — no `.wav` files, no audio backend.
- **The energy bound applies to the modal-path injection only** (Stage E3). The Stage 6 spatial-attenuation path is empirical and is not energy-budgeted in this follow-up.

## Tech stack — fixed

- **Python 3.10+** (use modern type hints, `dataclasses`).
- **`numpy`** for dense linear algebra.
- **`scipy.sparse`** + `scipy.sparse.linalg.eigsh` for FEM assembly and the generalized eigenproblem.
- **`warp-lang` on CPU device** for any hot inner loops. `wp.init()` and `device="cpu"`. **No CUDA.**
- **`polyscope`** for visualization (fast to integrate, decent enough). `pyvista` is a fallback.
- **`pylibigl`** if available, for the heat-method geodesic in Stage 6. Otherwise implement it from scratch (it's small).

Do **not** add a new dependency without justifying it in writing. No PyTorch, no JAX, no Taichi, no C++, no pybind11. The energy-injection follow-up does not require any new dependency.

## Constraints on Claude's behavior in this repo

1. **Follow the stage order.**
   - DCR core: Stage 1 (rigid body) → Stage 2 (FEM) → Stage 3 (modal) → Stage 4 (IIR) → Stage 5 (modal DCR) → Stage 6 (spatial DCR) → Stage 7 (scenes), per `prompts/dcr_implementation_prompt.md`.
   - Follow-up: Stage E0 (energy bookkeeping) → E1 (projection) → E2 (α cap) → E3 (wire injection) → E4 (aggregation + dissipation) → E5 (η sweep) → E6 (sound bound, optional), per `prompts/passive_energy_injection_implementation_prompt.md`.
   - Do not start any E-stage before DCR Stages 1–6 are passing acceptance.
   - Do not jump ahead within either sequence.

2. **Cite the source equation by number** in every docstring and inline comment that implements one. For DCR core, cite the paper equation. For the follow-up, cite the foundation section (§N) and reference §15 (the core inequality) in every injection-touching function.
   ```python
   def schur_system(M, J, v, f, phi, h, cfm, erp):
       """Build the Schur-complement linear system (paper Eq. 2):
           A = (1/h^2) * cfm * I + J M^{-1} J^T
           b = -(erp/h) * phi - J M^{-1} (M v + h f)
       """
   ```
   ```python
   def passive_alpha(s, qdot, E_max):
       """Passive scaling coefficient (foundation §6, core eq. §15):
           ΔE_modal(α) = α b + ½ α² a  ≤  E_max
       Returns α ∈ [0, 1] satisfying the bound.
       """
   ```

3. **No silent equation deviation.** If the implementation diverges from the paper or the foundation document for any reason (numerical stability, simplification, etc.), write a `# DEVIATION:` comment explaining what and why, and reference the source equation it diverges from.

4. **Naming clash discipline.**
   - The paper uses `ε` for both CFM and restitution. In code: always `cfm` (or `eps_cfm`) and `restitution` (or `eps_r`). Never just `eps`.
   - For the follow-up: `eta` for transfer efficiency, `alpha` for the passive scaling coefficient, `rho_i` for acoustic radiation. Never overload these names.

5. **Conventions:**
   - Generalized velocity per body: `v = [v_lin (3); ω (3)]`.
   - Quaternions: `(w, x, y, z)`.
   - Contact normals: point from body A out into body B; `λ_N ≥ 0`.
   - Sparse matrices: CSR for `K`, CSC for solver-input mass.
   - Units: SI (m, kg, s, N).
   - Modal state for the follow-up: `(q, qdot)` stored explicitly (R^{n_modes} each). With mass-normalized modes, `M_q = I` and no extra inverse is needed.

6. **Reference path first, then accelerate.** Always write the plain-numpy version that is obviously correct. Add a warp version only after the reference passes acceptance criteria, and only when there's a measured slowdown to justify it. Keep the reference code in the repo — do not delete it. This applies equally to the energy-injection follow-up; the per-step injection math is small (a handful of dot products and one scalar `α`), so a warp version is almost certainly unnecessary.

7. **Test before claiming.** Every stage has acceptance criteria in its prompt file. Run the test, generate the plot/MP4, and only then say a stage is done. For the follow-up specifically, this includes the energy invariant: `cumulative E_modal_injected ≤ η · cumulative E_loss + ε_tol` must be asserted across the full run, not just sampled.

8. **Be honest about limits.** If something in the paper or the foundation document is under-specified, say so, propose a defensible choice, and flag it as a candidate place to revisit. The foundation document's §14 ("claims to avoid") is the canonical list of things *not* to overclaim about the follow-up.

## Repo layout (target)

```
.
├── CLAUDE.md                                       # this file
├── CONTRIBUTIONS.md                                # contributions beyond the paper + math summary
├── prompts/                                        # build prompts and math foundation
│   ├── dcr_implementation_prompt.md                #   DCR core build plan — READ FIRST
│   ├── passive_energy_injection_implementation_prompt.md  # follow-up build plan
│   ├── passive_modal_energy_injection_foundation.md       # follow-up math foundation
│   └── deformation_aware_contact_frame.md          #   archived: tilt extension design (superseded by Version B)
├── reference/                                      # external references
│   └── DCR_SCA2020_preprint.pdf                    #   the paper
├── README.md                                       # human-readable summary, generated after Stage 1
├── pyproject.toml                                  # or requirements.txt
├── dcr/                                            # the library
│   ├── geom/                                       # mesh I/O, surface extraction, barycentrics
│   ├── rigid/                                      # Stage 1: rigid body simulator
│   │   └── energy.py                               # Stage E0: rigid_kinetic_energy()
│   ├── fem/                                        # Stage 2: linear FEM
│   ├── modal/                                      # Stages 3-4: eigenproblem + IIR
│   │   ├── energy.py                               # Stage E0: modal_energy()
│   │   ├── passive_inject.py                       # Stages E1-E3: Phi^T j, alpha, q̇ kick
│   │   └── homogeneous_stepper.py                  # Stage E3: free SDOF integrator
│   ├── dcr/                                        # Stages 5-6: the coupling layer
│   └── viewer/                                     # polyscope wrapper
├── scenes/                                         # python scene files (one per scenario)
├── scripts/                                        # entry points: run_stage1.py, ...
├── tests/                                          # pytest, one folder per stage
│   ├── stage1/ ... stage7/                         # DCR core
│   └── stageE0/ ... stageE6/                       # follow-up
├── data/                                           # mesh assets (tet + surface)
└── docs/                                           # per-stage notes, plots, MP4s
    ├── stage1.md ... stage7.md                     # DCR core
    └── stageE0.md ... stageE6.md                   # follow-up
```

## Commit and branching

- One feature branch per stage.
  - DCR core: `stage1-rigid`, `stage2-fem`, ..., `stage7-scenes`.
  - Follow-up: `stageE0-energy-bookkeeping`, `stageE1-modal-projection`, ..., `stageE6-sound-bound`.
- Tag the merge commit with the same name.
- Commit messages reference paper section/equation or foundation §N when relevant:
  - `stage1: implement Schur complement (Eq. 2)`
  - `stageE2: passive alpha cap (foundation §6, core eq. §15)`

## When in doubt

- Re-read the relevant paragraph of the paper, or the relevant section of the foundation document for follow-up work.
- Check the stage's acceptance criteria in the appropriate prompt file.
- If still stuck, **ask** before guessing — and if you do guess, mark it as a `# DEVIATION:`.

## What the user expects when interacting with Claude here

- Direct, concise answers. No "I'd love to help!" preambles.
- Code that runs on CPU only and starts with the simplest correct version.
- A clear statement of which stage is being worked on at the top of each response (e.g., "Working on Stage E2 — passive α coefficient").
- Test outputs (plot, console assertion, or screenshot path) cited when claiming a stage is done.
- Honest "I'm not sure" or "the paper is silent on this" / "the foundation is silent on this" when warranted.
- For the follow-up specifically: never claim more than the foundation §13 list permits. The §14 "claims to avoid" list is binding.
