"""DCR-paper-style validation of the "Dinner is served" scene (paper §5.2).

    python -m benchmarks.dinner_dcr.run_dinner_dcr [--quick] [--refine 1]

Duplicates the paper's ground-truth protocol and presentation style:
one scene, our method vs a fully elastic ground-truth simulation of the
same setting, judged on qualitative agreement — NOT mesh-convergence
metrology (see docs/benchmark_plan.md §3.1 for why). The paper compared
its IIR modal table against a SOFA stiff-elastic table at h = 1e-5 and
reported "qualitatively quite similar" (§5.2); here the native modal
solver (every body a deformable cargo on the §N2 network) is compared
against the all-FEM GT (every body FEM, `MultiFEMSim`).

Beyond the paper: the pot is dropped at THREE positions along the table
(the paper drops it once, at the centre; its position sweeps are shown
only on the ground/scaffold spatial path, §5.3). For each drop we record
every resting body's peak jump vs its horizontal distance from the drop
point — the distance-attenuation story on the table itself. For a flat
table the geodesic distance the paper uses reduces to the Euclidean
distance (paper §4.4: "for flat terrain, this simplifies ... to a simple
Euclidean distance").

Outputs: docs/dinner_dcr/response_vs_distance.png, near_far_traces.png,
results.json (+ per-drop GT csv/json under docs/dinner_dcr/gt_dN/).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402

from benchmarks.fem_gt.common import run_scene_gt   # noqa: E402
from scenes.reduced_dinner_table import build_reduced_dinner_table  # noqa: E402

OUT = ROOT / "docs" / "dinner_dcr"

# Drop points chosen on clear table (no body under the pot footprint):
# centre / two-thirds out / near the end, all on the z=0 aisle between the
# place-setting rows (candlesticks at x = ±0.45 are cleared by ≥ 45 mm).
DROPS = [(0.0, 0.0), (0.65, 0.0), (0.90, 0.0)]

# PAPER_CONFIG budget (the production operating point on this branch).
# support_basis="fem" = the G1 shared-operator arm: the native table's modal
# basis is the eigenbasis of the SAME discrete FEM operator the GT integrates
# (same R1 mesh rule) — without it the two arms are different tables and the
# comparison is meaningless (measured 30x mismatch with the debug basis).
# Two native variants:
#   rigid — dishes are plain rigid bodies, ONLY the table is modal. This is
#           the DCR paper's own configuration (§4.5: "many of the smaller
#           objects in our simulations treated simply as rigid bodies (e.g.,
#           plates, cups on the table)").
#   cargo — every body a deformable modal cargo on the §N2 network (our
#           generalization beyond the paper). Soft bodies (E=1e6) absorb
#           part of the impact -> weaker table ring, by construction.
NATIVE_RIGID = dict(solver="avbd", iterations=16, avbd_substeps=4,
                    support_basis="fem")
NATIVE_CARGO = dict(solver="avbd", iterations=16, avbd_substeps=4,
                    cargo_material="fem_rigid", cargo_all=True,
                    cargo_n_elastic=3, support_basis="fem")


def _native_run(drop_xz, t_run: float, cfg: dict,
                h: float = 1.0 / 120.0) -> dict:
    """Native arm: per-body peak upward jump [m] + rest (x,z) + timing."""
    handle = build_reduced_dinner_table(h=h, device="cpu",
                                        pot_drop_xz=drop_xz, **cfg)
    sol = handle.world._solver
    idx = {b.name: int(handle.world._descs[b.dcr_idx].avbd_body.index)
           for b in handle.bodies}
    P0 = sol.positions().copy()
    y0 = {n: float(P0[i][1]) for n, i in idx.items()}
    xz = {n: (float(P0[i][0]), float(P0[i][2])) for n, i in idx.items()}
    traces = {n: [] for n in idx}
    n_steps = int(round(t_run / h))
    t0 = time.perf_counter()
    for _ in range(n_steps):
        handle.world.step()
        P = sol.positions()
        for n, i in idx.items():
            traces[n].append(float(P[i][1]))
    wall = time.perf_counter() - t0
    assert all(np.all(np.isfinite(v)) for v in traces.values()), "native NaN"
    return dict(
        y0=y0, xz=xz,
        dy_max={n: max(v) - y0[n] for n, v in traces.items()},
        traces={n: v for n, v in traces.items()},
        h=h, ms_per_step=wall / n_steps * 1e3, wall_s=wall)


def _gt_run(drop_xz, tag: str, *, refine: int, h_fine: float,
            t_settle: float, t_run: float) -> dict:
    """GT arm: same scene mirrored into the all-FEM sim (pot position flows
    through the handle mirror), X3 park/settle/release protocol."""
    handle = build_reduced_dinner_table(device="cpu", solver="avbd",
                                        pot_drop_xz=drop_xz)
    out_dir = OUT / f"gt_{tag}"
    t0 = time.perf_counter()
    rec = run_scene_gt("dinner", handle, "pot", h_fine=h_fine,
                       t_settle=t_settle, t_run=t_run, refine=refine,
                       out_dir=out_dir)
    wall = time.perf_counter() - t0
    names = [b.name for b in handle.bodies]
    xz = {}
    sol = handle.world._solver
    P = sol.positions()
    for b in handle.bodies:
        i = int(handle.world._descs[b.dcr_idx].avbd_body.index)
        xz[b.name] = (float(P[i][0]), float(P[i][2]))
    com = rec["com_y"]
    dt = rec["times"][1] - rec["times"][0] if len(rec["times"]) > 1 else 0.0
    return dict(
        xz=xz,
        dy_max={n: float(np.max(np.asarray(com[n]) - com[n][0]))
                for n in names},
        traces={n: [float(v) for v in com[n]] for n in names},
        dt=float(dt), wall_s=wall)


def _gt_from_csv(drop_xz, tag: str) -> dict | None:
    """Reload a previously recorded GT run (same drop) from its CSV — the GT
    is by far the expensive arm (~18 min/drop); native variants iterate on
    top of it. Returns None if no recording exists."""
    import csv as _csv
    path = OUT / f"gt_{tag}" / "dinner_gt_r1.csv"
    if not path.exists():
        return None
    with open(path) as fh:
        rows = list(_csv.DictReader(fh))
    names = [c[len("com_y:"):] for c in rows[0] if c.startswith("com_y:")]
    com = {n: [float(r[f"com_y:{n}"]) for r in rows] for n in names}
    handle = build_reduced_dinner_table(device="cpu", pot_drop_xz=drop_xz)
    sol = handle.world._solver
    P = sol.positions()
    xz = {b.name: (float(P[int(handle.world._descs[b.dcr_idx].avbd_body.index)][0]),
                   float(P[int(handle.world._descs[b.dcr_idx].avbd_body.index)][2]))
          for b in handle.bodies}
    dt = (float(rows[1]["t"]) - float(rows[0]["t"])) if len(rows) > 1 else 0.0
    return dict(
        xz=xz,
        dy_max={n: float(np.max(np.asarray(com[n]) - com[n][0]))
                for n in names if n != "support"},
        traces={n: com[n] for n in names if n != "support"},
        dt=dt, wall_s=float("nan"))


def _dist(xz, drop_xz) -> float:
    return float(np.hypot(xz[0] - drop_xz[0], xz[1] - drop_xz[1]))


def _plot_response(results) -> None:
    fig, axes = plt.subplots(1, len(results), figsize=(4.6 * len(results), 3.8),
                             sharey=True)
    for ax, r in zip(np.atleast_1d(axes), results):
        drop = r["drop_xz"]
        for arm, style in (
                ("native_rigid", dict(marker="o", ls="-", c="#c0392b",
                                      label="native, rigid dishes (paper §4.5)")),
                ("native_cargo", dict(marker="^", ls=":", c="#d68910",
                                      label="native, all-cargo (ours)")),
                ("gt", dict(marker="s", ls="--", c="#2c3e50", mfc="none",
                            label="all-FEM ground truth"))):
            d = r[arm]
            # Exclude toppled/flung bodies (>0.3 m): the GT has frictionless
            # vertical-normal contact with unresolved side faces — post-topple
            # trajectories are explicitly unscored (multibody_gt DEVIATIONs).
            skip = {n for n, v in d["dy_max"].items() if v > 0.3}
            if skip:
                print(f"  [{arm} drop {drop}] excluded toppled/flung: "
                      f"{sorted(skip)}")
            pts = sorted((_dist(d["xz"][n], drop), d["dy_max"][n] * 1e3)
                         for n in d["dy_max"] if n != "pot" and n not in skip)
            ax.plot([p[0] for p in pts], [max(p[1], 1e-4) for p in pts],
                    lw=1.2, ms=4, **style)
        ax.set_yscale("log")
        ax.set_xlabel("distance from drop point [m]")
        ax.set_title(f"pot dropped at ({drop[0]:+.2f}, {drop[1]:+.2f})")
        ax.grid(alpha=0.3)
    np.atleast_1d(axes)[0].set_ylabel("peak upward jump [mm]")
    np.atleast_1d(axes)[0].legend()
    fig.suptitle("Dinner is served — response vs distance from impact "
                 "(native modal solver vs all-FEM ground truth)")
    fig.tight_layout()
    fig.savefig(OUT / "response_vs_distance.png", dpi=150)
    plt.close(fig)


def _plot_traces(results) -> None:
    """Near vs far plate height traces, native vs GT — the §5.2-style
    qualitative side-by-side (plot form; the paper used a video)."""
    r = results[1] if len(results) > 1 else results[0]
    drop = r["drop_xz"]
    nr = r["native_rigid"]
    plates = [n for n in nr["dy_max"] if n.startswith("plate")]
    near = min(plates, key=lambda n: _dist(nr["xz"][n], drop))
    far = max(plates, key=lambda n: _dist(nr["xz"][n], drop))
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), sharey=False)
    for ax, name in zip(axes, (near, far)):
        tn = np.asarray(nr["traces"][name])
        ax.plot(np.arange(tn.size) * nr["h"], (tn - tn[0]) * 1e3,
                c="#c0392b", lw=1.2, label="native, rigid dishes")
        tc = np.asarray(r["native_cargo"]["traces"][name])
        ax.plot(np.arange(tc.size) * r["native_cargo"]["h"], (tc - tc[0]) * 1e3,
                c="#d68910", lw=1.0, ls=":", label="native, all-cargo")
        tg = np.asarray(r["gt"]["traces"][name])
        ax.plot(np.arange(tg.size) * r["gt"]["dt"], (tg - tg[0]) * 1e3,
                c="#2c3e50", lw=1.0, ls="--", label="ground truth")
        ax.set_title(f"{name}  (d = {_dist(nr['xz'][name], drop):.2f} m)")
        ax.set_xlabel("t after release [s]")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("plate height change [mm]")
    axes[0].legend()
    fig.suptitle(f"near vs far plate, pot dropped at "
                 f"({drop[0]:+.2f}, {drop[1]:+.2f})")
    fig.tight_layout()
    fig.savefig(OUT / "near_far_traces.png", dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refine", type=int, default=1, choices=(0, 1, 2))
    ap.add_argument("--h-fine", type=float, default=5e-5)
    # 2.5 s, NOT the 0.4 s used by run_gt: the DCR-table GT support sags
    # under its own 74.5 kg self-weight and rings at f1 ~ 10 Hz with
    # zeta ~ alpha0/(2*omega) ~ 0.016 — the settle transient envelope is
    # e^{-(alpha0/2) t}, so 0.4 s leaves 67% of the ring alive (measured:
    # dishes tossed ~80 mm BEFORE the pot lands); 2.5 s leaves ~8%.
    ap.add_argument("--t-settle", type=float, default=2.5)
    ap.add_argument("--t-run", type=float, default=1.2)
    ap.add_argument("--quick", action="store_true",
                    help="smoke: h_fine 1e-4, settle 0.15 s, run 0.4 s, R0")
    ap.add_argument("--no-reuse-gt", action="store_true",
                    help="re-run the GT arm even if a recorded CSV exists")
    args = ap.parse_args()
    if args.quick:
        args.h_fine, args.t_settle, args.t_run = 1e-4, 0.15, 0.4
        args.refine = 0

    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for di, drop in enumerate(DROPS):
        tag = f"d{di}"
        rigid = _native_run(drop, args.t_run, NATIVE_RIGID)
        cargo = _native_run(drop, args.t_run, NATIVE_CARGO)
        gt = None if args.no_reuse_gt else _gt_from_csv(drop, tag)
        if gt is None:
            gt = _gt_run(drop, tag, refine=args.refine, h_fine=args.h_fine,
                         t_settle=args.t_settle, t_run=args.t_run)
        results.append(dict(drop_xz=drop, native_rigid=rigid,
                            native_cargo=cargo, gt=gt))
        mx = lambda d: max(v for k, v in d["dy_max"].items() if k != "pot") * 1e3
        print(f"drop {drop}: rigid {rigid['ms_per_step']:.1f} ms/step, "
              f"cargo {cargo['ms_per_step']:.1f} ms/step | "
              f"max jump rigid {mx(rigid):.2f} / cargo {mx(cargo):.2f} "
              f"/ gt {mx(gt):.2f} mm", flush=True)

    _plot_response(results)
    _plot_traces(results)
    slim = [dict(drop_xz=r["drop_xz"],
                 native_rigid=dict(dy_max=r["native_rigid"]["dy_max"],
                                   ms_per_step=r["native_rigid"]["ms_per_step"]),
                 native_cargo=dict(dy_max=r["native_cargo"]["dy_max"],
                                   ms_per_step=r["native_cargo"]["ms_per_step"]),
                 gt=dict(dy_max=r["gt"]["dy_max"], wall_s=r["gt"]["wall_s"]))
            for r in results]
    (OUT / "results.json").write_text(json.dumps(slim, indent=2))
    print(f"figures + results in {OUT}")


if __name__ == "__main__":
    main()
