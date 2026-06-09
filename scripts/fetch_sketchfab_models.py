#!/usr/bin/env python3
"""Fetch decorated render models from Sketchfab into ``model/{kind}/``.

The downloaded assets live under ``model/<kind>/`` and are committed to
the repo as the visual skins for the reduced-modal demo scenes. To keep
them redistributable, the fetch defaults to CC0 / CC-BY licenses only
(``--licenses cc0,by``); CC-BY requires attribution, which is recorded in
``model/ATTRIBUTION_sketchfab.md``.

The Sketchfab API token is read from ``--token`` or the
``SKETCHFAB_API_TOKEN`` environment variable; it is NEVER written to disk
or echoed in full. Do not hard-code it in any committed file.

For each render kind we:
  1. search Sketchfab for downloadable models matching a query,
  2. pick the first relevance-ranked result whose face count is in a sane
     range (light enough for the batched viewer, not a degenerate blob),
  3. download its glTF-binary (``glb``, single self-contained file) or
     glTF (``gltf`` zip) archive,
  4. unpack it to ``model/<kind>/<kind>.glb`` (or ``<kind>.gltf`` + the
     companion ``.bin``/textures) so ``scripts/render_assets`` finds it,
  5. record name / author / license / url in
     ``model/ATTRIBUTION_sketchfab.md`` (committed, satisfies CC-BY).

Usage:
    SKETCHFAB_API_TOKEN=... uv run python scripts/fetch_sketchfab_models.py
    uv run python scripts/fetch_sketchfab_models.py --token ... --kinds cone book
    uv run python scripts/fetch_sketchfab_models.py --kinds boulder --query "rock low poly"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import struct
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

_API = "https://api.sketchfab.com/v3"
_MODEL_DIR = Path(__file__).resolve().parent.parent / "model"

# Per-kind default search queries. One relevance-ranked, downloadable model
# is picked from the top results; override with --query for a single kind.
#
# These queries were curated so the first relevance-ranked, in-window
# downloadable hit is a usable single object (not an asset pack or a
# statue). Re-running with these defaults reproduces the demo asset set.
# The ledge "pedestal" body intentionally reuses the `boulder` kind (a
# stone block under the pillars) — clean low-poly plinths are scarce and
# the search returns statues — so there is no `pedestal` entry here.
_KIND_QUERIES: dict[str, str] = {
    # truck / road-impact scene
    "cone":    "traffic cone low poly",
    "lumber":  "wood log low poly",
    "crate":   "wooden crate low poly",
    # bookshelf scene
    "book":    "old hardcover book low poly",
    # cliff-ledge scene
    "boulder": "rock boulder low poly",
    "pillar":  "stone pillar column low poly",
}

# Acceptable face-count window: above the floor avoids degenerate/placeholder
# uploads; below the ceiling keeps the batched-mesh viewer responsive (the
# template is instanced across every body of the kind).
_FACE_MIN = 200
_FACE_MAX = 80_000


def _req(url: str, token: str | None = None, timeout: float = 60.0) -> bytes:
    headers = {"User-Agent": "DCR-reduced-modal-demo/1.0"}
    if token:
        headers["Authorization"] = f"Token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get_json(url: str, token: str | None = None) -> dict:
    return json.loads(_req(url, token).decode("utf-8"))


def _search(query: str, token: str, count: int = 24) -> list[dict]:
    qs = urllib.parse.urlencode({
        "type": "models",
        "q": query,
        "downloadable": "true",
        "count": count,
        "sort_by": "-relevance",
    })
    data = _get_json(f"{_API}/search?{qs}", token)
    return data.get("results", [])


def _face_count(result: dict, token: str) -> int | None:
    """Face count from the search hit if present, else from model detail."""
    fc = result.get("faceCount")
    if isinstance(fc, int) and fc > 0:
        return fc
    try:
        d = _get_json(f"{_API}/models/{result['uid']}", token)
    except Exception:
        return None
    fc = d.get("faceCount")
    return fc if isinstance(fc, int) and fc > 0 else None


def _license_ok(result: dict, token: str, allow: set[str] | None) -> bool:
    """True if the model's license slug is in `allow` (None = any)."""
    if not allow:
        return True
    lic = (result.get("license") or {}).get("slug")
    if lic is None:
        try:
            det = _get_json(f"{_API}/models/{result['uid']}", token)
            lic = (det.get("license") or {}).get("slug")
        except Exception:
            return False
    return lic in allow


