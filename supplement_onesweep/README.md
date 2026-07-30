# Supplemental material

Anonymous supplement for the submission *A Per-Row Danger Index and a
Reconstruction-Matched Effective Mass for One-Sweep Passive Contact
Coupling in Fixed-Budget Position-Based Solvers*.

## Layout

- `code/t_onesweep/` the validation suite (T1 to T14 and the T4 index
  audit) and the figure builder.
- `code/t_onesweep/benchmarks/` a generated three-file import shim, so
  the sources resolve their two absolute module names inside this
  package. It adds no behaviour; read its docstring.
- `code/t_onesweep/out/` seeded with the frozen CSVs that some checks
  read as INPUT, and where a re-run writes its own output. The seeded
  copies are byte-identical to the same names under `data/`.
- `code/host_excerpt/` verbatim, line-numbered excerpts of the
  production host, quoted as evidence for the reconstruction
  convention. Text files, not importable modules.
- `code/x1_passivity/` the three shipped-host weight-swap drivers.
- `data/` every CSV a number in the paper is taken from, with the
  `.config.json` manifest each run wrote. CSVs over 2 MB ship
  gzipped, which here is the 241x241 phase map and the T13
  ordering sweep; the mass-arm per-cell dump ships gzipped as its
  own harness wrote it.

## What runs from this package alone

The analytic and nonmodal checks are pure numpy and self-contained:

```
python code/t_onesweep/selftest_common.py     # 44 primitive checks
python code/t_onesweep/run_t1_identities.py
python code/t_onesweep/run_t2_phasemap.py
python code/t_onesweep/run_t3_nonmodal.py
python code/t_onesweep/run_t5_ordering.py
python code/t_onesweep/run_t7_reconstruction.py
python code/t_onesweep/run_t8_relaxation.py
python code/t_onesweep/run_t10_multimode.py   # operator form, exact
python code/t_onesweep/run_t11_accuracy.py    # converged reference
python code/t_onesweep/run_t4_index_audit.py  # reads t4_shipped.csv
python code/t_onesweep/run_t12_hypotheses.py
python code/t_onesweep/run_t13_ordering_kappa.py  # reads out/t5_ordering.csv
python code/t_onesweep/run_t14_passive_family.py  # T14a; reads out/t11_accuracy.csv
python code/t_onesweep/run_t14_warm_multirow.py  # T14c
python code/t_onesweep/run_t14_massarm_baseline.py  # mass-arm warm baseline
```

Each script prints a per-check PASS/FAIL table and exits nonzero on any
failure. Tolerances are stated in each file and are never loosened to
make a claim pass; where a float check is round-off limited the file
says so and supplies an exact-arithmetic check instead (T10, block E).

## What does NOT run from this package

T4, T6, T9, the equal-cost arm T14b and the cost measurements drive a
production position-based solver that is not redistributed here. Their
drivers are included so the protocol, the exact contact-row weights and
the operating points are auditable, and their outputs are included as
CSVs, but re-running them needs that host. This is stated so the package
is not mistaken for a complete reproduction of the shipped-row
experiments.

What the host DOES have to make auditable is its velocity reconstruction, since
every shipped-row result is read at that convention. `code/host_excerpt/` quotes
the two blocks verbatim with their source paths and line numbers: the rigid
read-back `V[i] = (X[i] - x_prev[i]) / h`, which is `kappa_r = 1` for every body,
and the modal commit `qdot = 2(q - q^n)/h - qdot^n` that the symplectic default
selects, which is `kappa = 2`. The shipped rows are therefore the mixed
`(kappa_r, kappa) = (1, 2)` case, and that can now be checked without the host.

## Environment

Python 3.12, numpy only (plus matplotlib for the figure builder).
The exact-arithmetic block of T10 uses the standard-library
`fractions` module. Runs were on a CPU, arm64.

## Number to source map

- boundary $(\omega h)^2 = 1 + m/M$, 0 of 58,081 cells misclassified
  -> `data/t2_phasemap.csv.gz`
- identity battery, 29/29 checks at rel <= 1e-12
  -> `data/t1_identities.csv`
- nonmodal collapse, 288/288 sign, max|y-(rho-1)| = 4.26e-14
  -> `data/t3_nonmodal.csv`
- ordering divisor (1+b)^2 = 10201 at b = 100, exact
  -> `data/t5_ordering.csv`
- shipped row: backward-Euler control 27/27 mass sign, 27/27 implicit passive; symplectic factor 2.000; implicit under midpoint dinner 9/9, shelf 2/9, ledge 4/9
  -> `data/t4_shipped.csv`
- rho_mid tracks 27/27 while rho_BE tracks 22/27 with 5 false negatives
  -> `data/t4_index_audit.csv`
