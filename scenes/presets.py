"""Scene and demo-style presets for the Reduced-Coordinate AVBD shelf.

Two preset families, both consumed by all run-* scripts and by the live
viser GUI:

  ScenePreset  — bundles a coherent set of *physical* parameters
                 (geometry, impactor, probes, basis sizing). Pick this
                 to describe WHAT is being simulated.

  DemoStyle    — bundles a coherent set of *visual amplification* knobs
                 (jump gain, impedance scaling, exaggeration). Pick this
                 to describe how WATCHABLE the result should be.

Resolution order (applied by `build_reduced_support_shelf(preset=..., ...)`
and the scripts' arg parsers):

    preset defaults  ←  individual `--<flag>` overrides on the CLI
                    ←  live GUI changes (viser)

Two of the scene-preset fields (`default_material`, `default_render_thickness`)
are explicitly designed to be overridden: the preset says "in this scene's
spirit, here's the material we'd pick", and the user can swap to another one
without losing the rest of the bundle.

If you add a preset:

  1. Add the entry to `PRESETS` (scene) or `DEMO_STYLES` (style).
  2. Update the table in `docs/scenes.md`.
  3. The CLI auto-discovers it via `--list-scenes` / `--list-styles`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


# ---------------------------------------------------------------------------
# Scene preset
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenePreset:
    """Coherent bundle of physical parameters for a named scene.

    All fields are SI units. Override individual fields by passing the
    same name as a kwarg to `build_reduced_support_shelf(preset=p, ...)`.
    """
    name: str
    description: str

    # Shelf geometry.
    shelf_length:    float        # m, x-extent
    shelf_width:     float        # m, z-extent
    shelf_thickness: float        # m, used in plate flexural rigidity
                                  #    D_flex = E·h³ / (12·(1-ν²))

    # Impactor (rigid body that strikes the shelf).
    impactor_mass:         float = 0.5     # kg
    impactor_half_extent:  float = 0.02    # m, cube half-edge
    impactor_drop_height:  float = 0.02    # m, above shelf
    impactor_v0_y:         float = -1.0    # m/s, initial vertical velocity

    # Probes (rigid bodies that get DCR-style hops).
    probe_mass:        float = 0.005       # kg
    probe_half_extent: float = 0.0075      # m
    probe_z_offset:    float = 0.0         # m, off-axis z-shift

    # Material / damping defaults — overridable from CLI.
    default_material:        str          = "wood"   # one of: steel, wood, plastic, soft
    default_render_thickness: float | None = None    # None → match shelf_thickness

    # Basis sizing (rarely tuned).
    n_modes_global: int = 6     # bending modes (sin profiles in x)
    n_modes_local:  int = 4     # Gaussian bump modes at contact zones


# Material → Young's modulus map (kept here so presets stay self-contained).
MATERIAL_YOUNGS: dict[str, float] = {
    "steel":   2.0e11,   # ~rigid in practice at these scales
    "wood":    1.0e10,   # the recommended demo material
    "plastic": 1.0e9,    # ~1.6 mm sag under 0.5 kg
    "soft":    1.0e8,    # ~rubber, exaggerated demo
}


PRESETS: dict[str, ScenePreset] = {
    # NOTE on drop heights: the presets use *watchable* drop heights
    # (15–30 cm) so the viser cube visibly falls. The benchmark scripts
    # in this repo were calibrated at impactor_drop_height = 0.02 m
    # (2 cm); to reproduce the docs/sweep_*/RESULTS.md numbers, pass
    # `--drop-height 0.02 --v0-y -1.0` explicitly to override.

    "research-baseline": ScenePreset(
        name="research-baseline",
        description=(
            "Current 5 mm thin shelf (30 × 15 cm). Used by all existing "
            "benchmarks and tests. Pick this to reproduce the impedance / "
            "jump-gain sweep numbers in docs/sweep_*/RESULTS.md "
            "(remember to pass --drop-height 0.02 --v0-y -1.0)."),
        shelf_length=0.30, shelf_width=0.15, shelf_thickness=0.005,
        impactor_mass=0.5, impactor_drop_height=0.15, impactor_v0_y=-1.0,
        default_material="wood",
    ),

    "cutting-board": ScenePreset(
        name="cutting-board",
        description=(
            "25 mm hardwood cutting board (30 × 20 cm). Drop a knife or "
            "rolling pin. Probes are at the corners — natural location to "
            "see deck items hop."),
        shelf_length=0.30, shelf_width=0.20, shelf_thickness=0.025,
        impactor_mass=0.15, impactor_drop_height=0.25, impactor_v0_y=-2.0,
        probe_z_offset=0.06,
        default_material="wood",
    ),

    "pantry-shelf": ScenePreset(
        name="pantry-shelf",
        description=(
            "15 mm particleboard shelf (60 × 30 cm). Realistic for the "
            "DCR paper's 'spice-jar-on-shelf' use case."),
        shelf_length=0.60, shelf_width=0.30, shelf_thickness=0.015,
        impactor_mass=0.25, impactor_drop_height=0.20, impactor_v0_y=-0.5,
        probe_z_offset=0.05,
        default_material="plastic",
    ),

    "dining-table": ScenePreset(
        name="dining-table",
        description=(
            "30 mm hardwood dining table (1 × 0.6 m). Realistic for the "
            "DCR Fig. 1 dinner-scene reproduction."),
        shelf_length=1.00, shelf_width=0.60, shelf_thickness=0.030,
        impactor_mass=0.50, impactor_drop_height=0.30, impactor_v0_y=-1.5,
        probe_z_offset=0.10,
        default_material="wood",
    ),

    "metal-plate": ScenePreset(
        name="metal-plate",
        description=(
            "5 mm steel plate (30 × 15 cm). Stiff, fast modes (~100 Hz). "
            "Probe response is impulse-driven, almost no sustained sag."),
        shelf_length=0.30, shelf_width=0.15, shelf_thickness=0.005,
        impactor_mass=0.5, impactor_drop_height=0.20, impactor_v0_y=-1.0,
        default_material="steel",
    ),
}


# ---------------------------------------------------------------------------
# Demo-style preset
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DemoStyle:
    """Coherent bundle of visual-amplification knobs.

    All fields are direct passthroughs to the corresponding
    `--<flag>` on the scripts; setting a flag explicitly overrides the
    style's value for that knob.
    """
    name: str
    description: str

    # Modal block tuning (research / impedance scaling, weak effect).
    support_response_gain:     float       = 1.0
    modal_damping_scale:       float       = 1.0
    modal_energy_cap_fraction: float | None = None

    # Artistic jump gain (strong, visible effect).
    modal_jump_gain:           float = 1.0
    modal_jump_max_height:     float = 0.01      # m → v_max ≈ 0.443 m/s

    # Render-only.
    display_q_exaggerate:      float = 1.0


DEMO_STYLES: dict[str, DemoStyle] = {
    "honest": DemoStyle(
        name="honest",
        description=(
            "γ=1, no exaggeration. Physical response only. Use this for "
            "papers, energy-budget plots, anything where numerical "
            "fidelity matters."),
    ),

    "visible": DemoStyle(
        name="visible",
        description=(
            "γ=4. The recommended default for screen recordings and "
            "progress demos. ~3 mm probe rise on a wood shelf."),
        modal_jump_gain=4.0,
    ),

    "aggressive": DemoStyle(
        name="aggressive",
        description=(
            "γ=12 + 4 cm hop ceiling. Cinematic. Energy cap engaged at "
            "η=0.5 so peak ΔE_q stays bounded by rigid loss."),
        modal_jump_gain=12.0,
        modal_jump_max_height=0.04,
        modal_energy_cap_fraction=0.5,
    ),

    "paper-figure": DemoStyle(
        name="paper-figure",
        description=(
            "γ=8, display-q-exaggerate=10. Makes the modal deformation "
            "visible in stills. Use for figures, NOT for video — the "
            "exaggeration breaks frame-to-frame motion continuity."),
        modal_jump_gain=8.0,
        display_q_exaggerate=10.0,
    ),
}


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

def get_scene(name: str) -> ScenePreset:
    """Return the preset; raise KeyError with a helpful message if missing."""
    try:
        return PRESETS[name]
    except KeyError:
        avail = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(
            f"Unknown scene preset {name!r}. Available: {avail}") from None


def get_style(name: str) -> DemoStyle:
    try:
        return DEMO_STYLES[name]
    except KeyError:
        avail = ", ".join(sorted(DEMO_STYLES.keys()))
        raise KeyError(
            f"Unknown demo style {name!r}. Available: {avail}") from None


def format_scene_table() -> str:
    """Markdown-style table for --list-scenes."""
    lines = [
        "  scene name        thickness  length    impactor",
        "  ----------------  ---------  --------  ----------------------",
    ]
    for p in PRESETS.values():
        lines.append(
            f"  {p.name:<16}  "
            f"{p.shelf_thickness*1e3:>6.1f} mm  "
            f"{p.shelf_length*1e2:>5.1f} cm  "
            f"{p.impactor_mass:>4.2f} kg, "
            f"v0={p.impactor_v0_y:+.1f} m/s")
    lines.append("")
    for p in PRESETS.values():
        lines.append(f"  {p.name}: {p.description}")
        lines.append("")
    return "\n".join(lines)


def format_style_table() -> str:
    """Markdown-style table for --list-styles."""
    lines = [
        "  style name      γ      ζ scale    η      exaggerate",
        "  --------------  -----  ---------  -----  ----------",
    ]
    for s in DEMO_STYLES.values():
        eta = "—" if s.modal_energy_cap_fraction is None else f"{s.modal_energy_cap_fraction:.2g}"
        lines.append(
            f"  {s.name:<14}  "
            f"{s.modal_jump_gain:>4.1f}   "
            f"{s.modal_damping_scale:>4.1f}       "
            f"{eta:<5}  "
            f"{s.display_q_exaggerate:>5.1f}")
    lines.append("")
    for s in DEMO_STYLES.values():
        lines.append(f"  {s.name}: {s.description}")
        lines.append("")
    return "\n".join(lines)


def resolve_scene_kwargs(
    preset: ScenePreset,
    *,
    material: str | None = None,
    render_thickness: float | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Resolve a scene preset + selective overrides into kwargs for
    `build_reduced_support_shelf`. Drop any override that is `None` so
    the preset default wins.

    Returns the `kwargs` dict — caller should pass it as
    `build_reduced_support_shelf(**kwargs)`.
    """
    mat = material if material is not None else preset.default_material
    if mat not in MATERIAL_YOUNGS:
        raise ValueError(
            f"Unknown material {mat!r}. Available: "
            f"{', '.join(sorted(MATERIAL_YOUNGS.keys()))}")
    youngs = MATERIAL_YOUNGS[mat]

    out: dict[str, Any] = dict(
        shelf_length=preset.shelf_length,
        shelf_width=preset.shelf_width,
        shelf_thickness=preset.shelf_thickness,
        impactor_mass=preset.impactor_mass,
        impactor_half_extent=preset.impactor_half_extent,
        impactor_drop_height=preset.impactor_drop_height,
        impactor_v0=(0.0, preset.impactor_v0_y, 0.0),
        probe_mass=preset.probe_mass,
        probe_half_extent=preset.probe_half_extent,
        youngs=youngs,
        n_modes_global=preset.n_modes_global,
        n_modes_local=preset.n_modes_local,
    )
    if preset.probe_z_offset != 0.0:
        # probe_xz defaults to (-0.4L, 0) and (+0.4L, 0); shift to ±off.
        out["probe_xz"] = [
            (-0.40 * preset.shelf_length, preset.probe_z_offset),
            (+0.40 * preset.shelf_length, preset.probe_z_offset),
        ]

    # Apply explicit overrides (skip None — preset value wins).
    for k, v in overrides.items():
        if v is not None:
            out[k] = v

    return out


def resolve_style_coupler_fields(
    style: DemoStyle,
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the coupler/scene kwargs implied by `style` and any
    explicit overrides (None values are skipped).

    Use the returned dict as kwargs to `build_reduced_support_shelf` —
    they are the demo-knob parameters that the scene builder forwards
    to the ReducedCoupledAVBDCoupler.
    """
    out: dict[str, Any] = dict(
        modal_impedance_scale     = style.support_response_gain,
        modal_damping_scale       = style.modal_damping_scale,
        modal_energy_cap_fraction = style.modal_energy_cap_fraction,
        modal_jump_gain           = style.modal_jump_gain,
        modal_jump_max_height     = style.modal_jump_max_height,
    )
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                out[k] = v
    return out
