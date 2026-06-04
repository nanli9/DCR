# AVBD-DCR Iteration Robustness Fix: Coherent Impact Impulse Bank

## 0. Context

The current AVBD-DCR coupling has already gone through two attempted fixes:

1. **Effective impulse source**
   - `lambda_only -> augmented / delta_p`
   - Result: no meaningful change in cumulative modal injection.
   - Diagnosis: impulse-source magnitude was not the limiting factor because the passive modal-energy cap was binding whenever injection fired.

2. **Impact energy reservoir**
   - Stores the rigid impact energy loss over a short causal window.
   - Result: partial success.
   - It fixes the worst symptom: low-iteration `iters=4` no longer gives exactly zero modal injection.
   - But it does **not** achieve iteration-insensitive modal excitation.

Measured shelf scene result:

| Config | iters=4 | iters=8 | iters=16 | iters=32 | CV |
|---|---:|---:|---:|---:|---:|
| `is_new` today, `lambda_only` | 0.00 J | 5.79 J | 12.55 J | 13.59 J | 0.689 |
| reservoir ON, `lambda_only` | 1.25 J | 6.48 J | 14.47 J | 15.49 J | 0.623 |
| reservoir ON, `delta_p` | 1.43 J | 7.95 J | 22.60 J | 22.60 J | 0.678 |

The reservoir fixes **timing starvation**, but the remaining gap is caused by **impulse smearing**.

At low AVBD iterations, the impact is spread across many small contact impulses. Modal injection is currently computed per frame, so the injectable modal kick energy behaves like:

```math
\sum_i \frac12 \|s_i\|^2
```

But a sharp coherent impact should behave more like:

```math
\frac12 \left\|\sum_i s_i\right\|^2
```

These are not equivalent. If the impulses are coherent, then:

```math
\frac12 \left\|\sum_i s_i\right\|^2
\gg
\sum_i \frac12 \|s_i\|^2
```

That is the missing mechanism.

---

## 1. Core Diagnosis

The low-iteration AVBD solve is not merely losing the energy budget. The budget is now deposited correctly.

The remaining problem is:

```text
same total impact impulse
-> distributed over many small frames
-> per-frame modal projection loses positive cross terms
-> injected vibration energy remains too small
```

For each frame `i`, the AVBD contact impulse projects into modal coordinates as:

```math
s_i = \Phi(x_i)^T J_i
```

Current per-frame passive injection uses:

```math
\Delta E_i(\alpha_i)
=
\alpha_i \dot q_i^T s_i
+
\frac12 \alpha_i^2 \|s_i\|^2
```

Even with a reservoir, if each `s_i` is tiny, the modal energy that can be injected per frame is tiny. The reservoir only provides budget; it does not reconstruct the coherent strike.

So the correct target is not more budget. It is **coherent impact reconstruction**.

---

## 2. Proposed Fix

Implement a short-lived **coherent impact impulse bank**.

Instead of immediately injecting each small modal impulse `s_i`, accumulate impulses belonging to the same physical impact event:

```math
S_{\mathrm{event}}
=
\sum_{i\in\mathcal W} s_i
```

where `\mathcal W` is a short causal impact window.

Then inject using the event-level modal impulse:

```math
\Delta E_{\mathrm{event}}(\alpha)
=
\alpha \dot q^T S_{\mathrm{event}}
+
\frac12 \alpha^2
\|S_{\mathrm{event}}\|^2
```

subject to the event reservoir budget:

```math
\Delta E_{\mathrm{event}}(\alpha)
\le
B_{\mathrm{event}}
```

This restores the positive cross terms lost by per-frame injection.

---

## 3. Why the Cross Terms Matter

For a sequence of modal impulses:

```math
S = \sum_i s_i
```

The coherent event energy term is:

```math
\frac12 \|S\|^2
=
\frac12
\left\|
\sum_i s_i
\right\|^2
```

Expanding:

```math
\frac12 \left\|\sum_i s_i\right\|^2
=
\frac12 \sum_i \|s_i\|^2
+
\sum_{i<j} s_i^T s_j
```

The current per-frame method effectively keeps only:

```math
\frac12 \sum_i \|s_i\|^2
```

and throws away the cross terms:

```math
\sum_{i<j} s_i^T s_j
```

If the low-iteration AVBD solve smears a single sharp impact across multiple frames, the `s_i` directions should be correlated, so:

