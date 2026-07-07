"""Per-scene tet-refinement convergence table (benchmark plan §3 acceptance).

    python -m benchmarks.fem_gt.refine_report [--out-dir benchmarks/fem_gt/out]

Reads the rung manifests written by `run_gt.py --refine {0,1,2}`
(`<scene>_gt.json`, `<scene>_gt_r1.json`, `<scene>_gt_r2.json`) and reports,
per scene: support nodes/tets, peak mid-span |u_y|, dominant ring frequency,
and the R(n)->R(n+1) change in both. Acceptance: BOTH change < 2 % — the
first rung whose step TO it moved < 2 % is the converged rung.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCENES = ("truck", "ledge", "shelf", "dinner", "cargo")
TOL = 0.02


def _load(out_dir: Path, scene: str, rung: int) -> dict | None:
    suffix = f"_r{rung}" if rung else ""
    p = out_dir / f"{scene}_gt{suffix}.json"
    if not p.exists():
        return None
    m = json.loads(p.read_text())
    if "peak_mid_uy" not in m:      # pre-ladder manifest (no metrics recorded)
        return None
    return m


def _pct(new: float, old: float) -> float:
    return abs(new - old) / max(abs(old), 1e-30) * 100.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).resolve().parent / "out")
    args = ap.parse_args()

    hdr = (f"{'scene':<8}{'rung':<6}{'support mesh':<16}{'nodes':>7}"
           f"{'peak|u_y| mm':>14}{'d%':>8}{'ring Hz':>10}{'d%':>8}"
           f"{'wall s':>8}  verdict")
    print(hdr)
    print("-" * len(hdr))
    for scene in SCENES:
        prev = None
        converged = None
        for rung in (0, 1, 2):
            m = _load(args.out_dir, scene, rung)
            if m is None:
                continue
            res = m["support"]["resolution"]
            nodes = m["bodies"]["support"]["n_nodes"]
            peak, ring = m["peak_mid_uy"], m["ring_hz"]
            if prev is None:
                d_peak = d_ring = None
            else:
                d_peak = _pct(peak, prev[0])
                d_ring = _pct(ring, prev[1])
                if converged is None and d_peak < TOL * 100 \
                        and d_ring < TOL * 100:
                    converged = rung
            verdict = ""
            if d_peak is not None:
                ok = d_peak < TOL * 100 and d_ring < TOL * 100
                verdict = "CONVERGED" if ok else "not yet"
            print(f"{scene:<8}R{rung:<5}"
                  f"{'x'.join(str(n) for n in res):<16}{nodes:>7}"
                  f"{peak * 1e3:>14.4f}"
                  f"{'' if d_peak is None else f'{d_peak:.1f}':>8}"
                  f"{ring:>10.1f}"
                  f"{'' if d_ring is None else f'{d_ring:.1f}':>8}"
                  f"{m.get('wall_s', float('nan')):>8.0f}  {verdict}")
            prev = (peak, ring)
        if converged is not None:
            print(f"{'':8}-> {scene}: converged at R{converged} "
                  f"(step to it moved both metrics < {TOL:.0%})")
        print()


if __name__ == "__main__":
    main()
