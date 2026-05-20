#!/usr/bin/env python3
"""Investigation: lateral drift in symmetric vertical drop.

One box falls vertically onto a static horizontal plane.
Zero initial horizontal velocity, zero spin.
Ideal physics: no lateral motion.

Ablation tests to identify the source of any observed lateral drift.
"""
from __future__ import annotations

import copy
import numpy as np
from dataclasses import dataclass

from dcr.rigid.body import RigidBody, Shape, ShapeType
from dcr.rigid.collision import detect_contacts, Contact
from dcr.rigid.solver import ConstraintSolver, _pick_friction_dirs, build_contact_jacobian_row


# ---------------------------------------------------------------------------
# Minimal scene: one box falling onto a plane
# ---------------------------------------------------------------------------

def make_box(mass, hx, hy, hz, position, restitution=0.3, friction=0.5):
    shape = Shape(kind=ShapeType.BOX, half_extents=np.array([hx, hy, hz]))
    body = RigidBody(mass=mass, shape=shape)
    body.position = np.array(position, dtype=np.float64)
    body.restitution = restitution
    body.friction = friction
    return body


def make_plane(normal=(0,1,0), point=(0,0,0), friction=0.5):
    n = np.array(normal, dtype=np.float64)
    n /= np.linalg.norm(n)
    shape = Shape(kind=ShapeType.PLANE, half_extents=n.copy())
    body = RigidBody(mass=0.0, shape=shape)
    body.position = np.array(point, dtype=np.float64)
    body.is_static = True
    body.friction = friction
    return body


@dataclass
class StepLog:
    frame: int
    x: float
    y: float
    vx: float
    vy: float
    wx: float  # angular vel x
    wy: float
    wz: float
    n_contacts: int
    lam_N: list[float]  # normal impulses per contact
    lam_T1: list[float]  # friction1 impulses
    lam_T2: list[float]  # friction2 impulses
    contact_points_x: list[float]
    tangent_rel_vx: list[float]  # tangential relative velocity before solve