```math
s_i^T s_j > 0
```

and those cross terms are physically meaningful. Losing them explains why low-iteration modal energy remains far too small.

---

## 4. Event-Level Passive Injection

For each impact event, maintain:

```text
S_event       # accumulated coherent modal impulse
B_event       # accumulated passive energy budget
age           # number of frames since event start
last_active   # last step where event received contact input
x_bar         # representative contact point
J_event       # optional accumulated physical impulse
normal_ref    # representative impact normal
body_id
support_id
patch_id
```

The event budget is updated by rigid energy loss:

```math
B_{\mathrm{event}}^{n+1}
=
\lambda_B B_{\mathrm{event}}^n
+
\eta E_{\mathrm{loss,event}}^n
-
E_{\mathrm{injected}}^n
```

with:

```math
B_{\mathrm{event}} \ge 0
```

The rigid loss term is:

```math
E_{\mathrm{loss}}
=
\max\left(0,
E_{\mathrm{rigid}}^{pre}
-
E_{\mathrm{rigid}}^{post}
\right)
```

The event injection must obey:

```math
E_{\mathrm{injected}}^n
\le
B_{\mathrm{event}}^n
```

and globally:

```math
\sum_n E_{\mathrm{injected}}^n
\le
\eta \sum_n E_{\mathrm{loss}}^n
+
\epsilon
```

---

## 5. Passive Alpha for Event Impulse

Let:

```math
S = S_{\mathrm{event}}
```

Define:

```math
a = S^T S
```

```math
b = \dot q^T S
```

The event-level modal energy change is:

```math
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha b
+
\frac12 \alpha^2 a
```

If the full event kick is affordable:

```math
b + \frac12 a \le B_{\mathrm{event}}
```

then:

```math
\alpha = 1
```

Otherwise solve:

```math
\alpha b + \frac12 \alpha^2 a = B_{\mathrm{event}}
```

The positive root is:

```math
\alpha^*
=
\frac{-b + \sqrt{b^2 + 2aB_{\mathrm{event}}}}{a}
```

Then clamp:

```math
\alpha
=
\operatorname{clamp}(\alpha^*,0,1)
```

Apply:

```math
\dot q \leftarrow \dot q + \alpha S
```

Debit:

```math
B_{\mathrm{event}}
\leftarrow
B_{\mathrm{event}}
-
\Delta E_{\mathrm{modal}}(\alpha)
```

If partially spent, keep the unspent impulse residual:

```math
S_{\mathrm{event}}
\leftarrow
(1-\alpha)S_{\mathrm{event}}
```

If fully spent:

```math
S_{\mathrm{event}} \leftarrow 0
```

---

## 6. Two Possible Banking Modes

### 6.1 Modal-Sum Mode

Accumulate already-projected modal impulses:

```math
S_{\mathrm{event}}
\leftarrow
S_{\mathrm{event}} + s_i
```

where:

```math
s_i = \Phi(x_i)^T J_i
```

This is the easiest implementation.

Pros:

```text
- minimal code change
- directly reuses existing project_impulse path
- easy to test
```

Cons:

```text
- sensitive to contact point jitter
- may accumulate inconsistent mode directions if contact samples move too much
```

---

### 6.2 Physical-Impulse Reconstruction Mode

Accumulate physical impulses first:

```math
J_{\mathrm{event}}
=
\sum_i J_i
```

Compute an impulse-weighted representative contact point:

```math
\bar x
=
\frac{\sum_i \|J_i\|x_i}{\sum_i \|J_i\|}
```

Then project once:

```math
S_{\mathrm{event}}
=
\Phi(\bar x)^T J_{\mathrm{event}}
```

This treats the low-iteration smeared contact sequence as one physical impact.

Pros:

```text
- less sensitive to contact point jitter
- closer to sharp-impact reconstruction
- likely better for low-iteration AVBD
```

Cons:

```text
- needs careful event identity and representative point tracking
- can be wrong if multiple independent impacts are merged
```

Recommended default for the next prototype:

```yaml
impact_bank_mode: impulse_reconstruct
```

Keep `modal_sum` as an ablation.

---

## 7. Event Identity

Use a stable event key:

```text
event_key = (rigid_body_id, support_id, contact_patch_id)
```

If there is no patch system yet, approximate with:

```text
event_key = (rigid_body_id, support_id, quantized_contact_region)
```

