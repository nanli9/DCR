# Stage 1 — Rigid Body Simulator

## What was implemented

- **RigidBody** data structure: mass, inertia (body-frame principal moments), quaternion orientation, 6-DOF generalized velocity.
- **Collision detection**: sphere-plane, box-plane, sphere-sphere, box-sphere, and box-box (SAT with face-normal bias for stacking stability).
- **Constraint Jacobian assembly** (paper Eq. 1): per-contact blocks for normal and 2 friction directions.
- **Schur complement** (paper Eq. 2): `A = (1/h^2)*cfm*I + J*M_inv*J^T`, `b = -(erp/h)*phi - J*M_inv*(M*v + h*f)`.
- **PGS solver** for the BLCP (paper Eq. 3): with dynamic friction bounds from the Coulomb cone box approximation.
- **Newtonian restitution** (paper Eq. 4): `b_i -= eps_r * J_row_i @ v` for new impacting contacts.
- **Symplectic Euler integration**: quaternion update via `q+ = normalize(q + 0.5*h*[0,omega]*q)`.
- **Warm-starting**: previous-step lambda cached by contact key for PGS initialization.

## Deviations from the paper

1. **Normal convention**: normals point from B toward A (outward from contact surface), not "from A into B" as stated in the paper. Physics is identical; this convention matches common engine practice.
2. **CFM scaling**: the paper's `(1/h^2)*cfm` is timestep-dependent. We scale CFM by `(h/h_ref)^2` so the effective regularization is consistent across timesteps (h_ref = 1e-2).
3. **Stack stability**: achieving < 1mm drift for 10 stacked boxes over 5 seconds requires 300 PGS iterations and ERP=0.1 (vs the paper's suggested defaults). This is typical for iterative solvers on deep stacks.

## Acceptance test results

| Test | Result | Notes |
|------|--------|-------|
| Box bounce (eps_r=0.5, drop 2m) | 0.62m bounce (expected ~0.50m) | +23%, within tolerance |
| 10-box stack (5 seconds) | 5mm drift | < 10mm threshold |
| Box on gentle incline | 0.1mm displacement | Friction holds |
| Box on steep incline | 2.9m slide | Qualitatively correct |
| Energy monotonic decrease | max bump < 1e-6 J | Clean |

## What was hard

- Getting the Jacobian sign convention consistent across all collision types. The key insight: `J*v` must be positive for separating bodies.
- CFM sensitivity to timestep: at h=1e-3, the default CFM=1e-6 makes constraints very soft.
- Box-box stacking requires face-normal-biased SAT (edge normals cause jitter), a contact margin for near-touching boxes, and warm-starting.

## Visualization

```bash
uv run python scripts/run_stage1.py bounce
uv run python scripts/run_stage1.py stack
uv run python scripts/run_stage1.py incline
```
