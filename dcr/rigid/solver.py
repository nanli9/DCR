"""Constraint solver for rigid body dynamics.

Implements the Schur-complement formulation (paper Eq. 2) and
Projected Gauss-Seidel (PGS) for the BLCP (paper Eq. 3).
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .body import RigidBody
from .collision import Contact


def _skew(v: NDArray[np.float64]) -> NDArray[np.float64]:
    """Skew-symmetric matrix [v]_x such that [v]_x @ w = cross(v, w)."""
    return np.array([
        [0, -v[2], v[1]],
        [v[2], 0, -v[0]],
        [-v[1], v[0], 0],
    ])


def build_contact_jacobian_row(contact: Contact,
                               bodies: list[RigidBody],
                               direction: NDArray[np.float64]
                               ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Build the 1x6 Jacobian blocks for one constraint direction.

    For a contact between body A and body B with direction d (normal or friction):
        J_A = [ d^T,   (r_A x d)^T]   (1x6)
        J_B = [-d^T,  -(r_B x d)^T]   (1x6)

    Gives J*v = d · (v_A_contact - v_B_contact), positive when separating.

    # DEVIATION: contact normal points from B toward A (outward from contact
    # surface), not "from A into B" as stated in the paper. The physics is
    # identical; this convention is more common in physics engines and means
    # lambda > 0 pushes A in the +normal direction (away from B).

    Returns (J_A, J_B) each of shape (6,).
    """
    body_a = bodies[contact.body_a]
    body_b = bodies[contact.body_b]
    r_a = contact.point - body_a.position  # lever arm for A
    r_b = contact.point - body_b.position  # lever arm for B

    J_a = np.zeros(6)
    J_a[0:3] = direction
    J_a[3:6] = np.cross(r_a, direction)

    J_b = np.zeros(6)
    J_b[0:3] = -direction
    J_b[3:6] = -np.cross(r_b, direction)

    return J_a, J_b


