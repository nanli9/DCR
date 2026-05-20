# Stage E0 — Energy Bookkeeping

Makes rigid and modal energy first-class observables. No simulation behavior changes.

## What was added

- `dcr/rigid/energy.py`: `rigid_kinetic_energy(bodies)` — sums `0.5 m ||v||^2 + 0.5 omega^T I omega` over dynamic bodies (foundation §1).
- `dcr/modal/energy.py`: `modal_energy(q, qdot, omega)` — computes `0.5 qdot^T qdot + 0.5 q^T Omega^2 q` (foundation §2).
- `World.step()`: pre/post solve energy sampling when `log_energy=True`. Records `(t, E_rigid_pre, E_rigid_post, E_loss)` per step.

## Acceptance results

**Bouncing ball (eps_r=0.5):** Energy drops by factor ~0.25 at each bounce. E_loss exactly accounts for E_pre - E_post. See `bouncing_ball_energy.png`.

**Free fall (no contact):** E_rigid matches analytical `0.5 m (gt)^2` with max drift of 1.6e-12 J. Symplectic Euler is effectively exact for this case. See `free_fall_energy.png`.

**Modal decay:** Single-mode E_modal decays as `exp(-2 xi omega t)` matching the analytical Rayleigh envelope. Final ratio after 1000 steps: sim=5.22e-28 vs analytical=5.16e-28. <5% period-averaged error. See `modal_decay.png`.

## Plots

- `docs/stageE0/bouncing_ball_energy.png`
- `docs/stageE0/free_fall_energy.png`
- `docs/stageE0/modal_decay.png`
- `docs/stageE0/energy.csv`
