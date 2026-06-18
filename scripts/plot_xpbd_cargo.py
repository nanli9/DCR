"""Stage 6 artifact — GPU-resident XPBD coupled dynamic modal contact constraint.

Drops a soft cube (fem / fem_rigid) onto the reduced-modal support and records,
per frame, the two-way tell-tales: cube COM height, cargo modal energy (the
cube's own flex), support modal energy, and contact penetration. For each
material it overlays three runs:

  * AVBD dynamic  — the validated Schur–Newton coupler (Stages 3/5);
  * XPBD dynamic  — this stage's compliant-constraint Gauss–Seidel coupler;
  * XPBD frozen   — the `freeze_qdot` counterfactual (q̇≡0, no ring).

The signature (`two_band_coupling.html`): XPBD reproduces AVBD's two-way ring
(the dynamic curves track; the frozen run carries ~0 modal energy), and neither
penetrates the support — so the XPBD primal realizes the same dynamic constraint.

Output: docs/avbd_native/stage6_xpbd_cargo.png

Run: .venv/bin/python scripts/plot_xpbd_cargo.py [--device cuda:0]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scenes.reduced_fem_rigid_cargo import build_cargo_scene

OUT = ROOT / "docs" / "avbd_native"


def run(kind, solver, freeze, n_steps, device, spin=4.0):
    h = build_cargo_scene(kind, device=device, solver=solver, freeze_qdot=freeze,
                          drop_height=0.04, spin=spin,
                          device_resident=(device != "cpu"))
    c, s = h.coupler, h.world._solver
    t, com_y, cargo_E, supp_E, pen = ([] for _ in range(5))
    for step in range(n_steps):
        h.world.step()
        t.append(step / 120.0)
        com_y.append(float(s.positions()[h.avbd_idx][1]))
        # modal KINETIC energy = the RING (the two-way tell-tale): it is the
        # mode's inertia M_q·q̇ that pushes a bystander back. The frozen control
        # holds q̇≡0 ⇒ this is exactly 0, while the static deflection PE is not.
        cargo_E.append(c.last_cargo_modal_KE)
        supp_E.append(c.last_modal_KE)
        pen.append(c.last_contact_residual)
    return dict(t=np.array(t), com_y=np.array(com_y),
                cargo_E=np.array(cargo_E), supp_E=np.array(supp_E),
                pen=np.array(pen))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--steps", type=int, default=240)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    materials = ["fem", "fem_rigid"]
    fig, axes = plt.subplots(len(materials), 4, figsize=(17, 7))
    cols = [("com_y", "cube COM height [m]"),
            ("cargo_E", "cargo modal KE (ring) [J]"),
            ("supp_E", "support modal KE (ring) [J]"),
            ("pen", "contact penetration [m]")]
    runs = [("AVBD dynamic", "avbd", False, "C0", "-"),
            ("XPBD dynamic", "xpbd", False, "C1", "--"),
            ("XPBD frozen",  "xpbd", True,  "C3", ":")]

    for row, kind in enumerate(materials):
        data = {lab: run(kind, slv, fz, args.steps, args.device)
                for (lab, slv, fz, _, _) in runs}
        for col, (key, ylabel) in enumerate(cols):
            ax = axes[row, col]
            for (lab, _slv, _fz, color, ls) in runs:
                d = data[lab]
                ax.plot(d["t"], d[key], ls, color=color, lw=1.6, label=lab)
            if col == 0:
                ax.set_ylabel(f"{kind}\n{ylabel}")
            else:
                ax.set_ylabel(ylabel)
            ax.set_xlabel("t [s]")
            ax.grid(alpha=0.3)
            if row == 0 and col == 0:
                ax.legend(fontsize=8, loc="upper right")
    fig.suptitle("Stage 6 — XPBD realizes the dynamic two-way modal constraint "
                 f"(device={args.device})", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    png = OUT / "stage6_xpbd_cargo.png"
    fig.savefig(png, dpi=110)
    print(f"wrote {png}")

    # quantitative summary the caption cites
    for kind in materials:
        rd = run(kind, "xpbd", False, args.steps, args.device)
        rf = run(kind, "xpbd", True, args.steps, args.device)
        print(f"  {kind:9s} XPBD dynamic peak cargo modal-KE={rd['cargo_E'].max():.3e}  "
              f"frozen peak={rf['cargo_E'].max():.3e}  "
              f"max pen(dyn)={rd['pen'].max():.2e} m")


if __name__ == "__main__":
    main()
