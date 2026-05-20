"""Stage 4 acceptance tests — IIR modal stepper (Eq. 10).

Criteria from dcr_implementation_prompt.md §4.4:
1. Unit impulse on a single mode produces a decaying sinusoid at the correct
   frequency ω_j and damping ratio implied by Rayleigh (α₀, α₁).
2. Sum of two modes excited simultaneously equals the sum of their individual
   responses (linearity check).
"""
import numpy as np

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis, IIRModalStepper


def _make_damped_table() -> ModalAnalysis:
    """Paper table with Rayleigh damping: α₀=2, α₁=1e-5."""
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    tol = 1e-8
    x_min, x_max = mesh.vertices[:, 0].min(), mesh.vertices[:, 0].max()
    z_min, z_max = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    on_xmin = np.abs(mesh.vertices[:, 0] - x_min) < tol
    on_xmax = np.abs(mesh.vertices[:, 0] - x_max) < tol
    on_zmin = np.abs(mesh.vertices[:, 2] - z_min) < tol
    on_zmax = np.abs(mesh.vertices[:, 2] - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)

    model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                     alpha0=2.0, alpha1=1e-5)
    return ModalAnalysis(fem=model, num_modes=10)


# ---------------------------------------------------------------------------
# Test 1: Impulse response on a single mode — correct frequency and decay
# ---------------------------------------------------------------------------
def test_single_mode_impulse_response():
    """A unit impulse on mode j should produce a decaying sinusoid at ω_d,j
    with envelope exp(-ξ_j ω_j t).
    """
    ma = _make_damped_table()
    stepper = IIRModalStepper(modal=ma)

    mode_j = 0
    omega_j = ma.frequencies[mode_j]
    xi_j = stepper.xi[mode_j]
    omega_d = omega_j * np.sqrt(1.0 - xi_j**2)

    print(f"  Mode {mode_j}: ω={omega_j:.2f}, ξ={xi_j:.6f}, ω_d={omega_d:.2f}")
    print(f"  Sub-step T={stepper.T:.2e} s")

    # Impulse on mode j only.
    r = np.zeros(ma.num_modes, dtype=np.float64)
    r[mode_j] = 1.0

    n_steps = 2000
    q_hist = stepper.step_n(n_steps, r=r)

    # Extract mode j response.
    q_j = q_hist[:, mode_j]
    t = np.arange(1, n_steps + 1) * stepper.T

    # --- Frequency check ---
    # Find zero crossings to measure period.
    crossings = np.where(np.diff(np.sign(q_j)))[0]
    if len(crossings) >= 4:
        # Average half-period from consecutive crossings.
        half_periods = np.diff(crossings) * stepper.T
        avg_period = 2.0 * np.mean(half_periods)
        measured_omega = 2.0 * np.pi / avg_period
        freq_err = abs(measured_omega - omega_d) / omega_d
        print(f"  Measured ω_d={measured_omega:.2f}, expected={omega_d:.2f}, "
              f"rel err={freq_err:.4f}")
        assert freq_err < 0.05, f"Frequency error {freq_err:.4f} > 5%"
    else:
        # Heavily damped — fewer crossings, just check decay.
        print("  Too few crossings for frequency measurement (heavily damped)")

    # --- Decay envelope check ---
    # Peak amplitudes should follow exp(-ξ ω t).
    peaks_idx = []
    for i in range(1, len(q_j) - 1):
        if abs(q_j[i]) > abs(q_j[i - 1]) and abs(q_j[i]) > abs(q_j[i + 1]):
            peaks_idx.append(i)

    if len(peaks_idx) >= 3:
        peak_times = t[peaks_idx]
        peak_amps = np.abs(q_j[peaks_idx])
        # Fit log(amplitude) vs time → slope should be -ξ ω.
        coeffs = np.polyfit(peak_times, np.log(peak_amps + 1e-30), 1)
        measured_decay = -coeffs[0]
        expected_decay = xi_j * omega_j
        decay_err = abs(measured_decay - expected_decay) / (expected_decay + 1e-12)
        print(f"  Decay rate: measured={measured_decay:.2f}, "
              f"expected={expected_decay:.2f}, rel err={decay_err:.4f}")
        assert decay_err < 0.10, f"Decay rate error {decay_err:.4f} > 10%"

    # Other modes should remain near zero (not excited).
    for j in range(ma.num_modes):
        if j == mode_j:
            continue
        assert np.max(np.abs(q_hist[:, j])) < 1e-10, (
            f"Mode {j} unexpectedly excited: max={np.max(np.abs(q_hist[:, j])):.2e}"
        )


