"""Gmsh .msh v2 ASCII file I/O for tetrahedral meshes."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .tet_mesh import TetMesh


def load_msh(path: str | Path) -> TetMesh:
    """Load a Gmsh v2 ASCII .msh file, keeping only 4-node tets (type 4).

    Supports both v2.2 and v4.1 ASCII formats (nodes + elements sections).
    """
    path = Path(path)
    with open(path) as f:
        lines = f.readlines()

    vertices: list[list[float]] = []
    tets: list[list[int]] = []
    idx = 0
    n_lines = len(lines)
    # Map from gmsh node id (1-based, possibly non-contiguous) to 0-based index.
    node_id_map: dict[int, int] = {}

    while idx < n_lines:
        line = lines[idx].strip()

        if line == "$Nodes":
            idx += 1
            header = lines[idx].strip().split()
            if len(header) == 1:
                # v2 format: single integer = num_nodes
                num_nodes = int(header[0])
                idx += 1
                for _ in range(num_nodes):
                    parts = lines[idx].strip().split()
                    nid = int(parts[0])
                    node_id_map[nid] = len(vertices)
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                    idx += 1
            else:
                # v4 format: num_entity_blocks num_nodes min_tag max_tag
                num_entity_blocks = int(header[0])
                num_nodes_total = int(header[1])
                idx += 1
                for _ in range(num_entity_blocks):
                    block_header = lines[idx].strip().split()
                    # entity_dim entity_tag parametric num_nodes_in_block
                    n_in_block = int(block_header[3])
                    idx += 1
                    # Read node tags
                    tags: list[int] = []
                    for _ in range(n_in_block):
                        tags.append(int(lines[idx].strip()))
                        idx += 1
                    # Read node coordinates
                    for tag in tags:
                        parts = lines[idx].strip().split()
                        node_id_map[tag] = len(vertices)
                        vertices.append([float(parts[0]), float(parts[1]), float(parts[2])])
                        idx += 1

        elif line == "$Elements":
            idx += 1
            header = lines[idx].strip().split()
            if len(header) == 1:
                # v2 format
                num_elems = int(header[0])
                idx += 1
                for _ in range(num_elems):
                    parts = lines[idx].strip().split()
                    elem_type = int(parts[1])
                    num_tags = int(parts[2])
                    if elem_type == 4:  # 4-node tet
                        node_ids = parts[3 + num_tags:]
                        tets.append([node_id_map[int(n)] for n in node_ids])
                    idx += 1
            else:
                # v4 format: num_entity_blocks num_elements min_tag max_tag
                num_entity_blocks = int(header[0])
                idx += 1
                for _ in range(num_entity_blocks):
                    block_header = lines[idx].strip().split()
                    # entity_dim entity_tag element_type num_elements_in_block
                    elem_type = int(block_header[2])
                    n_in_block = int(block_header[3])
                    idx += 1
                    for _ in range(n_in_block):
                        parts = lines[idx].strip().split()
                        if elem_type == 4:  # 4-node tet
                            # parts[0] is element tag, rest are node tags
                            tets.append([node_id_map[int(n)] for n in parts[1:]])
                        idx += 1
        else:
            idx += 1

    if not tets:
        raise ValueError(f"No tetrahedra found in {path}")

    return TetMesh(
        np.array(vertices, dtype=np.float64),
        np.array(tets, dtype=np.int32),
    )


def save_msh(mesh: TetMesh, path: str | Path) -> None:
    """Write a TetMesh as Gmsh v2.2 ASCII .msh."""
    path = Path(path)
    with open(path, "w") as f:
        f.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
        # Nodes (1-based)
        nv = mesh.vertices.shape[0]
        f.write(f"$Nodes\n{nv}\n")
        for i, v in enumerate(mesh.vertices):
            f.write(f"{i + 1} {v[0]:.10g} {v[1]:.10g} {v[2]:.10g}\n")
        f.write("$EndNodes\n")
        # Elements — all tets, type 4, 0 tags
        nt = mesh.tets.shape[0]
        f.write(f"$Elements\n{nt}\n")
        for i, t in enumerate(mesh.tets):
            f.write(f"{i + 1} 4 0 {t[0] + 1} {t[1] + 1} {t[2] + 1} {t[3] + 1}\n")
        f.write("$EndElements\n")
