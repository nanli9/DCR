"""Run the truck scene visually with a STEEL slab (E=200 GPa, rho=7850).

Wrapper around scripts/run_scenes.py that monkey-patches the truck scene's
slab material to structural steel without editing run_scenes.py. All other
CLI flags are forwarded to scripts.run_scenes.main().

Usage (defaults match the empirical baseline from the proposal addendum):

    uv run python scripts/run_truck_steel_visual.py \\
        --mode energy_prescribed_patch \\
        --beta 0.7 \\
        --deformed-normal-method barbic_james \\
        --sim-duration 8.0 \\
        --causal-gating

Add any flag scripts/run_scenes.py truck accepts; the script does not parse
its own arguments. The first argument to scripts.run_scenes.main() is
forced to 'truck'.
"""
import sys

# Patch BEFORE importing scripts.run_scenes (so the symbol it imports is the
# patched constructor).
import scripts.run_scenes as rs
from dcr.fem import Material as RealMaterial

_first_call = [True]


def steel_material(E, nu, rho):
    """Intercept the first Material(...) call (the truck slab) and swap
    it for structural steel. Subsequent calls pass through unchanged."""
    if _first_call[0]:
        _first_call[0] = False
        print(
            f"[steel_visual] swapping slab Material({E:.2g}, {nu}, {rho}) "
            "-> STEEL(E=200 GPa, rho=7850)",
            flush=True,
        )
        return RealMaterial(E=200.0e9, nu=0.3, rho=7850.0)
    return RealMaterial(E, nu, rho)


rs.Material = steel_material

# Force the scene argument to 'truck' (this wrapper only makes sense there).
argv = list(sys.argv)
if len(argv) < 2 or argv[1] != "truck":
    argv = [argv[0], "truck", *argv[1:]]
sys.argv = argv

rs.main()
