"""Scene audio-voice construction (Stage E6 demo) — shared by the offline
render (`scripts/render_sound.py`) and the Tier 1 live viser demo
(`scripts/run_native_scenes_viser.py --sound`), so both paths play the same
instruments.

Two things are built here:

- the SUPPORT voice: the scene's deformable slab (dinner table, truck road,
  cliff ledge, shelf board, cargo slab) — a grid-kind `AudioBasis` from the
  same FEM recipe the shared-operator sim arm uses, at whatever geometry and
  material the scene was actually built with;
- the BODY voices: one per rigid body whose name matches a `KIND_SPEC` entry
  (per-kind E/ν/ρ/ζ/thickness/τ_ref — a porcelain plate, a cast-iron pot, a
  wooden crate, a stone pillar…), pooled so identical bodies share one basis.

Materials per body kind: E/ν/ρ handbook-ish; ζ is a constant-Q render choice;
`thickness` is the REAL object thickness for the audio mesh (the collision
proxy is much thicker — `dcr/sound/audio_basis.py` DEVIATION notes);
`doublet_detune` splits degenerate pairs so they beat like a real, slightly
asymmetric object; `tau_ref` is the lumped Hertz contact-time constant for the
material pair. Bodies with no entry stay SILENT (candles, cargo cubes) — their
hits still ring the support voice and still fire the contact-noise transient.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from dcr.sound import build_box_audio_basis, build_shell_audio_basis, \
    build_table_audio_basis, load_audio_basis, save_audio_basis
from dcr.sound.audio_basis import AudioBasis

KIND_SPEC = {
    # basis="slab" (default): free-free FEM plate proxy — right for plate-like
    # and bar-like objects. basis="shell": closed-form Rayleigh ring modes —
    # right for open vessels (a cup is a shell, not a plate; the slab proxy put
    # it at 9 kHz with two modes; the ring series starts ~1.7 kHz with the real
    # mug partials). rim_factor = closed-bottom stiffening, kappa =
    # vertical-tap→rim coupling. doublet_detune = degenerate-pair split → the
    # beat ("warble") of a real, slightly asymmetric object. (audio_basis
    # DEVIATION notes.)

    # ---- dinner: porcelain, ceramic, cast iron, steel -------------------
    "plate": dict(youngs=70.0e9, poisson=0.22, zeta_const=1.5e-3,
                  num_modes=24, cells=(10, 2, 10),
                  thickness=0.005, density=2400.0,
                  doublet_detune=2.5e-3,
                  tau_ref=3.0e-4),                         # 5 mm porcelain
    "cup":   dict(basis="shell",
                  youngs=70.0e9, poisson=0.22, zeta_const=2.0e-3,
                  num_modes=8, thickness=0.003, density=2400.0,
                  rim_factor=1.0, kappa=0.6,
                  doublet_detune=3.0e-3,                   # ~3–5 Hz mug warble
                  tau_ref=3.0e-4),                         # 3 mm ceramic shell
    "pot":   dict(basis="shell",
                  youngs=110.0e9, poisson=0.28, zeta_const=2.5e-3,
                  num_modes=10, thickness=0.006, density=7200.0,
                  rim_factor=2.0, kappa=0.8,
                  doublet_detune=2.0e-3,                   # slow heavy beat
                  tau_ref=5.0e-4),                         # 6 mm cast iron pot
    "fork":  dict(youngs=200.0e9, poisson=0.30, zeta_const=1.0e-3,
                  num_modes=12, cells=(10, 2, 3),
                  thickness=0.003, density=7800.0,
                  doublet_detune=2.5e-3,
                  tau_ref=2.5e-4),                         # 3 mm steel
    "knife": dict(youngs=200.0e9, poisson=0.30, zeta_const=1.0e-3,
                  num_modes=12, cells=(10, 2, 3),
                  thickness=0.003, density=7800.0,
                  doublet_detune=2.5e-3,
                  tau_ref=2.5e-4),

    # ---- truck (road): wooden crates, PVC cones, timber ------------------
    # Wood is heavily damped — a knock, not a ring (ζ ~ 2e-2, two decades above
    # the ceramics above); PVC more so. τ_ref is long for the soft pairs (a
    # wood-on-wood contact is a dull thud, not a bright click).
    "crate":  dict(youngs=10.0e9, poisson=0.35, zeta_const=2.0e-2,
                   num_modes=12, cells=(8, 2, 8),
                   thickness=0.012, density=600.0,         # 12 mm plank walls
                   doublet_detune=3.0e-3,
                   tau_ref=8.0e-4),
    "cone":   dict(youngs=2.0e9, poisson=0.40, zeta_const=6.0e-2,
                   num_modes=6, cells=(6, 2, 6),
                   thickness=0.004, density=1400.0,        # 4 mm PVC shell
                   doublet_detune=4.0e-3,
                   tau_ref=2.0e-3),                        # soft → dull "pock"
    "lumber": dict(youngs=11.0e9, poisson=0.35, zeta_const=1.2e-2,
                   num_modes=10, cells=(8, 2, 8),
                   density=550.0,                          # SOLID: proxy = plank
                   doublet_detune=3.0e-3,
                   tau_ref=8.0e-4),

    # ---- ledge: granite pedestal + pillars, rock boulder ------------------
    # Stone: stiff, dense, lightly damped → a hard "clack" with a short bright
    # attack (τ_ref small). Solid bodies — no thickness override.
    "pedestal": dict(youngs=50.0e9, poisson=0.25, zeta_const=6.0e-3,
                     num_modes=10, cells=(8, 2, 8), density=2700.0,
                     doublet_detune=2.5e-3,
                     tau_ref=2.0e-4),
    "pillar":   dict(youngs=50.0e9, poisson=0.25, zeta_const=5.0e-3,
                     num_modes=8, cells=(3, 8, 3),         # tall thin column
                     density=2700.0,
                     doublet_detune=2.5e-3,
                     tau_ref=2.0e-4),
    "boulder":  dict(youngs=50.0e9, poisson=0.25, zeta_const=8.0e-3,
                     num_modes=10, cells=(6, 4, 6), density=2700.0,
                     doublet_detune=2.5e-3,
                     tau_ref=2.5e-4),

    # ---- shelf: books ----------------------------------------------------
    # A book is acoustically nearly dead (a paper block: enormous internal
    # damping, soft long contact) — a few modes at ζ ~ 1e-1 give the thwack its
    # body, and the attack-noise transient carries the rest.
    "book": dict(youngs=2.0e9, poisson=0.30, zeta_const=9.0e-2,
                 num_modes=4, cells=(8, 2, 8), density=800.0,
                 doublet_detune=4.0e-3,
                 tau_ref=2.5e-3),
}

# Scene body names that don't begin with their kind (the dropped impactors) →
# canonical kind. Everything else resolves by longest name prefix
# ("crate_rest_0" → "crate", "plate_2" → "plate"), so bodies of one kind share
# a pooled basis.
KIND_ALIAS = {
    "drop_heavy": "crate",     # truck: the heavy dropped crate
    "drop_book": "book",       # shelf: the dropped tome
}


def resolve_kind(name: str) -> str | None:
    """Body name → KIND_SPEC key, or None (a silent body: candle, cargo cube).

    Longest prefix wins, aliases first, so `crate_rest_0` → crate and
    `drop_book` → book without either shadowing the other."""
    parts = str(name).split("_")
    for i in range(len(parts), 0, -1):
        key = "_".join(parts[:i])
        if key in KIND_ALIAS:
            return KIND_ALIAS[key]
        if key in KIND_SPEC:
            return key
    return None


def _cache_path(cache_dir: str, name: str, inputs: dict) -> str:
    key = hashlib.sha256(
        json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:12]
    return os.path.join(cache_dir, f"{name}_{key}.npz")


def _load_or_build(path: str, build_fn, rebuild: bool, *, label: str = "",
                   verbose: bool = False, slow: bool = False):
    if os.path.exists(path) and not rebuild:
        return load_audio_basis(path)
    if verbose and slow:
        # The support eigensolve is the one blocking build (10–60 s for a big
        # slab); the viewer freezes on it, so say so rather than look hung.
        print(f"[basis] {label}: not cached — solving the support eigenproblem "
              "(one-off, 10–60 s; cached after)…", flush=True)
    basis = build_fn()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_audio_basis(path, basis)
    return basis


@dataclass
class SceneAudio:
    """Everything the offline render or the live tap needs, keyed by SOLVER
    body index. `support_basis` is None when the slab has no modes in the
    audible band (a rubbery low-E support doesn't ring — voice silent)."""

    support_basis: AudioBasis | None
    body_bases: dict[int, AudioBasis] = field(default_factory=dict)
    body_names: dict[int, str] = field(default_factory=dict)
    tau_ref_per_body: dict[int, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def build_scene_audio(
    handle,
    world,
    *,
    fs: float,
    support_length: float,
    support_width: float,
    support_thickness: float,
    youngs: float,
    density: float,
    poisson: float = 0.30,
    rayleigh_alpha0: float = 2.0,
    rayleigh_alpha1: float = 1.0e-5,
    support_modes: int = 64,
    support_fmin: float = 150.0,
    support_zeta_const: float | None = None,
    support_label: str = "support",
    cache_dir: str = "data/audio_basis",
    rebuild: bool = False,
    verbose: bool = True,
) -> SceneAudio:
    """Build (or load cached) audio bases for ANY of the reduced-support scenes
    (dinner / truck / ledge / shelf / cargo).

    Pass the SAME support geometry + material the scene builder received, so
    the audio slab is the instrument the sim actually rang. Bodies are voiced
    by name (`resolve_kind`); unmatched bodies stay silent by design.

    `support_label` only names the slab in the log line ("road", "ledge", …);
    the cache key is the geometry+material itself, so the offline render and
    the live viser share one cached eigensolve per (slab, material).
    """
    from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

    notes: list[str] = []

    support_inputs = dict(length=support_length, width=support_width,
                          thickness=support_thickness, youngs=youngs,
                          poisson=poisson, density=density,
                          alpha0=rayleigh_alpha0, alpha1=rayleigh_alpha1,
                          k=support_modes, fmin=support_fmin, fs=fs,
                          nx=N_GRID_X, nz=N_GRID_Z,
                          zeta_const=support_zeta_const,
                          radiation_v=2)   # weight-recipe version (cache key)
    support_basis = _load_or_build(
        _cache_path(cache_dir, "support", support_inputs),
        lambda: build_table_audio_basis(
            length=support_length, width=support_width,
            thickness=support_thickness, youngs=youngs, poisson=poisson,
            density=density, rayleigh_alpha0=rayleigh_alpha0,
            rayleigh_alpha1=rayleigh_alpha1, num_modes=support_modes,
            n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z, fs=fs,
            fmin_hz=support_fmin, zeta_const=support_zeta_const,
            name="support"),
        rebuild, label=support_label, verbose=verbose, slow=True)
    if support_basis.n_modes == 0:
        # E.g. the "soft"/"rubber" tabletop (E ≤ 1e8): every eigenmode falls
        # below the fmin crossover — physically a rubbery slab with no audible
        # ring. Voice silent (same policy as 0-mode body voices); impacts still
        # sound through the body voices + the contact-noise transient.
        msg = (f"{support_label}: no modes in [{support_fmin:.0f} Hz, 0.45·fs] "
               "— voice silent (low-E support has no audible band)")
        notes.append(msg)
        support_basis = None
        if verbose:
            print(f"[basis] {msg}")
    elif verbose:
        f = support_basis.freqs_hz()
        print(f"[basis] {support_label}: {support_basis.n_modes} modes, "
              f"{f.min():.0f}–{f.max():.0f} Hz")

    out = SceneAudio(support_basis=support_basis, notes=notes)
    basis_pool: dict[str, AudioBasis] = {}
    n_silent = 0
    for b in getattr(handle, "bodies", []):
        kind = resolve_kind(b.name)
        if kind is None:                       # candle, cargo cube, … — silent
            n_silent += 1
            continue
        spec = KIND_SPEC[kind]
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is None:
            continue
        avbd_idx = int(desc.avbd_body.index)
        mass = float(getattr(desc.avbd_body, "mass", 0.0)) or 1.0
        out.tau_ref_per_body[avbd_idx] = float(spec["tau_ref"])
        out.body_names[avbd_idx] = b.name
        basis_kind = spec.get("basis", "slab")
        builder_kwargs = {k: v for k, v in spec.items()
                          if k not in ("tau_ref", "basis")}
        pool_inputs = dict(prefix=kind, he=list(b.half_extents), mass=mass,
                           fs=fs, radiation_v=2, basis=basis_kind,
                           **{k: (list(v) if isinstance(v, tuple) else v)
                              for k, v in builder_kwargs.items()})
        pool_key = json.dumps(pool_inputs, sort_keys=True)
        if pool_key not in basis_pool:
            if basis_kind == "shell":
                build_fn = (lambda he=b.half_extents, sp=builder_kwargs,
                                   nm=kind:
                            build_shell_audio_basis(half_extents=he, fs=fs,
                                                    name=nm, **sp))
            else:
                build_fn = (lambda he=b.half_extents, m=mass,
                                   sp=builder_kwargs, nm=kind:
                            build_box_audio_basis(half_extents=he, mass=m,
                                                  fs=fs, name=nm, **sp))
            basis_pool[pool_key] = _load_or_build(
                _cache_path(cache_dir, kind, pool_inputs), build_fn, rebuild,
                label=kind, verbose=verbose)
            bb = basis_pool[pool_key]
            if bb.n_modes:
                fh = bb.freqs_hz()
                if verbose:
                    print(f"[basis] {kind}: {bb.n_modes} modes, "
                          f"{fh.min():.0f}–{fh.max():.0f} Hz")
            else:
                msg = (f"{kind}: no modes in the audible band — voice "
                       "silent (solid-proxy limitation, docs/stageE6)")
                notes.append(msg)
                if verbose:
                    print(f"[basis] {msg}")
        if basis_pool[pool_key].n_modes:
            out.body_bases[avbd_idx] = basis_pool[pool_key]
    if n_silent and verbose:
        print(f"[basis] {n_silent} body(s) unvoiced by design (no KIND_SPEC "
              "entry: candles, cargo cubes) — they still ring the support")
    return out


# Back-compat: the offline render (dinner-only) called this before the scene
# generalization. Same builder, dinner's geometry/material as defaults.
DinnerAudio = SceneAudio


def build_dinner_audio(
    handle,
    world,
    *,
    fs: float,
    table_length: float = 2.2,
    table_width: float = 1.1,
    table_thickness: float = 0.04,
    youngs: float = 1.1e9,
    poisson: float = 0.30,
    density: float = 770.0,
    rayleigh_alpha0: float = 2.0,
    rayleigh_alpha1: float = 1.0e-5,
    table_modes: int = 64,
    table_fmin: float = 150.0,
    table_zeta_const: float | None = None,
    cache_dir: str = "data/audio_basis",
    rebuild: bool = False,
    verbose: bool = True,
) -> SceneAudio:
    """Dinner-scene wrapper over `build_scene_audio` (the DCR §5.1 table:
    2.2 × 1.1 m, Table 2 wood). Kept so the offline render's dinner defaults
    live in one place."""
    return build_scene_audio(
        handle, world, fs=fs,
        support_length=table_length, support_width=table_width,
        support_thickness=table_thickness, youngs=youngs, poisson=poisson,
        density=density, rayleigh_alpha0=rayleigh_alpha0,
        rayleigh_alpha1=rayleigh_alpha1, support_modes=table_modes,
        support_fmin=table_fmin, support_zeta_const=table_zeta_const,
        support_label="table", cache_dir=cache_dir, rebuild=rebuild,
        verbose=verbose)