- shipped row, symplectic default, matched weight m(4+(omega h)^2): 27/27 passive
  -> `data/t4_matched.csv`
- reconstruction-general effective mass mu = m(kappa^2 + (omega h)^2), 7000 cells at rel <= 1e-12, 0 sign mismatches
  -> `data/t7_reconstruction.csv`
- relaxation boundary theta^2(kappa^2 + b) = 2 + m/M, 542 injecting to passive, 0 passive to injecting
  -> `data/t8_relaxation.csv`
- multi-coordinate operator form: matched charge passive on 3000/3000 float cells and exact on 300/300 rational cells; diagonal charge on non-diagonal K injects on 19/2000
  -> `data/t10_multimode.csv`
- accuracy against the converged reference: C+ = 0 for every weight; matched sweep equals the converged backward-Euler step to 5.5e-16; mass-only over-deposit (M+m(1+b))/(M+m); matched kappa=2 charge is 4x the converged midpoint charge
  -> `data/t11_accuracy.csv`
- system weight swap, three arms on 24 cells: explicit 8 injecting, backward-Euler 0, matched 0
  -> `data/weight_swap_matched.csv`
- published two-arm weight swap reused from the companion study
  -> `data/weight_swap_full.csv`
- scene parameters of every shipped-row cell: M, h, alpha-tilde, w_r, sum a_i, L, rho and rho_mid for 3 scenes x 9 stiffness scales, plus the Fig. 1 teaser scene
  -> `data/scene_params_cells.csv`
- per-mode modal parameters at stiffness scale 1: m_i, k_i, omega_i, zeta_i, the contact-row shape value U_i, a_i = U_i^2/m_i and b_i = (omega_i h)^2
  -> `data/scene_params_modes.csv`
- hypothesis pinning: the reconstruction-split dE at rel 5.5e-14 on 9000 cells; the mass-only boundary kappa^2 + b = 2 kappa_r + kappa_r(2-kappa_r) m/M with 0 of 4000 misclassified at each of five (kappa_r, kappa); the matched charge passive for every kappa at kappa_r = 1 and, under kappa_r = kappa, passive at every mass ratio iff kappa in [1/2, 2]; the over-deposit factor 1 + b m/(M+m); the damped amplitude gap 2 zeta omega h/(1 + M/m + b); the kappa = 2 reproducing charge mu* = m(2 + b/2); kappa = 1 exactness requiring zeta = 0. 28/28 checks
  -> `data/t12_hypotheses.csv`
- reconstruction-general ordering: D_B/D_A = (1+b)^2 at every kappa; trailing-spring injection iff (kappa^2+b)/(1+b)^2 > 2 + m/M, so 0 of 10,000 cells at kappa = 1 and 3840 of 10,000 at kappa = 2; failure band m/M < kappa^2 - 2 with edge b* = (sqrt(37)-5)/6 = 0.18046 at m = M; peak deposit (kappa^2-2)^2/[4(kappa^2-1)]. 56/56 checks, 40,705 rows, bit-identical to run_t5_ordering.py and to the shipped t5_ordering.csv at kappa = 1
  -> `data/t13_ordering_kappa.csv.gz`
- passive family (Cor. 3.4, Table 1 row T14a): W = c G^-1 telescopes Eq. (6) to dE = (v^2/2D^2)[c(c-2) a - w_r - 2 a_tilde], so exactly c in [0,2] is passive; 2500 randomized symmetric charges each met with an adversarial row, all 1222 inside the Loewner interval passive and all 1278 outside injecting; 720 exact-rational cells with the closed form and the sign law as equalities of rationals; the far endpoint c = 2 returns the converged amplitude to 2e-16, cross-checked against the shipped t11_accuracy.csv columns; c = 1 keeps at least 100% headroom to the injection threshold on all 4000 margin cells (median 171%) while c = 2 is under 1% on 0.20825 of them (median 36%)
  -> `data/t14_passive_family.csv`
- warm and two-row boundary (Table 1 row T14c; measurement only, nothing here is a theorem): the warm instrument matches the simulated sweep to 6.8e-15 relative on 13,050 cells and reduces to Eq. (6) cold; the mass-only index calls safe a row that injects on 2795 of 43,783 warm and two-row cells; the matched charge still injects on 4099 of 43,898; order alone flips 734 signs over 8095 two-row cells; the shipped kappa = 2 midpoint pairing is clean, 0 false negatives and 0 false positives of 4104 active cells; the cold control misclassifies 0 of 4800; resting contact stays secularly bounded over 20,000 substeps
  -> `data/t14_warm_multirow.csv`
