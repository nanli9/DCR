# AVBD-DCR Real Fix: Impact-Window Passive Energy Reservoir

## Goal

Fix the low-iteration AVBD-DCR starvation problem.

The failed fix was:

```text
lambda_only impulse source
→ augmented impulse source
→ delta_p impulse source
```

That does not close the gap because the modal injection is not primarily limited by raw impulse magnitude. The passive alpha cap is already binding when injection happens.

The real failure is timing:

```text
E_loss happens on one frame,
but DCR only injects on is_new contact frames.
```

At low AVBD iterations, the high-energy impact frame and the `is_new` frame can desynchronize. Then the modal budget exists for one step and disappears before DCR is allowed to spend it.

The real fix is:

```text
single-frame is_new budget
→ short-lived passive impact reservoir
```

---

# 1. Core Diagnosis

Current logic behaves like:

```text
if contact.is_new:
    E_max = eta * E_loss_this_step
    inject_modal_energy(E_max)
else:
    inject_nothing
```

This is too brittle.

If the solver dissipates rigid kinetic energy on step `n`, but the contact is classified as `is_new` on step `n+1` or `n+2`, then:

```math
E_{\mathrm{loss}}^n > 0
```

but

```math
E_{\mathrm{inject}}^n = 0
```

and by the time the contact becomes eligible:

```math
E_{\mathrm{loss}}^{n+1} \approx 0
```

so the modal system receives no energy.

Therefore the coupling is iteration-sensitive even if the total rigid energy loss is iteration-insensitive.

---

# 2. Correct Design

Introduce a short-lived impact reservoir per contact patch or body-support pair.

Each impact key `k` stores:

```text
B_k       : remaining impact energy budget
age_k     : number of steps since last deposit
body_id   : rigid body id
support_id: modal support id
patch_id  : contact patch id or persistent contact key
```

The reservoir is funded by rigid energy loss and spent by passive modal injection.

---

# 3. Physical Energy Definitions

Rigid kinetic energy:

```math
E_{\mathrm{rigid}}
=
\sum_b
\left(
\frac{1}{2}m_b\|v_b\|^2
+
\frac{1}{2}\omega_b^T I_b \omega_b
\right)
```

Modal energy:

```math
E_{\mathrm{modal}}
=
\frac{1}{2}\dot q^T \dot q
+
\frac{1}{2}q^T \Omega^2 q
```

Rigid energy loss during ordinary AVBD contact solve:

```math
E_{\mathrm{loss}}^n
=
\max
\left(
0,
E_{\mathrm{rigid,pre}}^n
-
E_{\mathrm{rigid,post}}^n
\right)
```

Total modal injection budget from this loss:

```math
D^n
=
\eta E_{\mathrm{loss}}^n
```

where:

```math
0 \le \eta \le 1
```

---

# 4. Deposit Into Impact Reservoir

Distribute the deposit `D^n` across active or recently active impact keys.

For contact `i`, define an impact weight.

Preferred weight, if pre-solve relative normal velocity is available:

```math
a_i
=
\max
\left(
0,
-J_{N,i} v_{\mathrm{rel},N,i}^{pre}
\right)
```

where:

```math
J_{N,i} \ge 0
```

is the normal impulse magnitude and

```math
v_{\mathrm{rel},N,i}^{pre}
=
n_i^T(v_{p,i}^{pre} - v_{s,i}^{pre})
```

Then:

```math
w_i
=
\frac{a_i}
{\sum_j a_j + \epsilon}
```

Fallback if pre-impact normal work is unavailable:

```math
w_i
=
\frac{|J_{N,i}|}
{\sum_j |J_{N,j}| + \epsilon}
```

Deposit for key `i`:

```math
D_i^n
=
w_i \eta E_{\mathrm{loss}}^n
```

Reservoir update before spending:

```math
B_i^{n+\frac{1}{2}}
=
\min
\left(
B_{\max},
\rho_B B_i^n + D_i^n
\right)
```

where:

```math
0 \le \rho_B \le 1
```

is the reservoir decay factor.

Recommended first values:

```yaml
eta: 0.5
rho_B: 0.5 to 0.8
reservoir_window_steps: 3 to 6
B_max: eta * recent_peak_E_loss
```

For a simpler first implementation, use a hard TTL instead of exponential decay:

