# Render-only asset folder for the viser viewer

Drop mesh files here and the dinner_table viewer auto-loads them as the
visual skins over the box collision proxies (DCR-paper style: simple
collision shape, decorated render).

## Convention

The viewer looks for `{kind}.{ext}` for each `SceneBox.render_kind` it
sees, in this priority order:

```
plate.obj | plate.glb | plate.gltf | plate.ply | plate.stl
pot.obj   | pot.glb   | pot.gltf   | pot.ply   | pot.stl
candle.obj | candle.glb | candle.gltf | candle.ply | candle.stl
```

If no file matches, the viewer falls back to a procedurally generated
cylinder template (the previous behavior).

## What gets loaded

Each mesh is automatically:
- Centered at its bounding-box centroid.
- Normalized so the bounding box is exactly `[-0.5, 0.5]^3` (per-axis).
  The viewer's per-instance `scale = 2 * half_extents` then recovers the
  real body size, matching the unit-cube convention used for everything
  else.
- Drawn flat-shaded with the per-body color from `SceneBox.color`
  (textures and per-vertex colors are ignored — the loader uses
  `viser.add_batched_meshes_simple` so all instances of one kind render
  as a single batched draw call).

Because each axis is normalized independently, the box collision proxy's
aspect ratio is what dictates the rendered aspect — pick `half_extents`
in `build_dinner_table_scene` to match the natural proportions of the
loaded mesh and the visual will look right.

## Kinds in this folder

The dinner scene uses `plate`, `fork`, `knife`, `candle`, `pot`, `spoon`.
The reduced-modal demo scenes (`scripts/run_reduced_scene_viser.py`) add:

| kind | used by scene(s) | object |
|------|------------------|--------|
| `crate`   | truck, shelf | dropped weight / road crate |
| `cone`    | truck        | traffic cones |
| `lumber`  | truck        | stacked timber |
| `book`    | shelf        | standing books |
| `boulder` | ledge        | dropped boulder + stone pedestal |
| `pillar`  | ledge        | balanced columns |

## Where to grab assets

The easy route is the fetch script — it searches Sketchfab, picks a
low-poly downloadable model per kind, restricts to **CC0 / CC-BY** so the
asset is redistributable in this repo, and records attribution in
`ATTRIBUTION_sketchfab.md`:

```
SKETCHFAB_API_TOKEN=<your token> uv run python scripts/fetch_sketchfab_models.py
# one kind with a custom search:
uv run python scripts/fetch_sketchfab_models.py --kinds boulder --query "rock low poly"
```

The token is read from `--token` / `$SKETCHFAB_API_TOKEN` and is never
written to disk. The curated default queries reproduce the committed set.

Or do it by hand: search Sketchfab for a CC0 / CC-BY model, download the
`.glb` / `.obj`, rename it to `{kind}.{ext}`, and drop it in
`model/{kind}/`. No further config — relaunch the viewer and it picks the
new template up.

## Verifying the load

On viewer startup you'll see one line per loaded kind:

```
[viewer] loaded render template for 'plate' from plate.obj (1483 verts, 2962 faces)
[viewer] loaded render template for 'pot' from pot.glb (2104 verts, 4208 faces)
[viewer] no render asset for 'candle' — falling back to cylinder template
```

In the browser's **Visualization** folder there's a **show collision
proxies** checkbox. ON = render every body as its AABB cube (what the
physics actually sees); OFF (default) = decorated meshes. Use it to
sanity-check that the loaded mesh fits the proxy box you set up.
