"""Stage 3 visualization: first 4 mode shapes on the paper's table slab.

Displays each mode as colored displacement magnitude on the surface mesh
using polyscope, laid out side by side. Matches paper Fig. 2 in spirit.
"""
import numpy as np
import polyscope as ps

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis


def main() -> None:
    # Paper table parameters: E=1.1 GPa, ν=0.3, ρ=770 kg/m³.
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=12, ny=8, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    # Fix corner columns (table legs): all Y-layers at the four XZ corners.
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
    model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed)

    print(f"Mesh: {mesh.num_vertices} verts, {mesh.num_tets} tets")
    print(f"Fixed nodes: {fixed.size}, free DOFs: {len(model.free_dofs)}, "
          f"fixed DOFs: {len(model.fixed_dofs)}")

    ma = ModalAnalysis(fem=model, num_modes=10)

    print("\nFirst 10 eigenfrequencies (rad/s):")
    for i, w in enumerate(ma.frequencies):
        print(f"  Mode {i}: ω = {w:.2f} rad/s  (f = {w / (2 * np.pi):.2f} Hz)")

    # Visualization with polyscope.
    ps.init()
    ps.set_up_dir("y_up")
    surface = mesh.extract_surface()

    # Lay out modes side by side along X, with spacing.
    n_modes = min(4, ma.num_modes)
    spacing = length * 1.3

    for mode_idx in range(n_modes):
        u_full = ma.mode_displacement(mode_idx)
        # Per-vertex displacement magnitude.
        ux = u_full[0::3]
        uy = u_full[1::3]
        uz = u_full[2::3]
        mag = np.sqrt(ux**2 + uy**2 + uz**2)

        # Deformed positions (exaggerated for visibility).
        scale = 0.03 / (mag.max() + 1e-30)
        deformed = mesh.vertices.copy()
        deformed[:, 0] += ux * scale
        deformed[:, 1] += uy * scale
        deformed[:, 2] += uz * scale

        # Offset each mode along X so they don't overlap.
        deformed[:, 0] += mode_idx * spacing

        name = f"mode_{mode_idx} (ω={ma.frequencies[mode_idx]:.1f})"
        sm = ps.register_surface_mesh(name, deformed, surface.faces)
        sm.add_scalar_quantity("displacement_mag", mag, defined_on="vertices",
                               enabled=True, cmap="viridis")

    ps.show()


if __name__ == "__main__":
    main()