A contact remains part of the same event only if it passes coherence gates.

---

## 8. Coherence Gates

Naively accumulating impulses is dangerous. It can manufacture energy by merging unrelated contacts.

Only accumulate when the current impulse is plausibly part of the same physical impact.

### 8.1 Directional Coherence in Modal Space

Require:

```math
\frac{s_i^T S_{\mathrm{event}}}
{\|s_i\|\,\|S_{\mathrm{event}}\| + \epsilon}
>
c_{\min}
```

Suggested default:

```yaml
coherence_cos_min: 0.5
```

If this fails:

```text
flush current event or start a new event
```

---

### 8.2 Normal Coherence

Require:

```math
n_i^T n_{\mathrm{ref}}
>
c_{n,\min}
```

Suggested default:

```yaml
normal_cos_min: 0.7
```

This prevents merging impacts from different sides or different contact orientations.

---

### 8.3 Contact Patch Coherence

Require the contact point to remain close to the representative event point:

```math
\|x_i - \bar x\| < r_{\mathrm{patch}}
```

Suggested default:

```yaml
patch_radius: 2-5 cm  # scene-scale dependent
```

For nondimensional code, use a fraction of the rigid body's bounding-box diagonal.

---

### 8.4 Temporal Window

Require:

```math
\mathrm{age}(\mathrm{event}) \le N_{\max}
```

Suggested:

```yaml
impact_bank_window: 4
max_event_age: 8
```

The bank must be short-lived. If it persists too long, it becomes an unphysical vibration amplifier.

---

### 8.5 Resting/Sliding Rejection

Do not accumulate impulses for resting support or long sliding contacts.

Reject if:

```math
|v_{\mathrm{rel},n}| < v_{\min}
```

and the contact has already been active for several frames.

Also reject if tangential impulse dominates:

```math
\frac{\|J_t\|}{|J_n| + \epsilon} > r_t
```

Suggested:

```yaml
tangential_dominance_max: 2.0
```

This keeps the bank focused on impact-like events, not frictional scraping.

---

## 9. Algorithm

```text
for each simulation step n:

    run ordinary AVBD step
    collect contact impulses J_i
    compute rigid energy loss E_loss

    for each eligible contact i:
        key = make_event_key(body_id, support_id, patch_id)
        event = get_or_create_event(key)

        compute modal impulse:
            s_i = Phi(x_i)^T J_i

        compute event budget share:
            B_i = eta * E_loss_share_i

        if event is new:
            initialize S_event, J_event, x_bar, normal_ref

        if coherence gates pass:
            B_event += B_i

            if impact_bank_mode == modal_sum:
                S_event += s_i

            if impact_bank_mode == impulse_reconstruct:
                J_event += J_i
                x_bar = impulse_weighted_average(x_bar, x_i, J_i)
                S_event = Phi(x_bar)^T J_event

        else:
            flush_or_start_new_event()

    for each active event:
        if event ready to inject:
            alpha = passive_alpha(S_event, B_event)
            qdot += alpha * S_event
            E_inj = modal_energy_change(alpha, S_event)
            B_event -= E_inj
            S_event *= (1 - alpha)

        age += 1

        if event expired or depleted:
            delete event
```

---

## 10. Event Readiness

There are two reasonable choices.

### Option A: Inject Every Frame from the Coherent Bank

Every frame, accumulate the current impulse, then immediately attempt to inject from the accumulated event impulse.

Pros:

```text
- low latency
- simplest behavior
```

Cons:

```text
- may still lose some coherence if alpha spends too early
```

---

### Option B: Wait Until Impact Window Ends

Accumulate impulses for a few frames, then inject once when:

```text
- contact separates, or
- event reaches impact_bank_window, or
- incoming impulse magnitude drops below threshold
```

Pros:

```text
- maximizes coherent reconstruction
- best chance to close low-iteration gap
```

Cons:

```text
- adds 2-4 frame latency
- less responsive visually
```

Recommended prototype:

```yaml
inject_policy: end_of_window
impact_bank_window: 4
```

Then compare against:

```yaml
inject_policy: every_frame
```

---

## 11. Diagnostics

The next diagnostic should compare:

```text
impulse_source = delta_p
use_impact_reservoir = true
use_coherent_impulse_bank = false / true
iters = 4, 8, 16, 32
```

Report:

