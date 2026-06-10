"""Per-kernel GPU profiler for the device-resident XPBD coupler.

Three views (adapted from scripts/_diag_warp_kernel_profile.py):
  1. step wall-clock (graph-ON).
  2. GPU activity by filter (graph replay vs memcpy vs memset vs uncaptured).
  3. Per-kernel GPU ms (graph-OFF via solver._graph_disabled).
"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import warp as wp
wp.init()
import time
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd

SUB, ITERS, H = 8, 4, 1.0 / 120.0
COUPLER = ("k_eval_and_gate", "k_count_active", "k_rowforce", "k_hq", "k_g",
           "k_body", "k_body_cross", "k_hmb", "k_schur", "k_rhs", "k_eps_solve",
           "k_backsub", "k_reduce_diag", "k_body_fdef", "k_fq_momentum",
           "k_iir", "k_modal_energy", "k_passivity", "k_sync_total",
           "k_anchor")


def fname(f):
    return {wp.TIMING_KERNEL: "kernel", wp.TIMING_KERNEL_BUILTIN: "builtin",
            wp.TIMING_GRAPH: "graph", wp.TIMING_MEMCPY: "memcpy",
            wp.TIMING_MEMSET: "memset"}.get(f, f"f{f}")


def build():
    h = build_reduced_shelf(h=H, device="cuda:0", iterations=ITERS,
                            avbd_substeps=SUB)
    h.rs.reset_state()
    return mirror_to_xpbd(h, h=H, substeps=SUB, iterations=ITERS,
                          device="cuda:0")


xh = build()
w = xh.world
solver = w.solver
for _ in range(40):
    w.step()
wp.synchronize()
print(f"device_resident={xh.coupler.device_resident} "
      f"hooks_device_resident={solver.hooks_device_resident} "
      f"graph_captured={solver._graph is not None}")

# (1) wall-clock
N = 200
t0 = time.perf_counter()
for _ in range(N):
    w.step()
wp.synchronize()
print(f"\n(1) step wall-clock = {(time.perf_counter()-t0)/N*1e3:.3f} ms/step")

# (2) GPU activity by filter (graph-ON)
PF = 60
wp.synchronize_device(solver.device)
wp.timing_begin(cuda_filter=wp.TIMING_ALL, synchronize=True)
for _ in range(PF):
    w.step()
res = wp.timing_end(synchronize=True)
by_filter = defaultdict(float)
by_name = defaultdict(lambda: [0.0, 0])
for r in res:
    by_filter[fname(r.filter)] += r.elapsed
    by_name[(fname(r.filter), r.name)][0] += r.elapsed
    by_name[(fname(r.filter), r.name)][1] += 1
print(f"\n(2) GPU activity (graph-ON, {PF} steps), per-step ms:")
tot = sum(by_filter.values())
for fn in sorted(by_filter, key=lambda k: -by_filter[k]):
    print(f"  {fn:8s} {by_filter[fn]/PF:8.4f}  ({100*by_filter[fn]/max(tot,1e-9):5.1f}%)")
print(f"  {'TOTAL':8s} {tot/PF:8.4f}")
print("  top activities:")
for (fn, nm), (ms, c) in sorted(by_name.items(), key=lambda kv: -kv[1][0])[:8]:
    print(f"    [{fn:6s}] {nm[:44]:44s} {ms/PF:7.4f} x{c/PF:.0f}")

# (3) per-kernel graph-OFF
solver._graph_disabled = True
solver._graph = None
for _ in range(3):
    w.step()
wp.timing_begin(cuda_filter=wp.TIMING_KERNEL, synchronize=True)
for _ in range(PF):
    w.step()
res = wp.timing_end(synchronize=True)
solver._graph_disabled = False
solver._graph = None
by_k = defaultdict(lambda: [0.0, 0])
for r in res:
    nm = r.name.replace("forward kernel ", "").replace("_cuda_kernel", "")
    by_k[nm][0] += r.elapsed
    by_k[nm][1] += 1
cpl = sum(ms for nm, (ms, _) in by_k.items() if any(k in nm for k in COUPLER))
core = sum(ms for nm, (ms, _) in by_k.items()
           if not any(k in nm for k in COUPLER))
rows = sorted(by_k.items(), key=lambda kv: -kv[1][0])
nl = sum(c for _, (_, c) in by_k.items())
print(f"\n(3) per-kernel GPU (graph-OFF, {PF} steps):")
print(f"  total kernel/step={(cpl+core)/PF:.3f} ms  "
      f"coupler={cpl/PF:.3f} ({100*cpl/max(cpl+core,1e-9):.0f}%)  "
      f"rigid/core={core/PF:.3f} ({100*core/max(cpl+core,1e-9):.0f}%)")
print(f"  launches/step={nl/PF:.0f}")
print(f"  {'kernel':32s} {'ms/step':>9} {'launch/step':>11} {'tag':>5}")
for nm, (ms, c) in rows[:26]:
    tag = "cpl" if any(k in nm for k in COUPLER) else "core"
    print(f"  {nm[:32]:32s} {ms/PF:9.4f} {c/PF:11.1f} {tag:>5}")
