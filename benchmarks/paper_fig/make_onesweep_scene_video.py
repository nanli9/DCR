#!/usr/bin/env python3
"""One-sweep SCENE video: the row weight decides whether bystanders launch.

Two acts, each a locked-camera, two-panel, slow-motion clip of ONE real scene.
Act 1 sets its panels side by side; act 2's table is 2.2 m long, so its two
panels are stacked, each spanning the full frame, and it locks its own camera.
Both panels of an act are independent runs of the same shipped
position-based host from identical build states at the same fixed budget
(1 constraint iteration x 8 substeps per 1/120 s frame). The ONLY difference
is the modal contact row's weight:

  shipped -- the mass-shaped weight 1/M_q
  matched -- the reconstruction-matched charge mass 1/(4 M_q + h^2 K_q),
             i.e. mu = m(kappa^2 + b) at the host's shipped kappa = 2

  ACT 1  a steel cantilever shelf: five standing books, a 6 kg weight dropped
         1.0 m a quarter of a metre away from them.
  ACT 2  a dinner table (2.2 x 1.1 m, the paper's own Table 2 material): six
         place settings, four teacups, two candlesticks, and a 5 kg pot
         dropped 0.8 m onto the BARE centre of the table. The pot never
         touches any of them; every response is transmitted through the table.

The pot-never-touches-anything claim is measured, not assumed, and it is
measured ROTATION-AWARE: the candlestick nearest the pot topples towards it, so
an upright axis-aligned half-extent test overstates the clearance badly (it
reports 155.9 mm where the real footprint gap is 86.5 mm). Over every recorded
substep of every recorded arm, the minimum separation between the pot's box and
any crockery box -- taken as the distance between their true rotated footprints
in the horizontal plane, and cross-checked as a 3D box-box separating-axis gap
-- is 86.5 mm (unfixed arm, substep 1152, the near candlestick; 148.5 mm on the
matched arm, 158.0 mm on the converged reference). That separation is strictly
positive at every substep, so the two boxes never overlap and no pot-crockery
contact can occur; the slates therefore quote a conservative 85 mm floor. The
same measurement on act 1 puts the dropped weight no closer than 128.4 mm to
any book, quoted as a 125 mm floor.

Nothing is staged. Every body pose, every board/table deflection and every
joule on screen is read from a frozen recording of those runs
(out/onesweep_scene_data/*.npz, written by onesweep_scene_record.py). No frame
is retimed relative to another: the two panels of an act advance on one shared
substep clock, so the divergence after the weight lands is the physics, not the
edit.

Playback is 32x slow motion (one captured substep = one video frame at 30 fps)
with a 0.9 s freeze at the energy peak. That is the only way the few
milliseconds in which the shipped-weight arm's bystanders leave the surface are
legible. Each act's playback window ends shortly after its motion dies out; on
the shelf that is 12 substeps after the last displacement of any body above
0.25 mm per substep, so the clip does not sit on a still frame.

Disclosure furniture carried by BOTH acts (D1-D4 of the honesty review):

  D1  a persistent slate states the operating point: iteration x substep
      budget, modal relaxation, passivity governor state, the support material,
      and the drop height. The effect is budget-graded, so an undisclosed
      budget would read as rigging -- and each act states ITS OWN measured
      grading, because the two scenes do not grade the same way: on the table
      the gain is gone at 4 x 8, on the shelf 4 x 8 still gains 856 J and it
      takes 8 x 8.
  D2  the big joule number is almost entirely SUPPORT-MODE energy (99.998% of
      it on the shelf, 98.4% on the table). It is labelled as board-/table-mode
      energy, and the bystanders' own TRANSLATIONAL kinetic energy is shown as
      its own, much smaller number. Translational is what the readout says,
      because translational is all it sums: the rotational part is excluded (no
      inertia tensor is stored in the recording), so the number cannot be read
      as the objects' total kinetic energy.
  D3  the converged reference is NOT on screen as a panel, so its scale is
      quoted in every panel from the two converged self-references. On the
      table those two agree (11.6 and 11.8 mm) and are quoted as a span. On the
      shelf they DISAGREE by 89x (9.6 mm at 1/960 s substeps, 0.1 mm at
      1/120 s), so act 1 states them as two disagreeing references on two
      substep grids rather than as a tolerance band -- a range there would
      claim a precision nobody has. The matched-weight arm is not ground truth:
      on the table it under-moves the converged scale.
  D4  the slow-motion factor AND the peak freeze are stated in the slate.

Claim discipline, held to the paper's line: that a finite-iteration coupling
can deposit spurious energy is a KNOWN effect and is conceded on screen; what
this clip shows is that the row's weight -- not its budget -- sets the sign, in
full scenes rather than a single parked row.

Run (needs ffmpeg on PATH):
  .venv/bin/python benchmarks/paper_fig/make_onesweep_scene_video.py
  .venv/bin/python benchmarks/paper_fig/make_onesweep_scene_video.py --quick
  .venv/bin/python benchmarks/paper_fig/make_onesweep_scene_video.py \
      --act dinner                     # one act alone, for iteration
  .venv/bin/python benchmarks/paper_fig/make_onesweep_scene_video.py \
      --act dinner --probe 0,45,130    # single PNGs, for framing checks
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

# ---- writable matplotlib cache BEFORE importing matplotlib (binding rule) ---- #
os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mplcache_onesweep_scene_")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The renderer and the arm palette are shared with the other paper artifacts so
# the two videos read as the same system. Neither file is modified here.
from benchmarks.paper_fig.figstyle import PALETTE                  # noqa: E402
from benchmarks.paper_fig.render3d import (                        # noqa: E402
    Camera, Renderer, assert_layering_valid, box_corners, slab_top)

# ----------------------------- dark-theme constants -------------------------- #
FPS_DEFAULT = 30
W_IN, H_IN, DPI = 16.0, 9.0, 120                # 1920 x 1080 (even dims)
BG = "#0f1116"
FG = "#e8e8ea"
DIM = "#9aa0a8"
FAINT = "#767d88"
PANEL_EDGE = "#2a2f3a"
GRID = "#232833"

C_UNFIXED = PALETTE["clamp_off"]                # vermillion -- shipped weight
C_FIXED = "#4ea36b"                             # green      -- matched weight
SUPPORT_COLOR = (0.60, 0.63, 0.68)              # steel board / table

ARM_COLOR = {"unfixed": C_UNFIXED, "fixed": C_FIXED}
ARM_LABEL = {"unfixed": "mass-shaped row weight",
             "fixed": "matched row weight"}
ARM_SUB = {"unfixed": r"$1/M_q$",
           "fixed": r"$1/(4M_q + h^2K_q)$   $\mu = m(4+b)$"}

DATA_DIR = os.path.join(_ROOT, "benchmarks", "paper_fig", "out",
                        "onesweep_scene_data")
OUT_MP4 = os.path.join(_ROOT, "benchmarks", "paper_fig", "out",
                       "onesweep_scene_video.mp4")

# The one line of prose that is on screen for the whole clip. The injection
# phenomenon is prior art and is conceded here, not claimed.
CONCESSION = ("A fixed-iteration coupling can deposit energy: a known effect. "
              "What differs here is the row's weight, not its iteration budget.")

CLOSING_LINE = ("One index per contact row, computable before the solve: the "
                "matched weight prices the row for the host's own "
                "reconstruction.")
CLOSING_FORMULA = (r"$w \;=\; 1/(4M_q + h^2K_q)$"
                   r"$\qquad$ from $\;\mu = m(\kappa^2 + b)\;$ at the "
                   r"shipped $\kappa = 2$")
CLOSING_SLATE = ("both acts:  1 iteration x 8 substeps  |  modal relax 1.0  |  "
                 "passivity governor OFF  |  independent runs, nothing toggled "
                 "mid-trajectory  |  offline CPU float64, no real-time claim")


# --------------------------------------------------------------------------- #
# act specifications                                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Act:
    key: str
    npz: str
    title: str
    layout: str                      # "side" (2 panels) | "stack" (2 rows)
    cam: dict
    pre_roll: int                    # substeps of run-up shown before contact
    post_roll: int                   # substeps shown after contact
    mode_noun: str                   # D2: what the big joule number really is
    item_noun: str                   # what a bystander is called
    conv_label: str                  # D3: how the converged refs are named
    conv_range: str                  # D3: their value, when they agree
    conv_note: str                   # D3: one full-width line, when they do not
    slate_a: str                     # D1: the operating point
    slate_b: str                     # D1/D4 caveats (playback rate prepended)
    slate_c: str                     # D1: remaining caveats (may be empty)
    grid_x: tuple                    # real scale ruling drawn in front
    grid_z: tuple
    grid_step: float
    ghost_mm: float                  # rest-pose silhouette threshold
    head_room: float = 0.0           # empty band at the top of a panel
    masses_json: str | None = None   # only where the npz carries no masses
    margin: float = 0.07
    body_lw: float = 0.6
    extra: dict = field(default_factory=dict)


ACT_SHELF = Act(
    key="shelf",
    npz=os.path.join(DATA_DIR, "onesweep_scene_traj.npz"),
    title="Same drop, same budget: only the contact-row weight differs",
    layout="side",
    # Near-profile: the eye sits almost in the books' own plane (4.7 deg of
    # azimuth for depth cue only) and 8 deg above the board, which is also what
    # makes the renderer's support-behind-bodies draw order exact (see
    # render3d.assert_layering_valid).
    cam=dict(eye=(0.10, 0.255, 1.20), target=(0.00, 0.070, 0.0), fov_deg=24.0),
    pre_roll=45,
    # M2: the recorded arm keeps drifting for another 260 substeps, but at
    # <= 0.22 mm per substep -- 8.7 s of playback in which nothing reads as
    # motion and the rise readout is frozen. The window now ends 12 substeps
    # after the last displacement of ANY body above 0.25 mm/substep (substep
    # 700; for a bystander alone it is substep 654), which still contains the
    # whole launch, the 15.6 deg tilt peak (substep 600) and the final 56.82 mm
    # running-max rise (reached at substep 540).
    post_roll=280,
    mode_noun="board-mode energy",
    item_noun="book",
    conv_label="",
    conv_range="",
    # D3, act 1: the two converged self-references DISAGREE by 89x here
    # (9.647 mm at 32x8 on the 1/960 s substep grid, 0.108 mm at 500x1 on the
    # 1/120 s grid), so they are stated as two references on two grids. A
    # "0.1 to 9.7 mm" range read as a tolerance band, which it is not.
    conv_note=("converged references disagree 89x:  9.6 mm at 1/960 s "
               "substeps,  0.1 mm at 1/120 s"),
    slate_a=("operating point:  1 iteration x 8 substeps per 1/120 s frame"
             "  |  modal relaxation 1.0  |  passivity governor OFF"
             "  |  steel shelf, E = 200 GPa, thickness 30 mm"
             "  |  6 kg dropped 1.00 m, never closer than 125 mm to a book"),
    slate_b=("independent runs, nothing toggled mid-trajectory  |  offline "
             "CPU float64, no real-time claim"),
    # D1, measured for THIS act (the shelf grades differently from the table):
    # 1x8 +925,494 J -> 2x8 +151,140 J -> 4x8 +856 J -> 8x8 0 J, same substep
    # grid, same shipped weight, only the iteration count raised.
    slate_c=("budget grading measured on this shelf:  raising only the "
             "iteration count, 2 x 8 still gains 151,140 J and 4 x 8 gains "
             "856 J; the gain first vanishes at 8 x 8"),
    grid_x=(-0.40, 0.40),
    grid_z=(0.10, 0.14),
    grid_step=0.10,
    ghost_mm=3.0,
    masses_json=os.path.join(DATA_DIR, "act1_shelf_energy_split.json"),
)

ACT_DINNER = Act(
    key="dinner",
    npz=os.path.join(DATA_DIR, "onesweep_dinner_traj.npz"),
    title="Second scene, same test: only the contact-row weight differs",
    layout="stack",
    # The table is 2.2 x 1.1 m, so this act locks its OWN camera: a long side
    # view from 4.9 m, 17 deg above the table plane and 5 deg off its axis, far
    # enough that the near and far place settings stay legible without the
    # perspective swelling the near row.
    cam=dict(eye=(0.41, 1.52, 4.66), target=(0.00, 0.09, 0.0), fov_deg=24.0),
    pre_roll=30,
    post_roll=845,
    mode_noun="table-mode energy",
    item_noun="item",
    # D3, act 2: here the two converged self-references AGREE (11.578 mm at
    # 500x1, 11.776 mm at 32x8), so a span is honest -- and it is labelled as
    # covering both substep grids.
    conv_label="converged references, both grids",
    conv_range="11.6 to 11.8 mm",
    conv_note="",
    # B1: the old "no object within 155 mm" was measured with UPRIGHT
    # axis-aligned half-extents. The near candlestick topples towards the pot,
    # and the true rotated-footprint gap falls to 86.5 mm (substep 1152). The
    # claim that matters -- no pot-crockery contact, so every crockery response
    # is carried by the table -- is what is stated, with a conservative floor.
    slate_a=("operating point:  1 iteration x 8 substeps per 1/120 s frame"
             "  |  modal relaxation 1.0  |  passivity governor OFF"
             "  |  table E = 1.1 GPa, the paper's own material, not tuned"
             "  |  5 kg dropped 0.80 m onto the bare centre"),
    slate_b=("independent runs, nothing toggled mid-trajectory  |  offline "
             "CPU float64, no real-time claim"),
    # D1, measured for THIS act only (m5: the shelf grades differently and
    # states its own): 1x8 +808.8 J -> 2x8 +3.2 J -> 4x8 0 J -> 8x8 0 J.
    slate_c=("the pot never contacts any object:  its rotated footprint stays "
             "more than 85 mm clear of every one, so every response is carried "
             "by the table  |  budget grading measured on this table:  2 x 8 "
             "still gains 3.2 J, and at 4 x 8 the gain is gone entirely"),
    grid_x=(-1.10, 1.10),
    grid_z=(0.46, 0.54),
    grid_step=0.20,
    ghost_mm=8.0,
    head_room=0.20,
    body_lw=0.45,
)

ACTS = {"shelf": ACT_SHELF, "dinner": ACT_DINNER}


# --------------------------------------------------------------------------- #
# frozen bundle                                                                #
# --------------------------------------------------------------------------- #
class Scene:
    """Accessor over the frozen recording. Nothing here computes physics."""

    def __init__(self, act: Act):
        if not os.path.exists(act.npz):
            raise SystemExit(f"missing {act.npz} -- run onesweep_scene_record.py")
        self.act = act
        self.d = np.load(act.npz)
        self.half = np.asarray(self.d["half"], float)
        self.color = np.asarray(self.d["color"], float)
        self.is_impactor = np.asarray(self.d["is_impactor"], bool)
        self.names = [str(s) for s in self.d["body_names"]]
        self.rest = np.asarray(self.d["support_rest"], float)
        self.Uy = np.asarray(self.d["support_Uy"], float)
        self.nx, self.nz = (int(v) for v in self.d["grid"])
        self.thick = float(self.d["support_thickness"])
        self.h = float(self.d["h_sub"])
        self.n = int(self.d["n_common"])
        self.nb = self.half.shape[0]
        self.impact = int(self.d["unfixed/impact_idx"])
        self.lo = max(0, self.impact - act.pre_roll)
        self.hi = min(self.n, self.impact + act.post_roll)
        self.mass = self._masses()
        self._ke_cache: dict[str, np.ndarray] = {}
        self._rise_cache: dict[str, np.ndarray] = {}
        self._wid_cache: dict[tuple, list[str]] = {}

    # ---- D2: the bystanders' own translational kinetic energy -------------
    def _masses(self) -> np.ndarray:
        """Per-body mass in kg.

        The dinner recording carries `mass`. The shelf recording predates that
        key, so its masses come from the recorded energy-split artifact (which
        recovered them by rebuilding the same scene); they are never guessed.
        """
        if "mass" in self.d.files:
            return np.asarray(self.d["mass"], float)
        p = self.act.masses_json
        if not p or not os.path.exists(p):
            raise SystemExit(f"missing {p} -- needed for the D2 kinetic-energy "
                             f"readout of act '{self.act.key}'")
        with open(p) as fh:
            table = json.load(fh)["body_masses_kg"]
        return np.array([float(table[n]) for n in self.names])

    def ke_bystander(self, arm) -> np.ndarray:
        """sum_b 1/2 m_b |v_b|^2 over every body except the impactor.

        Translational only, matching the recorded D2 split; the rotational part
        is deliberately excluded so the number cannot be inflated.
        """
        if arm not in self._ke_cache:
            v = np.asarray(self.d[f"{arm}/vel"], float)[:, ~self.is_impactor]
            m = self.mass[~self.is_impactor]
            self._ke_cache[arm] = 0.5 * (m[None, :, None] * v ** 2).sum(axis=(1, 2))
        return self._ke_cache[arm]

    def rise_running_max(self, arm) -> np.ndarray:
        """Highest lift of any bystander so far, in mm (running max)."""
        if arm not in self._rise_cache:
            r = np.asarray(self.d[f"{arm}/book_rise_mm"], float).max(axis=1)
            self._rise_cache[arm] = np.maximum.accumulate(
                np.where(np.arange(len(r)) >= self.lo, r, -np.inf))
        return self._rise_cache[arm]

    def pos(self, arm, f):
        return self.d[f"{arm}/pos"][f]

    def quat(self, arm, f):
        return self.d[f"{arm}/quat"][f]

    def top(self, arm, f):
        return slab_top(self.rest, self.Uy, self.d[f"{arm}/q"][f])

    def e_total(self, arm):
        return np.asarray(self.d[f"{arm}/e_total"], float)

    def e_modal(self, arm):
        return np.asarray(self.d[f"{arm}/e_modal"], float)

    def rest_pose(self, arm):
        """Pose one substep before first contact -- the bystanders' own rest."""
        r = int(self.d[f"{arm}/ref_idx"])
        return self.d[f"{arm}/pos"][r], self.d[f"{arm}/quat"][r]

    def hold_frame(self, arm="unfixed"):
        """The substep the clip pauses on: the arm's total-energy peak.

        Data-driven, not chosen by eye -- it is one substep after first contact
        in both recordings, so the pause lands on the headline instant.
        """
        e = self.e_total(arm)[self.lo:self.hi]
        return self.lo + int(np.argmax(e))


