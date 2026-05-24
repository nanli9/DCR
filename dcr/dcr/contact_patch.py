"""Contact patch primitives for the patch-based DCR follow-up
(prompt §7 + §9.1; foundation §7).

# DEVIATION from the existing per-contact response paths (Versions A/B in
# `passive_dcr.py`): the patch formulation aggregates simultaneous contacts
# sharing the same body pair into a single response point, replacing the
# point-impulse pathology where a corner contact's lever arm `r` grows
# unbounded and the angular kick Δω = I⁻¹·(r × λ) diverges (prompt §0,
# §1.3, §7).

This module is intentionally response-agnostic — it only builds the
geometric `ContactPatch` (centroid, averaged rest normal, clamped lever
arms). Deformed-normal averaging at the centroid (prompt §9.3), the
3×3 patch effective-mass matrix (prompt §9.4), Coulomb projection
(prompt §9.5), and passivity scaling (prompt §9.6) are deferred to
later plans.

The patch centroid `x̄` and per-body lever arms `r̄_a`, `r̄_b` are
the primary handoff to those later steps; the contact indices and
weights are kept for diagnostics / A-B-ing against per-contact paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from ..rigid.body import RigidBody, ShapeType
from ..rigid.collision import Contact


_EPS_NORMAL = 1e-9
"""Below this magnitude the weighted-sum of rest normals is treated as
degenerate (antiparallel cancellation, etc.). Raises rather than silently
emitting a zero-length normal."""


@dataclass(frozen=True)
class ContactPatch:
    """A clustered group of simultaneous contacts on a single body pair.

    Foundation §7.1-7.3 / prompt §7:
        x̄    = Σ w_j x_j / Σ w_j                  (weighted centroid)
        n̄'   = normalize(Σ w_j n_j)                (averaged rest normal)
        r̄    = clamp_length(x̄ - x_COM, r_max)     (per-body lever arm)

    The deformed normal at `x̄` is computed by the coupler (prompt §9.3)
    and is NOT stored here — different coupler instances may use
    different deformed-normal backends (patch_fit / barbic_james) on the
    same geometric patch.

    Attributes:
        body_a, body_b: body indices, normalized so `body_a <= body_b`
            (deterministic cluster keys).
        contact_indices: indices into the step's `contacts` list that this
            patch aggregates. Preserves input order.
        x_bar: (3,) weighted centroid in world frame.
        n_rest_bar: (3,) unit-length weighted-average rest normal,
            oriented "canonical A → B" — i.e., FROM canonical body_a
            TOWARD canonical body_b. NOTE: this is the OPPOSITE of the
            sign convention stored in `Contact.normal` (which follows
            the rigid-solver convention "pushes body_a away from body_b",
            equivalent to pointing toward body_a). `build_patch` flips
            the sign as needed during averaging; see its docstring.
        r_bar_a, r_bar_b: (3,) lever arms `x̄ - body.position`, each
            clamped to its own body's `r_max` (foundation §7.3).
        weights: (k,) per-contact weights used for averaging. Either the
            rigid solver's λ_N (default) or uniform 1.0.
        r_max_a, r_max_b: lever-arm clamp ceilings actually applied
            (`+inf` for static planes — they don't move so the lever arm
            on them has no dynamic meaning).
    """
    body_a: int
    body_b: int
    contact_indices: tuple[int, ...]
    x_bar: NDArray[np.float64]
    n_rest_bar: NDArray[np.float64]
    r_bar_a: NDArray[np.float64]
    r_bar_b: NDArray[np.float64]
    weights: NDArray[np.float64]
    r_max_a: float
    r_max_b: float


# ----------------------------------------------------------------------
# Clustering
# ----------------------------------------------------------------------


def cluster_contacts_by_body_pair(
    contacts: Sequence[Contact],
) -> list[tuple[int, int, list[int]]]:
    """Group contact indices by `(min(a,b), max(a,b))` (prompt §9.1).

    Returns a list of `(body_a, body_b, [contact_index, ...])` tuples with:
      * `body_a <= body_b` (canonical key — `(2,1)` and `(1,2)` collapse).
      * Outer list sorted by `(body_a, body_b)` for determinism.
      * Inner list preserves the original input order of contact indices.

    The "body pair" is the simplest defensible patch criterion: simultaneous
    contacts on the same pair share both the deforming foundation and the
    receiving rigid body, so averaging their geometry produces a single
    well-defined response point. More elaborate criteria (spatial radius,
    same tet) are §9 step-N-ahead concerns and would replace this function.
    """
    by_pair: dict[tuple[int, int], list[int]] = {}
    for ci, c in enumerate(contacts):
        a, b = c.body_a, c.body_b
        key = (a, b) if a <= b else (b, a)
        by_pair.setdefault(key, []).append(ci)
    return [(a, b, idxs) for (a, b), idxs in sorted(by_pair.items())]


# ----------------------------------------------------------------------
# Lever-arm clamp
# ----------------------------------------------------------------------


def patch_lever_arm_clamp(body: RigidBody) -> float:
    """Default `r_max` for a body, from its collision shape (prompt §9.1).

    BOX   → ‖half_extents‖  (corner radius — the patch centroid can never
                              physically be farther than this from the COM)
    SPHERE→ half_extents[0]  (radius)
    PLANE → +inf             (static; lever arm has no dynamic effect)

    This is a *default*; the caller may pass an explicit `r_max` to
    `build_patch` to override it (e.g., a tighter clamp to attenuate the
    corner-migration feedback loop documented in prompt §1.3 / §7).
    """
    kind = body.shape.kind
    if kind is ShapeType.PLANE:
        return float("inf")
    if kind is ShapeType.SPHERE:
        return float(body.shape.half_extents[0])
    if kind is ShapeType.BOX:
        return float(np.linalg.norm(body.shape.half_extents))
    # Unknown shape: be conservative and don't clamp. A future shape type
    # should add its own branch.
    return float("inf")


def _clamp_length(v: NDArray[np.float64], r_max: float) -> NDArray[np.float64]:
    """Return `v` scaled so its norm ≤ r_max. Pass-through if already inside."""
    if not np.isfinite(r_max):
        return v
    n = float(np.linalg.norm(v))
    if n <= r_max or n == 0.0:
        return v
    return v * (r_max / n)


# ----------------------------------------------------------------------
# Patch construction
# ----------------------------------------------------------------------


def build_patch(
    body_a: int,
    body_b: int,
    contact_idxs: Sequence[int],
    contacts: Sequence[Contact],
    bodies: Sequence[RigidBody],
    weight_mode: str = "lambda_n",
    lambda_n: NDArray[np.float64] | None = None,
    r_max_a: float | None = None,
    r_max_b: float | None = None,
) -> ContactPatch:
    """Build a `ContactPatch` from a cluster of simultaneous contacts.

    Foundation §7.1-7.3 / prompt §7. `(body_a, body_b)` must already be
    in canonical order (`body_a <= body_b`); pass the tuple from
    `cluster_contacts_by_body_pair` directly. Each contact in
    `contact_idxs` is required to share that pair.

    Args:
        body_a, body_b: canonical body pair (`body_a <= body_b`).
        contact_idxs: indices into `contacts` of the contacts in this
            patch. Order is preserved into `ContactPatch.contact_indices`.
        contacts: full step-level contact list.
        bodies: full body list (for COM positions and shape-based r_max).
        weight_mode: "lambda_n" (default) uses the rigid solver's
            per-contact normal impulse as the weight; "uniform" weights
            every contact equally. Other values raise `ValueError`.
        lambda_n: (n_contacts,) per-contact normal impulses from the
            rigid solver. When `weight_mode="lambda_n"`, this is indexed
            by `contact_idxs[j]` to recover this patch's weights. Falls
            back to uniform if `None` (so callers without the solver
            output — e.g., pre-solve introspection — still work).
        r_max_a, r_max_b: explicit lever-arm clamps. When `None`,
            `patch_lever_arm_clamp(body)` is used.

    Notes on weighting and the rest-normal sum:
        * Each contact j contributes `w_j * n_rest_j` to the un-normalized
          n̄' sum. If two contacts on the same pair carry near-antiparallel
          normals (geometrically unusual but possible with thin shells),
          the sum can cancel; we raise `ValueError` rather than emit a
          near-zero unit vector that downstream code would normalize into
          NaN.
        * Weights are clipped to 0 (negative λ_N would indicate a solver
          bug; treat as zero contribution rather than poisoning the
          centroid).

    Returns:
        A frozen `ContactPatch`.
    """
    if not contact_idxs:
        raise ValueError("build_patch: contact_idxs must be non-empty")
    if body_a > body_b:
        raise ValueError(
            f"build_patch: body_a ({body_a}) > body_b ({body_b}); pass the "
            f"canonical pair from cluster_contacts_by_body_pair")
    if weight_mode not in ("lambda_n", "uniform"):
        raise ValueError(
            f"build_patch: unknown weight_mode {weight_mode!r} "
            "(expected 'lambda_n' or 'uniform')")

    # --- Weights ----------------------------------------------------------
    k = len(contact_idxs)
    if weight_mode == "uniform" or lambda_n is None:
        weights = np.ones(k, dtype=np.float64)
    else:
        weights = np.empty(k, dtype=np.float64)
        for j, ci in enumerate(contact_idxs):
            if 3 * ci >= len(lambda_n):
                # Solver vector layout is 3 rows per contact; if the caller
                # passed the raw lam vector, we index lam[3*ci] for λ_N.
                # If the caller already extracted λ_N per contact (length
                # == n_contacts), allow that too.
                if ci >= len(lambda_n):
                    raise ValueError(
                        f"build_patch: lambda_n length {len(lambda_n)} "
                        f"cannot index contact {ci}")
                weights[j] = max(0.0, float(lambda_n[ci]))
            else:
                weights[j] = max(0.0, float(lambda_n[3 * ci]))
        # Degenerate case: all λ_N <= 0 (solver returned zero load). Fall
        # back to uniform so the patch geometry is still well-defined; the
        # zero load itself means the response stage will skip this patch.
        if float(np.sum(weights)) <= 0.0:
            weights = np.ones(k, dtype=np.float64)

    w_sum = float(np.sum(weights))
    # w_sum > 0 by construction (uniform = k; lambda_n falls back above).

    # --- Centroid (foundation §7.1) ---------------------------------------
    x_bar = np.zeros(3, dtype=np.float64)
    for j, ci in enumerate(contact_idxs):
        x_bar += weights[j] * contacts[ci].point
    x_bar /= w_sum

    # --- Averaged rest normal (foundation §7.2) ---------------------------
    # The Contact dataclass's docstring says "normal points from A into B",
    # but the actual collision.py implementations (e.g., _detect_box_plane)
    # store the *rigid solver convention*: the normal that, when paired
    # with λ_N > 0, pushes body_a away from body_b. Equivalently the
    # stored normal points from body_b TOWARD body_a (B → A), not A → B
    # as the docstring suggests. (Verified against the shelf trajectory
    # data: with the docstring reading the patch mode produced inverted
    # push_dir and downward "sticky" kicks.)
    #
    # We re-orient every contact's normal to the canonical A→B direction
    # (from canonical body_a TOWARD canonical body_b), so downstream code
    # (PassiveDCRCoupler._compute_distant_response_patch) can read
    # `n_rest_bar` as "from foundation toward receiver" when the
    # foundation is canonical body_a.
    #
    # Mapping (stored points toward original c.body_a):
    #   c.body_a == canonical body_a (no swap) → stored points toward
    #       canonical body_a = OPPOSITE of canonical A→B → FLIP.
    #   c.body_a == canonical body_b (swap)    → stored points toward
    #       canonical body_b = canonical A→B → KEEP.
    n_sum = np.zeros(3, dtype=np.float64)
    for j, ci in enumerate(contact_idxs):
        c = contacts[ci]
        n_j = -c.normal if c.body_a == body_a else c.normal
        n_sum += weights[j] * n_j
    n_norm = float(np.linalg.norm(n_sum))
    if n_norm < _EPS_NORMAL:
        raise ValueError(
            "build_patch: degenerate normal sum (contacts have "
            "near-antiparallel rest normals); cannot form patch normal")
    n_rest_bar = n_sum / n_norm

    # --- Per-body lever arms (foundation §7.3) ----------------------------
    body_A = bodies[body_a]
    body_B = bodies[body_b]
    rA_max = patch_lever_arm_clamp(body_A) if r_max_a is None else float(r_max_a)
    rB_max = patch_lever_arm_clamp(body_B) if r_max_b is None else float(r_max_b)
    r_bar_a = _clamp_length(x_bar - body_A.position, rA_max)
    r_bar_b = _clamp_length(x_bar - body_B.position, rB_max)

    return ContactPatch(
        body_a=body_a,
        body_b=body_b,
        contact_indices=tuple(contact_idxs),
        x_bar=x_bar,
        n_rest_bar=n_rest_bar,
        r_bar_a=r_bar_a,
        r_bar_b=r_bar_b,
        weights=weights,
        r_max_a=rA_max,
        r_max_b=rB_max,
    )


# ----------------------------------------------------------------------
# §9.4-9.6 helpers: K, λ = K⁻¹ Δv_des, Coulomb projection, passivity
# ----------------------------------------------------------------------


def _skew(r: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return [r]_× — the 3×3 skew matrix satisfying [r]_× · v = r × v."""
    rx, ry, rz = float(r[0]), float(r[1]), float(r[2])
    return np.array([
        [  0.0, -rz,   ry],
        [   rz, 0.0,  -rx],
        [  -ry,  rx,  0.0],
    ], dtype=np.float64)


