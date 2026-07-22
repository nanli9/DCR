# MIG 2026 — Decision Table 1 (rewrite plan §10, Stage C)

"Guardrail outcome and decision." Rows are the practitioner's options in the
plan §5 order; every value has a frozen source. E6a-1 did NOT support the
shared-block path (worse at deployable budgets), so that row reports the negative
honestly rather than recommending it. Ready to drop into the body at Stage E.

## Provenance (frozen sources)

| cell | value | source |
|---|---|---|
| ungoverned XPBD energy | up to 4.4×10⁷ J (R up to 1.2×10⁵), 9/24 | `eq2_utilization.csv`, E1b: 2.2–4.5×10⁷ J |
| more-iter XPBD converges | serial holds by K≈24–32 (R 0.30 @32×1) | `k_convergence*.csv`, `e6a1…csv` (serial 32×1 holds) |
| more-iter XPBD contact | gap 27.9 mm→3.6 µm by K=64 | `complementarity_residual.csv` |
| more-iter XPBD trajectory | fixed point 34% of ref peak (formulation gap) | `selfconvergence*.csv` (R4) |
| block condensation | worse at 8×2/16×4/32×1; injects where serial holds | `e6a1_block_condensation.csv` (E6a-1) |
| implicit control | 0/24, converged at K=2 | `eq2_utilization.csv`, `k_convergence.csv` |
| governor energy | Eq.(2) holds unconditionally, 90 cells ≤1.1×10⁻¹³ J | Prop.; `eq2_utilization.csv` governed |
| governor penetration | 21.6 mm (72% board) @4×1; 9.8 mm deployed | `projection_validity*.csv` (E-S3), R5.4 |
| governor trajectory | L∞ 33%→71% of ref peak (worse) | `governed_accuracy*.csv` (R5.1b) |
| governor cost | +0.9–3.4% @16×4; +6.6–34% deployed | R7 timings, E-C6 |

## LaTeX (Table 1)

```latex
\begin{table}[t]
\centering\footnotesize
\setlength{\tabcolsep}{3pt}
\caption{Practitioner options for a fixed-budget XPBD rigid host that needs
low-cost modal vibration, in the recommended order of preference. One
implementation of each control; values are measured where a number is given.
The shared-block ablation (E6a-1) is reported, not recommended: it does not fix
the injection and is worse at deployable budgets.}
\label{tab:decision}
\begin{tabular}{@{}p{1.7cm}p{1.5cm}p{1.35cm}p{1.2cm}p{1.15cm}@{}}
\toprule
option & energy & contact validity & trajectory & when to use \\
\midrule
implicit realization (control) & never overdraws ($0/24$) & valid & the
reference & architecture is flexible \\[2pt]
more XPBD iterations & converges, holds by $K{\approx}24$--$32$ & gap
$\to3.6\,\mu$m by $K{=}64$ & approaches ref; $34\%$ residual & fixed host,
budget affordable \\[2pt]
shared-block condensation & \emph{not} a fix; worse at $8{\times}2$--$32{\times}1$
& --- & --- & \textbf{not recommended} \\[2pt]
cumulative governor & holds Eq.~\eqref{eq:invariant} ($\le10^{-13}$~J) & $21.6$~mm
pen.\ ($72\%$ board) & $L_\infty$ $71\%$ of ref & last resort, containment only \\[2pt]
ungoverned direct row & overdraws up to $4.4{\times}10^{7}$~J ($9/24$) & --- &
diverges & the diagnosed failure \\
\bottomrule
\end{tabular}
\end{table}
```

Notes for the caption/prose (Stage E):
- Keep "one implementation of each control; not compliance- or cost-matched"
  (nonclaim 4).
- The governor row's guarantee and cost must sit together (plan §5, C5).
- The block-condensation row is E6a-1's negative result; label it a probe, do not
  generalize (plan §9).
- Cost column omitted from the table to keep it legible; runtime facts go in
  §runtime prose (governor +0.9–3.4% @16×4, +6.6–34% deployed; iterations 8–64×
  row-evals). E4 (matched wall-clock) would refine this row if run.
