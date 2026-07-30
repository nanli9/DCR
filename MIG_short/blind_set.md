# Blind Evaluation Set

8 entries, each given as title and abstract only, in a uniform format.
Authors, affiliations, venue, dates, identifiers, and provenance have been removed
from every entry, and typography has been normalized. The order is arbitrary.

---

## P01

**Title.** DRUMS: Drummer Reconstruction Using Midi Sequences

**Abstract.** We present a system for generating expressive, full-body drumming performances from MIDI input, combining rhythmic precision with lifelike motion. Unlike prior work that focuses on limited gestures or audio-driven models, our approach produces coordinated animations of the entire performer, including hands, torso, legs, and facial expressions, driven solely by symbolic MIDI. Our system integrates a Bi-directional LSTM to predict fine-grained 3D hand trajectories, using sticks parented to the hands and synchronized with MIDI events. It also includes a retrieval-based module that generates expressive upper-body and facial motion conditioned on musical phrasing, and a pedal enforcement component that procedurally animates the feet. Our method addresses the unique challenges of drumming, where rhythm is both heard and seen in dynamic, physically grounded motion. To the best of our knowledge, this is the first system to generate full-body drum performances from raw MIDI. Our approach enables new applications in virtual concerts, immersive training, game animation, and digital avatar performance.

---

## P02

**Title.** Expressive Animation Retiming from Impulse-Based Gestures

**Abstract.** We present a method for retiming existing 3D animations able to handle seamlessly arbitrary impulse-like user gestures, thus enabling expressive video-based control inspired from common review sessions used in animation studios. The approach works in recording two videos with fast, impulse-based, gestures: one synchronized with the existing 3D animation and another featuring a new time sequence. We then propose an automatic generation of a modified 3D animation retimed to match the sequences of the second video. To this end, we introduce a robust and automatic method relying on Dynamic Time Warping able to compute the sequential correspondence between the timings of the impulse gestures. The method can adapt to various individual gestures without requiring dedicated learning, and can take into account the semantic integrity of the original 3D animation after retiming.

---

## P03

**Title.** A Per-Row Danger Index and a Reconstruction-Matched Effective Mass for One-Sweep Passive Contact Coupling in Fixed-Budget Position-Based Solvers

**Abstract.** Position-based engines resolve contacts under a small, fixed local iteration budget, and a cheap way to make a stiff prop ring is to carry a few global modal amplitudes as extra unknowns in the unilateral contact row. At a few iterations per substep such a row can add energy rather than remove it. That it happens is known and not our claim; practitioner accounts report it as a tuning hazard without a framework. We supply that framework for the shared contact-to-modal row, parameterized by the host's velocity reconstruction q̇+ = κ Δq/h, which one cold read-back of Δq/h against 2Δq/h identifies. A pre-solve danger index ρ, a ratio of two quadratic forms a host already assembles, predicts whether one mass-only sweep injects; the sign boundary is κ² + (ωh)² = 2 + m/M. Charging the restorative block at the reconstruction-matched operator κ² M_c + h² K_c, in both the denominator and the correction, makes one sweep passive for any κ ≠ 0 (rigid read-back at Δz/h) and any number of coupled coordinates, and at κ = 1 with ζ = 0 it reproduces the converged implicit step exactly. Reconstruction dependence is a main finding: the mass-only and backward-Euler-shaped weights inject at low stiffness on the shipped symplectic host (κ = 2); the matched one does not. The closed forms are machine-checked to 10⁻¹² relative on a 58,081-cell phase map and a nonmodal mass-spring collapse, and in exact rational arithmetic for the operator identity; on a shipped contact row the matched weight is passive on all 27 cells, and a three-arm weight swap takes the modal-energy overrun count from 8 of 24 to 0. Every theorem is confined to one sweep from a cold start with e = 0 and one normal-only row.

---

## P04

**Title.** Trajectory-aware Smears for Stylized 3D Animations

