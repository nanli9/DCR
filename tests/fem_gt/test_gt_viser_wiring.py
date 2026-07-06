"""GT viser wiring — headless (viser server stubbed, as in
tests/avbd_native/test_viser_all_cargo_wiring.py): every FEM body renders,
the settle→release protocol fires, verts stay finite under exaggeration."""
from __future__ import annotations

import contextlib
import sys
import types
from argparse import Namespace

import numpy as np
import pytest


class _Widget:
    def __init__(self, value=None):
        self.value = value
        self.vertices = None

    def on_update(self, fn):
        pass

    def on_click(self, fn):
        pass


class _GUI:
    def add_folder(self, name):
        return contextlib.nullcontext()

    def add_dropdown(self, name, options, initial_value=None, hint=None):
        return _Widget(initial_value)

    def add_checkbox(self, name, initial_value=False, hint=None):
        return _Widget(initial_value)

    def add_slider(self, name, mn, mx, step, value, hint=None):
        return _Widget(value)

    def add_button(self, name):
        return _Widget()

    def add_text(self, name, initial_value=""):
        return _Widget(initial_value)


class _Scene:
    def add_mesh_simple(self, name, vertices=None, faces=None, color=None,
                        flat_shading=False, side="double"):
        w = _Widget()
        w.vertices = vertices
        return w

    def add_line_segments(self, name, points=None, colors=None,
                          line_width=1.0, visible=True):
        w = _Widget()
        w.points = points
        w.visible = visible
        return w

    def remove_by_name(self, name):
        pass


class _Server:
    def __init__(self, host="0.0.0.0", port=0):
        self.scene = _Scene()
        self.gui = _GUI()


def test_gt_viser_shelf_wiring(monkeypatch):
    fake = types.ModuleType("viser")
    fake.ViserServer = _Server
    monkeypatch.setitem(sys.modules, "viser", fake)
    from scripts.run_fem_gt_viser import GTViser

    args = Namespace(scene="shelf", quick=True, t_settle=0.05,
                     body_youngs=1.0e6, exag=200.0, steps_per_frame=100,
                     port=0, wireframe=True)
    v = GTViser(args)
    # every FEM body (support + 6 shelf bodies) has a surface mesh + wireframe
    assert len(v._surf) == len(v.sim.bodies) == 7
    assert len(v._wire) == 7
    # impactor parked far away during settle
    assert v.sim.body(v.imp_name).com()[0] > 50.0
    for _ in range(8):                      # 800 fine steps ⇒ past t_settle
        v.step_frame()
    assert v.released
    imp = v.sim.body(v.imp_name)
    assert abs(imp.com()[0] - v._imp_com0[0]) < 0.01   # restored to the drop
    for b, sv, mesh in v._surf:
        assert np.all(np.isfinite(mesh.vertices)), b.name
    # wireframe: (E,2,3) segments, finite, refreshed while visible
    for b, edges, wire in v._wire:
        assert wire.points.shape == (len(edges), 2, 3)
        assert np.all(np.isfinite(wire.points)), b.name
    # toggle off: handles hidden, updates skipped
    v.gui_wire.value = False
    v._wire_changed()
    assert not v.wireframe
    assert all(not w.visible for _, _, w in v._wire)