# --------------------------------------------------------------------------- #
# framing: one box for every displayed frame of both arms                      #
# --------------------------------------------------------------------------- #
def make_camera(act: Act) -> Camera:
    """The act's locked camera, at unit aspect.

    DEVIATION from the sibling paper scripts: they pass the panel's width/height
    ratio into `Camera(aspect=...)`, which divides projected x by that ratio
    while the axes are then drawn with `set_aspect("equal")` -- so a world
    square lands on screen `ratio` times taller than wide. That is invisible at
    the shelf's ratio and ruinous at this act's, where a 2.2 m table would be
    drawn as if it were 0.4 m across. render3d.py is not modified: the camera
    is simply kept at unit aspect (undistorted) and the letterboxing is done in
    the axis limits below, which is where a plain painter's renderer wants it.
    """
    return Camera(aspect=1.0, **act.cam)


def global_bounds(sc: Scene, arms, box_ratio, step=3):
    """Lock xlim/ylim once. A comparison whose camera moves is not a comparison.

    Computed over every body corner of every sampled frame of every rendered
    arm, so nothing displayed can ever leave the frame and the view cannot
    breathe between panels or beats. The limits are padded to the panel's own
    width/height ratio, so `set_aspect("equal")` fills the panel exactly and
    every body keeps its true proportions. `head_room` adds an empty band at
    the top of the view for the readout strip; it is applied identically to
    both panels, so it cannot bias the comparison.
    """
    act = sc.act
    cam = make_camera(act)
    pts = []
    for arm in arms:
        pos, quat = sc.d[f"{arm}/pos"], sc.d[f"{arm}/quat"]
        for f in range(sc.lo, sc.hi, step):
            for i in range(sc.nb):
                pts.append(box_corners(sc.half[i], pos[f, i], quat[f, i]))
    # a strip of the support on each side, so bodies never touch the frame edge
    board_y = float(sc.rest[0, 1])
    x0, x1 = act.grid_x
    z0, z1 = float(sc.rest[:, 2].min()), float(sc.rest[:, 2].max())
    pts.append(np.array([[sx, board_y - sc.thick, sz]
                         for sx in (x0 - 0.02, x1 + 0.02) for sz in (z0, z1)]))
    xy, _ = cam.project(np.vstack(pts))
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    c = 0.5 * (lo + hi)
    hw, hh = 0.5 * (hi - lo) * (1.0 + act.margin)
    if hw / hh < box_ratio:
        hw = hh * box_ratio
    else:
        hh = hw / box_ratio
    ylim = (c[1] - hh, c[1] + hh)
    xlim = (c[0] - hw, c[0] + hw)
    if act.head_room > 0.0:
        # grow the view (keeping the ratio) and put all the new space on top
        hh2 = hh * (1.0 + act.head_room)
        hw2 = hh2 * box_ratio
        ylim = (c[1] - hh, c[1] - hh + 2.0 * hh2)
        xlim = (c[0] - hw2, c[0] + hw2)
    return xlim, ylim


