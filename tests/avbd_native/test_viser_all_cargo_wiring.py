"""Viser all-cargo wiring (§N2 generalization) — headless.

`viser.ViserServer` is stubbed (it opens a real websocket server, which a
sandbox/CI box may not allow), so this exercises everything the viewer script
decides: AVBD routing when the network is on, all-bodies deformable render
collection, network/passivity flag sync, and the legacy --no-all-cargo mode.
"""
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

    def reset(self):
        pass


class _Scene:
    def add_mesh_simple(self, name, vertices=None, faces=None, color=None,
                        flat_shading=False, side="double"):
        w = _Widget()
        w.vertices = vertices
        return w

    def add_batched_meshes_simple(self, name, vertices=None, faces=None,
                                  batched_wxyzs=None, batched_positions=None,
                                  batched_scales=None, batched_colors=None,
                                  flat_shading=False, side="double"):
        # decorated-model instancing (viser >= 0.2.x); the viewer later writes
        # handle.batched_positions / .batched_wxyzs each frame
        w = _Widget()
        w.batched_positions = batched_positions
        w.batched_wxyzs = batched_wxyzs
        return w

    def remove_by_name(self, name):
        pass


class _Server:
    def __init__(self, host="0.0.0.0", port=0):
        self.scene = _Scene()
        self.gui = _GUI()

    def stop(self):
        pass


@pytest.fixture()
def viser_stub(monkeypatch):
    fake = types.ModuleType("viser")
    fake.ViserServer = _Server
    monkeypatch.setitem(sys.modules, "viser", fake)


def _args(scene, **over):
    base = dict(
        scene=scene, solver="xpbd", kind="fem_rigid", material=None,
        device="cpu", modal_relax=0.7, symplectic=False, be=False,
        no_cargo=False, spin=4.0, no_network=False, ride=False,
        passivity=False, inject=False, inject_xpbd=False,
        cube_exag=1.0, support_exag=1.0, port=0, no_all_cargo=False)
    base.update(over)
    return Namespace(**base)


def _viser(args):
    from scripts.run_native_scenes_viser import UnifiedViser
    return UnifiedViser(args)


@pytest.mark.parametrize("scene", ["truck", "ledge", "shelf", "dinner"])
def test_all_cargo_scene_wiring(viser_stub, scene):
    v = _viser(_args(scene))
    # network is AVBD-native: the all-cargo build must route xpbd -> avbd
    assert v._eff_solver == "avbd"
    # every body renders as a deformable with its real box shape
    assert len(v._deforms) == len(v.handle.bodies)
    assert not v._boxes
    sol = v.world._solver
    assert bool(sol._modal_contact_network)
    # passivity: cargo-path wiring — ledger on, monitor unless the box is ticked
    assert bool(sol._enforce_modal_passivity)
    assert bool(sol._psv_monitor_only)
    for _ in range(10):
        v.world.step()
    for d in v._deforms:
        assert np.all(np.isfinite(v._deform_verts(d))), d["name"]


def test_legacy_mode_single_deformable(viser_stub):
    v = _viser(_args("shelf", no_all_cargo=True, be=True))
    # legacy: one deformable impactor + rigid bystanders, solver NOT rerouted
    assert v._eff_solver == "xpbd"
    assert len(v._deforms) == 1
    assert len(v._boxes) == len(v.handle.bodies) - 1


def test_inject_xpbd_preset_disables_all_cargo(viser_stub):
    v = _viser(_args("cargo", inject_xpbd=True))
    # the support-path blow-up demo must stay non-cargo (shelf, xpbd, sympl.)
    assert v.scene == "shelf" and v.solver == "xpbd"
    assert not v.all_cargo
    assert not getattr(v.world._solver, "_cargo_enabled", False)
