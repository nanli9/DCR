"""Warp device kernels for `SolverXPBD`.

Stage 0 scaffolding placeholder. The XPBD device kernels land alongside their
CPU references (CLAUDE.md rule 6 — reference path first, then accelerate):

* Stage 2 — predict (x̂ = x + h v + h²g), compliant box↔box + floor contact GS
  projection (α = compliance/h², λ ≥ 0) with positional Coulomb friction, and
  the velocity update v = (x − x_prev)/h / ω = log(q ⊗ q_prev⁻¹)/h.
* Stage 3 — per-mode compliant modal-elastic (α_i = 1/K_q[i,i], Macklin §3.5
  damped update) + unilateral support-contact rows reading y_rest + U_y·q.
* Stage 4 — cargo modal block projection (per-mode + abd nonlinear V⊥).

The reusable contact GEOMETRY (SAT 15-axis + Sutherland-Hodgman face-clip
manifold, LBVH broadphase) stays in `kernels_6dof.py` and is shared with
`SolverAVBD`; only the projection kernels differ and live here.

Spec: Macklin et al. 2016 (XPBD) + §3.5 damping; `two_band_coupling.html`.
Reference math to re-express on-device: `dcr/avbd/reduced_coupled_xpbd_kernels.py`.
"""
from __future__ import annotations

# Kernels are added in Stage 2+. Intentionally empty in Stage 0.