# ---------------------------------------------------------------------------
# Test 2: Linearity — sum of two individual impulses equals combined
# ---------------------------------------------------------------------------
def test_linearity():
    """Exciting modes 0 and 1 simultaneously should equal the sum of
    exciting each individually.
    """
    ma = _make_damped_table()
    n_steps = 500

    # Individual responses.
    r0 = np.zeros(ma.num_modes, dtype=np.float64)
    r0[0] = 1.0
    stepper_a = IIRModalStepper(modal=ma)
    q_a = stepper_a.step_n(n_steps, r=r0)

    r1 = np.zeros(ma.num_modes, dtype=np.float64)
    r1[1] = 0.5
    stepper_b = IIRModalStepper(modal=ma)
    q_b = stepper_b.step_n(n_steps, r=r1)

    # Combined response.
    r_both = r0 + r1
    stepper_c = IIRModalStepper(modal=ma)
    q_c = stepper_c.step_n(n_steps, r=r_both)

    # Check linearity: q_c ≈ q_a + q_b.
    err = np.max(np.abs(q_c - (q_a + q_b)))
    print(f"  Linearity error: {err:.2e}")
    assert err < 1e-12, f"Linearity violated: max error {err:.2e}"


# ---------------------------------------------------------------------------
# Test 3: Sub-step size satisfies Nyquist
# ---------------------------------------------------------------------------
def test_substep_nyquist():
    """T = π / (2 ω_max) guarantees ≥ 4 samples per highest-mode period."""
    ma = _make_damped_table()
    stepper = IIRModalStepper(modal=ma)

    omega_max = ma.frequencies[-1]
    period_min = 2.0 * np.pi / omega_max
    samples_per_period = period_min / stepper.T
    print(f"  T={stepper.T:.2e}, shortest period={period_min:.2e}, "
          f"samples/period={samples_per_period:.1f}")
    assert samples_per_period >= 4.0 - 1e-10, (
        f"Nyquist violated: {samples_per_period:.1f} samples per period"
    )


# ---------------------------------------------------------------------------
# Test 4: Undamped impulse produces constant-amplitude oscillation
# ---------------------------------------------------------------------------
def test_undamped_oscillation():
    """With zero Rayleigh damping, impulse response should not decay."""
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    tol = 1e-8
    x_min, x_max = mesh.vertices[:, 0].min(), mesh.vertices[:, 0].max()
    z_min, z_max = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    on_xmin = np.abs(mesh.vertices[:, 0] - x_min) < tol
    on_xmax = np.abs(mesh.vertices[:, 0] - x_max) < tol
    on_zmin = np.abs(mesh.vertices[:, 2] - z_min) < tol
    on_zmax = np.abs(mesh.vertices[:, 2] - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)

    # Zero damping.
    model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                     alpha0=0.0, alpha1=0.0)
    ma = ModalAnalysis(fem=model, num_modes=10)
    stepper = IIRModalStepper(modal=ma)

    r = np.zeros(ma.num_modes, dtype=np.float64)
    r[0] = 1.0

    n_steps = 2000
    q_hist = stepper.step_n(n_steps, r=r)
    q0 = q_hist[:, 0]

    # Find peaks — amplitude should be roughly constant.
    peaks_idx = []
    for i in range(1, len(q0) - 1):
        if abs(q0[i]) > abs(q0[i - 1]) and abs(q0[i]) > abs(q0[i + 1]):
            peaks_idx.append(i)

    if len(peaks_idx) >= 4:
        peak_amps = np.abs(q0[peaks_idx])
        # Amplitude variation should be tiny (numerical only).
        variation = (peak_amps.max() - peak_amps.min()) / peak_amps.mean()
        print(f"  Undamped peak amplitude variation: {variation:.2e}")
        assert variation < 0.01, f"Undamped amplitude varies by {variation:.2%}"
    else:
        raise AssertionError("Not enough peaks in undamped response")
