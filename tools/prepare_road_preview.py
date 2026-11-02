#!/usr/bin/env python3
\"\"\"Prepare a review-only road preview for the Nalchik Arch pilot.

Run from repository root:
  py tools/road_reference/prepare_road_preview.py

Reads nalchik_archa/roads.geojson and writes three NEW files under
nalchik_archa/review/. The source file is never overwritten.
Uses only Python's standard library.
\"\"\"
import json
from pathlib import Path

SOUTH, WEST, NORTH, EAST = 43.518, 43.6115, 43.5215, 43.615
ROOT = Path.cwd()
INPUT = ROOT / "nalchik_archa" / "roads.geojson"
OUT_DIR = ROOT / "nalchik_archa" / "review"
OUT_GEOJSON = OUT_DIR / "clipped_roads.geojson"
OUT_SVG = OUT_DIR / "road_preview.svg"
OUT_REPORT = OUT_DIR / "clip_report.txt"

def clip_segment(a, b):
    x0, y0 = a
    x1, y1 = b
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - WEST, EAST - x0, y0 - SOUTH, NORTH - y0)
    u0, u1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-15:
            if qi < 0:
                return None
            continue
        r = qi / pi
        if pi < 0:
            if r > u1:
                return None
            u0 = max(u0, r)
        else:
            if r < u0:
                return None
            u1 = min(u1, r)
    return ([x0 + u0 * dx, y0 + u0 * dy],
            [x0 + u1 * dx, y0 + u1 * dy])

def same_point(a, b, eps=1e-12):
    return abs(a[0]-b[0]) < eps and abs(a[1]-b[1]) < eps

def clip_linestring(coords):
    pieces, current = [], []
    for a, b in zip(coords, coords[1:]):
        segment = clip_segment(a, b)
        if segment is None:
            if len(current) >= 2:
                pieces.append(current)
            current = []
            continue
        start, end = segment
        if not current:
            current = [start, end]
        elif same_point(current[-1], start):
            if not same_point(current[-1], end):
                current.append(end)
        else:
            if len(current) >= 2:
                pieces.append(current)
            current = [start, end]
    if len(current) >= 2:
        pieces.append(current)
    return pieces

def iter_lines(geometry):
    if not geometry:
        return
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "LineString":
        yield coords
    elif kind == "MultiLineString":
        yield from coords

def svg_preview(features):
    width, height, margin = 1200, 900, 35
    lon_factor = 0.727
    geo_w = (EAST-WEST) * lon_factor
    geo_h = NORTH-SOUTH
    scale = min((width-2*margin)/geo_w, (height-2*margin)/geo_h)
    drawn_w, drawn_h = geo_w*scale, geo_h*scale
    left, top = (width-drawn_w)/2, (height-drawn_h)/2

    def xy(pt):
        lon, lat = pt
        return left+(lon-WEST)*lon_factor*scale, top+(NORTH-lat)*scale

    shapes = []
    colours = {
        "motorway":"#b44b4b", "trunk":"#c36a44", "primary":"#d18a32",
        "secondary":"#c8ad42", "tertiary":"#8d9f6b",
        "residential":"#718da8", "service":"#8c8c8c"
    }
    for feature in features:
        for line in iter_lines(feature.get("geometry")):
            for piece in clip_linestring(line):
                points = " ".join(f"{x:.2f},{y:.2f}" for x,y in map(xy,piece))
                props = feature.get("properties") or {}
                cls = str(props.get("road_class", props.get("highway", "road")))
                colour = colours.get(cls, "#777777")
                shapes.append(f'<polyline points="{points}" fill="none" stroke="{colour}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="#fbfaf6"/>'
        f'<rect x="{left:.2f}" y="{top:.2f}" width="{drawn_w:.2f}" height="{drawn_h:.2f}" fill="none" stroke="#444" stroke-dasharray="7 5"/>'
        + "".join(shapes)
        + f'<text x="28" y="28" font-family="Arial,sans-serif" font-size="18" fill="#222">Nalchik Arch pilot - clipped OSM road centerlines (review only)</text>'
        + f'<text x="28" y="{height-18}" font-family="Arial,sans-serif" font-size="13" fill="#555">Not a road-surface preview. Bounds: {WEST}, {SOUTH} to {EAST}, {NORTH}</text></svg>'
    )

def main():
    if not INPUT.exists():
        raise SystemExit(f"Input not found: {INPUT}\\nRun from the repository root.")
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    source_features = data.get("features", [])
    output_features = []
    input_coords = output_coords = 0
    for feature in source_features:
        pieces = []
        for line in iter_lines(feature.get("geometry")):
            input_coords += len(line)
            pieces.extend(clip_linestring(line))
        if not pieces:
            continue
        for piece in pieces:
            output_coords += len(piece)
        geometry = {
            "type": "LineString" if len(pieces) == 1 else "MultiLineString",
            "coordinates": pieces[0] if len(pieces) == 1 else pieces
        }
        output_features.append({
            "type": "Feature",
            "id": feature.get("id"),
            "properties": dict(feature.get("properties") or {}),
            "geometry": geometry
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {"type":"FeatureCollection", "name":"nalchik_archa_clipped_roads_review_only", "features":output_features}
    OUT_GEOJSON.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\\n", encoding="utf-8")
    OUT_SVG.write_text(svg_preview(output_features), encoding="utf-8")
    report = (
        "NALCHIK ARCH PILOT - CLIPPING REPORT\\n"
        "Status: REVIEW ONLY; no BeamNG.Earth integration performed.\\n"
        f"Input features: {len(source_features)}\\n"
        f"Features with geometry inside bounds: {len(output_features)}\\n"
        f"Input line coordinates counted: {input_coords}\\n"
        f"Output line coordinates: {output_coords}\\n"
        f"Bounds (south, west, north, east): {SOUTH}, {WEST}, {NORTH}, {EAST}\\n"
        f"Output GeoJSON: {OUT_GEOJSON.as_posix()}\\n"
        f"Preview SVG: {OUT_SVG.as_posix()}\\n\\n"
        "IMPORTANT: this preview shows clipped OSM centerlines only. It does not create road widths,\\n"
        "carriageway edges, sidewalks, curbs, markings, parking or driveways. Manual review is still required.\\n"
    )
    OUT_REPORT.write_text(report, encoding="utf-8")
    print(report)

if __name__ == "__main__":
    main()
