"""SolverImpulse — the velocity-impulse (Schur+PGS, paper Eq. 2/3) native
backend carrying the dynamic modal constraint of
docs/07_17_report/contact_forces.html as extra DOF columns.

Acceptance mirrors the report's evidence sections:
  * statics ledger — settled multipliers ARE the load path (m·g per joint)
  * two-way causality — the stacked cube rings ONLY through the modal network
  * §15 passivity — ledger passive/holds across the network, globally
  * payload mass-loading — the two-way plate pre-sags under the payload
"""
import numpy as np
import pytest

from dcr.avbd._solver.solver_impulse import SolverImpulse


H = 1.0 / 120.0
MG = 0.6 * 9.81   # the cargo-network cube weight


def _settled_normal_force(sv, key0, h_sub):
    """Sum of settled normal multipliers (as force, λ/h) for rows of key0."""
    return sum(float(l) for row, l in zip(sv._last_rows, sv._last_lambda)
               if row.friction_of < 0 and row.key[0] == key0) / h_sub


# ---------------------------------------------------------------------------
# unit level: floor rest + analytic support sag
# ---------------------------------------------------------------------------


def test_floor_rest_statics():
    """Paper Eq. 2/3 baseline: a box rests on the floor; the settled normal
    multipliers carry exactly its weight and the body does not drift."""
    s = SolverImpulse(dt=H, iterations=12, substeps=4)
    b = s.add_box(position=(0.0, 0.05, 0.0), half_extents=(0.05,) * 3,
                  mass=0.6, friction=0.5)
    s.add_floor_contact_box(b, floor_y=0.0, friction=0.5)
    for _ in range(240):
        s.step()
    P, V = s.positions(), s.velocities()
    assert abs(P[0, 1] - 0.05) < 1e-4
    assert np.linalg.norm(V[0]) < 1e-8
    F = _settled_normal_force(s, "f", s.dt / s.substeps)
    assert abs(F - MG) / MG < 1e-3


def test_support_static_sag_analytic():
    """One mass-normalized mode, uniform U_y = 1: static equilibrium is
    K·q = −m·g (foundation 'contact as a constraint on (z,q)'), and the body
    rides the deformed surface y_rest + U_y·q — the same gap function as the
    report §1, solved at velocity level."""
    om = 2 * np.pi * 10.0
    s = SolverImpulse(dt=H, iterations=12, substeps=4)
    b = s.add_box(position=(0.0, 0.15, 0.0), half_extents=(0.05,) * 3,
                  mass=0.6, friction=0.5)
    s.set_modal_support(np.eye(1), np.diag([om * om]),
                        np.diag([2 * 0.01 * om]))
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                s.add_support_contact_corner(
                    b, (sx * 0.05, sy * 0.05, sz * 0.05), 0.10,
                    np.array([1.0]), friction=0.5)
    for _ in range(480):
        s.step()
    q = float(s.modal_q[0])
    q_expect = -MG / (om * om)
    assert abs(q - q_expect) < 1e-6 * max(1.0, abs(q_expect))
    # body sits ON the deformed surface: y = y_rest + q + half
    assert abs(s.positions()[0, 1] - (0.10 + q + 0.05)) < 1e-4
    F = _settled_normal_force(s, "s", s.dt / s.substeps)
    assert abs(F - MG) / MG < 1e-3
    assert s._psv_ledger.passive() and s._psv_ledger.holds()


# ---------------------------------------------------------------------------
# scene level: the §N2 cargo network on the impulse backend
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cargo_net_on():
    from scenes.reduced_cargo_network import build_cargo_network_scene
    hdl = build_cargo_network_scene(network=True, solver="impulse")
    peak_a_upper = 0.0
    sv = hdl.world._solver
    iu = hdl.avbd_idx["upper"]
    for _ in range(360):                       # 3 s — impact + settle
        hdl.world.step()
        peak_a_upper = max(peak_a_upper,
                           float(np.linalg.norm(sv.cargo_a(iu))))
    return hdl, peak_a_upper


