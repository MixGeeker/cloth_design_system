#!/usr/bin/env python3
"""Headless Blender preview of exact flat panels and schematic garment assembly.

Usage:
  blender --background --python-exit-code 1 --python scripts/blender_preview.py -- \
    --patterns output/patterns.json --profile output/profile.json --outdir output/preview

The .blend is editable. The assembled forms are measurement-driven display meshes,
not cloth simulation, pattern-to-body draping, collision validation or a fit proof.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def arguments():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=2000, help="PNG width in pixels")
    parser.add_argument("--color", default="2F9FAD", help="Generic accent color, hex RGB")
    return parser.parse_args(args)


def material(name, rgb, roughness=.75):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*rgb, 1)
    node.inputs["Roughness"].default_value = roughness
    return mat


def add_mesh(name, verts, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def line(name, points, mat, radius=.001, closed=False):
    if len(points) < 2:
        return
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    polyline = curve.splines.new("POLY")
    polyline.points.add(len(points) - 1)
    for point, coordinates in zip(polyline.points, points):
        point.co = (*coordinates, 1)
    polyline.use_cyclic_u = closed
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def text(name, body, x, z, size, mat, y=-.3):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = body
    curve.size = size
    curve.space_character = 1.05
    curve.extrude = 0
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = (x, y, z)
    obj.rotation_euler = (math.pi / 2, 0, 0)
    obj.data.materials.append(mat)
    return obj


def ellipsoid(name, location, radii, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = radii
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def tube(name, rings, mat, caps=True, count=64):
    """Z-aligned elliptical section mesh; rings are x,y,z,rx,ry."""
    verts = [(x + rx * math.cos(2 * math.pi * j / count),
              y + ry * math.sin(2 * math.pi * j / count), z)
             for x, y, z, rx, ry in rings for j in range(count)]
    faces = []
    for i in range(len(rings) - 1):
        for j in range(count):
            k = (j + 1) % count
            faces.append((i * count + j, i * count + k,
                          (i + 1) * count + k, (i + 1) * count + j))
    if caps:
        faces.extend([tuple(reversed(range(count))),
                      tuple((len(rings) - 1) * count + j for j in range(count))])
    obj = add_mesh(name, verts, faces, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def segment(name, start, end, radius1, radius2, mat):
    a, b = Vector(start), Vector(end)
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=radius1, radius2=radius2,
                                   depth=(b - a).length, location=(a + b) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def ellipse_radii(circumference_mm, ratio=1.5):
    unit_perimeter = math.pi * (3 * (ratio + 1) - math.sqrt((3 * ratio + 1) * (ratio + 3)))
    minor = circumference_mm / 1000 / unit_perimeter
    return minor * ratio, minor


def body_and_garment(profile, center, back, mats):
    p = {key: float(value) / 1000 for key, value in profile.items()
         if isinstance(value, (int, float)) and not isinstance(value, bool)}
    height = p["height"]
    head_height = p["head"] / math.pi * 1.25
    shoulder_z = height - head_height - .06
    waist_z = shoulder_z - p["back_waist_length"]
    bust_z = shoulder_z - p["back_waist_length"] * .37
    hip_z = waist_z - height * .115
    knee_z = max(.3, waist_z - p["waist_to_knee"])
    bust_rx, bust_ry = ellipse_radii(profile["bust"])
    waist_rx, waist_ry = ellipse_radii(profile["waist"])
    hip_rx, hip_ry = ellipse_radii(profile["hip"])
    face = "BACK" if back else "FRONT"
    base_name = f"{face}_"
    body = mats["body"]
    ellipsoid(base_name + "head", (center, 0, height - head_height / 2),
              (p["head"] / math.pi / 2, .083 * height / 1.68, head_height / 2), body)
    neck_rx, neck_ry = ellipse_radii(profile["neck"], 1.1)
    tube(base_name + "neck", [(center, 0, shoulder_z, neck_rx, neck_ry),
                             (center, 0, shoulder_z + .085, neck_rx, neck_ry)], body)
    tube(base_name + "torso", [(center, 0, hip_z, hip_rx, hip_ry),
                              (center, 0, waist_z, waist_rx, waist_ry),
                              (center, 0, bust_z, bust_rx, bust_ry),
                              (center, 0, shoulder_z, p["shoulder"] / 2, bust_ry * .65)], body)
    upper_radius = p["upper_arm"] / (2 * math.pi)
    wrist_radius = p["wrist"] / (2 * math.pi)
    for side in (-1, 1):
        x = center + side * p["shoulder"] / 2
        shoulder = (x, 0, shoulder_z - .012)
        elbow = (x + side * .055, 0, shoulder_z - p["arm_length"] * .52)
        wrist = (x + side * .095, 0, shoulder_z - p["arm_length"] * .985)
        segment(base_name + f"upper_arm_{side}", elbow, shoulder, upper_radius * .76, upper_radius, body)
        segment(base_name + f"forearm_{side}", wrist, elbow, wrist_radius, upper_radius * .76, body)
        ellipsoid(base_name + f"hand_{side}", (wrist[0] + side * .01, 0, wrist[2] - .05),
                  (.032, .02, .065), body)
        leg_x = center + side * hip_rx * .52
        segment(base_name + f"thigh_{side}", (leg_x, 0, knee_z), (leg_x, 0, hip_z),
                .05 * height / 1.68, hip_rx * .43, body)
        segment(base_name + f"calf_{side}", (leg_x, 0, .07), (leg_x, 0, knee_z),
                .032 * height / 1.68, .05 * height / 1.68, body)
        ellipsoid(base_name + f"foot_{side}", (leg_x, -.035, .045), (.043, .10, .045), body)
        # A sleeve display primitive, not a draped copy of the cutting panel.
        tube(base_name + f"schematic_sleeve_{side}",
             [(elbow[0], 0, elbow[2] + .035, upper_radius * 1.50, upper_radius * 1.40),
              (x, 0, shoulder_z - .015, upper_radius * 1.18, upper_radius * 1.14)], mats["accent"], caps=False)
    # These rings explicitly derive from profile girths plus display clearance.
    garment = tube(base_name + "SCHEMATIC_bodice", [
        (center, 0, waist_z - .045, waist_rx + .021, waist_ry + .019),
        (center, 0, waist_z, waist_rx + .014, waist_ry + .014),
        (center, 0, bust_z, bust_rx + .016, bust_ry + .016),
        (center, 0, shoulder_z - .060, bust_rx * .88, bust_ry * .91)], mats["cloth"], caps=False)
    garment["fit_status"] = "Unsimulated schematic; not a panel-to-body solution"
    skirt_length = min(p["waist_to_knee"] * .52, .32)
    hem_z = waist_z - skirt_length
    tube(base_name + "SCHEMATIC_skirt", [
        (center, 0, hem_z, hip_rx * 1.37, hip_ry * 1.34),
        (center, 0, hip_z + .03, hip_rx + .03, hip_ry + .025),
        (center, 0, waist_z, waist_rx + .019, waist_ry + .019)], mats["accent"], caps=False)
    tube(base_name + "hem_binding", [
        (center, 0, hem_z, hip_rx * 1.375, hip_ry * 1.345),
        (center, 0, hem_z + .015, hip_rx * 1.355, hip_ry * 1.325)], mats["ink"], caps=False)
    for index in range(8):
        theta = 2 * math.pi * index / 8
        line(base_name + f"schematic_seam_{index}", [
            (center + (waist_rx + .022) * math.cos(theta), (waist_ry + .020) * math.sin(theta), waist_z - .045),
            (center + (waist_rx + .015) * math.cos(theta), (waist_ry + .015) * math.sin(theta), waist_z),
            (center + (bust_rx + .017) * math.cos(theta), (bust_ry + .017) * math.sin(theta), bust_z)],
            mats["accent"], .0017)
    # Front and back markings clarify viewpoint; back uses a closure marker.
    if back:
        line(base_name + "closure_marker", [(center, -.14, waist_z),
                                            (center, -.14, shoulder_z - .085)], mats["ink"], .003)
    else:
        ellipsoid(base_name + "generic_charm", (center, -neck_ry - .012, shoulder_z - .035),
                  (.016, .005, .016), mats["accent"])
    for side in (-1, 1):
        x = center + side * (p["shoulder"] / 2 + .011)
        ellipsoid(base_name + f"generic_disc_{side}", (x, -upper_radius * 1.14, shoulder_z - .090),
                  (.039, .007, .039), mats["cloth"])
        ellipsoid(base_name + f"generic_disc_center_{side}", (x, -upper_radius * 1.14 - .007, shoulder_z - .090),
                  (.023, .005, .023), mats["accent"])
    text(base_name + "label", face + " / schematic", center - .24, -.095, .032, mats["ink"])
    return height


def outlines(payload):
    records = payload
    if isinstance(payload, dict):
        records = payload.get("patterns", payload.get("panels", payload.get("pieces", [])))
    if not isinstance(records, list) or not records:
        raise ValueError("Pattern JSON must be a nonempty list or have patterns/panels/pieces")
    for record in records:
        points = record.get("outline", record.get("outline_mm", record.get("polygon_mm", record.get("points"))))
        if not points or len(points) < 3:
            raise ValueError(f"Missing polygon outline in {record.get('id', '?')}")
        if any(len(p) < 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v)
                               for v in p[:2]) for p in points):
            raise ValueError("Pattern coordinates must be finite XY millimetres")
        record["outline"] = points
    return records


def panel_layout(records, mats, left=.15, top=1.75, width=1.63, height=1.58):
    packed = []
    x, y, row_height = 0.0, 0.0, 0.0
    packing_width = 1600
    for record in records:
        points = record["outline"]
        x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
        y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
        panel_w, panel_h = x1 - x0 + 65, y1 - y0 + 105
        if x + panel_w > packing_width and x:
            x, y, row_height = 0, y + row_height, 0
        packed.append((record, x, y, x0, y0, panel_w, panel_h))
        x += panel_w
        row_height = max(row_height, panel_h)
    total_w = max(item[1] + item[5] for item in packed)
    total_h = y + row_height
    scale = min(width / total_w, height / total_h)
    for record, px, py, x0, y0, pw, ph in packed:
        origin_x, origin_z = left + px * scale, top - py * scale
        def point(xy, depth=-.09):
            return (origin_x + (xy[0] - x0 + 15) * scale, depth,
                    origin_z - (xy[1] - y0 + 70) * scale)
        border = [point(p, -.08) for p in record["outline"]]
        obj = add_mesh("FLAT_" + record.get("id", "panel"), border,
                       [tuple(range(len(border)))], mats["cloth"])
        obj["component_id"] = record.get("component_id", "")
        obj["quantity"] = record.get("quantity", 1)
        obj["source_units"] = "mm"
        obj["display_scale"] = scale * 1000
        line(obj.name + "_cut", [point(p, -.093) for p in record["outline"]], mats["ink"], .0012, True)
        if record.get("stitchline"):
            stitch = record["stitchline"]
            for a, b in zip(stitch, stitch[1:] + stitch[:1]):
                length = math.dist(a[:2], b[:2])
                count = max(1, int(length / 9))
                for i in range(count):
                    t0, t1 = i / count, min((i + .58) / count, 1)
                    a1 = [a[k] + (b[k] - a[k]) * t0 for k in range(2)]
                    b1 = [a[k] + (b[k] - a[k]) * t1 for k in range(2)]
                    line(obj.name + "_stitch", [point(a1, -.095), point(b1, -.095)], mats["accent"], .0008)
        if record.get("grainline"):
            grain = record["grainline"]
            line(obj.name + "_grain", [point(p, -.096) for p in grain], mats["muted"], .0008)
        label = record.get("id", "panel").replace("_", " ")
        text(obj.name + "_label", label, origin_x + .006, origin_z - .02,
             min(.019, 20 * scale), mats["ink"], -.12)
        text(obj.name + "_quantity", f"CUT {record.get('quantity', 1)} | mm source", origin_x + .006,
             origin_z - .039, min(.013, 15 * scale), mats["muted"], -.12)
    return len(records)


def main():
    args = arguments()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    if isinstance(profile, dict) and "profile" in profile:
        profile = profile["profile"]
    required = ("height", "bust", "waist", "hip", "shoulder", "neck", "back_waist_length",
                "front_waist_length", "arm_length", "upper_arm", "wrist", "waist_to_knee", "head")
    if any(key not in profile or isinstance(profile[key], bool) or
           not isinstance(profile[key], (int, float)) or
           not math.isfinite(profile[key]) or not 0 < profile[key] < 3000 for key in required):
        raise ValueError("Profile must contain positive finite body measurements in mm")
    if profile.get("units", "mm") != "mm":
        raise ValueError("Profile units must be mm")
    if not 256 <= args.resolution <= 8000:
        raise ValueError("Resolution must be between 256 and 8000 pixels")
    records = outlines(json.loads(args.patterns.read_text(encoding="utf-8")))
    args.outdir.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    try:
        accent = tuple(int(args.color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError("--color must be six hexadecimal RGB digits") from exc
    if len(args.color.lstrip("#")) != 6:
        raise ValueError("--color must be six hexadecimal RGB digits")
    mats = {
        "accent": material("Configurable accent", accent),
        "cloth": material("Unbleached prototype cloth", (.93, .94, .91)),
        "body": material("Neutral measurement mannequin", (.57, .62, .63)),
        "ink": material("Graphite", (.045, .083, .105)),
        "muted": material("Secondary text", (.26, .34, .37)),
        "background": material("Warm studio backdrop", (.89, .91, .89)),
    }
    # Graphic layers are unlit for a clean, readable plate behind the 3D forms.
    for name in ("ink", "muted", "background"):
        mat = mats[name]
        color = tuple(mat.diffuse_color)
        mat.node_tree.nodes.clear()
        output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        emission = mat.node_tree.nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = color
        emission.inputs["Strength"].default_value = 1
        mat.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    height = profile["height"] / 1000
    body_and_garment(profile, -1.32, False, mats)
    # A separately labelled rear schematic uses the same measurement envelope.
    before = set(bpy.data.objects)
    body_and_garment(profile, -.54, True, mats)
    for obj in set(bpy.data.objects) - before:
        if obj.type == "FONT":
            continue
        # Rotate the assembly 180 degrees about its vertical axis for a real rear view.
        obj.location.x = -1.08 - obj.location.x
        obj.location.y = -obj.location.y
        obj.rotation_euler.z += math.pi
    # A closure marker belongs on the back-facing surface after the rotation.
    line("REAR_visible_closure", [(-.54, -.17, height - .065 - profile["head"] / 1000 / math.pi * 1.25 - profile["back_waist_length"] / 1000),
                                 (-.54, -.17, height - .14 - profile["head"] / 1000 / math.pi * 1.25)], mats["ink"], .002)
    total = panel_layout(records, mats, top=max(1.75, height))
    top = max(1.75, height) + .27
    text("Title", "GARMENT FOUNDATION / ENGINEERING PREVIEW", -1.73, top, .050, mats["ink"])
    profile_id = str(profile.get("id", "custom"))
    subtitle = f"PROFILE {profile_id}   |   {profile['height']:g} mm height   |   {total} cutting panels   |   editable Blender scene"
    text("Subtitle", subtitle, -1.73, top - .074, .025, mats["muted"])
    text("AssemblyTitle", "MEASUREMENT-DRIVEN FORMS", -1.73, top - .15, .027, mats["ink"])
    text("PatternTitle", "EXACT SOURCE OUTLINES / DISPLAY SCALED", .15, top - .15, .024, mats["ink"])
    text("Warning1", "UNSIMULATED: no drape, collision, fit or sewing validation", -1.73, -.185, .029, mats["ink"])
    text("Warning2", "Generic design hypothesis. Check full-size patterns, attachment tests and a fabric toile before production.", -1.73, -.24, .021, mats["muted"])
    line("Divider", [(.06, .05, -.1), (.06, .05, top - .15)], mats["muted"], .001)
    add_mesh("Backdrop", [(-2, .45, -.4), (2, .45, -.4), (2, .45, top + .15), (-2, .45, top + .15)],
             [(0, 1, 2, 3)], mats["background"])
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene["preview_status"] = "UNSIMULATED / SCHEMATIC / NOT A FIT OR REFERENCE-FIDELITY PROOF"
    scene["source_pattern_file"] = str(args.patterns.resolve())
    scene["source_profile_file"] = str(args.profile.resolve())
    scene["profile_id"] = profile_id
    scene["pattern_count"] = total
    scene["profile_mm_json"] = json.dumps(profile, sort_keys=True)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = round(args.resolution * (top + .48) / 3.75)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.7, .75, .8, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .25
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast" if "Medium High Contrast" in [item.identifier for item in scene.view_settings.bl_rna.properties['look'].enum_items] else "None"
    for x, z, power, size in [(-1.6, 3.1, 60, 4.0), (2.0, 2.4, 40, 3.0)]:
        bpy.ops.object.light_add(type="AREA", location=(x, -3.4, z))
        obj = bpy.context.object
        obj.data.energy = power
        obj.data.shape = "DISK"
        obj.data.size = size
        obj.rotation_euler = (Vector((0, 0, 1)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add(location=(0, -9, (top - .25) / 2))
    camera = bpy.context.object
    camera.name = "Overview_orthographic"
    camera.rotation_euler = (math.pi / 2, 0, 0)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.75
    scene.camera = camera
    scene.render.filepath = str((args.outdir / "overview.png").resolve())
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str((args.outdir / "preview.blend").resolve()))
    bpy.ops.render.render(write_still=True)
    summary = {"profile_id": profile_id, "pattern_count": total,
               "blend": "preview.blend", "png": "overview.png", "simulated": False,
               "assembly_method": "measurement-driven generic display primitives; not derived by draping the panels",
               "flat_panel_method": "exact input outlines in mm, uniformly scaled for display",
               "limitations": ["No cloth simulation", "No collision or fit validation", "No reference-fidelity claim"],
               "resolution": [scene.render.resolution_x, scene.render.resolution_y]}
    (args.outdir / "preview_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("PREVIEW_COMPLETE " + json.dumps(summary))


if __name__ == "__main__":
    main()