def run_single_drop(
    h=1e-3,
    n_steps=800,
    pgs_iterations=80,
    erp=0.2,
    friction=0.5,
    restitution=0.3,
    warm_start=True,
    warm_start_friction=True,  # if False, zero-init friction rows only
    force_normal=False,  # force contact normal to exact (0,1,0)
    rotate_tangent=0.0,  # rotation angle (radians) for tangent basis
    label="baseline",
) -> list[StepLog]:
    """Run a single box drop and return per-step logs."""
    gravity = np.array([0.0, -9.81, 0.0])
    plane = make_plane(friction=friction)
    box = make_box(mass=1.0, hx=0.04, hy=0.04, hz=0.04,
                   position=(0.25, 0.5, 0.0),
                   restitution=restitution, friction=friction)
    bodies = [box, plane]  # box=0, plane=1

    solver = ConstraintSolver(h=h, cfm=1e-6, erp=erp, pgs_iterations=pgs_iterations)

    # Monkey-patch for ablation controls
    original_pick_friction = _pick_friction_dirs
    if rotate_tangent != 0.0:
        def rotated_pick(normal):
            t1, t2 = original_pick_friction(normal)
            c, s = np.cos(rotate_tangent), np.sin(rotate_tangent)
            t1_new = c * t1 + s * t2
            t2_new = -s * t1 + c * t2
            return t1_new, t2_new
        import dcr.rigid.solver as solver_mod
        solver_mod._pick_friction_dirs = rotated_pick

    prev_contacts = []
    logs = []

    for frame in range(n_steps):
        # Gravity
        for body in bodies:
            body.force = np.zeros(6)
            if not body.is_static:
                body.force[0:3] = body.mass * gravity

        # Detect contacts
        contacts = detect_contacts(bodies, prev_contacts)

        if force_normal:
            for c in contacts:
                c.normal = np.array([0.0, 1.0, 0.0])

        # --- Pre-solve logging: tangential relative velocity ---
        tang_rel_vx = []
        for c in contacts:
            t1, t2 = (rotated_pick(c.normal) if rotate_tangent != 0.0
                       else original_pick_friction(c.normal))
            # Relative velocity at contact point
            v_a = box.velocity
            r_a = c.point - box.position
            v_contact_a = v_a[:3] + np.cross(v_a[3:], r_a)
            # Plane is static, v_b = 0
            v_rel = v_contact_a  # relative to plane
            v_tang_t2 = np.dot(v_rel, t2)  # t2 = (-1,0,0), so this is -vx
            tang_rel_vx.append(float(v_tang_t2))

        # Warm-start control
        if not warm_start:
            solver._prev_lambda = {}
        elif not warm_start_friction:
            # Zero out friction rows in warm-start cache
            new_cache = {}
            for key, val in solver._prev_lambda.items():
                if key[-1] == 0:  # normal row
                    new_cache[key] = val
                # skip friction rows (row_type 1 and 2)
            solver._prev_lambda = new_cache

        # Solve
        lam = solver.solve(bodies, contacts)

        # Extract per-contact impulses
        lam_N, lam_T1, lam_T2 = [], [], []
        cp_x = []
        for ci in range(len(contacts)):
            if 3*ci+2 < len(lam):
                lam_N.append(float(lam[3*ci]))
                lam_T1.append(float(lam[3*ci+1]))
                lam_T2.append(float(lam[3*ci+2]))
            cp_x.append(float(contacts[ci].point[0]))

        logs.append(StepLog(
            frame=frame,
            x=float(box.position[0]),
            y=float(box.position[1]),
            vx=float(box.velocity[0]),
            vy=float(box.velocity[1]),
            wx=float(box.velocity[3]),
            wy=float(box.velocity[4]),
            wz=float(box.velocity[5]),
            n_contacts=len(contacts),
            lam_N=lam_N,
            lam_T1=lam_T1,
            lam_T2=lam_T2,
            contact_points_x=cp_x,
            tangent_rel_vx=tang_rel_vx,
        ))

        # Integrate positions
        for body in bodies:
            if body.is_static:
                continue
            body.position += h * body.velocity[:3]
            from dcr.rigid.body import quat_integrate
            body.orientation = quat_integrate(body.orientation, body.velocity[3:6], h)

        prev_contacts = contacts

    # Restore original function
    if rotate_tangent != 0.0:
        import dcr.rigid.solver as solver_mod
        solver_mod._pick_friction_dirs = original_pick_friction

    return logs


def analyze_logs(logs: list[StepLog], label: str) -> dict:
    """Extract summary statistics from a run."""
    x_vals = [l.x for l in logs]
    vx_vals = [l.vx for l in logs]
    x0 = x_vals[0]
    max_dx = max(abs(x - x0) for x in x_vals)
    max_vx = max(abs(vx) for vx in vx_vals)

    # Find first frame with contact
    first_contact = next((l.frame for l in logs if l.n_contacts > 0), None)

    # Check if there's a reversal: x increases then decreases (or vice versa)
    has_drift = max_dx > 1e-6
    has_reversal = False
    if has_drift:
        # Find peak displacement
        peak_frame = max(range(len(x_vals)), key=lambda i: abs(x_vals[i] - x0))
        peak_dx = x_vals[peak_frame] - x0
        # Check if displacement reverses after peak
        post_peak = x_vals[peak_frame:]
        if peak_dx > 0:
            has_reversal = any(x - x0 < peak_dx * 0.5 for x in post_peak[-100:])
        elif peak_dx < 0:
            has_reversal = any(x - x0 > peak_dx * 0.5 for x in post_peak[-100:])

    # Check pre-contact tangential velocity
    pre_contact_vx = 0.0
    if first_contact is not None and first_contact > 0:
        pre_contact_vx = logs[first_contact - 1].vx

    # Sum of friction impulses
    total_lam_T2 = sum(sum(l.lam_T2) for l in logs)
    max_lam_T2 = max((max(abs(v) for v in l.lam_T2) if l.lam_T2 else 0) for l in logs)

    # Max angular velocity
    max_wz = max(abs(l.wz) for l in logs)
    max_wx = max(abs(l.wx) for l in logs)

    return {
        "label": label,
        "has_drift": has_drift,
        "has_reversal": has_reversal,
        "max_dx_mm": max_dx * 1000,
        "max_vx_mm_s": max_vx * 1000,
        "pre_contact_vx": pre_contact_vx,
        "total_lam_T2": total_lam_T2,
        "max_lam_T2": max_lam_T2,
        "max_wz": max_wz,
        "max_wx": max_wx,
        "first_contact": first_contact,
    }