def test_stack_statics_ledger(cargo_net_on):
    """Report 'The static ledger is exact': every joint of the settled stack
    carries the weight above it, read straight off the multipliers — adding
    modal columns did not corrupt statics. Tolerance 3% (PGS at the demo's
    12×4 budget)."""
    hdl, _ = cargo_net_on
    sv = hdl.world._solver
    h_sub = sv.dt / sv.substeps
    idx = hdl.avbd_idx
    rows = list(zip(sv._last_rows, sv._last_lambda))

    def joint_force(pred):
        return sum(float(l) for r, l in rows
                   if r.friction_of < 0 and pred(r)) / h_sub

    # resting cube → slab: m·g
    F_rest = joint_force(lambda r: r.key[0] == "s"
                         and sv._support[r.key[1]].bi == idx["resting"])
    # base cube → slab: 3·m·g (base + mid + upper)
    F_base = joint_force(lambda r: r.key[0] == "s"
                         and sv._support[r.key[1]].bi == idx["base"])
    # box-box joints: base↔mid = 2·m·g, mid↔upper = m·g
    F_bm = joint_force(lambda r: r.key[0] == "bb"
                       and {r.key[1], r.key[2]} == {idx["base"], idx["mid"]})
    F_mu = joint_force(lambda r: r.key[0] == "bb"
                       and {r.key[1], r.key[2]} == {idx["mid"], idx["upper"]})
    assert abs(F_rest - MG) / MG < 0.03
    assert abs(F_base - 3 * MG) / (3 * MG) < 0.03
    assert abs(F_bm - 2 * MG) / (2 * MG) < 0.03
    assert abs(F_mu - MG) / MG < 0.03
    # the stack is still standing
    X = sv.positions()
    assert abs(X[idx["mid"], 1] - 0.15) < 5e-3
    assert abs(X[idx["upper"], 1] - 0.25) < 5e-3


def test_network_causality_on_off(cargo_net_on):
    """Report 'it is genuinely two-way': upper touches only mid — two box-box
    hops from the slab. Network ON it rings; OFF its amplitude is identically
    zero. The ring reached it purely through the shared rows."""
    _, peak_on = cargo_net_on
    assert peak_on > 1e-6

    from scenes.reduced_cargo_network import build_cargo_network_scene
    hdl = build_cargo_network_scene(network=False, solver="impulse")
    sv = hdl.world._solver
    iu = hdl.avbd_idx["upper"]
    peak_off = 0.0
    for _ in range(360):
        hdl.world.step()
        peak_off = max(peak_off, float(np.linalg.norm(sv.cargo_a(iu))))
    assert peak_off == 0.0
    X = sv.positions()
    assert abs(X[hdl.avbd_idx["upper"], 1] - 0.25) < 5e-3


def test_passivity_ledger_network(cargo_net_on):
    """Foundation §15, enforced globally across the network: cumulative
    E_modal gain ≤ η·cumulative rigid loss, and peak modal energy never
    exceeds initial + η·Σloss (reservoir form). Asserted across the FULL run,
    not sampled (CLAUDE.md rule 7)."""
    hdl, _ = cargo_net_on
    led = hdl.world._solver._psv_ledger
    assert led.n_steps == 360 * hdl.world._solver.substeps
    assert led.holds()
    assert led.passive()


# ---------------------------------------------------------------------------
# payload mass-loading (the report's live A/B) — two-way pre-sag
# ---------------------------------------------------------------------------


def test_payload_two_way_presag():
    """Report 'payload mass-loading A/B': with the payload IN the plate's
    contact rows (two-way) the plate pre-sags under its weight BEFORE the
    impactor arrives; the one-way (uncoupled) plate stays flat. Sag, detune,
    and damping are back-reaction — they require the shared row."""
    from scenes.payload_plate import build_payload_plate_scene

    def presag(coupled):
        hdl = build_payload_plate_scene(coupled=coupled, solver="impulse")
        sv = hdl.world._solver
        rs = hdl.rs
        for _ in range(110):                    # settle, before impact
            hdl.world.step()
        rs.q[:] = sv.modal_q
        return float(rs.probe_U[0, 1, :] @ rs.q)

    sag_two_way = presag(True)
    sag_one_way = presag(False)
    assert sag_two_way < -2e-3          # ≥ 2 mm pre-sag under the payload
    assert abs(sag_one_way) < 0.2 * abs(sag_two_way)