# --------------------------------------------------------------------------- #
# one scene panel                                                              #
# --------------------------------------------------------------------------- #
def scene_axes(fig, rect):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(PANEL_EDGE)
        sp.set_linewidth(1.0)
    return ax


def draw_scene(ax, sc: Scene, arm, f, *, xlim, ylim, ghosts=True):
    """Real cubes, real support deflection, true scale, locked camera."""
    act = sc.act
    ax.clear()
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    r = Renderer(make_camera(act), ambient=0.46, diffuse=0.60)

    # real reference ruling on the support's REST plane (the undeflected
    # surface), kept to the strip in FRONT of every body. render3d draws line
    # work over the polygons, so a full-footprint lattice would show through
    # the boxes; nearer than every body, it cannot.
    r.add_ground_grid(float(sc.rest[0, 1]), act.grid_x, act.grid_z,
                      step=act.grid_step, color="#7b8290", lw=0.7, alpha=0.8)

    top = sc.top(arm, f)
    r.add_slab_seamless(top, sc.nx, sc.nz, sc.thick, SUPPORT_COLOR)

    pos, quat = sc.pos(arm, f), sc.quat(arm, f)
    p0, q0 = sc.rest_pose(arm)

    # the painter's-algorithm premise (bodies never behind the support) is
    # checked against the DEFLECTED surface on every frame, not assumed
    bottoms = []
    for i in range(sc.nb):
        V = box_corners(sc.half[i], pos[i], quat[i])
        bottoms.append(V[int(np.argmin(V[:, 1]))])
    assert_layering_valid(np.array(bottoms), top)

    moved = np.linalg.norm(pos - p0, axis=1) * 1e3
    for i in range(sc.nb):
        # dashed silhouette = where this bystander was resting before contact.
        # The impactor's own descent is the input, not a result, so it gets none.
        if ghosts and moved[i] > act.ghost_mm and not sc.is_impactor[i]:
            r.add_box_wire(sc.half[i], p0[i], q0[i], color="#7b828e", lw=0.9,
                           ls=(0, (3, 2)), alpha=0.85)
        r.add_box(sc.half[i], pos[i], quat[i], sc.color[i],
                  edge=(0.12, 0.13, 0.16))
    r.draw(ax, xlim=xlim, ylim=ylim, lw=act.body_lw)
    return ax


