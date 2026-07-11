"""Dinner-scene audio-voice construction (Stage E6 demo) — shared by the
offline render (`scripts/render_sound.py`) and the Tier 1 live viser demo
(`scripts/run_native_scenes_viser.py --sound`), so both paths play the same
instruments.

Materials per body-name prefix: E/ν/ρ handbook-ish; ζ is a constant-Q render
choice; `thickness` is the REAL object thickness for the audio mesh (the
collision proxy is much thicker — `dcr/sound/audio_basis.py` DEVIATION
notes); `tau_ref` is the lumped Hertz contact-time constant per material
pair. Candles stay silent (their hits still ring the table).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from dcr.sound import build_box_audio_basis, build_table_audio_basis, \
    load_audio_basis, save_audio_basis
from dcr.sound.audio_basis import AudioBasis

KIND_SPEC = {
    "plate": dict(youngs=70.0e9, poisson=0.22, zeta_const=1.5e-3,
                  num_modes=24, cells=(10, 2, 10),
                  thickness=0.005, density=2400.0,
                  tau_ref=3.0e-4),                         # 5 mm porcelain
    "cup":   dict(youngs=70.0e9, poisson=0.22, zeta_const=2.0e-3,
                  num_modes=16, cells=(8, 2, 8),
                  thickness=0.003, density=2400.0,
                  tau_ref=3.0e-4),                         # 3 mm shell proxy
    "pot":   dict(youngs=110.0e9, poisson=0.28, zeta_const=2.5e-3,
                  num_modes=20, cells=(8, 2, 8),
                  thickness=0.006, density=7200.0,
                  tau_ref=5.0e-4),                         # 6 mm cast iron
    "fork":  dict(youngs=200.0e9, poisson=0.30, zeta_const=1.0e-3,
                  num_modes=12, cells=(10, 2, 3),
                  thickness=0.003, density=7800.0,
                  tau_ref=2.5e-4),                         # 3 mm steel
    "knife": dict(youngs=200.0e9, poisson=0.30, zeta_const=1.0e-3,
                  num_modes=12, cells=(10, 2, 3),
                  thickness=0.003, density=7800.0,
                  tau_ref=2.5e-4),
}


def _cache_path(cache_dir: str, name: str, inputs: dict) -> str:
    key = hashlib.sha256(
        json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:12]
    return os.path.join(cache_dir, f"{name}_{key}.npz")


def _load_or_build(path: str, build_fn, rebuild: bool):
    if os.path.exists(path) and not rebuild:
        return load_audio_basis(path)
    basis = build_fn()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_audio_basis(path, basis)
    return basis


@dataclass
class DinnerAudio:
    """Everything the offline render or the live tap needs, keyed by SOLVER
    body index."""

    table_basis: AudioBasis
    body_bases: dict[int, AudioBasis] = field(default_factory=dict)
    body_names: dict[int, str] = field(default_factory=dict)
    tau_ref_per_body: dict[int, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


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
) -> DinnerAudio:
    """Build (or load cached) audio bases for the dinner scene as built:
    pass the SAME table material/thickness the scene builder received so the
    audio table is the instrument the sim actually rang."""
    from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

    notes: list[str] = []

    table_inputs = dict(length=table_length, width=table_width,
                        thickness=table_thickness, youngs=youngs,
                        poisson=poisson, density=density,
                        alpha0=rayleigh_alpha0, alpha1=rayleigh_alpha1,
                        k=table_modes, fmin=table_fmin, fs=fs,
                        nx=N_GRID_X, nz=N_GRID_Z,
                        zeta_const=table_zeta_const)
    table_basis = _load_or_build(
        _cache_path(cache_dir, "table", table_inputs),
        lambda: build_table_audio_basis(
            length=table_length, width=table_width,
            thickness=table_thickness, youngs=youngs, poisson=poisson,
            density=density, rayleigh_alpha0=rayleigh_alpha0,
            rayleigh_alpha1=rayleigh_alpha1, num_modes=table_modes,
            n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z, fs=fs,
            fmin_hz=table_fmin, zeta_const=table_zeta_const, name="table"),
        rebuild)
    if verbose:
        f = table_basis.freqs_hz()
        print(f"[basis] table: {table_basis.n_modes} modes, "
              f"{f.min():.0f}–{f.max():.0f} Hz"
              if table_basis.n_modes else "[basis] table: 0 modes in band!")

    out = DinnerAudio(table_basis=table_basis, notes=notes)
    basis_pool: dict[str, AudioBasis] = {}
    for b in getattr(handle, "bodies", []):
        prefix = b.name.split("_")[0] if "_" in b.name else b.name
        spec = KIND_SPEC.get(prefix)
        if spec is None:
            continue
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is None:
            continue
        avbd_idx = int(desc.avbd_body.index)
        mass = float(getattr(desc.avbd_body, "mass", 0.0)) or 1.0
        out.tau_ref_per_body[avbd_idx] = float(spec["tau_ref"])
        out.body_names[avbd_idx] = b.name
        builder_kwargs = {k: v for k, v in spec.items() if k != "tau_ref"}
        pool_inputs = dict(prefix=prefix, he=list(b.half_extents), mass=mass,
                           fs=fs, **{k: (list(v) if isinstance(v, tuple)
                                          else v)
                                     for k, v in builder_kwargs.items()})
        pool_key = json.dumps(pool_inputs, sort_keys=True)
        if pool_key not in basis_pool:
            basis_pool[pool_key] = _load_or_build(
                _cache_path(cache_dir, prefix, pool_inputs),
                lambda he=b.half_extents, m=mass, sp=builder_kwargs,
                       nm=prefix:
                    build_box_audio_basis(half_extents=he, mass=m, fs=fs,
                                          name=nm, **sp),
                rebuild)
            bb = basis_pool[pool_key]
            if bb.n_modes:
                fh = bb.freqs_hz()
                if verbose:
                    print(f"[basis] {prefix}: {bb.n_modes} modes, "
                          f"{fh.min():.0f}–{fh.max():.0f} Hz")
            else:
                msg = (f"{prefix}: no modes in the audible band — voice "
                       "silent (solid-proxy limitation, docs/stageE6)")
                notes.append(msg)
                if verbose:
                    print(f"[basis] {msg}")
        if basis_pool[pool_key].n_modes:
            out.body_bases[avbd_idx] = basis_pool[pool_key]
    return out