```math
B_i^{n+\frac{1}{2}}
=
B_i^n + D_i^n
```

and delete the reservoir if:

```math
\mathrm{age}_i > W
```

where:

```math
W \in [3,6]
```

steps.

---

# 5. Eligibility Gates

Do not require `is_new`.

Replace:

```text
contact.is_new == true
```

with a causal impact-window gate.

A contact key `i` is eligible if:

```math
B_i^{n+\frac{1}{2}} > \epsilon_B
```

and:

```math
\mathrm{age}_i \le W
```

and the contact is still geometrically relevant:

```math
g_i^n \le \delta_{\mathrm{gate}}
```

where `g_i` is the contact gap.

For modal support contact:

```math
g_i(z,q)
=
n_i^T
\left(
p_i(z)-x_{s,i}(q)
\right)
-
\delta_{\mathrm{shell}}
```

The contact is near if:

```math
g_i(z,q) \le \delta_{\mathrm{gate}}
```

Optional velocity gate:

```math
v_{\mathrm{rel},N,i}
<
v_{\mathrm{separate,max}}
```

Do **not** require strong closing velocity after the solve, because AVBD may already have stopped the body. A strict closing gate can recreate the same starvation.

Recommended first version:

```text
eligible if:
    reservoir has energy
    key age <= W
    same body/support/patch remains active or near-active
    gap <= delta_gate
```

---

# 6. Modal Injection From Reservoir

For each eligible impact key `i`, compute the modal impulse direction.

Impulse source options may remain:

```text
lambda_only
augmented
delta_p
```

But this is now secondary. The reservoir is the main fix.

Given world impulse:

```math
J_i
```

at support point:

```math
x_i
```

project to modal coordinates:

```math
s_i
=
\Phi(x_i)^T J_i
```

Aggregate all eligible impulses:

```math
s
=
\sum_{i \in \mathcal E} s_i
```

where:

```math
\mathcal E
```

is the set of reservoir-eligible contacts.

Candidate modal velocity:

```math
\dot q_{\mathrm{cand}}
=
\dot q_{\mathrm{old}} + \alpha s
```

Modal energy change from scaled kick:

```math
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha \dot q_{\mathrm{old}}^T s
+
\frac{1}{2}\alpha^2 s^T s
```

Let:

```math
a = s^T s
```

```math
b = \dot q_{\mathrm{old}}^T s
```

Available reservoir budget:

```math
E_{\max}^n
=
\sum_{i \in \mathcal E} B_i^{n+\frac{1}{2}}
```

If:

```math
b + \frac{1}{2}a \le E_{\max}^n
```

then:

```math
\alpha = 1
```

Otherwise:

```math
\alpha^*
=
\frac{-b + \sqrt{b^2 + 2aE_{\max}^n}}{a}
```

and:

```math
\alpha
=
\operatorname{clamp}(\alpha^*,0,1)
```

Apply:

```math
\dot q^{n+}
=
\dot q^n + \alpha s
```

Actual injected modal energy:

```math
E_{\mathrm{inj}}^n
=
\max
\left(
0,
E_{\mathrm{modal}}(\dot q^{n+},q^n)
-
E_{\mathrm{modal}}(\dot q^n,q^n)
\right)
```

Required invariant:

```math
E_{\mathrm{inj}}^n
\le
E_{\max}^n + \epsilon
```

---

# 7. Spend Reservoir After Injection

Distribute the actual spent energy back to participating reservoirs.

If per-contact modal contribution is available:

```math
c_i
=
\max
\left(
0,
\alpha \dot q_{\mathrm{old}}^T s_i
+
\frac{1}{2}\alpha^2 s_i^T s_i
\right)
```

Then:

```math
r_i
=
\frac{c_i}
{\sum_j c_j + \epsilon}
```

Fallback:

```math
r_i
=
\frac{B_i^{n+\frac{1}{2}}}
{\sum_j B_j^{n+\frac{1}{2}} + \epsilon}
```

Spend:

```math
S_i^n
=
r_i E_{\mathrm{inj}}^n
```

Reservoir after spending:

```math
B_i^{n+1}
=
\max
\left(
0,
B_i^{n+\frac{1}{2}} - S_i^n
\right)
```

Expire unused budget:

```math
B_i^{n+1} = 0
\quad
\text{if}
\quad
\mathrm{age}_i > W
```