# --------------------------------------------------------------------------- #
# frames -> png                                                                #
# --------------------------------------------------------------------------- #
class Writer:
    """Sequentially numbered PNGs; a held frame is copied, not re-rendered."""

    def __init__(self, d):
        self.d = d
        self.n = 0
        self.marks: list[tuple[str, int]] = []

    def mark(self, label):
        self.marks.append((label, self.n))

    def add(self, fig, times=1):
        p = os.path.join(self.d, f"f{self.n:05d}.png")
        fig.savefig(p, dpi=DPI, facecolor=BG)
        for _ in range(times - 1):
            self.n += 1
            shutil.copyfile(p, os.path.join(self.d, f"f{self.n:05d}.png"))
        self.n += 1


def _fmt_j(v: float) -> str:
    v = float(v)
    if v >= 1000.0:
        return f"{v:,.0f} J"
    if v >= 10.0:
        return f"{v:.1f} J"
    if v >= 0.1:
        return f"{v:.2f} J"
    if v >= 0.001:
        return f"{v:.3f} J"
    return "<0.001 J"


def _fmt_mm(v: float) -> str:
    return f"{max(float(v), 0.0):.1f} mm"


# --------------------------------------------------------------------------- #
# disclosure furniture                                                         #
# --------------------------------------------------------------------------- #
def slow_factor(sc: Scene, fps: int, step: int) -> float:
    """D4: how much slower than reality the playback runs."""
    return 1.0 / (sc.h * fps * step)


