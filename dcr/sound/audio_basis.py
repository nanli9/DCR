"""Audio-band modal bases (Stage E6 demo).

The audio band is the set of eigenmodes ABOVE what the co-solved sim-rate band
can represent (substep Nyquist) — rendered open-loop at audio rate, never fed
back into the solver. Both builders solve the paper's generalized eigenproblem
(Eq. 6):

    K ψ_i = ω_i² M ψ_i

with mass-normalized ψ (so M_q = I, Eq. 7) and per-mode damping ratio

    ζ_i = D_q,ii / (2 ω_i) = α₀/(2ω_i) + α₁ ω_i / 2      (Rayleigh, Eq. 7)

or a constant ζ override for materials whose audible ring the sim's Rayleigh
fit was never meant to model.

# DEVIATION (paper Eq. 7 / two_band_coupling design): the audio basis is a
# RENDER-side object. It may hold more modes than the co-solved band, and for
# ceramic/steel bodies it may use a constant-ζ damping law instead of the FEM
# Rayleigh D_q. This never affects the dynamics — the bank is open-loop
# (one-way is physically defensible up here: modal displacement per unit
# impulse ~ 1/ω, back-reaction energy ~ 1/ω²).
# DEVIATION (radiation): per-mode listening weights are a √(σ·S)-scaled RMS
# surface-displacement heuristic (see `radiation_weight`), not an acoustic-
# transfer (BEM/FFAT) solve. The render is *plausible*, not measured-accurate.
# Disclosed in docs/stageE6.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
import scipy.sparse.linalg as spla

C_AIR = 343.0    # speed of sound in air [m/s], for the radiation heuristic


def radiation_weight(
    phi_rms: NDArray[np.float64],
    omega: NDArray[np.float64],
    area: float,
) -> NDArray[np.float64]:
    """Per-mode listening weight  w_i = √(σ_i · S) · rms(Φ_y,i).

    Far-field radiated power of a vibrating surface is ~ ρ_air·c·σ(ω)·S·⟨v²⟩,
    so listening pressure ∝ √(σ·S)·(surface-velocity rms). The bare-rms
    heuristic this replaces dropped both factors, which inverted the physical
    balance between small and large radiators: mass-normalized modes make a
    light body's Φ large (∝ 1/√m), so a ~7 kg pot slab out-shouted the ~75 kg
    table by >60 dB per unit impulse. σ is a compact-source (dipole-like)
    acoustic short-circuit roll-off for an unbaffled radiator:

        σ_i = (k_i a)² / (1 + (k_i a)²),   k_i = ω_i / c_air,  a = √(S/π)

    → σ → 1 once the source is large against the wavelength, ∝ (ka)² below.

    # DEVIATION (radiation, supersedes the bare-RMS note): still a heuristic —
    # no Helmholtz/BEM/FFAT transfer, no directivity, no listener distance,
    # no baffling. Disclosed in docs/stageE6.
    """
    area = max(float(area), 1e-12)
    k = np.asarray(omega, dtype=np.float64) / C_AIR
    ka2 = (k * np.sqrt(area / np.pi)) ** 2
    sigma = ka2 / (1.0 + ka2)
    return np.sqrt(sigma * area) * np.asarray(phi_rms, dtype=np.float64)


@dataclass
class AudioBasis:
    """A bank-ready modal basis: frequencies, damping, and contact-side shape
    samples. Two kinds:

    - ``kind="grid"`` (the table): Φ·ŷ sampled on the reduced-support
      (n_grid_x × n_grid_z) grid, world (x, z) → bilinear interp
      (same index convention as `dcr.avbd.reduced_support.evaluate_basis_at_point`:
      idx = i * n_grid_z + k).
    - ``kind="corners"`` (free boxes): signed φ_y at the 8 box corners in the
      BODY frame, matched to a contact by the sign signature of its corner
      offset. Assumes the contact normal ≈ ±ŷ in body frame (bodies resting
      near-flat); disclosed approximation.
    """

    name: str
    kind: str                                   # "grid" | "corners"
    omega: NDArray[np.float64]                  # (r,) rad/s, ascending
    zeta: NDArray[np.float64]                   # (r,) damping ratios
    weight: NDArray[np.float64]                 # (r,) listening weights (heuristic)
    # grid kind
    phi_grid: NDArray[np.float64] | None = None      # (n_pts, r) Φ_y on grid
    length: float = 0.0
    width: float = 0.0
    n_grid_x: int = 0
    n_grid_z: int = 0
    # corners kind
    phi_corners: NDArray[np.float64] | None = None   # (8, r) signed φ_y, body frame
    corner_signs: NDArray[np.float64] | None = None  # (8, 3) sign signature
    # provenance (JSON) — cache-validation key
    params_json: str = ""

    @property
    def n_modes(self) -> int:
        return int(self.omega.shape[0])

    def freqs_hz(self) -> NDArray[np.float64]:
        return self.omega / (2.0 * np.pi)


def phi_at_xz(basis: AudioBasis, x: float, z: float) -> NDArray[np.float64]:
    """Bilinear-interpolate the grid basis at world (x, z) → (r,) Φ_y.

    Replicates `evaluate_basis_at_point`'s grid mapping exactly (grid centered
    on the support, idx = i * n_grid_z + k), so a corner the solver saw at
    (x, z) reads the same shape sample here.
    """
    assert basis.kind == "grid" and basis.phi_grid is not None
    nx, nz = basis.n_grid_x, basis.n_grid_z
    fx = (x + basis.length / 2.0) / basis.length * (nx - 1)
    fz = (z + basis.width / 2.0) / basis.width * (nz - 1)
    ix = int(np.clip(np.floor(fx), 0, nx - 2))
    iz = int(np.clip(np.floor(fz), 0, nz - 2))
    tx = float(np.clip(fx - ix, 0.0, 1.0))
    tz = float(np.clip(fz - iz, 0.0, 1.0))
    p = basis.phi_grid
    u00 = p[ix * nz + iz]
    u10 = p[(ix + 1) * nz + iz]
    u01 = p[ix * nz + iz + 1]
    u11 = p[(ix + 1) * nz + iz + 1]
    return ((1 - tx) * (1 - tz) * u00 + tx * (1 - tz) * u10
            + (1 - tx) * tz * u01 + tx * tz * u11)


def phi_at_corner(basis: AudioBasis, off_a: NDArray[np.float64]) -> NDArray[np.float64]:
    """Look up the (r,) signed φ_y sample for the box corner whose body-frame
    offset sign signature matches `off_a`."""
    assert basis.kind == "corners" and basis.phi_corners is not None
    s = np.sign(np.asarray(off_a, dtype=np.float64))
    s[s == 0.0] = 1.0
    match = np.all(basis.corner_signs == s[None, :], axis=1)
    idx = int(np.argmax(match))
    return basis.phi_corners[idx]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _rayleigh_zeta(omega: NDArray[np.float64], alpha0: float,
                   alpha1: float) -> NDArray[np.float64]:
    """ζ_i = α₀/(2ω_i) + α₁ω_i/2 — diagonal of D_q over 2ω (Eq. 7)."""
    w = np.maximum(omega, 1e-12)
    return alpha0 / (2.0 * w) + alpha1 * w / 2.0


def build_table_audio_basis(
    *,
    length: float,
    width: float,
    thickness: float,
    youngs: float,
    poisson: float,
    density: float,
    rayleigh_alpha0: float,
    rayleigh_alpha1: float,
    num_modes: int = 64,
    n_grid_x: int,
    n_grid_z: int,
    fs: float = 44100.0,
    fmin_hz: float = 150.0,
    zeta_const: float | None = None,
    name: str = "table",
) -> AudioBasis:
    """Audio basis for the table: k lowest eigenmodes of the SAME FEM recipe
    as the shared-operator sim arm (`scenes/reduced_dinner_table.py`,
    support_basis="fem": 20 cells/m, 3 through thickness, corner-column
    Dirichlet set) — solved via `ModalAnalysis` (paper Eq. 6), Φ_y sampled on
    the reduced-support grid.

    `fmin_hz` is the band-split crossover: modes below it belong to the
    co-solved sim band (substep-Nyquist representable) and are also poor
    radiators (acoustic short-circuit), so they are DROPPED from the audio
    bank — each mode sounds from exactly one band. Modes above 0.45·fs are
    dropped as unrepresentable at the render rate.

    `zeta_const` overrides the Rayleigh damping with a constant modal ζ —
    a per-material RENDER choice (module DEVIATION note): the scene's
    Rayleigh α (fit for wood-scale sim damping) makes every material thud;
    a steel table should ring (ζ ~ 3e-4), plastic stay dull (ζ ~ 8e-3).
    None keeps the sim's Rayleigh law (the wood default).
    """
    # Imports deferred: FEM assembly pulls in scipy.sparse machinery the
    # offline WAV path doesn't otherwise need.
    from dcr.fem.fem_model import FEMModel
    from dcr.fem.material import Material
    from dcr.fem.multibody_gt import corner_column_nodes
    from dcr.geom.tet_mesh import make_slab_tet_mesh
    from dcr.modal.modal_analysis import ModalAnalysis
    from dcr.modal.passive_inject import eval_basis_at_point

    mesh = make_slab_tet_mesh(
        length=length, width=width, height=thickness,
        nx=max(6, int(round(20.0 * length))),
        ny=max(4, int(round(20.0 * width))), nz=3)
    fem = FEMModel(mesh=mesh,
                   material=Material(E=youngs, nu=poisson, rho=density),
                   fixed_nodes=corner_column_nodes(mesh),
                   alpha0=rayleigh_alpha0, alpha1=rayleigh_alpha1)
    modal = ModalAnalysis(fem=fem, num_modes=int(num_modes))

    omega = np.asarray(modal.frequencies, dtype=np.float64)
    zeta = (np.full(omega.shape, float(zeta_const))
            if zeta_const is not None
            else _rayleigh_zeta(omega, rayleigh_alpha0, rayleigh_alpha1))

    # Band-split crossover + render-Nyquist guard.
    f_hz = omega / (2.0 * np.pi)
    keep = (f_hz >= fmin_hz) & (f_hz <= 0.45 * fs)

    # Sample Φ(x, z) on the support grid (same scaffolding as
    # fem_modal_support.make_fem_modal_support).
    surface = mesh.extract_surface()
    vert_to_surf = np.full(mesh.num_vertices, -1, dtype=np.int32)
    for si, vi in enumerate(modal.surface_vertex_indices):
        vert_to_surf[int(vi)] = si
    V = mesh.vertices
    mesh_top_y = float(V[:, 1].max())
    xs = np.linspace(float(V[:, 0].min()), float(V[:, 0].max()), n_grid_x)
    zs = np.linspace(float(V[:, 2].min()), float(V[:, 2].max()), n_grid_z)
    phi_grid = np.zeros((n_grid_x * n_grid_z, int(np.sum(keep))), dtype=np.float64)
    kept_cols = np.where(keep)[0]
    for i, x in enumerate(xs):
        for k, z in enumerate(zs):
            p = np.array([x, mesh_top_y, z], dtype=np.float64)
            U3r = eval_basis_at_point(
                p, surface, modal.U_surf, modal.surface_vertex_indices,
                vert_to_surf)
            phi_grid[i * n_grid_z + k, :] = U3r[1, kept_cols]

    omega, zeta = omega[keep], zeta[keep]
    # Listening weight = √(σ·S)·rms(Φ_y over the grid), S = table-top plan
    # area (`radiation_weight` DEVIATION note).
    weight = radiation_weight(np.sqrt(np.mean(phi_grid ** 2, axis=0)),
                              omega, length * width)

    params = dict(kind="table", length=length, width=width,
                  thickness=thickness, youngs=youngs, poisson=poisson,
                  density=density, alpha0=rayleigh_alpha0,
                  alpha1=rayleigh_alpha1, num_modes=num_modes,
                  n_grid_x=n_grid_x, n_grid_z=n_grid_z, fs=fs,
                  fmin_hz=fmin_hz, zeta_const=zeta_const,
                  radiation_v=2)
    return AudioBasis(
        name=name, kind="grid", omega=omega, zeta=zeta, weight=weight,
        phi_grid=phi_grid, length=length, width=width,
        n_grid_x=n_grid_x, n_grid_z=n_grid_z,
        params_json=json.dumps(params, sort_keys=True))


def build_box_audio_basis(
    *,
    half_extents: tuple[float, float, float],
    mass: float,
    youngs: float,
    poisson: float,
    zeta_const: float,
    num_modes: int = 24,
    fs: float = 44100.0,
    fmin_hz: float = 60.0,
    cells: tuple[int, int, int] = (8, 2, 8),
    thickness: float | None = None,
    density: float | None = None,
    name: str = "box",
) -> AudioBasis:
    """Free-free audio basis for a rigid box proxy (plate / cup / utensil).

    Solves Eq. 6 on the box's tet mesh with NO Dirichlet BCs. eigsh uses a
    NEGATIVE shift σ (K − σM = K + |σ|M is SPD) so shift-invert works on the
    singular free-free K; the 6 rigid-body modes come back at ω ≈ 0 and are
    dropped by the `fmin_hz` cut.

    # DEVIATION (scene material): by default ρ is derived from the SIM body
    # mass and the proxy volume (ρ = m / V), keeping the audio object
    # inertially consistent with the body the solver integrated. E, ν, ζ are
    # per-material render choices (constant ζ, not the table's Rayleigh law —
    # module docstring DEVIATION).
    # DEVIATION (audio geometry): `thickness` overrides the y-extent of the
    # AUDIO mesh only — the collision proxy is a thick box (a 2 cm "plate"),
    # but the thing that rings is the real ~5 mm ceramic. Using the
    # real-object thickness (+ optionally its tabulated `density`) puts the
    # eigenfrequencies in the physically right band; the solver's geometry is
    # untouched. Disclosed in docs/stageE6.
    """
    from dcr.fem.fem_model import FEMModel
    from dcr.fem.material import Material
    from dcr.geom.tet_mesh import make_slab_tet_mesh

    hx, hy, hz = (float(v) for v in half_extents)
    t_full = float(thickness) if thickness is not None else 2.0 * hy
    hy = t_full / 2.0
    volume = 4.0 * hx * hz * t_full
    rho = (float(density) if density is not None
           else float(mass) / max(volume, 1e-12))

    mesh = make_slab_tet_mesh(length=2 * hx, width=2 * hz, height=t_full,
                              nx=int(cells[0]), ny=int(cells[2]),
                              nz=int(cells[1]))
    fem = FEMModel(mesh=mesh, material=Material(E=youngs, nu=poisson, rho=rho),
                   fixed_nodes=np.array([], dtype=np.int32))

    k_req = int(num_modes) + 8          # 6 rigid modes + slack
    n_dof = fem.K.shape[0]
    k_req = min(k_req, n_dof - 2)
    sigma = -float((2.0 * np.pi * 30.0) ** 2)   # SPD shift (see docstring)
    eigenvalues, eigvecs = spla.eigsh(
        fem.K.tocsc(), k=k_req, M=fem.M.tocsc(), sigma=sigma, which="LM")
    order = np.argsort(eigenvalues)
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigvecs = eigvecs[:, order]
    # Mass-normalize (ψᵀMψ = 1) — same convention as ModalAnalysis (Eq. 6/7).
    for i in range(eigvecs.shape[1]):
        nrm = np.sqrt(eigvecs[:, i] @ (fem.M @ eigvecs[:, i]))
        eigvecs[:, i] /= max(nrm, 1e-30)

    omega_all = np.sqrt(eigenvalues)
    f_hz = omega_all / (2.0 * np.pi)
    keep = (f_hz >= fmin_hz) & (f_hz <= 0.45 * fs)
    kept = np.where(keep)[0][:int(num_modes)]
    omega = omega_all[kept]
    zeta = np.full(omega.shape, float(zeta_const), dtype=np.float64)

    # Signed φ_y at the 8 corners (body frame), free-free: all DOFs are free,
    # so full-mesh vertex v ↔ rows 3v..3v+2 of the eigenvectors directly.
    V = mesh.vertices
    center = 0.5 * (V.min(axis=0) + V.max(axis=0))
    Vc = V - center[None, :]
    corner_signs = np.array([[sx, sy, sz]
                             for sy in (-1.0, 1.0)
                             for sx in (-1.0, 1.0)
                             for sz in (-1.0, 1.0)], dtype=np.float64)
    phi_corners = np.zeros((8, omega.shape[0]), dtype=np.float64)
    for ci, s in enumerate(corner_signs):
        target = np.array([s[0] * hx, s[1] * hy, s[2] * hz])
        v_idx = int(np.argmin(np.sum((Vc - target[None, :]) ** 2, axis=1)))
        phi_corners[ci, :] = eigvecs[3 * v_idx + 1, kept]

    # Listening weight = √(σ·S)·rms(eigvec), S = the slab proxy's plan area
    # (its two large faces are the radiators; the unbaffled/dipole character
    # is what σ models — `radiation_weight` DEVIATION note).
    weight = radiation_weight(np.sqrt(np.mean(eigvecs[:, kept] ** 2, axis=0)),
                              omega, 4.0 * hx * hz)

    params = dict(kind="box", half_extents=[hx, hy, hz], mass=mass,
                  youngs=youngs, poisson=poisson, zeta_const=zeta_const,
                  num_modes=num_modes, fs=fs, fmin_hz=fmin_hz,
                  cells=list(cells), thickness=t_full, density=rho,
                  radiation_v=2)
    return AudioBasis(
        name=name, kind="corners", omega=omega, zeta=zeta, weight=weight,
        phi_corners=phi_corners, corner_signs=corner_signs,
        params_json=json.dumps(params, sort_keys=True))


# ---------------------------------------------------------------------------
# npz cache
# ---------------------------------------------------------------------------

def params_hash(params_json: str) -> str:
    return hashlib.sha256(params_json.encode()).hexdigest()[:16]


def save_audio_basis(path: str, basis: AudioBasis) -> None:
    np.savez_compressed(
        path,
        name=np.array(basis.name), kind=np.array(basis.kind),
        omega=basis.omega, zeta=basis.zeta, weight=basis.weight,
        phi_grid=(basis.phi_grid if basis.phi_grid is not None
                  else np.zeros((0, 0))),
        grid_meta=np.array([basis.length, basis.width,
                            basis.n_grid_x, basis.n_grid_z]),
        phi_corners=(basis.phi_corners if basis.phi_corners is not None
                     else np.zeros((0, 0))),
        corner_signs=(basis.corner_signs if basis.corner_signs is not None
                      else np.zeros((0, 0))),
        params_json=np.array(basis.params_json),
    )


def load_audio_basis(path: str) -> AudioBasis:
    d = np.load(path, allow_pickle=False)
    gm = d["grid_meta"]
    phi_grid = d["phi_grid"]
    phi_corners = d["phi_corners"]
    return AudioBasis(
        name=str(d["name"]), kind=str(d["kind"]),
        omega=d["omega"], zeta=d["zeta"], weight=d["weight"],
        phi_grid=(phi_grid if phi_grid.size else None),
        length=float(gm[0]), width=float(gm[1]),
        n_grid_x=int(gm[2]), n_grid_z=int(gm[3]),
        phi_corners=(phi_corners if phi_corners.size else None),
        corner_signs=(d["corner_signs"] if d["corner_signs"].size else None),
        params_json=str(d["params_json"]),
    )