or with exponential decay:

```math
B_i^{n+1}
=
\rho_B
\max
\left(
0,
B_i^{n+\frac{1}{2}} - S_i^n
\right)
```

---

# 8. Global Passivity Invariant

The reservoir cannot create energy because total deposits are bounded by rigid energy loss.

Per step:

```math
\sum_i D_i^n
\le
\eta E_{\mathrm{loss}}^n
```

Across all steps:

```math
\sum_n E_{\mathrm{inj}}^n
\le
\sum_n \eta E_{\mathrm{loss}}^n
+
\sum_i B_i^0
+
\epsilon
```

If initial reservoirs are zero:

```math
\sum_n E_{\mathrm{inj}}^n
\le
\eta
\sum_n E_{\mathrm{loss}}^n
+
\epsilon
```

This is the main passive guarantee.

---

# 9. Why This Fixes Iteration Sensitivity

Old behavior:

```text
Low AVBD iters:
    E_loss spike happens
    is_new false
    budget disappears
    modal injection starves
```

New behavior:

```text
Low AVBD iters:
    E_loss spike happens
    budget is stored
    contact becomes eligible within W steps
    modal injection spends stored budget passively
```

The modal system no longer depends on exact same-frame alignment between:

```text
contact.is_new
```

and:

```text
E_loss spike
```

Therefore the method should become much less sensitive to AVBD iteration count.

---

# 10. Implementation Plan

## File: `dcr/dcr/passive_dcr.py`

Add reservoir configuration:

```python
use_impact_reservoir: bool = True
reservoir_window_steps: int = 4
reservoir_decay: float = 0.65
reservoir_eps: float = 1e-10
reservoir_max: float | None = None
```

Add state:

```python
impact_reservoirs: dict[ImpactKey, ImpactReservoirEntry]
last_E_reservoir_deposit: float
last_E_reservoir_spent: float
last_E_reservoir_expired: float
cum_E_reservoir_deposit: float
cum_E_reservoir_spent: float
cum_E_reservoir_expired: float
```

Where:

```python
@dataclass(frozen=True)
class ImpactKey:
    body_id: int
    support_id: int
    patch_id: int | str
```

and:

```python
@dataclass
class ImpactReservoirEntry:
    energy: float = 0.0
    age: int = 0
    last_seen_step: int = 0
```

---

## File: `dcr/avbd/world.py`

After ordinary AVBD solve, compute:

```math
E_{\mathrm{loss}}^n
=
\max
\left(
0,
E_{\mathrm{rigid,pre}}^n
-
E_{\mathrm{rigid,post}}^n
\right)
```

Pass to coupler:

```python
coupler.process_step(
    contacts=contacts,
    lambdas=lambdas,
    h=h,
    E_loss=E_loss,
    contact_keys=current_keys,
    ...
)
```

If `body_dp` and `k_normal` already exist from the previous ablation, keep them as optional impulse-source inputs. They are not the main fix.

---

## File: `dcr/dcr/passive_dcr.py`

Process order should become:

```text
1. Age all reservoirs.
2. Deposit eta * E_loss into active/recent contact reservoirs.
3. Select eligible reservoirs.
4. Build modal impulse direction s from eligible contacts.
5. Compute passive alpha using E_max = sum eligible reservoir energy.
6. Apply qdot += alpha * s.
7. Measure actual injected modal energy.
8. Debit reservoirs.
9. Expire old reservoirs.
10. Log all reservoir diagnostics.
```

Pseudo-code:

```python
def process_step(..., E_loss: float, contact_keys=None, ...):
    self._age_reservoirs()

    if self.use_impact_reservoir:
        deposits = self._compute_contact_deposits(
            contacts=contacts,
            contact_keys=contact_keys,
            E_loss=E_loss,
            eta=self.eta,
        )
        self._deposit_reservoirs(deposits)

        eligible = self._eligible_reservoir_contacts(
            contacts=contacts,
            contact_keys=contact_keys,
        )

        E_max = sum(self.impact_reservoirs[key].energy for key in eligible)

    else:
        eligible = [c for c in contacts if c.is_new]
        E_max = self.eta * E_loss

    s = self._build_modal_impulse_direction(eligible)

    alpha = passive_alpha(
        qdot=self.qdot,
        s=s,
        E_max=E_max,
    )

    E_modal_pre = modal_energy(self.q, self.qdot)

    self.qdot += alpha * s

    E_modal_post = modal_energy(self.q, self.qdot)

    E_inj = max(0.0, E_modal_post - E_modal_pre)

    if self.use_impact_reservoir:
        self._debit_reservoirs(eligible, E_inj)

    self._expire_old_reservoirs()
```