```text
ΣE_loss
Σbudget_deposited
ΣE_injected
budget_utilization = ΣE_injected / Σbudget_deposited
CV(E_injected)
num_events
mean_event_window
mean_event_age
mean ||Σs_i||² / Σ||s_i||²
peak modal energy
visible displacement / toppling metric
passivity violations
```

Critical coherence metric:

```math
R_{\mathrm{coherence}}
=
\frac{\left\|\sum_i s_i\right\|^2}
{\sum_i \|s_i\|^2 + \epsilon}
```

If low-iteration AVBD is merely smearing one coherent impact, expect:

```math
R_{\mathrm{coherence}} \gg 1
```

The bank should then recover a large part of the missing modal energy.

---

## 12. Acceptance Criteria

Primary acceptance target:

```math
\mathrm{CV}(E_{\mathrm{injected}}) < 0.35
```

Fallback acceptance target:

```math
\mathrm{CV}(E_{\mathrm{banked}})
<
0.5\,\mathrm{CV}(E_{\mathrm{reservoir\ only}})
```

Budget utilization should improve at low iterations:

```math
\frac{\sum E_{\mathrm{injected}}}{\sum B_{\mathrm{deposited}}}
\quad\text{should increase significantly at iters=4.}
```

Passivity must remain true:

```math
\sum E_{\mathrm{injected}}
\le
\eta \sum E_{\mathrm{loss}} + \epsilon
```

No-energy cases must remain inert:

```math
\eta = 0 \Rightarrow E_{\mathrm{injected}} = 0
```

```math
B_{\mathrm{event}} = 0 \Rightarrow E_{\mathrm{injected}} = 0
```

---

## 13. Expected Results

Current best low-iteration result:

```text
iters=4, reservoir ON, delta_p: ~1.43 J
```

Target after coherent bank:

```text
iters=4 should move substantially toward the iters=8/16/32 range.
```

A realistic target is:

```text
iters=4: 8-15 J
iters=8: 12-20 J
iters=16: 20-23 J
iters=32: 20-23 J
```

Do not demand exact equality. Some iteration dependence is physically plausible because a softer under-converged solve can produce genuinely different motion.

But if `iters=4` remains near `1-2 J`, then the problem is not just temporal smearing. It means the low-iteration AVBD trajectory is physically too different, and a separate collision estimator is needed.

---

## 14. Secondary Fallback: Sharp Collision Impulse Estimator

If coherent banking still fails, stop trying to recover the impact from AVBD's smeared impulse sequence.

Estimate a sharp normal collision impulse directly from pre-impact relative velocity and effective mass.

Normal relative velocity:

```math
v_{\mathrm{rel},n}
=
n^T(v_p - v_s)
```

For a rigid body contact point with offset `r`, define effective inverse mass along normal:

```math
K_n
=
n^T
\left(
\frac{1}{m}I_3
+
[r]_\times^T I^{-1}[r]_\times
\right)
n
```

Then estimate normal impulse:

```math
J_n
=
-\frac{(1+e)v_{\mathrm{rel},n}}{K_n}
```

with:

```math
J = J_n n
```

Project to modal coordinates:

```math
S_{\mathrm{impact}}
=
\Phi(x)^T J
```

Still cap by the measured passive reservoir:

```math
\Delta E_{\mathrm{modal}}
\le
\eta E_{\mathrm{loss}}
```

This creates a hybrid design:

```text
AVBD resolves contact motion;
DCR reconstructs a sharp impact impulse for modal excitation;
explicit reservoir keeps the excitation passive.
```

This is less elegant than pure AVBD extraction, but likely more robust for real-time low-iteration use.

---

## 15. Recommended Next Prototype Config

```yaml
avbd_dcr:
  impulse_source: delta_p

  use_impact_reservoir: true
  reservoir_default: off_until_validated

  use_coherent_impulse_bank: true
  coherent_bank_default: off_until_validated

  impact_bank_mode: impulse_reconstruct
  inject_policy: end_of_window
  impact_bank_window: 4
  max_event_age: 8

  coherence_cos_min: 0.5
  normal_cos_min: 0.7
  tangential_dominance_max: 2.0

  preserve_passivity: true
  eta: 0.5

  diagnostics:
    log_event_count: true
    log_event_age: true
    log_budget_deposited: true
    log_budget_utilization: true
    log_R_coherence: true
    log_CV_across_iterations: true
    log_passivity_violations: true
```

