"""Collision detection for Stage 1.

Supports: sphere-plane, box-plane, sphere-sphere.
Contact normals point from body A into body B (paper convention: lambda_N >= 0).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .body import RigidBody, ShapeType


@dataclass
class Contact:
    """A single contact point between two bodies.

    Attributes:
        body_a: index of body A in the world body list.
        body_b: index of body B in the world body list.
        point: (3,) world-space contact point.
        normal: (3,) unit normal pointing from A into B.
        penetration: signed penetration depth (positive = overlapping).
        is_new: True if this contact did not exist last step (for restitution).
    """
    body_a: int
    body_b: int
    point: NDArray[np.float64]
    normal: NDArray[np.float64]
    penetration: float
    is_new: bool = True


def _detect_sphere_plane(idx_sphere: int, sphere: RigidBody,
                         idx_plane: int, plane: RigidBody) -> list[Contact]:
    """Sphere vs infinite plane."""
    radius = sphere.shape.half_extents[0]
    plane_normal = plane.shape.half_extents.copy()  # unit normal stored here
    plane_point = plane.position

    # Signed distance from sphere center to plane
    dist = np.dot(sphere.position - plane_point, plane_normal) - radius
    if dist > 0.0:
        return []

    contact_point = sphere.position - plane_normal * (radius + dist * 0.5)
    # Normal points from sphere (A) into plane (B) — but plane is "below",
    # so normal should push sphere upward. Convention: normal from A to B.
    # Since the plane is body B and we want normal pointing into B's surface,
    # the normal is the plane normal (pointing away from plane toward sphere).
    # Actually: normal points from A into B. A=sphere, B=plane.
    # The plane's outward normal points toward the sphere.
    # "Into B" = into the plane = opposite of plane normal.
    # But lambda_N >= 0 should push bodies apart, so:
    #   impulse on A = +J^T * lambda = +normal * lambda (pushes A away from B)
    #   impulse on B = -J^T * lambda = -normal * lambda (pushes B away from A)
    # For sphere above plane: normal = plane_normal (pointing up) means
    # lambda > 0 pushes sphere up — correct.
    return [Contact(
        body_a=idx_sphere,
        body_b=idx_plane,
        point=contact_point,
        normal=plane_normal.copy(),
        penetration=-dist,
    )]


def _detect_box_plane(idx_box: int, box: RigidBody,
                      idx_plane: int, plane: RigidBody) -> list[Contact]:
    """Box vs infinite plane. Up to 4 contacts (one per penetrating corner)."""
    hx, hy, hz = box.shape.half_extents
    R = box.rotation_matrix()
    plane_normal = plane.shape.half_extents.copy()
    plane_point = plane.position

    # 8 corners in body frame
    corners_body = np.array([
        [-hx, -hy, -hz],
        [+hx, -hy, -hz],
        [+hx, +hy, -hz],
        [-hx, +hy, -hz],
        [-hx, -hy, +hz],
        [+hx, -hy, +hz],
        [+hx, +hy, +hz],
        [-hx, +hy, +hz],
    ])

    contacts = []
    for corner_b in corners_body:
        corner_w = box.position + R @ corner_b
        dist = np.dot(corner_w - plane_point, plane_normal)
        if dist < 0.0:
            contact_point = corner_w - plane_normal * (dist * 0.5)
            contacts.append(Contact(
                body_a=idx_box,
                body_b=idx_plane,
                point=contact_point,
                normal=plane_normal.copy(),
                penetration=-dist,
            ))
    return contacts


def _detect_sphere_sphere(idx_a: int, a: RigidBody,
                          idx_b: int, b: RigidBody) -> list[Contact]:
    """Sphere vs sphere."""
    ra = a.shape.half_extents[0]
    rb = b.shape.half_extents[0]
    diff = b.position - a.position
    dist = np.linalg.norm(diff)
    overlap = ra + rb - dist
    if overlap <= 0.0:
        return []

    if dist < 1e-12:
        normal = np.array([0.0, 1.0, 0.0])
    else:
        normal = diff / dist  # from A toward B

    contact_point = a.position + normal * (ra - overlap * 0.5)
    return [Contact(
        body_a=idx_a,
        body_b=idx_b,
        point=contact_point,
        normal=normal,
        penetration=overlap,
    )]


def _detect_box_sphere(idx_box: int, box: RigidBody,
                       idx_sphere: int, sphere: RigidBody) -> list[Contact]:
    """Box vs sphere. Find closest point on OBB to sphere center."""
    R = box.rotation_matrix()
    hx, hy, hz = box.shape.half_extents
    half = np.array([hx, hy, hz])

    # Sphere center in box local frame
    d = sphere.position - box.position
    local = R.T @ d

    # Clamp to box
    closest_local = np.clip(local, -half, half)
    closest_world = box.position + R @ closest_local

    diff = sphere.position - closest_world
    dist = np.linalg.norm(diff)
    radius = sphere.shape.half_extents[0]

    if dist > radius:
        return []

    if dist < 1e-12:
        # Sphere center inside box — use the axis of least penetration
        # to push sphere out
        pen_axes = half - np.abs(local)
        axis = int(np.argmin(pen_axes))
        normal_local = np.zeros(3)
        normal_local[axis] = 1.0 if local[axis] >= 0 else -1.0
        normal = R @ normal_local
        penetration = pen_axes[axis] + radius
    else:
        normal = diff / dist  # from box toward sphere
        penetration = radius - dist

    # Normal from A (box) into B (sphere)
    contact_point = closest_world + normal * (penetration * 0.5)
    return [Contact(
        body_a=idx_box,
        body_b=idx_sphere,
        point=contact_point,
        normal=normal,
        penetration=penetration,
    )]


def _detect_box_box(idx_a: int, a: RigidBody,
                    idx_b: int, b: RigidBody,
                    margin: float = 1e-3) -> list[Contact]:
    """Box vs box using SAT (Separating Axis Theorem).

    Tests 15 axes. Biases toward face normals for stability. Uses a small
    contact margin to maintain contacts at near-touching configurations.
    """
    Ra = a.rotation_matrix()
    Rb = b.rotation_matrix()
    ha = a.shape.half_extents
    hb = b.shape.half_extents
    d = b.position - a.position  # vector from A center to B center

    axes_a = [Ra[:, i] for i in range(3)]
    axes_b = [Rb[:, i] for i in range(3)]

    # Track best face-normal axis and best overall axis separately.
    # Prefer face normals for contact normal selection (more stable).
    min_face_overlap = np.inf
    best_face_axis = np.zeros(3)
    min_edge_overlap = np.inf

    def _overlap_on_axis(axis: NDArray[np.float64]) -> float:
        length = np.linalg.norm(axis)
        if length < 1e-10:
            return np.inf  # degenerate — treat as non-separating
        axis = axis / length
        proj_a = sum(ha[i] * abs(np.dot(axes_a[i], axis)) for i in range(3))
        proj_b = sum(hb[i] * abs(np.dot(axes_b[i], axis)) for i in range(3))
        return proj_a + proj_b - abs(np.dot(d, axis))

    def _orient_normal(axis: NDArray[np.float64]) -> NDArray[np.float64]:
        """Orient normal to point from B toward A."""
        n = axis / np.linalg.norm(axis)
        if np.dot(d, n) > 0:
            return -n
        return n

    # Test 6 face normals
    for ax in axes_a + axes_b:
        ov = _overlap_on_axis(ax)
        if ov < -margin:
            return []  # separated
        if ov < min_face_overlap:
            min_face_overlap = ov
            best_face_axis = _orient_normal(ax)

    # Test 9 edge-edge cross products (separation only; don't use for normal)
    for i in range(3):
        for j in range(3):
            edge_ax = np.cross(axes_a[i], axes_b[j])
            ov = _overlap_on_axis(edge_ax)
            if ov < -margin:
                return []
            min_edge_overlap = min(min_edge_overlap, ov)

    # Use face normal (robust for stacking; edge normals cause jitter).
    normal = best_face_axis
    penetration = max(0.0, min(min_face_overlap, min_edge_overlap))

    # Generate contact points: project corners of each box onto the contact
    # plane and keep those inside the other box's footprint.
    contacts = []

    def _corners_of(body: RigidBody) -> NDArray[np.float64]:
        R = body.rotation_matrix()
        he = body.shape.half_extents
        signs = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                          [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]], dtype=np.float64)
        return body.position + (R @ (signs * he).T).T

    def _signed_dist_to_obb_face(point: NDArray[np.float64],
                                 body: RigidBody, face_normal: NDArray[np.float64]) -> float:
        """Signed distance along normal from point to the closest face of the OBB."""
        R = body.rotation_matrix()
        he = body.shape.half_extents
        local = R.T @ (point - body.position)
        # Check if within the tangential footprint (with tolerance)
        for ax in range(3):
            ax_dir = R[:, ax]
            if abs(np.dot(ax_dir, face_normal)) > 0.9:
                continue  # this is the normal axis, skip
            if abs(local[ax]) > he[ax] + margin:
                return np.inf  # outside footprint
        # Signed distance along normal
        return np.dot(point - body.position, face_normal) - \
               sum(he[i] * abs(np.dot(R[:, i], face_normal)) for i in range(3))

    # Corners of B closest to A along normal
    corners_b = _corners_of(b)
    for corner in corners_b:
        # Check if this corner is "under" box A (within footprint)
        sd = _signed_dist_to_obb_face(corner, a, -normal)
        if sd < margin:
            cp = corner - normal * (sd * 0.5) if sd < 0 else corner
            contacts.append(Contact(
                body_a=idx_a, body_b=idx_b,
                point=cp, normal=normal.copy(),
                penetration=penetration,
            ))

    # Corners of A closest to B along normal
    corners_a = _corners_of(a)
    for corner in corners_a:
        sd = _signed_dist_to_obb_face(corner, b, normal)
        if sd < margin:
            cp = corner + normal * (sd * 0.5) if sd < 0 else corner
            contacts.append(Contact(
                body_a=idx_a, body_b=idx_b,
                point=cp, normal=normal.copy(),
                penetration=penetration,
            ))

    if not contacts:
        mid = 0.5 * (a.position + b.position)
        contacts.append(Contact(
            body_a=idx_a, body_b=idx_b,
            point=mid, normal=normal.copy(),
            penetration=penetration,
        ))

    # Keep at most 4 contacts (spread them out for stability)
    if len(contacts) > 4:
        contacts = contacts[:4]

    return contacts


def detect_contacts(bodies: list[RigidBody],
                    prev_contacts: list[Contact] | None = None,
                    tolerance: float = 0.01) -> list[Contact]:
    """Broad + narrow phase collision detection.

    Marks contacts as is_new=False if a similar contact existed in prev_contacts
    (within spatial tolerance). This is needed for restitution (Eq. 4).
    """
    contacts: list[Contact] = []
    n = len(bodies)

    for i in range(n):
        for j in range(i + 1, n):
            a, b = bodies[i], bodies[j]
            ka, kb = a.shape.kind, b.shape.kind

            new_contacts: list[Contact] = []

            if ka == ShapeType.SPHERE and kb == ShapeType.PLANE:
                new_contacts = _detect_sphere_plane(i, a, j, b)
            elif ka == ShapeType.PLANE and kb == ShapeType.SPHERE:
                new_contacts = _detect_sphere_plane(j, b, i, a)
            elif ka == ShapeType.BOX and kb == ShapeType.PLANE:
                new_contacts = _detect_box_plane(i, a, j, b)
            elif ka == ShapeType.PLANE and kb == ShapeType.BOX:
                new_contacts = _detect_box_plane(j, b, i, a)
            elif ka == ShapeType.SPHERE and kb == ShapeType.SPHERE:
                new_contacts = _detect_sphere_sphere(i, a, j, b)
            elif ka == ShapeType.BOX and kb == ShapeType.SPHERE:
                new_contacts = _detect_box_sphere(i, a, j, b)
            elif ka == ShapeType.SPHERE and kb == ShapeType.BOX:
                new_contacts = _detect_box_sphere(j, b, i, a)
            elif ka == ShapeType.BOX and kb == ShapeType.BOX:
                new_contacts = _detect_box_box(i, a, j, b)

            contacts.extend(new_contacts)

    # Mark resting contacts (existed in previous step)
    if prev_contacts is not None:
        for c in contacts:
            for pc in prev_contacts:
                if ({c.body_a, c.body_b} == {pc.body_a, pc.body_b}
                        and np.linalg.norm(c.point - pc.point) < tolerance):
                    c.is_new = False
                    break

    return contacts
