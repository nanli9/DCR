#!/usr/bin/env python3
"""Load a scene module and display it in polyscope.

Usage:
    python scripts/run_viewer.py scenes/test_box.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <scene_file.py>")
        sys.exit(1)

    scene_path = Path(sys.argv[1]).resolve()
    if not scene_path.exists():
        print(f"Scene file not found: {scene_path}")
        sys.exit(1)

    # Dynamically import the scene module.
    spec = importlib.util.spec_from_file_location("scene", scene_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "build_scene"):
        print(f"Scene module {scene_path.name} must define build_scene() -> list[SceneObject]")
        sys.exit(1)

    objects = module.build_scene()

    from dcr.viewer import Viewer
    viewer = Viewer()
    for obj in objects:
        viewer.add(obj)
    viewer.show()


if __name__ == "__main__":
    main()