**Abstract.** Smearing is an essential effect to expressively convey motion in stylized animations. In this paper, we extend the method of Basset et al. to better emphasize the main motion's trajectory of an object when generating elongated in-betweens, i.e., when stretching a 3D object along its trajectory to cover adjacent frames. This limits visual artifacts such as intersections that typically occur when trajectories self-overlap due to local rotations or abrupt changes of direction (trajectories with high curvatures or even discontinuities at contacts). We address these cases with minor computational and memory overheads, and offer enhanced impact expressiveness by combining smear and squash-and-stretch effects at collisions.

---

## P05

**Title.** Storyboarding in Extended Reality: leveraging real-world elements in storyboard creation

**Abstract.** Recent technological innovations, especially in extended reality (XR) and artificial intelligence (AI), redefine storytelling approaches. These innovations are expanding creative possibilities for filmmakers while transforming how audiences engage with and experience films and other entertainment products. Despite technological advancements, the pre-production phase depends primarily on traditional planning and visualization methods. This research proposes a novel paradigm to create storyboards in XR, leveraging the capabilities of object-detection and pose-estimation systems to benefit the storyboarding phase. An application has been designed and developed to create 3D storyboards on a real scale within a physical environment and all its furniture. Wearing a head-mounted display for XR, users can move in the physical space, enrich it with virtual elements and characters, and frame the environment to obtain storyboard panels that mix real and virtual elements. The proposed system has been tested to assess its usability, and initial findings indicate that users have appreciated this application.

---

## P06

**Title.** Investigating How Text and Motion Style Shape Directness In Embodied Conversational Agents

**Abstract.** Embodied Conversational Agents (ECAs) are becoming more widely used for various applications, notably in health. Some studies have demonstrated the effectiveness of delivering Motivational Interviews (MIs), a patient-centred behaviour change method, with ECAs. Despite showing promise, the effect of agent communication style on MI effectiveness remains underexplored. Directness has been shown to impact satisfaction and preference of dialogue systems, and effectiveness in some cases. However, outside of verbal style, how to control directness in ECAs to achieve these goals is not well understood. We designed an ECA to convey different levels of directness through language and Non-Verbal behaviours (NVBs), then evaluated the impact of language and NVB on directness with a perception study. The results showed that language influenced perceived directness, and that NVB contributed when aligned with indirect language. These findings suggest ways to shape conversational agents' communication style to enhance their effectiveness.

---

## P07

**Title.** Controller influence on self-determination versus performance in a mobile augmented reality platform game

**Abstract.** In this work, we investigate three control strategies - joystick, laser, and tilt - for playing a platform game in mobile augmented reality. We analyze these strategies using both objective game metrics as well as self-reported measures of autonomy, competence, and intuitiveness. We found no significant differences in self-reported autonomy and competence between our three controllers, despite clear differences in duration needed to play, clear differences in the amount of movement of the character, and significant differences in intuitiveness ratings. All controllers were effective for playing the game. However, despite the joystick's faster completion times and higher intuitiveness ratings, half of our players still chose our laser or tilt controller as their favorite. These results were consistent even with different difficulties of game level.

---

## P08

**Title.** Adaptive Sub-stepping for Constrained Rigid Body Simulations

**Abstract.** Achieving stable simulation of constrained rigid body systems is a primary concern for many computer graphics applications, such as video games, robotic planning, and virtual reality training. In this paper, we present a novel adaptive sub-stepping scheme that achieves stable simulation by adaptively reducing the time step as needed. Our approach employs a diagonalized geometric stiffness matrix as a heuristic to determine when smaller time steps are required, and adjusts the number of sub-steps accordingly. Our method is straightforward to integrate into existing rigid body simulators, and further eliminates manually tuning the number of sub-steps required. We demonstrate the ability of our method to produce stable simulates at real-time frame rates using a number of challenging, complex examples.

---
