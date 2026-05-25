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
    """
    step: int
    t: float                          # sim time at end of step
    E_rigid_KE_post: float            # rigid kinetic energy AFTER rigid solve
                                      #   (and after DCR velocity kicks)
    E_modal_post: float               # ½‖q̇‖² + ½‖ω q‖² at end of step
    dE_rigid_loss: float              # = world.last_E_loss (E_pre - E_post,
                                      #   raw rigid KE lost in solve)
    dE_modal_injected: float          # change in E_modal due to coupler kick:
                                      #   = last_E_modal_post_kick
                                      #     - last_E_modal_pre_kick
                                      #   POSITIVE for A/B modes (injection),
                                      #   may be NEGATIVE for patch mode
                                      #   (back-reaction extracts from modes)
    alpha: float                      # last_alpha (passive scaling coef
                                      #   used by A/B modes; 0 for patch)
    eta: float                        # world.eta at this step (constant per run)


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

    def cumulative_modal_injected(self) -> NDArray[np.float64]:
        """Cumulative POSITIVE injected modal energy (clipped at zero per
        step). Negative deltas (extraction in patch mode) are NOT counted
        as injection — they appear in `cumulative_modal_extracted()`."""
        d = self.dE_modal_injected()
        return np.cumsum(np.maximum(0.0, d))

    def cumulative_modal_extracted(self) -> NDArray[np.float64]:
        """Cumulative POSITIVE extracted modal energy: sum of `-dE` where
        `dE < 0`. This is the patch-mode back-reaction draining the
        reservoir."""
        d = self.dE_modal_injected()
        return np.cumsum(np.maximum(0.0, -d))

    def invariant_violation(self) -> float:
        """Max excess of cumulative_modal_injected over eta * cumulative
        rigid loss (foundation §15). 0 or negative means bound held."""
        if not self.entries:
            return 0.0
        eta = self.entries[0].eta
        bound = eta * self.cumulative_rigid_loss()
        injected = self.cumulative_modal_injected()
        return float(np.max(injected - bound))
