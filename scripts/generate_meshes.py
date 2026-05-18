"""Generate bundled tet mesh assets for data/."""
from pathlib import Path

from dcr.geom import make_beam_tet_mesh, make_block_tet_mesh, make_slab_tet_mesh, save_msh

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)

# Beam: 1m x 0.05m x 0.05m, 20x2x2 hex cells
beam = make_beam_tet_mesh(length=1.0, width=0.05, height=0.05, nx=20, ny=2, nz=2)
save_msh(beam, DATA / "beam.msh")
print(f"beam.msh: {beam.num_vertices} verts, {beam.num_tets} tets")

# Block: 0.2m cube, 3x3x3
block = make_block_tet_mesh(size=0.2, nx=3, ny=3, nz=3)
save_msh(block, DATA / "block.msh")
print(f"block.msh: {block.num_vertices} verts, {block.num_tets} tets")

# Slab: 1m x 0.6m x 0.05m table-like, 10x6x1
slab = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05, nx=10, ny=6, nz=1)
save_msh(slab, DATA / "slab.msh")
print(f"slab.msh: {slab.num_vertices} verts, {slab.num_tets} tets")