- equal cost (Table 1 row T14b) on the same 27 shipped cells as T4 and T9: the mass-only weight injects on 22, 17, 9, 6 and 2 cells at 1, 2, 4, 8 and 16 iterations, the last still overshooting one cell by 28.3 times its incoming kinetic energy, while the matched weight injects on 0 at one iteration for 1.004 times the substep cost; median returned amplitude 0.567 (matched, one iteration) against 0.853 (mass-only, 16 iterations), the 64-iteration converged step being 1.0 at 20.5 times the cost. Ratios only; absolute microseconds are never quoted
  -> `data/t14_equalcost.csv`
- cost: the matched weight runs at 0.99231 to 1.01753 times the mass-only default on the shipped rows (3 scenes x 5 trials, r = 16, 16 and 24 modes), and a dense G^-1 row costs 6.812 to 14.481 times the diagonal accumulation for r = 4 to 64 (8 timing blocks x 1000 rows). Ratios measured between two costs on one host; the absolute microseconds are a numpy reference implementation and are not production representative, as the manifests state
  -> `data/tcost_shipped.csv`
- system-level corroboration of the boundary on the frozen 24-cell weight swap (no rerun; reads weight_swap_full.csv READ-ONLY): 8 injecting cells under the explicit mass-only weight against 0 under the implicit one, the explicit arm bit-faithful to the frozen baseline below 1e-6, and the logged inverse mobility matching 1 + (omega h)^2 within 5% on every row
  -> `data/t6_ews_corroboration.csv`
- mass-only weight on the warm and two-row cells: the injection count of the weight itself, on the same deterministic populations as run_t14_warm_multirow.py, so the index-miss count and the injection count are reported on stated denominators
  -> `data/t14_massarm_baseline.csv`
- per-substep TOTAL mechanical energy on the same 24-cell grid, i.e. the theorem's own E+ > E- sign rather than the modal ratio: 10 of 24 cells above the window start under the explicit weight, 1 of 24 under backward-Euler (that one at 1.2e-5 of the impactor kinetic energy) and 0 of 24 matched; the position-based update's ballistic drift makes those counts lower bounds
  -> `data/weight_swap_energy.csv`
- per-cell dump behind the mass-arm baseline summary: one row per warm or two-row cell with its measured sign, so the counts can be recomputed rather than taken on trust
  -> `data/t14_massarm_baseline_cells.csv.gz`

## Scene parameters

`data/scene_params_cells.csv` and `data/scene_params_modes.csv` carry every
parameter the closed forms need, so each shipped-row number in the paper can be
recomputed from the package. `code/t_onesweep/dump_scene_params.py` regenerates
both from the same scene builders the shipped-row runs use (it needs the
production host, like T4, T6 and T9).

Conventions used in both files:

- The modal bases are mass-normalized, so `m_i = 1` kg for every mode and
  `a_i = U_i^2`, where `U_i` is the mode's shape value at the contact row.
- `w_r` is the row-visible rigid mobility `1/M + j_a^T I^-1 j_a`; the column
  `M_row_kg` is `1/w_r` and is smaller than the impactor mass because of the
  corner lever arm.
- `a_tilde = alpha/h^2` with `alpha` the solver's support compliance, `1e-8` m/N
  in every scene.
- `rho = L/(w_m + 2 a_tilde)` with `w_m = w_r + sum a_i` and `L = sum a_i b_i`
  is the `kappa = 1` index; `rho_mid = (L + 2 sum a_i)/(w_r + 2 a_tilde)` is the
  `kappa = 2` index the shipped symplectic host is governed by.
- The stiffness sweep is zeta-preserving: at scale `s`, `omega_i(s) =
  sqrt(s) omega_i(1)` while `m_i`, `U_i` and `zeta_i` are unchanged. The modes
  table is therefore written once, at `s = 1`.
- The 27 shipped-row cells run at one iteration and one substep, so
  `h = 1/120` s; the Fig. 1 teaser runs at one iteration and eight substeps, so
  `h = 1/960` s.

## Reproduced from a clean interpreter

Every command in the run block under *What runs from this package alone* was
re-run from a fresh copy of this package on a machine where the source
repository is NOT importable, and each exited zero. Run them from the package
root; they do not care about the working directory beyond that. The only
prerequisite is Python 3 with numpy: there is nothing to install and no path to
set.

Each check regenerates its own CSV into `code/t_onesweep/out/`. For the
deterministic checks that CSV is byte-identical to the copy shipped in `data/`
(the seeds are fixed in the sources); the accompanying `.config.json` differs in
`git_sha` and `generated_utc` only, because a package unpacked outside a
checkout has no commit to report.

## Integrity

`SHA256SUMS` lists a digest for every file above. The package was
scanned to confirm it carries no home-directory path, username or
other author-identifying token.
