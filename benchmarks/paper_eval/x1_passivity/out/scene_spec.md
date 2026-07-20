| quantity | unit | shelf | ledge | table |
|---|---|---|---|---|
| support length | m | 0.80 | 1.20 | 2.20 |
| support width | m | 0.30 | 0.80 | 1.10 |
| support thickness | m | 0.030 | 0.080 | 0.040 |
| support top height | m | 0.015 | 0.040 | 0.030 |
| Young's modulus E | Pa | 5e+08 | 1e+10 | 1.1e+09 |
| density | kg/m^3 | 600 | 500 | 770 |
| Poisson ratio | - | 0.30 | 0.30 | 0.30 |
| impactor mass | kg | 6.0 | 50.0 | 5.0 |
| impactor drop height | m | 0.50 | 0.80 | 0.50 |
| impactor initial speed | m/s | 0.0 | 0.0 | -- |
| Rayleigh alpha_0 | 1/s | 3.0 | 2.0 | 2.0 |
| Rayleigh alpha_1 | s | 1.0e-05 | 1.0e-05 | 1.0e-05 |
| global modes REQUESTED | - | 10 | 12 | 10 |
| local modes REQUESTED | - | 14 | 16 | 14 |
| timestep h | s | 0.008333 | 0.008333 | 0.008333 |
| modal rank r REALIZED | - | 16 | 16 | 24 |
|   of which stiff cluster | - | 6 | 4 | 14 |
| lowest mode | Hz | 20.3 | 118.1 | 4.7 |
| highest mode | Hz | 24708 | 190903 | 5202 |
| support rows (eq. 1) | - | 48 | 40 | 200 |
| dynamic bodies | - | 7 | 6 | 26 |

Seeds: none. The CPU path has no RNG; every run is bit-deterministic on a fixed machine (Apple M4, CPython 3.12).

**REQUESTED vs REALIZED modes.** `n_modes_local` is clamped to the number of distinct contact zones (`scenes/reduced_scene_common.py:242`, deduped within 15 mm, because coincident bumps make Mq singular), so the delivered rank is smaller than `n_modes_global + n_modes_local` on the shelf and ledge. The paper's Table 1 prints the REALIZED rank.