def print_detailed_log(logs, label, frame_start=300, frame_end=400):
    """Print detailed per-frame log for a range."""
    print(f"\n{'='*80}")
    print(f"Detailed log: {label}  (frames {frame_start}-{frame_end})")
    print(f"{'='*80}")
    print(f"{'frm':>4} {'x':>10} {'vx':>10} {'vy':>10} {'wz':>10} "
          f"{'#c':>3} {'lN[0]':>10} {'lT2[0]':>10} {'trel_vx':>10}")
    for l in logs:
        if l.frame < frame_start or l.frame > frame_end:
            continue
        lN0 = l.lam_N[0] if l.lam_N else 0
        lT2_0 = l.lam_T2[0] if l.lam_T2 else 0
        trel = l.tangent_rel_vx[0] if l.tangent_rel_vx else 0
        print(f"{l.frame:4d} {l.x:10.6f} {l.vx:10.6f} {l.vy:10.6f} {l.wz:10.6f} "
              f"{l.n_contacts:3d} {lN0:10.6f} {lT2_0:10.6f} {trel:10.6f}")


def main():
    print("="*80)
    print("INVESTIGATION: Lateral drift in symmetric vertical drop")
    print("="*80)
    print()

    # --- Task 2: Detailed baseline logging ---
    print("Running baseline with detailed logging...")
    baseline_logs = run_single_drop(label="baseline")
    print_detailed_log(baseline_logs, "baseline", 320, 370)

    # Check pre-contact state
    first_c = next((l.frame for l in baseline_logs if l.n_contacts > 0), None)
    if first_c:
        l_pre = baseline_logs[first_c - 1]
        l_at = baseline_logs[first_c]
        print(f"\n--- Task 3: Pre-contact verification ---")
        print(f"Frame before first contact ({first_c-1}): vx={l_pre.vx:.2e}, wz={l_pre.wz:.2e}")
        print(f"Frame of first contact ({first_c}): vx={l_at.vx:.2e}, n_contacts={l_at.n_contacts}")
        print(f"  lam_T1 = {l_at.lam_T1}")
        print(f"  lam_T2 = {l_at.lam_T2}")
        print(f"  tangent_rel_vx = {l_at.tangent_rel_vx}")
        if abs(l_pre.vx) < 1e-12 and any(abs(t) > 1e-10 for t in l_at.lam_T2):
            print("  ** ARTIFACT DETECTED: nonzero friction impulse with zero tangential velocity **")

    # --- Task 4: Ablation tests ---
    results = []

    print("\n--- Running ablation tests ---")

    # A. mu=0 (no friction)
    print("  [A] mu=0...")
    logs_a = run_single_drop(friction=0.0, label="A: mu=0")
    results.append(analyze_logs(logs_a, "A: mu=0"))

    # B. No friction warm-start
    print("  [B] No friction warm-start...")
    logs_b = run_single_drop(warm_start_friction=False, label="B: no friction WS")
    results.append(analyze_logs(logs_b, "B: no friction WS"))

    # C. No warm-start at all
    print("  [C] No warm-start...")
    logs_c = run_single_drop(warm_start=False, label="C: no WS")
    results.append(analyze_logs(logs_c, "C: no WS"))

    # D. PGS iteration sweep
    for iters in [80, 160, 320, 640]:
        print(f"  [D] PGS iterations={iters}...")
        logs_d = run_single_drop(pgs_iterations=iters, label=f"D: PGS={iters}")
        results.append(analyze_logs(logs_d, f"D: PGS={iters}"))

    # E. Rotated tangent basis (45 degrees)
    print("  [E] Tangent rotated 45 deg...")
    logs_e = run_single_drop(rotate_tangent=np.pi/4, label="E: tangent+45deg")
    results.append(analyze_logs(logs_e, "E: tangent+45deg"))

    # E2. Rotated tangent basis (90 degrees) — swaps t1 and t2
    print("  [E2] Tangent rotated 90 deg...")
    logs_e2 = run_single_drop(rotate_tangent=np.pi/2, label="E: tangent+90deg")
    results.append(analyze_logs(logs_e2, "E: tangent+90deg"))

    # G. No Baumgarte (erp=0)
    print("  [G] erp=0 (no Baumgarte)...")
    logs_g = run_single_drop(erp=0.0, label="G: erp=0")
    results.append(analyze_logs(logs_g, "G: erp=0"))

    # H. Force contact normal to exact (0,1,0)
    print("  [H] Forced normal (0,1,0)...")
    logs_h = run_single_drop(force_normal=True, label="H: forced normal")
    results.append(analyze_logs(logs_h, "H: forced normal"))

    # Baseline (for the table)
    results.insert(0, analyze_logs(baseline_logs, "Baseline (PGS=80)"))

    # --- Task 5: Diagnosis table ---
    print("\n" + "="*80)
    print("DIAGNOSIS TABLE")
    print("="*80)
    print(f"{'Test':<25} {'Drift?':<7} {'Rev?':<6} {'max|dx| mm':<12} "
          f"{'max|vx| mm/s':<14} {'max|lT2|':<12} {'max|wz|':<10}")
    print("-"*86)
    for r in results:
        print(f"{r['label']:<25} {'YES' if r['has_drift'] else 'no':<7} "
              f"{'YES' if r['has_reversal'] else 'no':<6} "
              f"{r['max_dx_mm']:<12.4f} {r['max_vx_mm_s']:<14.4f} "
              f"{r['max_lam_T2']:<12.6f} {r['max_wz']:<10.6f}")

    # --- Task 6: Final conclusion ---
    r_base = results[0]
    r_mu0 = results[1]
    r_no_ws = results[3]  # C: no WS
    r_pgs640 = results[7]  # D: PGS=640
    r_rot45 = results[8]   # E: tangent+45deg
    r_rot90 = results[9]   # E: tangent+90deg
    r_erp0 = results[10]
    r_forced = results[11]

    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    print(f"\n1. mu=0 eliminates drift: {r_mu0['max_dx_mm'] < 0.001}")
    print(f"   → Drift is friction-mediated: {'YES' if r_mu0['max_dx_mm'] < 0.001 else 'NO'}")

    print(f"\n2. Warm-start effect:")
    print(f"   Baseline max|dx|: {r_base['max_dx_mm']:.4f} mm")
    print(f"   No WS max|dx|:    {r_no_ws['max_dx_mm']:.4f} mm")
    ws_ratio = r_no_ws['max_dx_mm'] / max(r_base['max_dx_mm'], 1e-12)
    print(f"   Ratio: {ws_ratio:.2f}x")

    print(f"\n3. PGS convergence effect:")
    for r in results:
        if r['label'].startswith('D:'):
            print(f"   {r['label']}: max|dx| = {r['max_dx_mm']:.4f} mm")

    print(f"\n4. Tangent basis rotation effect:")
    print(f"   Baseline:    max|dx| = {r_base['max_dx_mm']:.4f} mm")
    print(f"   +45 deg:     max|dx| = {r_rot45['max_dx_mm']:.4f} mm")
    print(f"   +90 deg:     max|dx| = {r_rot90['max_dx_mm']:.4f} mm")

    print(f"\n5. Baumgarte (ERP) effect:")
    print(f"   Baseline (erp=0.2): max|dx| = {r_base['max_dx_mm']:.4f} mm")
    print(f"   erp=0:              max|dx| = {r_erp0['max_dx_mm']:.4f} mm")

    print(f"\n6. Forced normal effect:")
    print(f"   Baseline:        max|dx| = {r_base['max_dx_mm']:.4f} mm")
    print(f"   Forced (0,1,0):  max|dx| = {r_forced['max_dx_mm']:.4f} mm")

    # Final conclusion
    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)


if __name__ == "__main__":
    main()
