"""Stage E6 — scene-agnostic voice wiring (the `--sound` flag on every scene).

The audio layer is scene-generic: the SUPPORT voice is built from whatever
slab geometry + material the scene was built with, and BODY voices are
resolved from body names. These tests pin the two mappings that make that
work — no FEM eigensolve, so they stay fast. The end-to-end tap-on-a-real-scene
checks live in test_live_sound.py / test_device_ring.py.
"""
from __future__ import annotations

import inspect

import pytest

from scripts.sound_voices import KIND_SPEC, resolve_kind


# ---------------------------------------------------------------------------
# body name -> instrument
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,kind", [
    # dinner
    ("plate_0", "plate"), ("fork_3", "fork"), ("knife_5", "knife"),
    ("cup_2", "cup"), ("pot", "pot"),
    # truck: the resting crates and the dropped one share the crate instrument
    ("crate_rest_0", "crate"), ("drop_heavy", "crate"),
    ("cone_4", "cone"), ("lumber_2", "lumber"),
    # ledge
    ("pedestal", "pedestal"), ("pillar_1", "pillar"), ("boulder", "boulder"),
    # shelf: the standing books and the dropped tome
    ("book_0", "book"), ("drop_book", "book"),
    # silent by design — no instrument, but their hits still ring the support
    ("candle_0", None), ("cube_1", None), ("impactor", None),
    ("probe_0", None),
])
def test_resolve_kind(name, kind):
    assert resolve_kind(name) == kind


def test_kind_spec_is_complete_and_sane():
    """Every instrument must carry the knobs the builders need, and the alias
    targets must exist (a typo'd alias would silently mute a body)."""
    from scripts.sound_voices import KIND_ALIAS

    for k in KIND_ALIAS.values():
        assert k in KIND_SPEC
    for kind, spec in KIND_SPEC.items():
        assert spec["tau_ref"] > 0.0
        assert spec["youngs"] > 0.0
        assert 0.0 < spec["zeta_const"] < 1.0
        assert spec["num_modes"] >= 1
        if spec.get("basis") == "shell":          # Rayleigh ring: needs both
            assert spec["thickness"] > 0.0 and spec["density"] > 0.0
            assert spec["rim_factor"] > 0.0 and 0.0 < spec["kappa"] <= 1.0
        else:                                     # free-free slab proxy
            assert len(spec["cells"]) == 3


# ---------------------------------------------------------------------------
# scene -> support slab geometry (what the audio slab must be built from)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scene", ["cargo", "truck", "ledge", "shelf",
                                   "dinner"])
def test_viser_support_geometry_matches_builder(scene):
    """`UnifiedViser._support_geometry` reads the slab extents straight off the
    scene builder's signature (the viewer never overrides them). If a builder
    renames or drops those kwargs, the audio slab would silently stop matching
    the simulated one — assert the lookup resolves and agrees."""
    from scenes.reduced_cargo_network import build_cargo_network_scene
    from scripts.run_native_scenes_viser import _PROD, UnifiedViser

    viser = UnifiedViser.__new__(UnifiedViser)    # no server, no scene build
    viser.scene = scene
    length, width = UnifiedViser._support_geometry(viser)

    builder = (build_cargo_network_scene if scene == "cargo"
               else _PROD[scene])
    p = inspect.signature(builder).parameters
    lname = "table_length" if scene == "dinner" else "support_length"
    wname = "table_width" if scene == "dinner" else "support_width"
    assert length == pytest.approx(p[lname].default)
    assert width == pytest.approx(p[wname].default)
    assert length > 0.0 and width > 0.0