def patch_effective_mass_matrix(
    body: RigidBody,
    r_bar: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Per-body 3×3 contact-point effective-mass matrix at lever `r_bar`.

    Prompt §4 / foundation §4:
        K = (1/m) I_3 + R · I_world_inv · R^T
        where R = [r̄]_×.

    The mapping K maps an impulse λ ∈ R^3 applied at the patch centroid
    (offset r̄ from the COM) to the resulting change in the body's
    contact-point velocity v_p = v + ω × r̄:
        Δv_p = K · λ.

    Derivation: applying λ to the body produces
        Δv_lin = (1/m) λ,        Δω = I⁻¹ (r̄ × λ),
        Δv_p   = Δv_lin + Δω × r̄
               = (1/m) λ + (I⁻¹ (r̄ × λ)) × r̄.
    Rewriting with R = [r̄]_× (and the identity R^T = -R) gives the form
    above. K is symmetric positive-definite for non-degenerate r̄ / I.

    Static bodies (is_static or infinite mass) get K = 0 — they cannot
    receive contact-point velocity changes; callers must filter these.
    """
    if body.is_static or not np.isfinite(body.mass) or body.mass <= 0.0:
        return np.zeros((3, 3), dtype=np.float64)
    R = _skew(r_bar)
    I_inv = body.inertia_world_inv()
    return (1.0 / body.mass) * np.eye(3) + R @ I_inv @ R.T


def solve_patch_impulse(
    K: NDArray[np.float64],
    dv_des: NDArray[np.float64],
) -> NDArray[np.float64]:
    """λ = K⁻¹ Δv_des (prompt §4). Pure linear-solve wrapper for clarity."""
    return np.linalg.solve(K, dv_des)


def cone_project_impulse(
    lam: NDArray[np.float64],
    n: NDArray[np.float64],
    mu: float,
) -> tuple[NDArray[np.float64], bool]:
    """Coulomb cone projection on the 3-vector impulse `lam` (prompt §5).

        λ_n  = max(0, λ·n)               (non-adhesive normal)
        λ_t  = λ - (λ·n) n               (tangential)
        if ||λ_t|| > μ λ_n:
            λ_t ← μ λ_n · λ_t / ||λ_t||
        λ'   = λ_n n + λ_t

    Returns the projected impulse and a `was_clipped` flag (True if any
    of the three projection steps actually altered λ).

    The function projects in-place semantically; both the normal-clamp
    (λ·n < 0 → λ_n = 0; the support cannot pull the body through it) and
    the tangential clamp count toward `was_clipped`.
    """
    n_unit = n / max(float(np.linalg.norm(n)), 1e-30)
    lam_n_signed = float(lam @ n_unit)
    lam_t_vec = lam - lam_n_signed * n_unit
    lam_n = max(0.0, lam_n_signed)
    clipped = False
    if lam_n_signed < 0.0:
        clipped = True
    lam_t_mag = float(np.linalg.norm(lam_t_vec))
    budget = mu * lam_n
    if lam_t_mag > budget and lam_t_mag > 1e-30:
        lam_t_vec = lam_t_vec * (budget / lam_t_mag)
        clipped = True
    return lam_n * n_unit + lam_t_vec, clipped


def patch_passive_scaling(
    lam: NDArray[np.float64],
    v_p: NDArray[np.float64],
    K: NDArray[np.float64],
    E_cap: float,
) -> tuple[float, float, float]:
    """Passivity scaling `s ∈ [0, 1]` for the patch impulse (prompt §6).

    ΔKE(s·λ) = s·a + ½·s²·b,  with
        a = λ · v_p,
        b = λ · K · λ.

    If ΔKE(λ) > E_cap, scale by s solving s·a + ½·s²·b = E_cap. Positive
    root (prompt §6):
        s = (-a + √(a² + 2·b·E_cap)) / b.
    Clamped to [0, 1] (no inflation; no negation).

    Returns:
        (s, a, b) — the scale and the linear/quadratic coefficients.
        s = 1.0 means passivity was not binding; s < 1.0 means it was.
        a, b are returned so callers can log realized ΔKE = s·a + ½·s²·b.

    Edge cases:
        * b ≈ 0 (degenerate K or zero λ): treat as no-op, s = 1.0.
        * E_cap ≤ 0: kick disallowed entirely, s = 0.0.
        * dE_unscaled = a + ½·b already ≤ E_cap: s = 1.0 (full kick fits).
        * Discriminant negative (only possible if a·E_cap is very
          negative — kick is dissipative *and* E_cap < 0, both nonsensical):
          fall back to s = 0.
    """
    a = float(lam @ v_p)
    b = float(lam @ (K @ lam))
    if b <= 1e-30:
        return 1.0, a, b
    if E_cap <= 0.0:
        return 0.0, a, b
    dE_unscaled = a + 0.5 * b
    if dE_unscaled <= E_cap:
        return 1.0, a, b
    disc = a * a + 2.0 * b * E_cap
    if disc < 0.0:
        return 0.0, a, b
    s = (-a + np.sqrt(disc)) / b
    return float(np.clip(s, 0.0, 1.0)), a, b