---

# 11. Diagnostics

Add logs per step:

```text
step
E_loss
eta_E_loss
num_contacts
num_new_contacts
num_active_contacts
num_reservoirs
num_eligible_reservoirs
E_reservoir_total_before
E_reservoir_deposit
E_reservoir_spent
E_reservoir_expired
E_reservoir_total_after
raw_s_norm
alpha
E_modal_injected
fill_ratio
```

Where:

```math
\mathrm{fill\_ratio}
=
\frac
{E_{\mathrm{modal,injected}}}
{\eta E_{\mathrm{loss}} + E_{\mathrm{reservoir,previous}} + \epsilon}
```

For iteration comparison, log cumulative values:

```math
E_{\mathrm{loss,cum}}
=
\sum_n E_{\mathrm{loss}}^n
```

```math
E_{\mathrm{deposit,cum}}
=
\sum_n \sum_i D_i^n
```

```math
E_{\mathrm{inj,cum}}
=
\sum_n E_{\mathrm{inj}}^n
```

```math
E_{\mathrm{expired,cum}}
=
\sum_n E_{\mathrm{expired}}^n
```

Global fill ratio:

```math
R_{\mathrm{fill}}
=
\frac
{E_{\mathrm{inj,cum}}}
{\eta E_{\mathrm{loss,cum}} + \epsilon}
```

---

# 12. Required Diagnostic Script

Create:

```text
scripts/_diag_impact_reservoir_iter_sensitivity.py
```

Run:

```text
iters ∈ {4, 8, 16, 32}
use_impact_reservoir ∈ {false, true}
```

For each config, report:

```text
iters
use_reservoir
cum_E_loss
cum_eta_E_loss
cum_E_deposit
cum_E_injected
cum_E_expired
final_E_reservoir
fill_ratio
num_E_loss_spike_steps
num_is_new_steps
num_eligible_reservoir_steps
peak_E_modal
```

Compute coefficient of variation:

```math
\mathrm{CV}
=
\frac{\sigma}{\mu}
```

Old method:

```math
\mathrm{CV}_{\mathrm{old}}
=
\frac
{\operatorname{std}(E_{\mathrm{inj,cum}})}
{\operatorname{mean}(E_{\mathrm{inj,cum}})}
```

Reservoir method:

```math
\mathrm{CV}_{\mathrm{reservoir}}
=
\frac
{\operatorname{std}(E_{\mathrm{inj,cum,reservoir}})}
{\operatorname{mean}(E_{\mathrm{inj,cum,reservoir}})}
```

Pass condition:

```math
\frac
{\mathrm{CV}_{\mathrm{reservoir}}}
{\mathrm{CV}_{\mathrm{old}}}
<
0.5
```

Stronger target:

```math
\frac
{\mathrm{CV}_{\mathrm{reservoir}}}
{\mathrm{CV}_{\mathrm{old}}}
<
0.25
```

Also require:

```math
E_{\mathrm{inj,cum}}
\le
\eta E_{\mathrm{loss,cum}}
+
\epsilon
```

and:

```math
E_{\mathrm{deposit,cum}}
=
\eta E_{\mathrm{loss,cum}}
\pm \epsilon
```

up to expired or unspent reservoir bookkeeping.

---

# 13. Important Guardrails

## Guardrail 1: Do not make the reservoir long-lived

This must be an impact-window reservoir, not a global energy bank.

Bad:

```text
store unused E_loss forever
```

Good:

```text
store E_loss for W = 3 to 6 frames
```

Reason: if budget lives forever, old impacts can create delayed bumps unrelated to the current contact.

---

## Guardrail 2: Do not fund modal injection from support-created energy

If the moving support later adds energy to the rigid body, do not recycle that as fresh `E_loss`.

Deposit should come from the ordinary AVBD impact phase only:

```math
E_{\mathrm{loss,ordinary}}^n
=
\max
\left(
0,
E_{\mathrm{rigid,pre ordinary}}^n
-
E_{\mathrm{rigid,post ordinary}}^n
\right)
```

