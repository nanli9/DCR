# CLAUDE.md — Project Guide

> Read this file at the start of every session before touching code.

## What this project is

A **from-scratch Python reproduction** of the SCA 2020 paper:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

The paper PDF is at `DCR_SCA2020_preprint.pdf` (project root). The detailed staged build plan is in `dcr_implementation_prompt.md`. **Read that file before you write a line of code.**

The end goal of this repo, for now, is to reproduce the **core DCR method**: modal-path response for small objects, spatial-attenuation path for large objects, and a qualitative ground-truth comparison. That's it.

## What this project is NOT

- Not a fork or extension of follow-up papers. No bounce maps, no contact sounds, no anisotropic friction, no GPU port.
- Not a production physics engine. Numerical robustness comes second to readability and faithfulness to the paper.
- Not real-time yet. Get correctness first.

If a user asks for any of the above, the answer is "out of scope for this repo — let's finish DCR core first."

## Tech stack — fixed

- **Python 3.10+** (use modern type hints, `dataclasses`).
- **`numpy`** for dense linear algebra.
- **`scipy.sparse`** + `scipy.sparse.linalg.eigsh` for FEM assembly and the generalized eigenproblem.
- **`warp-lang` on CPU device** for any hot inner loops. `wp.init()` and `device="cpu"`. **No CUDA.**
- **`polyscope`** for visualization (fast to integrate, decent enough). `pyvista` is a fallback.
- **`pylibigl`** if available, for the heat-method geodesic in Stage 6. Otherwise implement it from scratch (it's small).

Do **not** add a new dependency without justifying it in writing. No PyTorch, no JAX, no Taichi, no C++, no pybind11.

## Constraints on Claude's behavior in this repo

1. **Follow the stage order in `dcr_implementation_prompt.md`.** Stage 1 (rigid body) → Stage 2 (FEM) → Stage 3 (modal) → Stage 4 (IIR) → Stage 5 (modal DCR) → Stage 6 (spatial DCR) → Stage 7 (scenes). Do not jump ahead. Each stage has acceptance criteria that must be demonstrated (test passing + a short visual artifact) before the next stage begins.

2. **Cite the paper equation by number** in every docstring and inline comment that implements one. Example:
   ```python
   def schur_system(M, J, v, f, phi, h, cfm, erp):
       """Build the Schur-complement linear system (paper Eq. 2):
           A = (1/h^2) * cfm * I + J M^{-1} J^T
           b = -(erp/h) * phi - J M^{-1} (M v + h f)
       """
   ```

3. **No silent equation deviation.** If the implementation diverges from the paper for any reason (numerical stability, simplification, etc.), write a `# DEVIATION:` comment explaining what and why.

4. **Naming clash discipline.** The paper uses `ε` for both CFM and restitution. In code: always `cfm` (or `eps_cfm`) and `restitution` (or `eps_r`). Never just `eps`.

5. **Conventions:**
   - Generalized velocity per body: `v = [v_lin (3); ω (3)]`.
   - Quaternions: `(w, x, y, z)`.
   - Contact normals: point from body A out into body B; `λ_N ≥ 0`.
   - Sparse matrices: CSR for `K`, CSC for solver-input mass.
   - Units: SI (m, kg, s, N).

6. **Reference path first, then accelerate.** Always write the plain-numpy version that is obviously correct. Add a warp version only after the reference passes acceptance criteria, and only when there's a measured slowdown to justify it. Keep the reference code in the repo — do not delete it.

7. **Test before claiming.** Every stage has acceptance criteria in `dcr_implementation_prompt.md`. Run the test, generate the plot/MP4, and only then say a stage is done.

8. **Be honest about limits.** If something in the paper is under-specified (it happens), say so, propose a defensible choice, and flag it as a candidate place for the result to diverge from the paper.

## Repo layout (target)

```
.
├── CLAUDE.md                          # this file
├── dcr_implementation_prompt.md       # the staged build plan — READ THIS FIRST
├── DCR_SCA2020_preprint.pdf           # the paper
├── README.md                          # human-readable summary, generated after Stage 1
├── pyproject.toml                     # or requirements.txt
├── dcr/                               # the library
│   ├── geom/                          # mesh I/O, surface extraction, barycentrics
│   ├── rigid/                         # Stage 1: rigid body simulator
│   ├── fem/                           # Stage 2: linear FEM
│   ├── modal/                         # Stages 3-4: eigenproblem + IIR
│   ├── dcr/                           # Stages 5-6: the coupling layer
│   └── viewer/                        # polyscope wrapper
├── scenes/                            # python scene files (one per scenario)
├── scripts/                           # entry points: run_stage1.py, ...
├── tests/                             # pytest, one folder per stage
├── data/                              # mesh assets (tet + surface)
└── docs/                              # per-stage notes, plots, MP4s
    ├── stage1.md ...
    └── stage7.md
```

## Commit and branching

- One feature branch per stage: `stage1-rigid`, `stage2-fem`, etc.
- Tag the merge commit with the same name.
- Commit messages reference paper section/equation when relevant: `stage1: implement Schur complement (Eq. 2)`.

## When in doubt

- Re-read the relevant paragraph of the paper.
- Check `dcr_implementation_prompt.md` for the stage's acceptance criteria.
- If still stuck, **ask** before guessing — and if you do guess, mark it as a `# DEVIATION:`.

## What the user expects when interacting with Claude here

- Direct, concise answers. No "I'd love to help!" preambles.
- Code that runs on CPU only and starts with the simplest correct version.
- A clear statement of which stage is being worked on at the top of each response.
- Test outputs (plot, console assertion, or screenshot path) cited when claiming a stage is done.
- Honest "I'm not sure" or "the paper is silent on this" when warranted.
