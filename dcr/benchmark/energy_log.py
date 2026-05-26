"""Per-step energy-bookkeeping log for one DCRWorld run.

Sampled at the end of every `DCRWorld.step()` when
`world.enable_energy_logging` is True. Captures the quantities needed
to show that the passive energy bound (foundation §15) holds:

    cumulative dE_modal_injected  <=  eta * cumulative dE_rigid_loss

and to plot the energy budget over time (E_rigid_KE, E_modal,
cumulative losses + injections, alpha scaling per step).

The logger lives on the WORLD because both rigid (E_loss) and modal
(E_modal) quantities are needed and the world is the only place both
are in scope at the right boundaries (post-solve, post-coupler).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class EnergyLogEntry:
    """One step's energy snapshot.

    All values in SI (J). `dE_*` are per-step deltas, not cumulative.
    Column names on disk follow `benchmark/BENCHMARK_PROMPT.md` §2.1;
    Python-side field names are kept verbose for readability and remapped
    in `EnergyLog.to_csv()`.
    """
    step: int
    t: float                          # sim time at end of step
    E_rigid_KE_post: float            # → CSV col "E_rigid_KE": rigid KE AFTER
                                      #   rigid solve + DCR velocity kicks
    E_modal_post: float               # → CSV col "E_modal": ½‖q̇‖² + ½‖ω q‖²
    dE_rigid_loss: float              # = world.last_E_loss (E_pre - E_post,
                                      #   raw rigid KE lost in solve)
    dE_modal_injected: float          # POSITIVE part of modal energy delta
                                      #   this step (max(dE, 0)).
    dE_modal_extracted: float         # POSITIVE part of modal energy DROP
                                      #   this step (max(-dE, 0)). Tracks the
                                      #   patch-mode back-reaction draining
                                      #   the modal reservoir.
    alpha: float                      # last_alpha (passive scaling coef
                                      #   used by A/B modes; NaN for paper
                                      #   baseline coevoet mode per §2.1).
    eta: float                        # world.eta at this step (constant)
    beta: float                       # world.beta at this step (constant)
    n_active_kicks: int               # DCR distant-velocity kicks issued
                                      #   this step (after any α/cap clip).
    n_active_contacts: int            # total active contacts in solver.


@dataclass
class EnergyLog:
    """Accumulator over a single run."""
    entries: list[EnergyLogEntry] = field(default_factory=list)

    def append(self, entry: EnergyLogEntry) -> None:
        self.entries.append(entry)

    def __len__(self) -> int:
        return len(self.entries)

    # -------- vectorized accessors (used by plotting + invariant checks) --

    def times(self) -> NDArray[np.float64]:
        return np.array([e.t for e in self.entries], dtype=np.float64)

    def E_rigid(self) -> NDArray[np.float64]:
        return np.array([e.E_rigid_KE_post for e in self.entries],
                        dtype=np.float64)

    def E_modal(self) -> NDArray[np.float64]:
        return np.array([e.E_modal_post for e in self.entries],
                        dtype=np.float64)

    def dE_rigid_loss(self) -> NDArray[np.float64]:
        return np.array([e.dE_rigid_loss for e in self.entries],
                        dtype=np.float64)

    def dE_modal_injected(self) -> NDArray[np.float64]:
        return np.array([e.dE_modal_injected for e in self.entries],
                        dtype=np.float64)

    def alpha(self) -> NDArray[np.float64]:
        return np.array([e.alpha for e in self.entries], dtype=np.float64)

    def cumulative_rigid_loss(self) -> NDArray[np.float64]:
        return np.cumsum(self.dE_rigid_loss())

    def dE_modal_extracted(self) -> NDArray[np.float64]:
        return np.array([e.dE_modal_extracted for e in self.entries],
                        dtype=np.float64)

    def cumulative_modal_injected(self) -> NDArray[np.float64]:
        """Cumulative POSITIVE injected modal energy (the per-step deltas
        are already clipped at zero in `EnergyLogEntry.dE_modal_injected`).
        Drops show up in `cumulative_modal_extracted()`."""
        return np.cumsum(self.dE_modal_injected())

    def cumulative_modal_extracted(self) -> NDArray[np.float64]:
        """Cumulative POSITIVE extracted modal energy — patch-mode
        back-reaction draining the reservoir."""
        return np.cumsum(self.dE_modal_extracted())

    def invariant_violation(self) -> float:
        """Max excess of cumulative_modal_injected over eta * cumulative
        rigid loss (foundation §15). 0 or negative means bound held."""
        if not self.entries:
            return 0.0
        eta = self.entries[0].eta
        bound = eta * self.cumulative_rigid_loss()
        injected = self.cumulative_modal_injected()
        return float(np.max(injected - bound))

    # ----------------- serialization (CSV / npz) ------------------------

    def to_csv(self, path) -> None:
        """Write one row per step in `BENCHMARK_PROMPT.md` §2.1 schema.

        Columns (case-sensitive — the plotter selects by name):
            step, t,
            E_rigid_KE, E_modal,
            dE_rigid_loss, dE_modal_injected, dE_modal_extracted,
            cum_E_loss, cum_E_budget_eta,
            cum_E_injected, cum_E_extracted,
            alpha, eta, beta,
            n_active_kicks, n_active_contacts
        """
        import csv
        import math
        from pathlib import Path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cum_loss = self.cumulative_rigid_loss()
        cum_inj = self.cumulative_modal_injected()
        cum_ext = self.cumulative_modal_extracted()
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "step", "t",
                "E_rigid_KE", "E_modal",
                "dE_rigid_loss", "dE_modal_injected", "dE_modal_extracted",
                "cum_E_loss", "cum_E_budget_eta",
                "cum_E_injected", "cum_E_extracted",
                "alpha", "eta", "beta",
                "n_active_kicks", "n_active_contacts",
            ])
            for i, e in enumerate(self.entries):
                cum_budget = e.eta * cum_loss[i]
                # NaN α written as the string "nan" — spec §2.1 explicitly
                # admits NaN here for paper-baseline coevoet rows.
                alpha_str = (
                    "nan" if (isinstance(e.alpha, float) and math.isnan(e.alpha))
                    else f"{e.alpha:.6e}"
                )
                w.writerow([
                    e.step, f"{e.t:.6f}",
                    f"{e.E_rigid_KE_post:.6e}", f"{e.E_modal_post:.6e}",
                    f"{e.dE_rigid_loss:.6e}", f"{e.dE_modal_injected:.6e}",
                    f"{e.dE_modal_extracted:.6e}",
                    f"{cum_loss[i]:.6e}", f"{cum_budget:.6e}",
                    f"{cum_inj[i]:.6e}", f"{cum_ext[i]:.6e}",
                    alpha_str, f"{e.eta:.6e}", f"{e.beta:.6e}",
                    e.n_active_kicks, e.n_active_contacts,
                ])
