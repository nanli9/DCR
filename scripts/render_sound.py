"""Stage E6 demo — run the dinner scene headless, log the native contact
excitation, and render the impact soundtrack offline (band-split modal bank,
ledger-capped; see CLAUDE.md E6 scope and dcr/sound/*).

    python scripts/render_sound.py --seconds 6 --out exports/sound/dinner.wav

Produces: WAV (+ spectrogram PNG alongside), console diagnostics including the
E6 inequality check, optional raw log npz (--save-log) and MP4 mux (--mux).
Synthesis is NOT a contribution — this is the render demo of the E6 bound.
For the LIVE version, see `run_native_scenes_viser.py --scene dinner --sound`.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dcr.sound import (                                    # noqa: E402
    Voice,
    extract_impulses,
    filter_settle,
    render_soundtrack,
    write_wav,
)
from dcr.sound.logger import attach_sound_logger           # noqa: E402
from scripts.sound_voices import build_dinner_audio        # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--h", type=float, default=1.0 / 120.0)
    ap.add_argument("--substeps", type=int, default=2)
    ap.add_argument("--iterations", type=int, default=6)
    ap.add_argument("--device", default="cpu",
                    help="sim device; cpu records via the substep hook, "
                    "cuda:* via the device staging ring (graph-capture-safe, "
                    "drained per frame — sound_stage_kernels.py)")
    ap.add_argument("--drop-xz", type=float, nargs=2, default=(0.0, 0.0))
    ap.add_argument("--drop-height", type=float, default=0.5)
    ap.add_argument("--support-basis", choices=("debug", "fem"),
                    default="debug", help="sim-band basis (audio is always "
                    "true-FEM; the bank is open-loop either way)")
    ap.add_argument("--fs", type=float, default=44100.0)
    ap.add_argument("--eta-audio", type=float, default=1.0)
    ap.add_argument("--tail", type=float, default=1.5)
    ap.add_argument("--tau-ref", type=float, default=8.0e-4)
    ap.add_argument("--j-floor", type=float, default=1.0e-3,
                    help="impulse floor [N·s] for event extraction "
                    "(events.extract_impulses docstring)")
    ap.add_argument("--settle-quiet", type=float, default=0.15,
                    help="settle muting: play nothing until this long an "
                    "event-free window has passed (kills the t≈0 placement-"
                    "gap clinks; 0 disables — events.settle_arm_index)")
    ap.add_argument("--settle-max", type=float, default=1.5,
                    help="settle muting deadline [s]")
    ap.add_argument("--settle-prominence", type=float, default=5.0,
                    help="arm early on an event this many × louder than the "
                    "loudest muted clink (impacts inside the settle window "
                    "break through; 0 disables)")
    ap.add_argument("--table-modes", type=int, default=64)
    ap.add_argument("--table-fmin", type=float, default=150.0,
                    help="band-split crossover [Hz] for the table voice")
    ap.add_argument("--table-gain", type=float, default=1.0)
    ap.add_argument("--body-gain", type=float, default=1.0)
    ap.add_argument("--zeta-contact", type=float, default=0.08,
                    help="choked modal ζ for body voices while they carry "
                    "support load (contact-damping choke, render.py "
                    "DEVIATION; 0 disables)")
    ap.add_argument("--noise", type=float, default=0.35,
                    help="contact-noise transient level: noise:modal "
                    "loudness ratio, charged to the E6 ledger as "
                    "noise²·e_kick (shaping.py DEVIATION; 0 disables)")
    ap.add_argument("--out", default="exports/sound/dinner_impact.wav")
    ap.add_argument("--basis-cache", default="data/audio_basis")
    ap.add_argument("--rebuild-basis", action="store_true")
    ap.add_argument("--save-log", default=None,
                    help="also save the raw SoundLog npz here")
    ap.add_argument("--mux", default=None,
                    help="existing MP4 to mux the WAV onto (needs ffmpeg)")
    args = ap.parse_args()

    from scenes.reduced_dinner_table import build_reduced_dinner_table

    # ---- 1. Scene + logger + headless run --------------------------------
    source = "ring" if args.device.startswith("cuda") else "hook"
    print(f"[scene] dinner table, drop at {tuple(args.drop_xz)}, "
          f"h=1/{round(1/args.h)}, substeps={args.substeps}, "
          f"iters={args.iterations}, sim basis={args.support_basis}, "
          f"device={args.device} ({source} tap)")
    handle = build_reduced_dinner_table(
        h=args.h, device=args.device, iterations=args.iterations,
        avbd_substeps=args.substeps, pot_drop_xz=tuple(args.drop_xz),
        pot_drop_height=args.drop_height, solver="avbd",
        support_basis=args.support_basis)
    world = handle.world
    logger = attach_sound_logger(world, source=source)

    n_steps = int(round(args.seconds / args.h))
    t0 = time.perf_counter()
    for i in range(n_steps):
        world.step()
        if source == "ring":
            logger.drain()
        if (i + 1) % int(round(1.0 / args.h)) == 0:
            print(f"[run] t={((i + 1) * args.h):.1f}s "
                  f"({time.perf_counter() - t0:.1f}s wall)")
    log = logger.finalize()
    logger.detach()
    print(f"[log] {log.n_substeps} substeps, {log.F.shape[1]} support rows, "
          f"peak F={float(log.F.max()):.1f} N")
    if args.save_log:
        os.makedirs(os.path.dirname(args.save_log) or ".", exist_ok=True)
        log.to_npz(args.save_log)
        print(f"[log] saved -> {args.save_log}")

    # ---- 2. Audio bases (cached, shared with the live demo) ---------------
    # Table params = the scene-builder defaults used in the build call above.
    da = build_dinner_audio(
        handle, world, fs=args.fs,
        table_thickness=0.04, youngs=1.1e9, poisson=0.30, density=770.0,
        table_modes=args.table_modes, table_fmin=args.table_fmin,
        cache_dir=args.basis_cache, rebuild=args.rebuild_basis)
    body_voices = {idx: Voice(name=da.body_names[idx], basis=basis,
                              gain=args.body_gain)
                   for idx, basis in da.body_bases.items()}

    # ---- 3. Render (E6-capped) --------------------------------------------
    events = extract_impulses(log, j_floor=args.j_floor)
    print(f"[events] {events.n_events} impact events above "
          f"{args.j_floor:g} N·s "
          f"(max J={events.impulse.max() if events.n_events else 0:.3g} N·s)")
    if args.settle_quiet > 0.0:
        events, n_muted = filter_settle(events, quiet_gap=args.settle_quiet,
                                        mute_max=args.settle_max,
                                        prominence=args.settle_prominence)
        if n_muted:
            t0_play = events.t[0] if events.n_events else float("inf")
            print(f"[events] settle-muted {n_muted} placement/sag clinks; "
                  f"first played event at t={t0_play:.3f}s")
    audio, diag = render_soundtrack(
        log, support_voice=(Voice(name="table", basis=da.support_basis,
                                  gain=args.table_gain)
                            if da.support_basis is not None else None),
        body_voices=body_voices, fs=args.fs, eta_audio=args.eta_audio,
        tail=args.tail, tau_ref=args.tau_ref, events=events,
        tau_ref_per_body=da.tau_ref_per_body,
        zeta_contact=(args.zeta_contact if args.zeta_contact > 0 else None),
        noise_frac=args.noise)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_wav(args.out, audio, args.fs)
    print(f"[wav] {args.out}  ({diag['n_samples'] / args.fs:.1f}s)")
    print(f"[E6] events={diag['n_events']} capped={diag['n_capped']} "
          f"min_gamma={diag['min_gamma']:.3f} "
          f"choke_toggles={diag['n_choke_toggles']} "
          f"noise_bursts={diag['n_noise_bursts']}")
    print(f"[E6] kick energy {diag['cum_kick_energy_J']:.4g} J  <=  "
          f"eta_audio * rigid loss {args.eta_audio} * "
          f"{diag['cum_rigid_loss_J']:.4g} J : "
          f"{'HOLDS' if diag['e6_holds'] else 'VIOLATED'}")
    assert diag["e6_holds"], "E6 audio inequality violated — investigate"

    # Spectrogram PNG next to the WAV.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.specgram(audio, NFFT=2048, Fs=args.fs, noverlap=1536,
                    cmap="magma", vmin=-140)
        ax.set_xlabel("time [s]"); ax.set_ylabel("freq [Hz]")
        ax.set_ylim(0, 8000)
        ax.set_title("dinner impact render (E6-capped)")
        png = os.path.splitext(args.out)[0] + "_spec.png"
        fig.tight_layout(); fig.savefig(png, dpi=120); plt.close(fig)
        print(f"[png] {png}")
    except Exception as e:                                  # pragma: no cover
        print(f"[png] spectrogram skipped: {e}")

    if args.mux:
        out_mp4 = os.path.splitext(args.out)[0] + "_muxed.mp4"
        cmd = ["ffmpeg", "-y", "-i", args.mux, "-i", args.out,
               "-c:v", "copy", "-c:a", "aac", "-shortest", out_mp4]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"[mux] {out_mp4}")
        except Exception as e:                              # pragma: no cover
            print(f"[mux] failed ({e}); WAV is still at {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