def fit_text(fig, txt, max_frac=0.955, min_size=6.5, step=0.25):
    """Shrink a one-line label until it fits the frame. Deterministic.

    The slates are long and the frame is fixed, so this is a guard against a
    disclosure line being silently clipped off the edge of the video.
    """
    r = fig.canvas.get_renderer()
    w_px = fig.get_figwidth() * fig.dpi
    while txt.get_fontsize() > min_size:
        if txt.get_window_extent(renderer=r).width / w_px <= max_frac:
            break
        txt.set_fontsize(txt.get_fontsize() - step)
    return txt


def add_footers(fig, sc: Scene, fps, step, hold_frames: int | None = None):
    """One line of prose (the concession) + the metadata slate (D1 and D4).

    The slate is fine print, not prose: it is what a reader has to be able to
    pause on to know what operating point produced the footage. D1 (budget,
    relaxation, governor, material, drop) is the first line; D4 (the
    slow-motion factor AND the freeze at the peak) opens the second; the third
    carries this act's own measured budget grading.

    `hold_frames` is the number of byte-identical frames the peak freeze
    actually emits. It is disclosed because "32x slow motion" is not true of
    those frames -- they run at 0x -- and an undisclosed freeze in a clip whose
    whole argument is a few milliseconds long would be a real omission.
    """
    fit_text(fig, fig.text(0.5, 0.080, CONCESSION, ha="center", va="center",
                           fontsize=11.5, color=DIM))
    fit_text(fig, fig.text(0.5, 0.056, sc.act.slate_a, ha="center",
                           va="center", fontsize=9.5, color=FAINT))
    freeze = ""
    if hold_frames:
        # "the same frame N times" rather than "N identical frames": the source
        # frames ARE one file copied N times, but h264 does not reconstruct
        # them bit-identically, and the claim on screen should be true of the
        # encoded video a reader actually holds.
        freeze = (f", then frozen {hold_frames / fps:.1f} s at the energy peak "
                  f"(the same frame {hold_frames} times)")
    slate_b = (f"playback {slow_factor(sc, fps, step):.0f}x slow motion, one "
               f"captured substep per video frame{freeze}  |  {sc.act.slate_b}")
    fit_text(fig, fig.text(0.5, 0.034, slate_b, ha="center", va="center",
                           fontsize=9.5, color=FAINT))
    if sc.act.slate_c:
        fit_text(fig, fig.text(0.5, 0.013, sc.act.slate_c, ha="center",
                               va="center", fontsize=9.5, color=FAINT))


def readout_fields(sc: Scene):
    """The numbers each panel carries. D2 is rows 1-2, D3 is the last entry.

    Row 1 is the headline joule number, named for what it actually is (D2):
    energy in the support's own modes, not in the objects. Row 2 is the objects'
    own TRANSLATIONAL kinetic energy, which is three to six orders of magnitude
    smaller; it is named translational because that is all `ke_bystander` sums
    (the recording stores no inertia tensor, so the rotational part is simply
    not in the number, and calling it "kinetic energy" overstated it).

    The last entry is static (D3) and comes in two shapes, chosen per act by
    the data: a label+value pair where the two converged self-references agree,
    and a single full-width note where they disagree, so that a disagreement
    can never be read as a tolerance band.
    """
    act = sc.act
    out = [
        (act.mode_noun, lambda arm, f: _fmt_j(sc.e_modal(arm)[f]), "arm"),
        (f"{act.item_noun}s' translational kinetic energy",
         lambda arm, f: _fmt_j(sc.ke_bystander(arm)[f]), "fg"),
        (f"highest {act.item_noun} lifted so far",
         lambda arm, f: _fmt_mm(sc.rise_running_max(arm)[f]), "fg"),
    ]
    if act.conv_note:
        out.append((act.conv_note, None, "note"))
    else:
        out.append((act.conv_label, lambda arm, f: act.conv_range, "dim"))
    return out


LAB_SIZE_SIDE, VAL_SIZE_SIDE = 12.5, 13.5
LAB_SIZE_ROW, VAL_SIZE_ROW = 11.5, 12.5


def _text_frac_w(fig, s, size, family=None) -> float:
    """Width of `s`, as a fraction of the frame, measured not guessed.

    Drawn off-canvas, measured, removed. Deterministic for a given matplotlib
    and font set, and dpi-independent (points per figure width is fixed), which
    is what lets the layout below GUARANTEE that a label and its value never
    collide instead of hoping a hand-tuned column fraction still fits.
    """
    t = fig.text(0.0, -1.0, s, fontsize=size, family=family)
    w = t.get_window_extent(renderer=fig.canvas.get_renderer()).width
    t.remove()
    return w / (fig.get_figwidth() * fig.dpi)


