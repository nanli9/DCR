#!/usr/bin/env python3
"""Stage 2 visualization: FEM static deformation of a table under a box drop.

A large flat slab (table) is modeled as a tet mesh with linear FEM.
The table is supported at its four edges. A rigid box sits on the
center, and its weight is applied as a concentrated load to the
nearest FEM node.  The deformed shape is shown with a displacement
color map.

Note: actual rigid-FEM coupling is Stage 5-6 (DCR).  This demo
applies the box weight as a static load to preview the FEM pipeline.

Usage:
    python scripts/run_stage2.py              # default: 1 kg box
    python scripts/run_stage2.py --mass 5.0   # heavier box
    python scripts/run_stage2.py --scale 500  # amplify deformation display
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import polyscope as ps

from dcr.geom import make_slab_tet_mesh, make_box
from dcr.fem import Material, FEMModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mass", type=float, default=1.0, help="Box mass [kg]")
    parser.add_argument("--scale", type=float, default=0.0,
                        help="Deformation display scale (0 = auto)")
    parser.add_argument("--E", type=float, default=1.1e9, help="Young's modulus [Pa]")
    args = parser.parse_args()

    # --- Table slab ---
    table_length = 2.0    # X extent [m]
    table_width = 1.0     # Z extent [m]
    table_thick = 0.08    # Y thickness [m]
    table_y = 0.8         # table center Y position

    # _make_box_tet_mesh(lx, ly, lz): X = length, Y = thickness, Z = width.
    # This way the thin dimension is Y (vertical) and the table surface is XZ.
    from dcr.geom.tet_mesh import _make_box_tet_mesh
    slab = _make_box_tet_mesh(
        lx=table_length, ly=table_thick, lz=table_width,
        nx=20, ny=2, nz=10,
    )
    # Shift table center up to table_y.
    slab.vertices[:, 1] += table_y

    mat = Material(E=args.E, nu=0.3, rho=600.0)

    # Fix nodes along the four edges of the XZ surface (perimeter support).
    verts = slab.vertices
    x_min, x_max = verts[:, 0].min(), verts[:, 0].max()
    z_min, z_max = verts[:, 2].min(), verts[:, 2].max()
    edge_tol_x = table_length / 20 + 1e-6  # one cell width
    edge_tol_z = table_width / 10 + 1e-6
    edge_mask = (
        (verts[:, 0] < x_min + edge_tol_x) |
        (verts[:, 0] > x_max - edge_tol_x) |
        (verts[:, 2] < z_min + edge_tol_z) |
        (verts[:, 2] > z_max - edge_tol_z)
    )
    fixed_nodes = np.where(edge_mask)[0].astype(np.int32)
    print(f"Table: {slab.num_vertices} verts, {slab.num_tets} tets, "
          f"{fixed_nodes.size} fixed nodes")

    model = FEMModel(mesh=slab, material=mat, fixed_nodes=fixed_nodes)

    # --- Apply box weight as point load at table center ---
    box_mass = args.mass
    box_size = 0.15
    box_pos = np.array([0.0, table_y + table_thick / 2 + box_size / 2, 0.0])

    # Find the closest FEM node to the box contact point (center of table top).
    contact_pt = np.array([0.0, table_y + table_thick / 2, 0.0])
    dists = np.linalg.norm(verts - contact_pt, axis=1)
    nearest_node = np.argmin(dists)
    print(f"Box ({box_mass:.1f} kg) contact: node {nearest_node} at {verts[nearest_node]}")

    # Build force vector: box weight in -Y at nearest node.
    f_full = np.zeros(model.n_full_dofs, dtype=np.float64)
    # Also include table self-weight (gravity load on all nodes).
    m_diag = model.M_full.diagonal()
    f_full[1::3] = m_diag[1::3] * (-9.81)
    # Add box weight at contact node.
    f_full[3 * nearest_node + 1] += -box_mass * 9.81
    f_free = f_full[model.free_dofs]

    # Solve static: K u = f.
    u = model.static_solve(f_free)
    u_reshaped = u.reshape(-1, 3)
    disp_mag = np.linalg.norm(u_reshaped, axis=1)
    max_disp = disp_mag.max()
    print(f"Max displacement: {max_disp:.4e} m")

    # Auto-scale so deformation is visible (target: 5% of table length).
    if args.scale <= 0:
        if max_disp > 1e-15:
            scale = 0.05 * table_length / max_disp
        else:
            scale = 1.0
    else:
        scale = args.scale
    print(f"Display scale: {scale:.0f}x")

    deformed_verts = verts + scale * u_reshaped

    # --- Extract surface for visualization ---
    surf = slab.extract_surface()

    # --- Polyscope ---
    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Register undeformed table (transparent wireframe).
    sm_orig = ps.register_surface_mesh("table_rest", surf.vertices, surf.faces)
    sm_orig.set_color((0.5, 0.5, 0.5))
    sm_orig.set_transparency(0.3)
    sm_orig.set_edge_width(1.0)

    # Register deformed table with displacement color map.
    sm_def = ps.register_surface_mesh("table_deformed", deformed_verts, surf.faces)
    sm_def.add_scalar_quantity("displacement_mm", disp_mag * 1000,
                               defined_on="vertices", enabled=True,
                               cmap="viridis")
    sm_def.set_edge_width(1.0)

    # Register the box.
    box_mesh = make_box(half_extents=(box_size/2, box_size/2, box_size/2),
                        center=tuple(box_pos))
    sm_box = ps.register_surface_mesh("box", box_mesh.vertices, box_mesh.faces)
    sm_box.set_color((0.8, 0.3, 0.2))

    # Ground plane for reference.
    ground_verts = np.array([[-3, 0, -3], [3, 0, -3], [3, 0, 3], [-3, 0, 3.0]])
    ground_faces = np.array([[0, 2, 1], [0, 3, 2]], dtype=np.int32)
    sm_gnd = ps.register_surface_mesh("ground", ground_verts, ground_faces)
    sm_gnd.set_color((0.6, 0.6, 0.6))
    sm_gnd.set_transparency(0.5)

    # Interactive controls.
    current_scale = [scale]

    def ui_callback():
        changed, new_val = ps.imgui.SliderFloat("Deform scale",
                                                 current_scale[0],
                                                 1.0, scale * 5)
        if changed:
            current_scale[0] = new_val
            new_def = verts + current_scale[0] * u_reshaped
            sm_def.update_vertex_positions(new_def)

        ps.imgui.TextUnformatted(
            f"Max disp: {max_disp*1000:.3f} mm  |  "
            f"Box: {box_mass:.1f} kg  |  "
            f"Table: {model.total_mass():.1f} kg")

    ps.set_user_callback(ui_callback)
    ps.show()


if __name__ == "__main__":
    main()
