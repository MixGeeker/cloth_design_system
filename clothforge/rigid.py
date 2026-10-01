"""Parametric, watertight ornament prototypes; all coordinates are millimetres.

These shapes are generic engineering hypotheses, not authenticated costume references.
An actual rounded strap slot is modelled through every part. Meshes are generated
with the Python standard library, including rounded planar outlines and rounded
front/back edges. STL itself carries no units: import as millimetres.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]


def _rounded_rect(width: float, height: float, radius: float,
                  segments: int = 10) -> list[tuple[float, float]]:
    """Counter-clockwise rounded rectangle, with no coincident vertices."""
    if not 0 < radius < min(width, height) / 2:
        raise ValueError("Corner radius must be positive and below half the short side")
    points = []
    for cx, cy, start in ((width / 2 - radius, -height / 2 + radius, -90),
                          (width / 2 - radius, height / 2 - radius, 0),
                          (-width / 2 + radius, height / 2 - radius, 90),
                          (-width / 2 + radius, -height / 2 + radius, 180)):
        for step in range(segments + 1):
            angle = math.radians(start + 90 * step / segments)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _radial_slot(width: float, height: float, radius: float,
                 count: int = 64, angles: list[float] | None = None) -> list[tuple[float, float]]:
    """Sample a rounded rectangle on equally spaced radial rays."""
    if not 0 < radius < min(width, height) / 2:
        raise ValueError("Invalid slot corner radius")
    result = []
    for angle in angles or [2 * math.pi * i / count for i in range(count)]:
        cx, cy = math.cos(angle), math.sin(angle)
        low, high = 0.0, math.hypot(width, height)
        for _ in range(48):
            distance = (low + high) / 2
            dx = max(abs(distance * cx) - width / 2 + radius, 0)
            dy = max(abs(distance * cy) - height / 2 + radius, 0)
            if math.hypot(dx, dy) <= radius:
                low = distance
            else:
                high = distance
        result.append((low * cx, low * cy))
    return result


def _ornament_mesh(width: float, height: float, thickness: float,
                   slot_width: float, slot_height: float, *,
                   corner_radius: float, slot_radius: float = 2.0,
                   roundover: float = 0.55, slot_y: float = 0.0, circular: bool = False
                   ) -> tuple[list[Vec3], list[Face]]:
    """Extruded rounded annulus. The inner wall bounds a real through-slot.

    Equal vertex counts on nested convex loops avoid an external triangulator.
    Multiple edge rings approximate a quarter-circle roundover, not a cosmetic
    normal modifier. Winding is outward on all faces, including the slot wall.
    """
    values = (width, height, thickness, slot_width, slot_height, corner_radius,
              slot_radius, roundover)
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("All mesh dimensions must be finite and positive")
    if not math.isfinite(slot_y):
        raise ValueError("Slot offset must be finite")
    if thickness <= 2 * roundover:
        raise ValueError("Thickness must exceed two edge roundovers")
    if corner_radius <= roundover:
        raise ValueError("Corner radius must exceed the roundover")
    ligament = min((width - slot_width) / 2,
                   (height - slot_height) / 2 - abs(slot_y))
    if ligament <= 2 * roundover:
        raise ValueError("The strap slot must leave positive material around its edge")

    if circular and (abs(width - height) > 1e-6 or
                     math.hypot(slot_width / 2, abs(slot_y) + slot_height / 2) + 2 * roundover >= width / 2):
        raise ValueError("Circular ornament must contain its slot with adequate edge material")
    levels = []
    for step in range(5):
        angle = math.pi * step / 8
        levels.append((roundover * (1 - math.cos(angle)),
                       roundover * (1 - math.sin(angle))))
    levels.extend((thickness - z, inset) for z, inset in reversed(levels.copy()))
    angles = sorted(set([round(2 * math.pi * i / 64, 12) for i in range(64)] +
                        [round(math.atan2(-slot_y, x) % (2 * math.pi), 12)
                         for x in (width / 2, -width / 2)]))
    vertices: list[Vec3] = []
    faces: list[Face] = []
    n = 0
    for z, inset in levels:
        if circular:
            outer = []
            for angle in angles:
                cx, cy = math.cos(angle), math.sin(angle)
                distance = -slot_y * cy + math.sqrt((width / 2 - inset) ** 2 - (slot_y * cx) ** 2)
                outer.append((distance * cx, slot_y + distance * cy))
            inner = _radial_slot(slot_width + 2 * inset, slot_height + 2 * inset,
                                 slot_radius + inset, angles=angles)
        else:
            outer = _rounded_rect(width - 2 * inset, height - 2 * inset,
                                  corner_radius - inset)
            inner = _rounded_rect(slot_width + 2 * inset, slot_height + 2 * inset,
                                  slot_radius + inset)
        n = len(outer)
        vertices.extend((x, y, z) for x, y in outer)
        vertices.extend((x, y + slot_y, z) for x, y in inner)

    for level in range(len(levels) - 1):
        lower, upper = level * 2 * n, (level + 1) * 2 * n
        for i in range(n):
            j = (i + 1) % n
            faces.extend(((lower + i, lower + j, upper + j),
                          (lower + i, upper + j, upper + i)))
            # Reverse the winding for the inward-facing slot wall.
            faces.extend(((lower + n + i, upper + n + j, lower + n + j),
                          (lower + n + i, upper + n + i, upper + n + j)))
    top = (len(levels) - 1) * 2 * n
    for i in range(n):
        j = (i + 1) % n
        faces.extend(((top + i, top + j, top + n + j),
                      (top + i, top + n + j, top + n + i),
                      (i, n + j, j),
                      (i, n + i, n + j)))
    return vertices, faces


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(x * x for x in cross))
    if length < 1e-12:
        raise ValueError("Degenerate triangle in generated ornament")
    return tuple(x / length for x in cross)  # type: ignore[return-value]


def _write_stl(path: Path, name: str, vertices: list[Vec3], faces: list[Face]) -> None:
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(f"solid {name}_millimetres\n")
        for face in faces:
            points = [vertices[index] for index in face]
            normal = _normal(*points)
            stream.write("  facet normal " + " ".join(f"{v:.9g}" for v in normal) + "\n")
            stream.write("    outer loop\n")
            for point in points:
                stream.write("      vertex " + " ".join(f"{v:.9f}" for v in point) + "\n")
            stream.write("    endloop\n  endfacet\n")
        stream.write(f"endsolid {name}_millimetres\n")


def _measurement(profile: dict, name: str, default: float) -> float:
    value = profile.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite measurement in mm")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite measurement in mm")
    return float(value)


def generate_rigid(profile: dict, outdir: Path) -> list[dict]:
    """Write three printable hypothesis STLs and ``rigid_manifest.json``.

    Return one record per STL. ``file`` is relative to ``outdir``; ``bbox_mm`` is
    [width, height, thickness]. ``wall_mm`` is nominal plate thickness; minimum
    in-plane ligament and edge roundover are reported separately. Upper arm and neck
    drive gently clamped ornament scales; these are not structural body parts.
    """
    arm_scale = min(1.20, max(0.80, _measurement(profile, "upper_arm", 270) / 270))
    neck_scale = min(1.15, max(0.85, _measurement(profile, "neck", 330) / 330))
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    records = []
    for part_id, component, scale, width, height, thickness, slot_w, slot_h, radius, y in (
        ("shoulder_disc_left", "shoulder_disc", arm_scale, 76, 76, 3.2, 20, 5.5, 18, 22),
        ("shoulder_disc_right", "shoulder_disc", arm_scale, 76, 76, 3.2, 20, 5.5, 18, 22),
        ("neck_charm", "neck_charm", neck_scale, 32, 32, 2.8, 7, 3, 7, 8),
    ):
        width, height, slot_w, slot_h, radius, y = (
            value * scale for value in (width, height, slot_w, slot_h, radius, y))
        roundover = 0.55
        vertices, faces = _ornament_mesh(width, height, thickness, slot_w, slot_h,
                                         corner_radius=radius, slot_radius=1.0 * scale,
                                         roundover=roundover, slot_y=y, circular=True)
        filename = part_id + ".stl"
        _write_stl(outdir / filename, part_id, vertices, faces)
        ligament = width / 2 - math.hypot(slot_w / 2, abs(y) + slot_h / 2)
        records.append({
            "id": part_id,
            "component_id": component,
            "file": filename,
            "units": "mm",
            "bbox_mm": [round(width, 3), round(height, 3), thickness],
            "wall_mm": thickness,
            "edge_roundover_mm": roundover,
            "min_ligament_mm": round(ligament, 3),
            "strap_slot_mm": [round(slot_w, 3), round(slot_h, 3)],
            "strap_slot_center_mm": [0, round(y, 3)],
            "mount_notes": (
                "Real through-slot; use soft webbing or ribbon narrower than the slot, "
                "looped to a fabric backing. Keep hard plastic off bare skin and away "
                "from eyes. Deburr, sand and test the print and attachment before wear. "
                "This is a non-load-bearing decorative prototype. "
                "Neck mounting must use a soft breakaway attachment, never a closed rigid loop."
            ),
            "hypothesis": "Generic engineering interpretation; decorative relief, reference fidelity and attachment fit not verified.",
            "finish_notes": "Plain round shell. Optional concentric color finish; no copied symbol or filigree.",
            "print_notes": "Import STL as mm. Print broad face down. PETG or PLA prototype; verify slicer scale and fit. No validated strength or wear-safety claim.",
            "vertex_count": len(vertices),
            "triangle_count": len(faces),
        })
    (outdir / "rigid_manifest.json").write_text(
        json.dumps({"units": "mm", "parts": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return records