def widest_values(sc: Scene, arms, fields) -> list[str]:
    """The longest string each live field can show anywhere in this clip.

    Read off the recording (both arms, every displayed substep), so the value
    columns are sized for the real numbers rather than for today's frame.
    """
    key = tuple(arms)
    if key not in sc._wid_cache:
        out = []
        for _lab, getter, kind in fields:
            best = ""
            if getter is not None:
                for arm in arms:
                    for f in range(sc.lo, sc.hi):
                        s = getter(arm, f)
                        if len(s) > len(best):
                            best = s
            out.append(best)
        sc._wid_cache[key] = out
    return sc._wid_cache[key]


def place_readout(fig, sc: Scene, arm, rect, layout, arms=("unfixed", "fixed")):
    """Static labels, live values. Returns the value text objects, in order.

    m4: in the side-by-side layout this block used to sit INSIDE the panel, in
    its top-left corner -- which is exactly where the dark-red impactor hangs
    at the start of the act and falls through for the next ~35 frames, so the
    D3 line was drawn in faint grey over dark red. It now sits in the frame
    background ABOVE the panel (the panel is 0.05 shorter to make room), where
    the axes cannot draw at all, so no readout character can ever land on
    geometry. The stacked layout keeps its head-room band, which is empty by
    construction (`global_bounds` grows the view upward by `head_room`).
    """
    x0, y0, w, h = rect
    fields = readout_fields(sc)
    wid = widest_values(sc, arms, fields)
    col = {"arm": ARM_COLOR[arm], "fg": FG, "dim": FAINT, "note": FAINT}
    live = [(lab, kind, wv) for (lab, g, kind), wv in zip(fields, wid)
            if g is not None]
    out = []
    if layout == "side":
        xl = x0 + 0.012
        lab_w = max(_text_frac_w(fig, lab, LAB_SIZE_SIDE) for lab, _k, _v in live)
        val_w = max(_text_frac_w(fig, v, VAL_SIZE_SIDE, "monospace")
                    for _l, _k, v in live)
        xv = xl + lab_w + 0.028 + val_w
        y = y0 + h + 0.110                      # above the panel, not in it
        for lab, getter, kind in fields:
            if getter is None:                  # D3 note: one full-width line
                fit_text(fig, fig.text(xl, y0 + h + 0.026, lab, ha="left",
                                       va="center", fontsize=11.0, color=FAINT),
                         max_frac=w - 0.004)
                continue
            fig.text(xl, y, lab, ha="left", va="center", fontsize=LAB_SIZE_SIDE,
                     color=DIM)
            out.append(fig.text(xv, y, "", ha="right", va="center",
                                fontsize=VAL_SIZE_SIDE, color=col[kind],
                                family="monospace"))
            y -= 0.026
    else:
        # one horizontal line across the row's empty head-room band, laid out
        # by measurement: label, then its own value column, then the next pair
        y = y0 + h - 0.030
        size_l, size_v = LAB_SIZE_ROW, VAL_SIZE_ROW
        gap_lv, gap_f = 0.014, 0.030
        while True:
            wl = [_text_frac_w(fig, lab, size_l) for lab, _g, _k in fields]
            wv = [_text_frac_w(fig, v, size_v, "monospace") if v else 0.0
                  for v in wid]
            need = sum(wl) + sum(wv) + gap_lv * len(fields) + gap_f * (len(fields) - 1)
            if need <= w - 0.012 or size_l <= 7.5:
                break
            size_l -= 0.25
            size_v -= 0.25
        xl = x0 + 0.010
        for (lab, getter, kind), lw, vw in zip(fields, wl, wv):
            fig.text(xl, y, lab, ha="left", va="center", fontsize=size_l,
                     color=DIM if kind != "note" else FAINT)
            if getter is not None:
                out.append(fig.text(xl + lw + gap_lv + vw, y, "", ha="right",
                                    va="center", fontsize=size_v,
                                    color=col[kind], family="monospace"))
            xl += lw + gap_lv + vw + gap_f
    return out


def energy_strip(fig, sc: Scene, arms, rect):
    """Calm shared energy curve: the same instant on one axis. Not a card."""
    axt = fig.add_axes(rect)
    axt.set_facecolor(BG)
    t_ms = (np.arange(sc.n) - sc.impact) * sc.h * 1e3
    t0_ms = (sc.lo - sc.impact) * sc.h * 1e3
    t1_ms = (sc.hi - 1 - sc.impact) * sc.h * 1e3
    for arm in arms:
        axt.semilogy(t_ms, np.maximum(sc.e_total(arm), 1e-1),
                     color=ARM_COLOR[arm], lw=1.7)
    # The baseline is the scene's energy at the START of the recording, which
    # is the one value both arms share. It is deliberately not the energy just
    # before contact: by then the shipped-weight arm has already gained some,
    # from the RESTING bodies' own support rows, and the curve should show that
    # rather than hide it in the reference.
    e0 = float(sc.e_total(arms[0])[0])
    axt.axhline(e0, color="#7f8794", lw=1.0, ls=(0, (4, 3)))
    axt.text(t1_ms - 8, e0 * 1.6,
             f"scene's energy at the start of the run {e0:.1f} J",
             fontsize=10.5, color=DIM, va="bottom", ha="right")
    axt.set_xlim(t0_ms, t1_ms)
    # ---- M1: the axis must not be able to flatten its own headline ----------
    # `set_yticks([1e1, 1e3, 1e5])` was called AFTER `set_ylim`, and
    # Axes.set_ticks WIDENS the view limits to admit ticks that fall outside
    # them. On act 2 that silently pushed the top of the axis from 6 x 857 J =
    # 5.1e3 J up to 1e5 J, so the recorded 857 J peak was drawn at 59% of the
    # axis height instead of 79% and the highest labelled decade below it was
    # 1e1. Act 1 was unaffected (its ticks were already inside the limits),
    # which is exactly why the bug was invisible. The ticks are now DERIVED
    # from the limits (so none can ever be outside), set first, and the limits
    # are set last.
    ymax = max(float(sc.e_total(a)[sc.lo:sc.hi].max()) for a in arms)
    yhi = ymax * 4.0
    ndec = int(np.floor(np.log10(yhi)))
    ticks = [10.0 ** k for k in range(0, ndec + 1, 1 if ndec <= 4 else 2)]
    axt.set_yticks(ticks)
    axt.set_ylim(1.0, yhi)
    # and the peak is named, on the curve's own axis, so the headline number is
    # readable off the plot rather than only off the per-panel readout
    pk_arm = max(arms, key=lambda a: float(sc.e_total(a)[sc.lo:sc.hi].max()))
    axt.axhline(ymax, color=ARM_COLOR[pk_arm], lw=0.9, ls=(0, (4, 3)),
                alpha=0.8)
    # ABOVE its own line, not below: below is where the baseline annotation
    # already is on act 2's shorter strip, and two right-aligned labels 10 px
    # apart on a 78 px log axis printed on top of each other.
    axt.text(t1_ms - 8, ymax * 1.05, f"peak {ymax:,.0f} J",
             fontsize=10.5, color=ARM_COLOR[pk_arm], va="bottom", ha="right")
    axt.set_ylabel("total scene\nenergy [J]", color=DIM, fontsize=11)
    axt.set_xlabel("milliseconds after first contact", color=DIM, fontsize=11,
                   labelpad=2)
    axt.tick_params(colors=DIM, labelsize=10, length=3)
    for sp in axt.spines.values():
        sp.set_color(PANEL_EDGE)
    axt.grid(True, which="major", color=GRID, lw=0.6)
    return axt, axt.axvline(t0_ms, color=FG, lw=1.3)


