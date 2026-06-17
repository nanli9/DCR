#!/usr/bin/env python3
"""Per-CONTACT-POINT force vs sim time for the lumber stack, as a
THICKNESS × LAYER grid, for each solver (avbd, xpbd).

Reads contact_forces_long.csv; each panel shows the 4 individual corner contact
points of one stack layer at one slab thickness. Rows = thickness, cols = the
3 stack layers (bed→base, base→mid, mid→top).
"""
from __future__ import annotations

import csv
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = "docs/twobody/contact_force_sweep"
LUMBER = 1
LAYER_TITLE = {0: "bed→base (0→2)", 1: "base→mid (2→3)", 2: "mid→top (3→4)"}

# load everything once: (solver,kind,thk,layer) -> {cid: (t[],f[])}
data = defaultdict(lambda: defaultdict(lambda: ([], [])))
thks_seen = set()
with open(f"{OUT}/contact_forces_long.csv") as fh:
    for r in csv.DictReader(fh):
        if r["kind"] != "fem" or int(r["pile"]) != LUMBER:
            continue
        thk = float(r["thickness_m"]); thks_seen.add(thk)
        key = (r["solver"], thk, int(r["stack_layer"]))
        cid = int(r["contact_id"])
        data[key][cid][0].append(float(r["t_s"]))
        data[key][cid][1].append(float(r["force_N"]))

thks = sorted(thks_seen)
layers = [0, 1, 2]
for solver in ("avbd", "xpbd"):
    fig, axs = plt.subplots(len(thks), len(layers),
                            figsize=(14, 3.0 * len(thks)), sharex=True)
    for i, thk in enumerate(thks):
        for j, layer in enumerate(layers):
            ax = axs[i, j]
            cids = sorted(data[(solver, thk, layer)])
            for k, cid in enumerate(cids):
                t = np.array(data[(solver, thk, layer)][cid][0])
                f = np.array(data[(solver, thk, layer)][cid][1])
                ax.plot(t, f, lw=0.8, label=f"corner {k}")
            ax.grid(alpha=0.3)
            if i == 0:
                ax.set_title(LAYER_TITLE[layer], fontsize=10)
            if j == 0:
                ax.set_ylabel(f"{thk*1e3:.0f} mm\nforce [N]", fontsize=9)
            if i == len(thks) - 1:
                ax.set_xlabel("sim time [s]")
            if i == 0 and j == len(layers) - 1:
                ax.legend(fontsize=7, ncol=2, loc="upper right")
    fig.suptitle(f"Per-contact-point force — lumber stack (pile 1), {solver}-fem\n"
                 "rows = slab thickness, cols = stack layer, 4 lines = 4 corner "
                 "contacts (uneven corners = the stack ROCKS)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(f"{OUT}/8_per_contact_point_{solver}.png", dpi=120)
    plt.close(fig)
    print(f"wrote {OUT}/8_per_contact_point_{solver}.png  "
          f"(thicknesses {[f'{t*1e3:.0f}' for t in thks]} mm)")

import os  # noqa: E402
old = f"{OUT}/8_per_contact_point_lumber.png"
if os.path.exists(old):
    os.remove(old)   # superseded by the per-solver thickness grids
