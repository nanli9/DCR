"""Acceptance probe for the energy-conserving (implicit-midpoint) modal step.

Drops a 6 kg book on the soft reduced-modal shelf with 5 resting books and
compares four configs on the SAME scene:

    AVBD-BE, AVBD-symplectic, XPBD-BE, XPBD-symplectic

Reports, per config: peak / final resting-book KE, modal-surface ring count,
impactor bounce count, max book tilt & bounce height; and writes two figures:

  * docs/symplectic_modal/energy.png  — E_modal(t) ringing + decaying at the
    physical rate (symplectic) vs flatlining (BE), plus rigid KE.
  * docs/symplectic_modal/parity.png  — modal q(t) AVBD-symp vs XPBD-symp
    (the modal physics is now shared → should track closely).

Run:  .venv/bin/python scripts/probe_modal_symplectic.py
See:  prompts/symplectic_modal_integrator_prompt.md (acceptance 1–3).
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dcr.rigid.energy import rigid_kinetic_energy            # noqa: E402
from scenes.reduced_shelf import build_reduced_shelf         # noqa: E402

H = 1.0 / 120.0
N_FRAMES = 300                                              # 2.5 s


def _count_peaks(sig: np.ndarray, rel_thresh: float = 0.02) -> int:
    """Number of local maxima above rel_thresh * max(sig) (a 'ring' counter)."""
    sig = np.asarray(sig, dtype=np.float64)
    if sig.size < 3 or sig.max() <= 0.0:
        return 0
    thr = rel_thresh * sig.max()
    peaks = (sig[1:-1] > sig[:-2]) & (sig[1:-1] >= sig[2:]) & (sig[1:-1] > thr)
    return int(np.count_nonzero(peaks))


def _book_quats(world, idxs):
    return [np.asarray(world._descs[i].dcr_body.orientation, dtype=np.float64)
            for i in idxs]


def run(solver: str, symplectic: bool):
    handle = build_reduced_shelf(device="cpu", iterations=16, avbd_substeps=4,
                                 solver=solver)
    world = handle.world
    sol = world._solver
    sol._modal_symplectic = bool(symplectic)

    book_idxs = [i for i in handle.probe_indices if i != handle.impactor_idx]
    book_bodies = [world._descs[i].dcr_body for i in book_idxs]
    imp = world._descs[handle.impactor_idx].dcr_body

    # rest reference for the impactor (settled height) — track bounce vs first
    # contact minimum.
    q0_books = _book_quats(world, book_idxs)

    t = []
    book_ke = []
    modal_ke = []
    modal_pe = []
    rigid_ke = []
    imp_y = []
    q_dom = []                 # dominant (lowest) mode amplitude
    q_norm = []
    max_tilt = 0.0

    for f in range(N_FRAMES):
        world.step()
        bke = rigid_kinetic_energy(book_bodies)
        t.append(f * H)
        book_ke.append(bke)
        modal_ke.append(float(getattr(sol, "last_modal_KE", 0.0)))
        modal_pe.append(float(getattr(sol, "last_modal_PE", 0.0)))
        rigid_ke.append(rigid_kinetic_energy([d.dcr_body for d in world._descs]))
        imp_y.append(float(imp.position[1]))
        qv = sol._q if solver == "xpbd" else sol._q_modal_host
        qv = np.asarray(qv, dtype=np.float64)
        q_dom.append(float(qv[0]))
        q_norm.append(float(np.linalg.norm(qv)))
        # book tilt: angle from initial orientation
        for q_now, q_init in zip(_book_quats(world, book_idxs), q0_books):
            dot = abs(float(np.dot(q_now, q_init)))
            dot = min(1.0, dot)
            max_tilt = max(max_tilt, np.degrees(2.0 * np.arccos(dot)))

    book_ke = np.array(book_ke)
    modal_pe = np.array(modal_pe)
    modal_ke = np.array(modal_ke)
    imp_y = np.array(imp_y)
    # impact frame = first big drop in impactor y velocity (first local min of y)
    impact_f = int(np.argmin(imp_y[:max(2, N_FRAMES // 3)]))
    post = slice(impact_f, None)

    # surface ring signal: modal energy (KE+PE) oscillation after impact
    surf = modal_ke[post] + modal_pe[post]
    rings = _count_peaks(surf)
    bounces = _count_peaks(imp_y[post] - imp_y[post].min())
    bounce_mm = float((imp_y[post].max() - imp_y[post].min()) * 1000.0)

    return dict(
        solver=solver, symplectic=symplectic,
        peak_book_mJ=float(book_ke.max() * 1000.0),
        final_book_mJ=float(np.mean(book_ke[-20:]) * 1000.0),
        rings=rings, bounces=bounces, bounce_mm=bounce_mm,
        max_tilt_deg=float(max_tilt),
        peak_modal_mJ=float((modal_ke + modal_pe).max() * 1000.0),
        finite=bool(np.all(np.isfinite(book_ke)) and np.all(np.isfinite(modal_pe))),
        # series for plotting
        t=np.array(t), modal_E=modal_ke + modal_pe, rigid_ke=np.array(rigid_ke),
        q_dom=np.array(q_dom), q_norm=np.array(q_norm), book_ke=book_ke,
    )


def main():
    cfgs = [("avbd", False), ("avbd", True), ("xpbd", False), ("xpbd", True)]
    res = {}
    for solver, symp in cfgs:
        key = f"{solver}-{'symp' if symp else 'BE'}"
        print(f"running {key} ...", flush=True)
        res[key] = run(solver, symp)

    # ---- summary table ----
    print("\n=== resting-book probe (build_reduced_shelf cpu, iters=16, substeps=4) ===")
    hdr = (f"{'config':<12}{'peakKE mJ':>11}{'finalKE mJ':>12}{'rings':>7}"
           f"{'bounces':>9}{'bounce mm':>11}{'tilt deg':>10}{'modalE mJ':>11}"
           f"{'finite':>8}")
    print(hdr)
    print("-" * len(hdr))
    for key in res:
        r = res[key]
        print(f"{key:<12}{r['peak_book_mJ']:>11.1f}{r['final_book_mJ']:>12.1f}"
              f"{r['rings']:>7d}{r['bounces']:>9d}{r['bounce_mm']:>11.1f}"
              f"{r['max_tilt_deg']:>10.2f}{r['peak_modal_mJ']:>11.1f}"
              f"{str(r['finite']):>8}")

    # ---- figures ----
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "docs", "symplectic_modal")
    os.makedirs(outdir, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
        for key, c in [("avbd-BE", "tab:blue"), ("avbd-symp", "tab:red"),
                       ("xpbd-BE", "tab:cyan"), ("xpbd-symp", "tab:orange")]:
            r = res[key]
            ax[0].plot(r["t"], r["modal_E"] * 1000.0, label=key, color=c,
                       lw=1.2, ls="-" if "symp" in key else "--")
        ax[0].set_ylabel("modal energy [mJ]")
        ax[0].set_title("E_modal(t): symplectic rings & decays physically; BE flatlines")
        ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
        for key, c in [("avbd-symp", "tab:red"), ("xpbd-symp", "tab:orange")]:
            r = res[key]
            ax[1].plot(r["t"], r["book_ke"] * 1000.0, label=key, color=c, lw=1.2)
        for key, c in [("avbd-BE", "tab:blue"), ("xpbd-BE", "tab:cyan")]:
            r = res[key]
            ax[1].plot(r["t"], r["book_ke"] * 1000.0, label=key, color=c, lw=1.0,
                       ls="--")
        ax[1].set_ylabel("resting-book KE [mJ]"); ax[1].set_xlabel("t [s]")
        ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "energy.png"), dpi=110)
        print(f"\nwrote {os.path.join(outdir, 'energy.png')}")

        fig2, ax2 = plt.subplots(figsize=(9, 4))
        ax2.plot(res["avbd-symp"]["t"], res["avbd-symp"]["q_dom"],
                 label="AVBD-symp q[0]", color="tab:red", lw=1.3)
        ax2.plot(res["xpbd-symp"]["t"], res["xpbd-symp"]["q_dom"],
                 label="XPBD-symp q[0]", color="tab:orange", lw=1.0, ls="--")
        ax2.set_title("AVBD↔XPBD modal parity (shared symplectic stepper)")
        ax2.set_xlabel("t [s]"); ax2.set_ylabel("dominant mode q[0]")
        ax2.legend(); ax2.grid(alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(os.path.join(outdir, "parity.png"), dpi=110)
        print(f"wrote {os.path.join(outdir, 'parity.png')}")
    except Exception as e:  # pragma: no cover
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    main()
