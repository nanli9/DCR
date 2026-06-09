"""Decorated render-asset templates for the dinner-scene viewers.

Loads a 3D model from model/{kind}/ (gltf/glb/obj/...) per render_kind,
normalized to the unit cube so the body box half_extents drive the
rendered size. Falls back to a procedural cylinder/cube when no asset
is present. Extracted verbatim from the AVBD-branch run_scenes_avbd so
both the patch-DCR and reduced-modal dinner viewers share one loader.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

_CUBE_V = np.array([
    [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
    [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
], dtype=np.float32)
_CUBE_F = np.array([
    [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
    [2, 3, 7], [2, 7, 6], [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3],
], dtype=np.uint32)


def _make_cyl_y_template(sections: int) -> tuple[np.ndarray, np.ndarray]:
    """Unit cylinder template centered at origin, axis along +Y, fit in the
    unit cube [-0.5, 0.5]^3 so `scale=2*half_extents` per-instance recovers
    the real body (same convention as `_CUBE_V`). Side + top cap + bottom
    cap, all wound CCW from outside so flat shading lights correctly.
    """
    theta = 2.0 * np.pi * np.arange(sections, dtype=np.float64) / sections
    cx = 0.5 * np.cos(theta)
    cz = 0.5 * np.sin(theta)
    top = np.column_stack([cx, np.full(sections, 0.5), cz])
    bot = np.column_stack([cx, np.full(sections, -0.5), cz])
    tc = np.array([[0.0, 0.5, 0.0]])
    bc = np.array([[0.0, -0.5, 0.0]])
    V = np.vstack([top, bot, tc, bc]).astype(np.float32)
    tc_idx = 2 * sections
    bc_idx = 2 * sections + 1
    faces = []
    for i in range(sections):
        j = (i + 1) % sections
        # Side: two triangles, outward normal radially.
        faces.append([i, j, sections + i])
        faces.append([j, sections + j, sections + i])
        # Top cap fan, outward +Y.
        faces.append([tc_idx, j, i])
        # Bottom cap fan, outward -Y.
        faces.append([bc_idx, sections + i, sections + j])
    return V, np.array(faces, dtype=np.uint32)


# Procedural fallback templates per render_kind — used when no asset file is
# found in `model/`. Built lazily by `_resolve_kind_template` so the module
# loads even in envs without trimesh.
_FALLBACK_SECTIONS = {"plate": 28, "pot": 22, "candle": 12}

# Render-asset folder. Drop {kind}.obj / .glb / .gltf / .ply / .stl here to
# override the procedural template for that kind. See model/README.md.
_RENDER_MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
_SUPPORTED_MESH_EXTS = (".obj", ".glb", ".gltf", ".ply", ".stl")

# Resolved-template cache keyed by render_kind. None entry = "tried and
# failed to load; falling back". Populated by `_resolve_kind_template`.
_KIND_TEMPLATE_CACHE: dict[str, tuple[np.ndarray, np.ndarray]] = {}
_KIND_TEMPLATE_SOURCE: dict[str, str] = {}  # for the startup log line


def _normalize_to_unit_cube(v: np.ndarray) -> np.ndarray:
    """Recenter at bbox centroid + per-axis normalize so bbox = [-0.5, 0.5]^3.

    Matches the unit-cube convention so the same `scale = 2 * half_extents`
    mapping the viewer applies to `_CUBE_V` instances also recovers the
    rendered asset at the right size. Axes are normalized independently —
    the box collision proxy's aspect ratio is the rendered aspect ratio,
    so pick half_extents in the scene builder to match the loaded mesh's
    natural proportions.
    """
    v = np.asarray(v, dtype=np.float32)
    lo = v.min(axis=0)
    hi = v.max(axis=0)
    extent = np.maximum(hi - lo, 1e-12).astype(np.float32)
    center = (0.5 * (lo + hi)).astype(np.float32)
    return ((v - center) / extent).astype(np.float32)


def _try_load_asset(kind: str) -> tuple[np.ndarray, np.ndarray, str] | None:
    """Look for a render asset for `kind`. Search order:
        model/{kind}/{kind}.{ext}   — per-kind subdir (preferred; isolates
                                       companion .bin/textures across kinds)
        model/{kind}.{ext}          — flat single-file asset (self-contained .glb)
    First match wins, priority by extension (.glb > .gltf > .obj > .ply > .stl).
    Returns (V, F, src_label) or None.
    """
    if not _RENDER_MODEL_DIR.exists():
        return None
    candidates: list[Path] = []
    for ext in _SUPPORTED_MESH_EXTS:
        candidates.append(_RENDER_MODEL_DIR / kind / f"{kind}{ext}")
    for ext in _SUPPORTED_MESH_EXTS:
        candidates.append(_RENDER_MODEL_DIR / f"{kind}{ext}")
    for p in candidates:
        if not p.exists():
            continue
        try:
            import trimesh
            m = trimesh.load(str(p), force="mesh", process=False)
        except Exception as e:
            print(f"[viewer] failed to load {p}: {e}")
            continue
        v = _normalize_to_unit_cube(np.asarray(m.vertices))
        f = np.asarray(m.faces, dtype=np.uint32)
        return v, f, str(p.relative_to(_RENDER_MODEL_DIR))
    return None


def _resolve_kind_template(kind: str) -> tuple[np.ndarray, np.ndarray]:
    """Return the (V, F) template for `kind`, asset-loaded if available, else
    the procedural fallback. Cached so each kind is resolved + logged once.
    """
    if kind in _KIND_TEMPLATE_CACHE:
        return _KIND_TEMPLATE_CACHE[kind]
    if kind == "box":
        _KIND_TEMPLATE_CACHE[kind] = (_CUBE_V, _CUBE_F)
        _KIND_TEMPLATE_SOURCE[kind] = "builtin cube"
        return _KIND_TEMPLATE_CACHE[kind]
    loaded = _try_load_asset(kind)
    if loaded is not None:
        v, f, src = loaded
        _KIND_TEMPLATE_CACHE[kind] = (v, f)
        _KIND_TEMPLATE_SOURCE[kind] = src
        print(f"[viewer] loaded render template for '{kind}' from {src} "
              f"({v.shape[0]} verts, {f.shape[0]} faces)")
        return v, f
    sections = _FALLBACK_SECTIONS.get(kind)
    if sections is None:
        # Unknown kind we don't have a cylinder for — fall back to cube.
        v, f = _CUBE_V, _CUBE_F
        _KIND_TEMPLATE_SOURCE[kind] = "fallback cube (unknown kind)"
    else:
        v, f = _make_cyl_y_template(sections=sections)
        _KIND_TEMPLATE_SOURCE[kind] = f"fallback cylinder ({sections} sides)"
    _KIND_TEMPLATE_CACHE[kind] = (v, f)
    print(f"[viewer] no render asset for '{kind}' — using "
          f"{_KIND_TEMPLATE_SOURCE[kind]}")
    return v, f