def _pick(results: list[dict], token: str,
          allow_licenses: set[str] | None = None) -> dict | None:
    """First relevance-ranked, downloadable result inside the face window,
    optionally restricted to an allowed-license set (e.g. {cc0, by} so the
    asset can be redistributed in the repo with attribution)."""
    for r in results:
        if not r.get("isDownloadable"):
            continue
        if not _license_ok(r, token, allow_licenses):
            continue
        fc = _face_count(r, token)
        if fc is None:
            continue
        if _FACE_MIN <= fc <= _FACE_MAX:
            r["_faceCount"] = fc
            return r
    # Nothing in-window — fall back to the lightest downloadable hit.
    best = None
    for r in results:
        if not r.get("isDownloadable"):
            continue
        if not _license_ok(r, token, allow_licenses):
            continue
        fc = _face_count(r, token) or 10**9
        if best is None or fc < best[0]:
            best = (fc, r)
    if best is not None:
        best[1]["_faceCount"] = best[0]
        return best[1]
    return None


def _download_archive(uid: str, token: str) -> tuple[bytes, str]:
    """Return (archive_bytes, flavour) preferring single-file glb, then gltf."""
    info = _get_json(f"{_API}/models/{uid}/download", token)
    for flavour in ("glb", "gltf"):
        entry = info.get(flavour) or {}
        url = entry.get("url")
        if url:
            return _req(url, timeout=180.0), flavour
    raise RuntimeError(f"no glb/gltf download flavour for model {uid}")


def _is_glb(blob: bytes) -> bool:
    return len(blob) >= 4 and blob[:4] == b"glTF"


def _write_kind(kind: str, blob: bytes, flavour: str) -> Path:
    """Unpack the downloaded archive into model/<kind>/ and return the main
    asset path render_assets will resolve (model/<kind>/<kind>.{glb,gltf})."""
    out = _MODEL_DIR / kind
    out.mkdir(parents=True, exist_ok=True)
    # Clear any prior fetch so stale companion files never shadow the new one.
    for p in out.glob("*"):
        if p.is_file():
            p.unlink()

    # Case 1: a raw .glb (glTF binary magic) — write straight through.
    if _is_glb(blob):
        dest = out / f"{kind}.glb"
        dest.write_bytes(blob)
        return dest

    # Case 2: a zip archive (Sketchfab wraps both glb and gltf flavours).
    if zipfile.is_zipfile(io.BytesIO(blob)):
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            names = zf.namelist()
            # Find the primary gltf/glb entry (shallowest path wins).
            mains = [n for n in names if n.lower().endswith((".glb", ".gltf"))]
            if not mains:
                raise RuntimeError(f"{kind}: archive has no .glb/.gltf entry")
            mains.sort(key=lambda n: (n.count("/"), len(n)))
            main = mains[0]
            main_is_glb = main.lower().endswith(".glb")
            # Extract every member flat into out/ (drop archive subdirs so the
            # gltf's relative .bin/texture URIs still resolve side-by-side).
            for n in names:
                if n.endswith("/"):
                    continue
                data = zf.read(n)
                flat = Path(n).name
                (out / flat).write_bytes(data)
            main_flat = Path(main).name
            ext = ".glb" if main_is_glb else ".gltf"
            dest = out / f"{kind}{ext}"
            src = out / main_flat
            if src.resolve() != dest.resolve():
                if dest.exists():
                    dest.unlink()
                src.rename(dest)
            return dest

    raise RuntimeError(f"{kind}: download is neither glb nor zip ({len(blob)} B)")


