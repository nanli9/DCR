# Figure Export

All graphs/animations from the repo, copied here (originals untouched in `plot/` and `docs/`). 59 images, ~25 MB.

## energy_plots/ — coupled-energy traces (research/debug)
Energy-conservation traces for the coupled rigid↔modal stepper under different integrators and settings:
- `coupled_energy_iir.png`, `coupled_energy_bdf1.png`, `coupled_energy_wood_newmark*.png` — integrator variants (IIR, BDF1, Newmark; `_substep`, `_zoom`).
- `coupled_energy_g{1,4,8}*.png` — gain sweeps; `g4_cz{025,05,10}` and `g8_eta{025,05,10}` are the cz / η sub-sweeps.
- `coupled_energy_jump_g{1,4,8,12}.png` — jump scenario at increasing gain.
- `coupled_energy_smoke_*.png` — smoke tests (plain, static, iir, old_dcr_postkick, coupled_modal_bdf1).
- `coupled_energy_ab_eigen.png`, `coupled_energy_ab_synth.png`, `coupled_energy_postkick.png`, `coupled_energy_test_preset.png` — misc checks.

## stageE0/ — energy bookkeeping (follow-up Stage E0)
- `free_fall_energy.png`, `bouncing_ball_energy.png`, `modal_decay.png`

## stageE3/ — wired modal injection (Stage E3)
- `plate_displacement_comparison.png`, `plate_velocity_comparison.png`
- `energy_invariant.png`, `modal_energy_evolution.png`

## stageE4/ — aggregation + dissipation (Stage E4)
- `aggregation_comparison.png`, `monotone_dissipation.png`

## stageE5/ — η transfer-efficiency sweep (Stage E5)
- `dinner_eta_{0.0,0.1,0.3,0.5,1.0}.gif` — dinner scene at each η
- `energy_invariant.png`, `eta_sweep_strip.png`

## stage7/ — DCR core scenes (Stage 7)
- `compare.gif`, `spatial.gif`, `dinner.gif`

## avbd_native/ — AVBD-Native branch (current work)
- `stage1_dynamic_vs_frozen_{summary,dinner,ledge,shelf,truck}.png` — dynamic vs frozen constraint
- `stage3_fem_rigid_cargo.{png,gif}`, `stage4_abd_cargo.{png,gif}`, `stage5_fem_cargo.{png,gif}`
- `stage6_xpbd_cargo.png`, `m2_native_fem_rigid_cargo.{png,gif}`

> Not included: `benchmark/runs/*.csv` (B1–B7 sweeps, dinner/dt traces) are raw data, not yet plotted into images.
