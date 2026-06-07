# V6 — BCD vs Coupled-AVBD apples-to-apples

Scene: shelf + impactor (-0.5 m/s) + 2 probes; frames=30, iterations=4.

| Mode | Substeps | Step (ms) | Peak |q| (µm) | Peak probe |vy| (mm/s) | Overlay events |
|:---|---:|---:|---:|---:|---:|
|     bcd |  1 |     2.95 |  3543.28 |    25.68 |  0 |
|     bcd |  8 |    14.69 | 28253.51 |   570.90 |  0 |
| coupled |  1 |     7.35 |     3.23 |     1.53 |  0 |
| coupled |  8 |    63.84 |     8.10 |     8.51 |  0 |

## Cost decomposition

- Substep cost factor (BCD): 4.98× going 1→8 substeps (ideal: 8× if linear in substeps).
- Coupling cost factor (substeps=1): 2.49× going BCD→coupled at the same substep count.
- Coupling cost factor (substeps=8): 4.35× going BCD→coupled at the same substep count.