def _record_attribution(entries: list[dict]) -> None:
    """Merge this run's picks into model/.fetch_manifest.json (provenance)
    and regenerate model/ATTRIBUTION_sketchfab.md from the manifest.

    Merging — rather than overwriting — means fetching a single kind with a
    custom --query does not erase the attribution rows for the other kinds.
    """
    manifest_path = _MODEL_DIR / ".fetch_manifest.json"
    manifest: dict[str, dict] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            manifest = {}
    for e in entries:
        manifest[e["kind"]] = e
    # Drop kinds whose asset folder no longer exists (e.g. a dropped kind).
    manifest = {k: v for k, v in manifest.items() if (_MODEL_DIR / k).exists()}
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True))

    lines = [
        "# Sketchfab render assets — attribution\n",
        "\n",
        "Decorated render skins for the reduced-modal demo scenes, fetched\n",
        "from Sketchfab via `scripts/fetch_sketchfab_models.py`. Each model\n",
        "is licensed CC-BY 4.0 or CC0 (the fetch script restricts to those\n",
        "so the assets are redistributable in this repo). CC-BY requires\n",
        "attribution — the author + source URL below satisfy it. The\n",
        "committed `.glb` files are geometry-only derivatives (PBR textures\n",
        "stripped — the flat-shaded batched viewer never uses them).\n",
        "\n",
        "| kind | model | author | license | faces | url |\n",
        "|------|-------|--------|---------|-------|-----|\n",
    ]
    for kind in sorted(manifest):
        e = manifest[kind]
        lines.append(
            f"| {e['kind']} | {e['name']} | {e['author']} | "
            f"{e['license']} | {e['faces']} | {e['url']} |\n")
    (_MODEL_DIR / "ATTRIBUTION_sketchfab.md").write_text("".join(lines))
    print(f"[fetch] manifest now covers: {', '.join(sorted(manifest))}")


def _fetch_one(kind: str, query: str, token: str,
               allow_licenses: set[str] | None = None) -> dict | None:
    print(f"[fetch] {kind}: searching {query!r} …")
    results = _search(query, token)
    pick = _pick(results, token, allow_licenses)
    if pick is None:
        lic_note = (f" (license in {sorted(allow_licenses)})"
                    if allow_licenses else "")
        print(f"[fetch] {kind}: NO downloadable result for {query!r}{lic_note}")
        return None
    name = pick.get("name", "?")
    author = (pick.get("user") or {}).get("username", "?")
    lic = (pick.get("license") or {}).get("slug")
    if lic is None:
        try:
            det = _get_json(f"{_API}/models/{pick['uid']}", token)
            lic = (det.get("license") or {}).get("slug")
        except Exception:
            lic = "?"
    faces = pick.get("_faceCount", "?")
    # The bare-uid permalink always resolves (Sketchfab redirects it to the
    # full slug URL); the search's viewerUrl sometimes carries a "none" slug.
    url = f"https://sketchfab.com/3d-models/{pick['uid']}"
    print(f"[fetch] {kind}: picked {name!r} by {author} "
          f"(license={lic}, faces={faces})")
    blob, flavour = _download_archive(pick["uid"], token)
    dest = _write_kind(kind, blob, flavour)
    print(f"[fetch] {kind}: wrote {dest.relative_to(_MODEL_DIR.parent)} "
          f"({flavour}, {len(blob)/1e6:.2f} MB archive)")
    return dict(kind=kind, name=name, author=author, license=lic,
                faces=faces, url=url)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--token", default=os.environ.get("SKETCHFAB_API_TOKEN"),
                    help="Sketchfab API token (or set SKETCHFAB_API_TOKEN).")
    ap.add_argument("--kinds", nargs="*", default=sorted(_KIND_QUERIES),
                    help="render kinds to fetch (default: all new kinds).")
    ap.add_argument("--query", default=None,
                    help="override the search query (only valid with one --kinds).")
    ap.add_argument("--licenses", default="cc0,by",
                    help="comma-separated allowed Sketchfab license slugs "
                         "(default 'cc0,by' — redistributable in-repo with "
                         "attribution). Pass '' / 'any' to allow any license.")
    args = ap.parse_args(argv)

    if not args.token:
        print("error: no Sketchfab token (pass --token or set "
              "SKETCHFAB_API_TOKEN).", file=sys.stderr)
        return 2
    if args.query is not None and len(args.kinds) != 1:
        print("error: --query requires exactly one --kinds.", file=sys.stderr)
        return 2
    allow = None
    if args.licenses and args.licenses.lower() not in ("any", "all"):
        allow = {s.strip() for s in args.licenses.split(",") if s.strip()}

    entries: list[dict] = []
    for kind in args.kinds:
        query = args.query or _KIND_QUERIES.get(kind)
        if query is None:
            print(f"[fetch] {kind}: no default query; pass --query.", file=sys.stderr)
            continue
        try:
            rec = _fetch_one(kind, query, args.token, allow)
        except Exception as e:
            print(f"[fetch] {kind}: FAILED — {type(e).__name__}: {e}",
                  file=sys.stderr)
            continue
        if rec is not None:
            entries.append(rec)

    if entries:
        _record_attribution(entries)
    print(f"\n[fetch] done — {len(entries)}/{len(args.kinds)} kinds fetched.")
    return 0 if entries else 1


if __name__ == "__main__":
    raise SystemExit(main())