# --------------------------------------------------------------------------- #
# layout geometry                                                              #
# --------------------------------------------------------------------------- #
def panel_rects(layout):
    if layout == "side":
        pad, gap = 0.030, 0.016
        pw = (1.0 - 2 * pad - gap) / 2.0
        # m4: 0.455 rather than 0.505 -- the 0.05 comes off the top of the axes
        # so the readout can live outside them, where the impactor cannot reach
        # it. The panels stay identical to each other, so the comparison is
        # untouched; both views just lose 10% of their height.
        p_bot, p_h = 0.245, 0.455
        return [[pad, p_bot, pw, p_h], [pad + pw + gap, p_bot, pw, p_h]]
    x0, w, h = 0.045, 0.910, 0.300
    return [[x0, 0.590, w, h], [x0, 0.245, w, h]]


def panel_ratio(rect):
    """The panel's true width/height on the page (inches, not fractions)."""
    return (rect[2] * W_IN) / (rect[3] * H_IN)


# --------------------------------------------------------------------------- #
# one act                                                                      #
# --------------------------------------------------------------------------- #
def build_act(wr: Writer, sc: Scene, arms, *, fps, quick):
    act = sc.act
    step = 4 if quick else 1
    # m6: the opening was a 2.4 s still of a body in mid-air. It is now a 0.9 s
    # still, and the title instead STAYS UP over the first frames of real
    # playback (up to 4 substeps before contact, so it is always gone before
    # anything lands). The title is readable for as long as it was; the clip
    # just is not frozen while you read it.
    t_title = 0.4 if quick else 0.9
    title_play = max(1, (act.pre_roll - 4) // step)
    t_hold = 0.4 if quick else 0.9
    t_end = 0.8 if quick else 1.6
    hold_frames = int(t_hold * fps) + 1        # the played frame + its copies

    rects = panel_rects(act.layout)
    ratio = panel_ratio(rects[0])
    xlim, ylim = global_bounds(sc, arms, ratio)

    fig = plt.figure(figsize=(W_IN, H_IN), facecolor=BG)

    # opening title: shown over the pre-contact scene, then removed. No cards.
    # The stacked act needs its title higher and smaller: its first panel's
    # header sits where the side-by-side act has empty frame.
    ty, tsize = (0.945, 25.0) if act.layout == "side" else (0.966, 22.0)
    title = fig.text(0.5, ty, act.title, ha="center", va="center",
                     fontsize=tsize, color=FG, fontweight="bold")
    fit_text(fig, title, max_frac=0.90)
    add_footers(fig, sc, fps, step, hold_frames=hold_frames)

    axes, readouts = [], []
    for arm, rect in zip(arms, rects):
        axes.append(scene_axes(fig, rect))
        if act.layout == "side":
            cx = rect[0] + rect[2] / 2
            fig.text(cx, 0.876, ARM_LABEL[arm], ha="center", va="center",
                     fontsize=21, color=ARM_COLOR[arm], fontweight="bold")
            fig.text(cx, 0.843, ARM_SUB[arm], ha="center", va="center",
                     fontsize=14, color=DIM)
        else:
            hy = rect[1] + rect[3] + 0.026
            fig.text(rect[0] + 0.004, hy, ARM_LABEL[arm], ha="left",
                     va="center", fontsize=19, color=ARM_COLOR[arm],
                     fontweight="bold")
            fig.text(rect[0] + 0.245, hy, ARM_SUB[arm], ha="left", va="center",
                     fontsize=13, color=DIM)
        readouts.append(place_readout(fig, sc, arm, rect, act.layout,
                                      arms=arms))

    strip_rect = ([0.075, 0.145, 0.875, 0.086] if act.layout == "side"
                  else [0.075, 0.145, 0.875, 0.072])
    _, cursor = energy_strip(fig, sc, arms, strip_rect)

    # only the fields that carry a live value get a text object back
    live = [fld for fld in readout_fields(sc) if fld[1] is not None]

    def paint(f):
        for ax, arm in zip(axes, arms):
            draw_scene(ax, sc, arm, f, xlim=xlim, ylim=ylim)
        for vals, arm in zip(readouts, arms):
            for txt, fld in zip(vals, live):
                txt.set_text(fld[1](arm, f))
        cursor.set_xdata([(f - sc.impact) * sc.h * 1e3] * 2)

    # --- opening: a short hold on the pre-contact scene, under the title -----
    wr.mark(f"{act.key}:title")
    paint(sc.lo)
    wr.add(fig, times=int(t_title * fps))

    # --- play: one captured substep per frame (32x slow motion) ------------
    wr.mark(f"{act.key}:play")
    hold_at = sc.hold_frame(arms[0])
    for k, f in enumerate(range(sc.lo, sc.hi, step)):
        if k == title_play:                    # title leaves; nothing else moves
            title.set_text("")
        paint(f)
        wr.add(fig)
        if f <= hold_at < f + step:            # brief pause at the energy peak
            wr.add(fig, times=hold_frames - 1)

    # --- end: hold the settled state ---------------------------------------
    wr.mark(f"{act.key}:tail")
    wr.add(fig, times=int(t_end * fps))
    plt.close(fig)


def build_closing(wr: Writer, *, fps, quick):
    """One line of prose, one formula. No cards, no flashing."""
    fig = plt.figure(figsize=(W_IN, H_IN), facecolor=BG)
    fit_text(fig, fig.text(0.5, 0.605, CLOSING_LINE, ha="center", va="center",
                           fontsize=23, color=FG, fontweight="bold"),
             max_frac=0.90)
    fit_text(fig, fig.text(0.5, 0.475, CLOSING_FORMULA, ha="center",
                           va="center", fontsize=25, color=C_FIXED),
             max_frac=0.90)
    fit_text(fig, fig.text(0.5, 0.072, CONCESSION, ha="center", va="center",
                           fontsize=11.5, color=DIM))
    fit_text(fig, fig.text(0.5, 0.028, CLOSING_SLATE, ha="center",
                           va="center", fontsize=9.5, color=FAINT))
    wr.mark("closing")
    wr.add(fig, times=int((1.5 if quick else 3.4) * fps))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# probes                                                                       #
# --------------------------------------------------------------------------- #
def probe(sc: Scene, arms, frames, outdir):
    """Write single PNGs (offsets from the clip start) for framing checks."""
    os.makedirs(outdir, exist_ok=True)
    act = sc.act
    rects = panel_rects(act.layout)
    ratio = panel_ratio(rects[0])
    xlim, ylim = global_bounds(sc, arms, ratio)
    for k in frames:
        f = min(sc.hi - 1, sc.lo + int(k))
        fig = plt.figure(figsize=(W_IN, H_IN), facecolor=BG)
        add_footers(fig, sc, 30, 1)
        for arm, rect in zip(arms, rects):
            ax = scene_axes(fig, rect)
            draw_scene(ax, sc, arm, f, xlim=xlim, ylim=ylim)
            if act.layout == "side":
                cx = rect[0] + rect[2] / 2
                fig.text(cx, 0.876, ARM_LABEL[arm], ha="center", va="center",
                         fontsize=21, color=ARM_COLOR[arm], fontweight="bold")
                fig.text(cx, 0.843, ARM_SUB[arm], ha="center", va="center",
                         fontsize=14, color=DIM)
            else:
                hy = rect[1] + rect[3] + 0.026
                fig.text(rect[0] + 0.004, hy, ARM_LABEL[arm], ha="left",
                         va="center", fontsize=19, color=ARM_COLOR[arm],
                         fontweight="bold")
                fig.text(rect[0] + 0.245, hy, ARM_SUB[arm], ha="left",
                         va="center", fontsize=13, color=DIM)
            vals = place_readout(fig, sc, arm, rect, act.layout, arms=arms)
            live = [fl for fl in readout_fields(sc) if fl[1] is not None]
            for txt, fld in zip(vals, live):
                txt.set_text(fld[1](arm, f))
        fig.text(0.5, 0.100, f"t = {(f - sc.impact) * sc.h * 1e3:+.1f} ms",
                 ha="center", va="center", fontsize=13, color=DIM,
                 family="monospace")
        p = os.path.join(outdir, f"probe_{sc.act.key}_{k:05d}.png")
        fig.savefig(p, dpi=DPI, facecolor=BG)
        plt.close(fig)
        print(f"wrote {p}")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_MP4)
    ap.add_argument("--fps", type=int, default=FPS_DEFAULT)
    ap.add_argument("--act", default="both", choices=["both", "shelf", "dinner"],
                    help="render one act alone, for iteration")
    ap.add_argument("--quick", action="store_true",
                    help="every 4th substep, short holds -- for iterating")
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--probe", default=None,
                    help="comma-separated frame offsets: write PNGs, no video")
    ap.add_argument("--probe-dir",
                    default=os.path.join(tempfile.gettempdir(),
                                         "onesweep_scene_probe"))
    args = ap.parse_args()

    order = ["shelf", "dinner"] if args.act == "both" else [args.act]
    arms = ("unfixed", "fixed")

    if args.probe:
        for key in order:
            probe(Scene(ACTS[key]), arms, [int(v) for v in args.probe.split(",")],
                  args.probe_dir)
        return

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH")

    tmp = tempfile.mkdtemp(prefix="onesweep_scene_video_")
    wr = Writer(tmp)
    try:
        for key in order:
            sc = Scene(ACTS[key])
            build_act(wr, sc, arms, fps=args.fps, quick=args.quick)
            print(f"  act {key}: window [{sc.lo}, {sc.hi}) substeps, "
                  f"{wr.n} frames written so far", flush=True)
        build_closing(wr, fps=args.fps, quick=args.quick)
        dur = wr.n / args.fps
        print(f"rendered {wr.n} frames ({dur:.1f} s at {args.fps} fps)")
        for label, k in wr.marks:
            print(f"  {label:16s} frame {k:5d}  t = {k / args.fps:6.2f} s")
        cmd = ["ffmpeg", "-y", "-framerate", str(args.fps),
               "-i", os.path.join(tmp, "f%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
               # keyframe every 2 s: on this near-black background a long GOP
               # leaves a faint ghost of the removed opening title
               "-g", str(2 * args.fps), "-keyint_min", str(args.fps),
               "-map_metadata", "-1",              # strip metadata (anonymous)
               "-movflags", "+faststart", args.out]
        subprocess.run(cmd, check=True, capture_output=True)
        mb = os.path.getsize(args.out) / 1e6
        print(f"wrote {args.out}  ({mb:.1f} MB, {dur:.1f} s)")
    finally:
        if args.keep_frames:
            print(f"frames kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