Do not use:

```math
E_{\mathrm{rigid,after support}}
```

for the deposit calculation.

Otherwise the method can create a feedback loop:

```text
modal support pushes rigid
rigid energy changes
system treats this as new loss
modal gets refilled
```

---

## Guardrail 3: Keep impulse-source ablations, but do not call them the fix

Keep:

```text
lambda_only
augmented
delta_p
```

But the expected hierarchy is:

```text
impact reservoir: fixes iteration timing starvation
delta_p: improves impulse direction/physical attribution
augmented: cheap diagnostic, risky due to double-counting
lambda_only: baseline ablation
```

Recommended default for now:

```yaml
impulse_source: lambda_only
use_impact_reservoir: true
```

After the reservoir diagnostic passes, test:

```yaml
impulse_source: delta_p
use_impact_reservoir: true
```

Then decide whether `delta_p` improves behavior.

---

## Guardrail 4: Do not remove the passive alpha cap

The reservoir only changes when energy is available.

It does not remove:

```math
\Delta E_{\mathrm{modal}}
\le
E_{\max}
```

The local invariant must still hold:

```math
E_{\mathrm{inj}}^n
\le
\sum_i B_i^{n+\frac{1}{2}}
+
\epsilon
```

The global invariant must also hold:

```math
\sum_n E_{\mathrm{inj}}^n
\le
\eta
\sum_n E_{\mathrm{loss}}^n
+
\epsilon
```

---

# 14. Acceptance Criteria

The fix is successful only if all are true:

1. Low-iteration AVBD no longer produces zero modal injection when total rigid energy loss is large.

2. The cumulative injected modal energy becomes less sensitive to AVBD iteration count:

```math
\mathrm{CV}_{\mathrm{reservoir}}
<
0.5
\mathrm{CV}_{\mathrm{old}}
```

3. Stronger desired result:

```math
\mathrm{CV}_{\mathrm{reservoir}}
<
0.25
\mathrm{CV}_{\mathrm{old}}
```

4. Global passivity holds:

```math
\sum_n E_{\mathrm{inj}}^n
\le
\eta
\sum_n E_{\mathrm{loss}}^n
+
\epsilon
```

5. Reservoir expiration is nonzero in some tests, proving budget does not live forever.

6. With `use_impact_reservoir=false`, old behavior is reproduced.

7. With `eta=0`, no modal injection occurs:

```math
\eta = 0
\Rightarrow
E_{\mathrm{inj}}^n = 0
```

8. With no rigid energy loss, no reservoir deposit occurs:

```math
E_{\mathrm{loss}}^n = 0
\Rightarrow
D_i^n = 0
```

---

# 15. Minimal Test

Add a unit/integration test:

```text
tests/avbd/test_impact_reservoir_passivity.py
```

Test:

```text
Run shelf scene at iters = 4, 8, 16, 32.
Compare old single-frame budget against reservoir budget.
```

Assert:

```math
\sum_n E_{\mathrm{inj,reservoir}}^n
\le
\eta
\sum_n E_{\mathrm{loss}}^n
+
\epsilon
```

and:

```math
\mathrm{CV}_{\mathrm{reservoir}}
<
0.5
\mathrm{CV}_{\mathrm{old}}
```

Use loose tolerance initially because toppling/contact order can be chaotic.

---

# 16. Summary

The correct fix is not:

```text
read a better impulse
```

The correct fix is:

```text
make the passive energy budget event-consistent.
```

Replace:

```math
E_{\max}^n
=
\eta E_{\mathrm{loss}}^n
\quad
\text{only if contact.is_new}
```

with:

```math
B_i^{n+\frac{1}{2}}
=
\min
\left(
B_{\max},
\rho_B B_i^n + D_i^n
\right)
```

and:

```math
E_{\max}^n
=
\sum_{i \in \mathcal E} B_i^{n+\frac{1}{2}}
```

Then spend:

```math
E_{\mathrm{inj}}^n
\le
E_{\max}^n
```

and maintain:

```math
\sum_n E_{\mathrm{inj}}^n
\le
\eta
\sum_n E_{\mathrm{loss}}^n
+
\epsilon
```

This preserves passivity while removing the fragile same-frame dependency between AVBD energy loss and DCR `is_new` contact classification.