def _pick_friction_dirs(normal: NDArray[np.float64]
                        ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return two orthonormal tangent vectors to the contact normal."""
    if abs(normal[1]) < 0.9:
        t1 = np.cross(normal, np.array([0.0, 1.0, 0.0]))
    else:
        t1 = np.cross(normal, np.array([1.0, 0.0, 0.0]))
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(normal, t1)
    t2 /= np.linalg.norm(t2)
    return t1, t2


class ConstraintSolver:
    """Build and solve the Schur-complement BLCP for one time step.

    Paper Eq. 2:
        A = (1/h^2) * cfm * I  +  J * M_inv * J^T
        b = -(erp/h) * phi  -  J * M_inv * (M * v + h * f)

    Paper Eq. 3 (BLCP):
        A * lambda - b = w
        with box bounds on lambda, complementarity on w.

    Paper Eq. 4 (restitution):
        For new contacts: b_i -= restitution * J_row_i @ v
    """

    def __init__(self, h: float = 1e-2, cfm: float = 1e-6,
                 erp: float = 0.2, pgs_iterations: int = 50):
        self.h = h
        # DEVIATION: The paper's (1/h^2)*cfm term is timestep-dependent.
        # We store cfm as defined at h_ref=1e-2 and scale it so the effective
        # regularization cfm_eff = cfm * (h/h_ref)^2 is timestep-invariant.
        self._cfm_ref = cfm
        self._h_ref = 1e-2
        self.erp = erp
        self.pgs_iterations = pgs_iterations
        # Warm-starting: cache previous step's lambda and contact keys.
        self._prev_lambda: dict[tuple, float] = {}

    @property
    def cfm(self) -> float:
        """Effective CFM scaled for current timestep."""
        return self._cfm_ref * (self.h / self._h_ref) ** 2

    @staticmethod
    def _contact_key(c: Contact, row_type: int) -> tuple:
        """Create a hashable key for a constraint row.

        row_type: 0=normal, 1=friction1, 2=friction2.
        """
        # Round point to grid for matching across steps
        px = round(c.point[0], 3)
        py = round(c.point[1], 3)
        pz = round(c.point[2], 3)
        return (min(c.body_a, c.body_b), max(c.body_a, c.body_b),
                px, py, pz, row_type)

    def solve(self, bodies: list[RigidBody], contacts: list[Contact]
              ) -> NDArray[np.float64]:
        """Solve for constraint impulses and update body velocities.

        Returns the solved lambda vector (for diagnostics / DCR coupling).
        """
        if not contacts:
            # No contacts — just apply forces.
            for body in bodies:
                if body.is_static:
                    continue
                M_inv = body.mass_matrix_inv()
                body.velocity += self.h * M_inv @ body.force
            return np.array([])

        n_bodies = len(bodies)
        n_contacts = len(contacts)
        # 3 rows per contact: 1 normal + 2 friction
        n_constraints = 3 * n_contacts

        # --- Pre-compute per-body inverse mass matrices ---
        M_inv_list: list[NDArray[np.float64]] = []
        for body in bodies:
            if body.is_static:
                M_inv_list.append(np.zeros((6, 6)))
            else:
                M_inv_list.append(body.mass_matrix_inv())

        # --- Build full Jacobian J (n_constraints x 6*n_bodies) ---
        # and RHS vectors phi, restitution modifications.
        # Instead of the huge dense J, work with per-constraint sparse blocks.

        # For each constraint row: store (body_a_idx, J_a, body_b_idx, J_b)
        # Also build the diagonal of A and the off-diagonal couplings.

        # We'll build A and b directly in dense form for the BLCP.
        # A = (1/h^2)*cfm*I + J * M_inv * J^T   (Eq. 2)
        # This is n_constraints x n_constraints, manageable for < ~1000 contacts.

        J_blocks: list[tuple[int, NDArray[np.float64], int, NDArray[np.float64]]] = []
        constraint_keys: list[tuple] = []  # for warm-starting
        phi = np.zeros(n_constraints)
        restitution_rhs = np.zeros(n_constraints)
        lo = np.zeros(n_constraints)
        hi = np.full(n_constraints, np.inf)
        # Map: friction row index -> which normal row it depends on
        friction_normal_map: list[int] = [-1] * n_constraints
        friction_mu: list[float] = [0.0] * n_constraints

        for ci, contact in enumerate(contacts):
            row_n = 3 * ci       # normal row
            row_f1 = 3 * ci + 1  # friction row 1
            row_f2 = 3 * ci + 2  # friction row 2

            # --- Normal constraint ---
            J_a_n, J_b_n = build_contact_jacobian_row(
                contact, bodies, contact.normal)
            J_blocks.append((contact.body_a, J_a_n, contact.body_b, J_b_n))
            constraint_keys.append(self._contact_key(contact, 0))

            # phi is the signed gap: negative when penetrating (paper convention).
            # contact.penetration is positive when overlapping, so negate it.
            phi[row_n] = -contact.penetration

            # Normal bounds: lambda_N >= 0
            lo[row_n] = 0.0
            hi[row_n] = np.inf

            # Restitution (Eq. 4): for new impacting contacts
            if contact.is_new:
                # Pre-collision relative velocity in normal direction
                v_a = bodies[contact.body_a].velocity
                v_b = bodies[contact.body_b].velocity
                v_rel_n = J_a_n @ v_a + J_b_n @ v_b
                # Only apply restitution if approaching (v_rel_n < 0)
                if v_rel_n < -1e-4:
                    eps_r = max(bodies[contact.body_a].restitution,
                                bodies[contact.body_b].restitution)
                    restitution_rhs[row_n] = -eps_r * (J_a_n @ v_a + J_b_n @ v_b)

            # --- Friction constraints ---
            t1, t2 = _pick_friction_dirs(contact.normal)
            mu = min(bodies[contact.body_a].friction,
                     bodies[contact.body_b].friction)

            J_a_f1, J_b_f1 = build_contact_jacobian_row(contact, bodies, t1)
            J_blocks.append((contact.body_a, J_a_f1, contact.body_b, J_b_f1))
            constraint_keys.append(self._contact_key(contact, 1))
            phi[row_f1] = 0.0
            friction_normal_map[row_f1] = row_n
            friction_mu[row_f1] = mu

            J_a_f2, J_b_f2 = build_contact_jacobian_row(contact, bodies, t2)
            J_blocks.append((contact.body_a, J_a_f2, contact.body_b, J_b_f2))
            constraint_keys.append(self._contact_key(contact, 2))
            phi[row_f2] = 0.0
            friction_normal_map[row_f2] = row_n
            friction_mu[row_f2] = mu

        # --- Build A and b (Eq. 2) ---
        # A_ij = (1/h^2)*cfm*delta_ij + sum_body( J_i_body * M_inv_body * J_j_body^T )
        # b_i = -(erp/h)*phi_i - sum_body( J_i_body * M_inv_body * (M_body * v_body + h * f_body) )

        A = np.zeros((n_constraints, n_constraints))
        b = np.zeros(n_constraints)
        h = self.h

        # Precompute M_inv * J^T columns and the momentum term per body
        # For efficiency, compute A = J * M_inv * J^T by iterating over bodies
        # that appear in constraints.

        # Gather which constraint rows touch each body.
        body_rows: dict[int, list[tuple[int, NDArray[np.float64]]]] = {}
        for row_idx, (ba, Ja, bb, Jb) in enumerate(J_blocks):
            if not bodies[ba].is_static:
                body_rows.setdefault(ba, []).append((row_idx, Ja))
            if not bodies[bb].is_static:
                body_rows.setdefault(bb, []).append((row_idx, Jb))

        for body_idx, rows in body_rows.items():
            M_inv = M_inv_list[body_idx]
            for i, (ri, Ji) in enumerate(rows):
                MiJi = M_inv @ Ji  # (6,)
                for j in range(i, len(rows)):
                    rj, Jj = rows[j]
                    val = Ji @ (M_inv @ Jj)
                    A[ri, rj] += val
                    if ri != rj:
                        A[rj, ri] += val

        # Add CFM regularization (Eq. 2)
        A += (1.0 / h**2) * self.cfm * np.eye(n_constraints)

        # Build b (Eq. 2)
        for row_idx, (ba, Ja, bb, Jb) in enumerate(J_blocks):
            body_a = bodies[ba]
            body_b = bodies[bb]

            # J_row * M_inv * (M * v + h * f) for body A
            if not body_a.is_static:
                momentum_a = body_a.mass_matrix() @ body_a.velocity + h * body_a.force
                b[row_idx] -= Ja @ (M_inv_list[ba] @ momentum_a)

            if not body_b.is_static:
                momentum_b = body_b.mass_matrix() @ body_b.velocity + h * body_b.force
                b[row_idx] -= Jb @ (M_inv_list[bb] @ momentum_b)

        # ERP stabilization
        b -= (self.erp / h) * phi

        # Restitution (Eq. 4)
        b += restitution_rhs

        # --- PGS solve (Eq. 3) with warm-starting ---
        lam = np.zeros(n_constraints)
        for row_idx, key in enumerate(constraint_keys):
            if key in self._prev_lambda:
                lam[row_idx] = self._prev_lambda[key]
        lam = self._pgs(A, b, lam, lo, hi, friction_normal_map, friction_mu)

        # Cache lambda for warm-starting next step.
        self._prev_lambda = {}
        for row_idx, key in enumerate(constraint_keys):
            self._prev_lambda[key] = float(lam[row_idx])

        # --- Velocity update: v+ = v + h * M_inv * f + M_inv * J^T * lambda  (Eq. 1, row 1) ---
        # Accumulate J^T * lambda per body first
        jt_lam: dict[int, NDArray[np.float64]] = {}
        for row_idx, (ba, Ja, bb, Jb) in enumerate(J_blocks):
            li = lam[row_idx]
            if not bodies[ba].is_static:
                if ba not in jt_lam:
                    jt_lam[ba] = np.zeros(6)
                jt_lam[ba] += Ja * li
            if not bodies[bb].is_static:
                if bb not in jt_lam:
                    jt_lam[bb] = np.zeros(6)
                jt_lam[bb] += Jb * li

        for body_idx, body in enumerate(bodies):
            if body.is_static:
                continue
            M_inv = M_inv_list[body_idx]
            dv = h * M_inv @ body.force
            if body_idx in jt_lam:
                dv += M_inv @ jt_lam[body_idx]
            body.velocity += dv

        return lam

    def _pgs(self, A: NDArray[np.float64], b: NDArray[np.float64],
             lam: NDArray[np.float64],
             lo: NDArray[np.float64], hi: NDArray[np.float64],
             friction_normal_map: list[int],
             friction_mu: list[float]) -> NDArray[np.float64]:
        """Projected Gauss-Seidel for the BLCP (Eq. 3).

        For each row i:
            lambda_i = (b_i - sum_{j!=i} A_ij * lambda_j) / A_ii
            lambda_i = clamp(lambda_i, lo_i, hi_i)

        Friction bounds are updated dynamically:
            lo = -mu * lambda_N,  hi = +mu * lambda_N
        """
        n = len(lam)
        diag = A.diagonal().copy()
        diag_inv = np.where(np.abs(diag) > 1e-30, 1.0 / diag, 0.0)
        fnm = np.array(friction_normal_map, dtype=np.int64)
        fmu = np.array(friction_mu, dtype=np.float64)

        for _ in range(self.pgs_iterations):
            for i in range(n):
                # Update friction bounds based on current normal lambda
                if fnm[i] >= 0:
                    lam_n = lam[fnm[i]]
                    lo[i] = -fmu[i] * lam_n
                    hi[i] = fmu[i] * lam_n

                # GS update: b[i] - A[i,:] @ lam + A[i,i] * lam[i]
                residual = b[i] - A[i] @ lam + diag[i] * lam[i]
                lam[i] = np.clip(residual * diag_inv[i], lo[i], hi[i])

        return lam
