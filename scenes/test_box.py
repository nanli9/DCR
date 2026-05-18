"""Stage 0 test scene: a unit box sitting on a ground plane."""
from dcr.geom import make_box, make_ground_plane
from dcr.viewer import SceneObject


def build_scene() -> list[SceneObject]:
    """Return the list of objects for this scene."""
    box = make_box(half_extents=(0.5, 0.5, 0.5), center=(0.0, 0.5, 0.0))
    ground = make_ground_plane(size=10.0, y=0.0)

    return [
        SceneObject(name="box", mesh=box, color=(0.8, 0.4, 0.2)),
        SceneObject(name="ground", mesh=ground, color=(0.5, 0.5, 0.5),
                    transparency=0.8),
    ]