---

## 16. Code-Level Implementation Targets

Likely files:

```text
dcr/dcr/passive_dcr.py
    - add coherent impact bank state
    - add event creation / update / expiry
    - add passive_alpha over S_event
    - add event diagnostics

scripts/_diag_impact_bank_iter_sensitivity.py
    - compare reservoir_only vs coherent_bank
    - sweep iters = 4, 8, 16, 32
    - report CV and R_coherence

tests/avbd/test_coherent_impact_bank_passivity.py
    - eta=0 gives zero injection
    - total injected <= total budget
    - unrelated/opposite impulses do not accumulate
    - coherent impulses accumulate and recover cross terms
```

Optional helper module:

```text
dcr/dcr/impact_bank.py
    ImpactEvent
    ImpactBank
    update_event()
    coherence_check()
    compute_event_impulse()
    passive_event_injection()
```

A separate helper module is cleaner. Otherwise `passive_dcr.py` will become a dumping ground.

---

## 17. Unit Tests

### Test 1: Coherent impulses recover cross terms

Let:

```math
s_1 = s_2 = s
```

Per-frame energy term:

```math
E_{\mathrm{frame}}
=
\frac12\|s\|^2 + \frac12\|s\|^2
=
\|s\|^2
```

Banked energy term:

```math
E_{\mathrm{bank}}
=
\frac12\|2s\|^2
=
2\|s\|^2
```

Expected:

```math
E_{\mathrm{bank}} = 2E_{\mathrm{frame}}
```

---

### Test 2: Opposite impulses do not create fake energy

Let:

```math
s_1 = s,
\qquad
s_2 = -s
```

Then:

```math
S = s_1+s_2 = 0
```

Expected:

```math
E_{\mathrm{bank}} = 0
```

The coherence gate should either reject the second impulse or cancel the event safely.

---

### Test 3: Passivity bound

For arbitrary accumulated `S_event` and budget `B_event`, after injection:

```math
\Delta E_{\mathrm{modal}}
\le
B_{\mathrm{event}} + \epsilon
```

---

### Test 4: Budget depletion

After injection:

```math
B_{\mathrm{event}}^{after}
=
B_{\mathrm{event}}^{before}
-
\Delta E_{\mathrm{modal}}
```

and:

```math
B_{\mathrm{event}}^{after} \ge -\epsilon
```

---

### Test 5: Expiry prevents delayed bumps

If:

```math
\mathrm{age} > N_{\max}
```

then the event must be deleted or frozen with zero injection.

Expected:

```text
no delayed modal kick after expiry
```

---

## 18. Honest Research Framing

Do not claim:

```text
AVBD naturally gives iteration-insensitive modal excitation.
```

That is false under low iterations.

Use this framing instead:

```text
Low-iteration AVBD smears a sharp impact over multiple contact updates. We reconstruct a short-lived coherent impact event from that smeared sequence, then inject modal energy from the event-level impulse under an explicit passive energy budget.
```

This is defensible because:

1. the event bank is causal,
2. the event window is short,
3. coherence gates prevent unrelated contact merging,
4. energy injection remains capped by measured rigid energy loss,
5. the method can be disabled as an ablation.

---

## 19. Decision Tree

```text
1. Reservoir OFF, lambda_only
   -> baseline, known bad at low iterations.

2. Reservoir ON, delta_p
   -> fixes timing starvation, but still smeared-impulse limited.

3. Reservoir ON, delta_p, coherent bank ON
   -> next prototype; expected to recover coherent impact energy.

4. If coherent bank fails:
   -> use sharp collision impulse estimator capped by passive reservoir.
```

---

## 20. Bottom Line

The next fix should be:

```text
impact reservoir + delta_p + coherent impact impulse bank
```

not:

```text
more AVBD iterations
more lambda plumbing
more passivity line search
```

The current system has already proven that the budget and timing problems are partially solved. The remaining failure is that low-iteration AVBD spreads one impact into many tiny modal impulses and the current per-frame injection discards the coherent cross terms.

The coherent bank directly targets that failure.

If it succeeds, it gives a real-time, passivity-safe, low-iteration AVBD-DCR coupling.

If it fails, the honest conclusion is that low-iteration AVBD produces a genuinely different collision trajectory, and DCR needs a separate sharp-impact estimator rather than continued extraction from the smeared solver output.
