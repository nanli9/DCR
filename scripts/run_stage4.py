"""Stage 4 visualization: table vibrating after an impulse.

Excites all modes with a unit impulse and plays back the IIR response
as an animated polyscope surface, showing the decaying vibration.
Use left/right arrow or the slider to scrub through time.
"""
import numpy as np
import polyscope as ps

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis, IIRModalStepper


def main() -> None:
    # Paper table with mild Rayleigh damping.
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=12, ny=8, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    tol = 1e-8
    x_min, x_max = mesh.vertices[:, 0].min(), mesh.vertices[:, 0].max()
    z_min, z_max = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    on_xmin = np.abs(mesh.vertices[:, 0] - x_min) < tol
    on_xmax = np.abs(mesh.vertices[:, 0] - x_max) < tol
    on_zmin = np.abs(mesh.vertices[:, 2] - z_min) < tol
    on_zmax = np.abs(mesh.vertices[:, 2] - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)

    model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                     alpha0=2.0, alpha1=1e-5)
    ma = ModalAnalysis(fem=model, num_modes=10)
    stepper = IIRModalStepper(modal=ma)

    print("=" * 60)
    print("Stage 4 — IIR Modal Stepper Verification")
    print("=" * 60)
    print(f"Mesh: {mesh.num_vertices} verts, {mesh.num_tets} tets")
    print(f"Fixed corner nodes: {fixed.size}")
    print(f"Free DOFs: {len(model.free_dofs)}")
    print()

    # --- IIR coefficients summary ---
    print("IIR Stepper Parameters:")
    print(f"  Sub-step T = {stepper.T:.4e} s")
    print(f"  ω_max = {ma.frequencies[-1]:.2f} rad/s  →  Nyquist: "
          f"{(2*np.pi/ma.frequencies[-1]) / stepper.T:.1f} samples/period")
    print()

    print("Per-mode coefficients:")
    print(f"  {'Mode':>4}  {'ω (rad/s)':>10}  {'f (Hz)':>8}  {'ξ':>10}  "
          f"{'a1':>12}  {'a2':>12}  {'ar':>12}")
    for j in range(ma.num_modes):
        print(f"  {j:4d}  {ma.frequencies[j]:10.2f}  {ma.frequencies[j]/(2*np.pi):8.2f}  "
              f"{stepper.xi[j]:10.6f}  {stepper.a1[j]:12.8f}  {stepper.a2[j]:12.8f}  "
              f"{stepper.ar[j]:12.8e}")
    print()

    # --- Impulse response ---
    # Excite all modes with a unit impulse (simulates a hit in the center).
    r = np.ones(ma.num_modes, dtype=np.float64)
    n_steps = 2000
    q_hist = stepper.step_n(n_steps, r=r)

    # Log peak response and decay for each mode.
    print("Impulse response (unit impulse on all modes):")
    print(f"  {'Mode':>4}  {'Peak |q|':>12}  {'Peak step':>10}  "
          f"{'|q| at end':>12}  {'Decay ratio':>12}")
    for j in range(ma.num_modes):
        q_j = q_hist[:, j]
        peak_val = np.max(np.abs(q_j))
        peak_step = np.argmax(np.abs(q_j))
        end_val = np.abs(q_j[-1])
        decay = end_val / (peak_val + 1e-30)
        print(f"  {j:4d}  {peak_val:12.4e}  {peak_step:10d}  "
              f"{end_val:12.4e}  {decay:12.4e}")
    print()

    total_time = n_steps * stepper.T
    print(f"Total simulated time: {total_time*1000:.2f} ms ({n_steps} sub-steps)")

    # --- Frequency verification via zero-crossings (mode 0) ---
    q0 = q_hist[:, 0]
    crossings = np.where(np.diff(np.sign(q0)))[0]
    if len(crossings) >= 4:
        half_periods = np.diff(crossings) * stepper.T
        measured_T = 2.0 * np.mean(half_periods)
        measured_omega = 2.0 * np.pi / measured_T
        omega_d_expected = ma.frequencies[0] * np.sqrt(1.0 - stepper.xi[0]**2)
        print(f"Mode 0 frequency check (zero-crossings):")
        print(f"  Measured ω_d = {measured_omega:.2f} rad/s")
        print(f"  Expected ω_d = {omega_d_expected:.2f} rad/s")
        print(f"  Relative error = {abs(measured_omega - omega_d_expected)/omega_d_expected:.4f}")
    print()

    # Pre-compute full displacement at each frame.
    # Subsample for display: show every 4th sub-step.
    skip = 4
    display_indices = list(range(0, n_steps, skip))
    n_frames = len(display_indices)

    # Displacement scale for visibility.
    max_q = np.max(np.abs(q_hist))
    disp_scale = 0.04 / (max_q + 1e-30)

    print(f"Precomputing {n_frames} frames for polyscope playback...")
    surface = mesh.extract_surface()
    rest_verts = mesh.vertices.copy()

    # Precompute per-vertex displacement for each frame.
    frames_verts = np.zeros((n_frames, mesh.num_vertices, 3), dtype=np.float64)
    frames_mag = np.zeros((n_frames, mesh.num_vertices), dtype=np.float64)

    for fi, si in enumerate(display_indices):
        q = q_hist[si]
        u_free = ma.U @ q
        u_full = ma.expand_to_full(u_free)
        ux, uy, uz = u_full[0::3], u_full[1::3], u_full[2::3]
        frames_verts[fi, :, 0] = rest_verts[:, 0] + ux * disp_scale
        frames_verts[fi, :, 1] = rest_verts[:, 1] + uy * disp_scale
        frames_verts[fi, :, 2] = rest_verts[:, 2] + uz * disp_scale
        frames_mag[fi] = np.sqrt(ux**2 + uy**2 + uz**2)

    # Polyscope animation.
    ps.init()
    ps.set_up_dir("y_up")

    sm = ps.register_surface_mesh("table", frames_verts[0], surface.faces)
    sm.add_scalar_quantity("displacement", frames_mag[0],
                           defined_on="vertices", enabled=True, cmap="viridis",
                           vminmax=(0, frames_mag.max()))

    frame_idx = [0]
    is_playing = [True]

    def callback() -> None:
        import polyscope.imgui as imgui

        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val

        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])

        t_ms = display_indices[frame_idx[0]] * stepper.T * 1000
        imgui.Text(f"t = {t_ms:.2f} ms  (frame {frame_idx[0]}/{n_frames - 1})")

        if is_playing[0]:
            frame_idx[0] = (frame_idx[0] + 1) % n_frames

        fi = frame_idx[0]
        sm.update_vertex_positions(frames_verts[fi])
        sm.add_scalar_quantity("displacement", frames_mag[fi],
                               defined_on="vertices", enabled=True,
                               cmap="viridis",
                               vminmax=(0, frames_mag.max()))

    ps.set_user_callback(callback)
    ps.show()


if __name__ == "__main__":
    main()
