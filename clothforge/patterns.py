"""Measurement-driven, millimetre drafts for a generic costume-fabric prototype.

These are construction hypotheses, not a validated sloper or a reproduction of
a character illustration.  Make a toile, fit it, and redraft before cutting final cloth.
Polygons are unclosed: the last vertex connects to the first.  ``outline`` is
the CUT line; ``stitchline`` is the sewing boundary.  Named ``seams`` are sewing
or construction polylines, including internal dart legs.  Every coordinate is
in the same positive, piece-local millimetre frame.  Quantity counts cuts of
the displayed pattern; a cut-on-fold half represents one complete panel.

No external geometry packages, body-size lookup tables, or flat image scaling
are used.  Curves are sampled polylines, with their actual polyline lengths
used for matching mating seams.  Offset allowances are perpendicular to each
edge; they are not a scale factor applied to a bounding box.
"""

from __future__ import annotations

import math
from numbers import Real


MEASUREMENT_KEYS = (
    "height", "bust", "waist", "hip", "shoulder", "neck",
    "back_waist_length", "front_waist_length", "arm_length", "upper_arm",
    "wrist", "waist_to_knee", "head",
)

SEAM_ALLOWANCE_MM = 10.0
HEM_ALLOWANCE_MM = 15.0
_EPS = 1e-9


def polyline_length(points):
    """Length of an open polyline in the units of its coordinates."""
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(points, points[1:]))


def polygon_area(points):
    """Signed shoelace area of an implicitly closed polygon."""
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(points, points[1:] + points[:1])) / 2.0


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _on_segment(a, b, p):
    return (abs(_cross(_sub(b, a), _sub(p, a))) < 1e-7
            and min(a[0], b[0]) - _EPS <= p[0] <= max(a[0], b[0]) + _EPS
            and min(a[1], b[1]) - _EPS <= p[1] <= max(a[1], b[1]) + _EPS)


def _segments_intersect(a, b, c, d):
    ab, cd = _sub(b, a), _sub(d, c)
    o1, o2 = _cross(ab, _sub(c, a)), _cross(ab, _sub(d, a))
    o3, o4 = _cross(cd, _sub(a, c)), _cross(cd, _sub(b, c))
    if ((o1 > _EPS and o2 < -_EPS) or (o1 < -_EPS and o2 > _EPS)) and (
            (o3 > _EPS and o4 < -_EPS) or (o3 < -_EPS and o4 > _EPS)):
        return True
    return any((abs(o) < _EPS and _on_segment(s, e, p))
               for o, s, e, p in ((o1, a, b, c), (o2, a, b, d),
                                  (o3, c, d, a), (o4, c, d, b)))


def polygon_is_simple(points):
    """Reject crossings, overlapping non-neighbours, and zero-length edges."""
    if len(points) < 3 or abs(polygon_area(points)) < _EPS:
        return False
    count = len(points)
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < _EPS:
            return False
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            if _segments_intersect(a, b, points[j], points[(j + 1) % count]):
                return False
    return True


def offset_polygon(points, allowances):
    """Outward variable-width miter offset, with guarded acute-corner bevels.

    ``allowances[i]`` is the perpendicular distance from stitch edge i to its
    parallel cutting edge.  A zero allowance therefore supports a true fold.
    Unsupported offsets that self-intersect fail instead of returning unsafe
    cutting geometry.  Intended for these modest, simple garment polygons.
    """
    points = [[float(x), float(y)] for x, y in points]
    if len(points) != len(allowances):
        raise ValueError("Provide one seam allowance per stitchline edge")
    if not polygon_is_simple(points):
        raise ValueError("Cannot offset a degenerate or self-intersecting stitchline")
    if any(not isinstance(a, Real) or not math.isfinite(a) or a < 0
           for a in allowances):
        raise ValueError("Seam allowances must be finite, nonnegative millimetres")
    orientation = 1 if polygon_area(points) > 0 else -1
    lines = []
    for a, b, distance in zip(points, points[1:] + points[:1], allowances):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        normal = (orientation * dy / length, -orientation * dx / length)
        lines.append(((a[0] + normal[0] * distance,
                       a[1] + normal[1] * distance), (dx, dy)))
    result = []
    for i, vertex in enumerate(points):
        previous, u = lines[i - 1]
        current, v = lines[i]
        denominator = _cross(u, v)
        if abs(denominator) < _EPS:
            # A collinear join is supported only when both shifted lines agree.
            if abs(_cross(_sub(current, previous), u)) > 1e-6:
                raise ValueError("Changing allowance along a collinear edge is unsupported")
            result.append([current[0], current[1]])
            continue
        t = _cross(_sub(current, previous), v) / denominator
        intersection = [previous[0] + t * u[0], previous[1] + t * u[1]]
        limit = 8 * max(allowances[i - 1], allowances[i], 1.0)
        if math.hypot(intersection[0] - vertex[0], intersection[1] - vertex[1]) > limit:
            # A bevel avoids a dangerous long spike at a decorative pointed tip.
            prior_end = (previous[0] + u[0], previous[1] + u[1])
            result.extend([list(prior_end), list(current)])
        else:
            result.append(intersection)
    if not polygon_is_simple(result):
        raise ValueError("Seam allowance offset self-intersects; redraft this piece")
    return result


def _validated(profile):
    if not isinstance(profile, dict):
        raise ValueError("Measurements must be supplied as a dictionary in millimetres")
    missing = [key for key in MEASUREMENT_KEYS if key not in profile]
    if missing:
        raise ValueError("Missing millimetre measurements: " + ", ".join(missing))
    values = {}
    for key in MEASUREMENT_KEYS:
        value = profile[key]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{key} must be a numeric millimetre measurement")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be positive and finite")
        values[key] = float(value)
    if values["neck"] >= values["bust"]:
        raise ValueError("Neck must be smaller than bust; check millimetre units")
    if min(values["front_waist_length"], values["back_waist_length"]) < 220:
        raise ValueError("This prototype only supports adult torso lengths of at least 220 mm")
    if max(values["front_waist_length"], values["back_waist_length"],
           values["arm_length"], values["waist_to_knee"]) >= values["height"]:
        raise ValueError("Body segment lengths must be smaller than height")
    if min(values["bust"], values["waist"], values["hip"]) < 400:
        raise ValueError("This prototype only supports adult torso circumferences of at least 400 mm")
    return values


def _piece(piece_id, component_id, quantity, material, stitchline, seams,
           grainline, notes, dimensions=None, allowances=None, cut_on_fold=False,
           mirrored_pairs=0):
    allowances = list(allowances or [SEAM_ALLOWANCE_MM] * len(stitchline))
    outline = offset_polygon(stitchline, allowances)
    origin = (min(p[0] for p in outline), min(p[1] for p in outline))

    def move(points):
        return [[round(x - origin[0], 6), round(y - origin[1], 6)] for x, y in points]

    moved_outline = move(outline)
    dims = dict(dimensions or {})
    dims.update({
        "width_mm": round(max(p[0] for p in moved_outline), 6),
        "height_mm": round(max(p[1] for p in moved_outline), 6),
        "seam_allowance_mm": SEAM_ALLOWANCE_MM,
    })
    if cut_on_fold:
        cut_instruction = f"Cut {quantity} on fold; the fold has zero added seam allowance."
    elif mirrored_pairs:
        cut_instruction = f"Cut {mirrored_pairs} mirrored pair(s), {quantity} pieces total."
    else:
        cut_instruction = f"Cut {quantity} piece(s) at full displayed size."
    return {
        "id": piece_id, "component_id": component_id,
        "quantity": quantity, "material": material,
        "outline": moved_outline, "stitchline": move(stitchline),
        "seams": {name: move(points) for name, points in seams.items()},
        "grainline": move(grainline), "notes": [cut_instruction] + list(notes), "dimensions": dims,
        "cut_on_fold": cut_on_fold, "mirrored_pairs": mirrored_pairs,
        "cut_instruction": cut_instruction,
        "seam_allowances": [float(a) for a in allowances],
        "draft_status": "unfitted_engineering_interpretation",
        "units": "mm",
    }


def _rectangle(width, height):
    return [[0, 0], [width, 0], [width, height], [0, height]]


def _arc(radius, angle, steps=32):
    return [[radius * math.cos(angle * i / steps),
             radius * math.sin(angle * i / steps)] for i in range(steps + 1)]


def _annular_piece(piece_id, component_id, quantity, material, inner_length,
                   depth, angle, notes, dimensions=None):
    steps = 32
    chord_factor = 2 * steps * math.sin(angle / (2 * steps))
    radius = inner_length / chord_factor
    inner, outer = _arc(radius, angle, steps), _arc(radius + depth, angle, steps)
    stitchline = outer + list(reversed(inner))
    # Outer curved edge has a narrow turn-under hem; remaining edges are joins.
    allowances = [HEM_ALLOWANCE_MM] * steps + [SEAM_ALLOWANCE_MM] * (steps + 2)
    middle = angle / 2
    grainline = [[r * math.cos(middle), r * math.sin(middle)]
                 for r in (radius + depth * .25, radius + depth * .75)]
    dims = dict(dimensions or {})
    dims.update({"inner_seam_length_mm": inner_length, "radial_depth_mm": depth,
                 "angle_radians": angle, "inner_radius_mm": radius,
                 "hem_allowance_mm": HEM_ALLOWANCE_MM,
                 "curve_segments": steps})
    return _piece(piece_id, component_id, quantity, material, stitchline,
                  {"attachment": inner, "hem": outer,
                   "side_start": [inner[0], outer[0]],
                   "side_end": [inner[-1], outer[-1]]},
                  grainline, notes, dims, allowances=allowances)


def generate_patterns(profile: dict) -> list[dict]:
    """Generate eleven deterministic fabric drafts from adult measurements.

    All required input measurements are direct, positive values in mm.  Extra
    profile fields are ignored.  Ease and design proportions are explicit in
    each piece's dimensions; inferred dimensions must be checked on a toile.
    This function neither fits an avatar nor verifies wearability/support.
    """
    m = _validated(profile)
    waist_y = m["back_waist_length"]
    balance = m["front_waist_length"] - waist_y
    armhole_y = min(m["bust"] / 6 + 75, waist_y * .60)
    front_top = max(35.0, armhole_y * .48 - balance)
    if front_top >= armhole_y - 35:
        raise ValueError("Front/back balance is outside the supported draft; use a fitted block")
    bust_w = (m["bust"] + 80) / 4
    dart_intake = 12.0
    waist_w = (m["waist"] + 60) / 4 + dart_intake
    hip_w = (m["hip"] + 80) / 4
    hip_depth = m["height"] * .11
    hem_y = waist_y + hip_depth
    back_top = waist_y - min(100, waist_y * .23)
    band_depth = min(45.0, waist_y * .11)
    pieces = []
    common_notes = [
        "Original generic construction hypothesis; not traced artwork or a fidelity-validated character pattern.",
        "Unfitted adult draft. Make and adjust a toile before cutting final fabric; seam matching alone does not establish fit.",
        "Measurements drive drafting separately; this is not uniform scaling of a drawing or a ready-made sloper.",
    ]
    common_dimensions = {
        "bust_ease_mm": 80.0, "waist_ease_after_darts_mm": 60.0,
        "hip_ease_mm": 80.0, "dart_intake_mm": dart_intake,
        "inferred_waist_to_hip_mm": hip_depth,
        "front_back_balance_mm": balance,
        "shoulder_input_mm": m["shoulder"],
        "shoulder_geometry_modeled": False,
        "bust_quarter_mm": bust_w, "waist_quarter_before_dart_mm": waist_w,
        "hip_quarter_mm": hip_w,
    }

    def side_x(y):
        t = (y - armhole_y) / (waist_y - armhole_y)
        return bust_w + (waist_w - bust_w) * t

    for front in (True, False):
        suffix = "front" if front else "back"
        top = ([[0, front_top], [bust_w * .45, front_top + 20], [bust_w, armhole_y]]
               if front else [[0, back_top], [bust_w * .55, armhole_y + 45], [bust_w, armhole_y]])
        stitchline = top + [[waist_w, waist_y], [hip_w, hem_y], [0, hem_y]]
        center_allowance = 0.0 if front else 15.0
        allowances = [10.0] * len(stitchline)
        allowances[-1] = center_allowance
        dart_x = min(bust_w, waist_w, hip_w) * .52
        upper_apex_y = (armhole_y + 50 if front else waist_y - 40)
        lower_apex_y = waist_y + min(90.0, hip_depth * .65)
        apex, lower = [dart_x, upper_apex_y], [dart_x, lower_apex_y]
        seams = {
            "top": top, "side": stitchline[2:5], "hem": stitchline[4:6],
            "center_fold" if front else "center_back": [stitchline[-1], stitchline[0]],
            "dart_left": [apex, [dart_x - dart_intake / 2, waist_y], lower],
            "dart_right": [apex, [dart_x + dart_intake / 2, waist_y], lower],
            "waist_guide": [[0, waist_y], [waist_w, waist_y]],
        }
        notes = common_notes + [
            "Simplified high-front / deep-V open-upper-back foundation, without shoulder seams or engineered bust cups.",
            "Support, undergarment coverage, modesty, straps/boning and exact opening shape require a fitted toile and separate decisions.",
            "Shoulder width is recorded but not used by this strapless block: there are no shoulder seams. Broad-shoulder fit is UNVALIDATED; shoulder straps and sleeve support need a separate fitted design.",
            "Head circumference is recorded in the input only; headwear and rigid accessories are outside this fabric draft.",
            "Close each diamond waist dart by matching its marked legs; do not cut along dart marks.",
            "Waist-to-hip depth is inferred from height; replace with a direct measurement during fitting.",
            "Front is one half cut on fold; do not add a center-front allowance." if front else
            "Cut one mirrored pair. Center-back 15 mm allowance reserves an opening; select and fit closure before assembly.",
            "Hem attaches to the four hip-flounce gores; it is not a turn-under hem.",
        ]
        dims = dict(common_dimensions, center_allowance_mm=center_allowance,
                    hem_attachment_length_mm=hip_w, band_attachment_length_mm=polyline_length(top))
        pieces.append(_piece("torso_" + suffix, "torso", 1 if front else 2,
                             "white medium-weight woven shell", stitchline, seams,
                             [[dart_x * .45, waist_y - 35], [dart_x * .45, hem_y - 25]],
                             notes, dims, allowances, cut_on_fold=front,
                             mirrored_pairs=0 if front else 1))
        band_bottom = [[x, y + band_depth] for x, y in top]
        band_bottom[-1][0] = side_x(armhole_y + band_depth)
        band_poly = top + list(reversed(band_bottom))
        band_allowances = [10.0] * len(band_poly)
        band_allowances[-1] = center_allowance
        band_grain_x = bust_w * .15
        # The first top segment is linear, so its midpoint gives an interior mark.
        band_grain_y = top[0][1] + (top[1][1] - top[0][1]) * band_grain_x / top[1][0]
        pieces.append(_piece("upper_band_" + suffix, "upper_band", 1 if front else 2,
                             "sky-blue contrast woven", band_poly,
                             {"top_attachment": top, "lower_edge": band_bottom,
                              "side": [top[-1], band_bottom[-1]]},
                             [[band_grain_x, band_grain_y + 8],
                              [band_grain_x, band_grain_y + band_depth - 8]],
                             common_notes + [
                                 "Simple faced overlay following torso top; sculpted cups and independent curved back bands are not modeled.",
                                 "Top stitching length matches the same-named torso panel; sew or baste as an overlay after fitting.",
                                 "Dark piping, white cross-straps, lining and ornament mounts are not drafted here.",
                             ], {"band_depth_mm": band_depth,
                                 "attachment_length_mm": polyline_length(top)},
                             band_allowances, cut_on_fold=front,
                             mirrored_pairs=0 if front else 1))

    flounce_depth = min(m["height"] * .062, m["waist_to_knee"] * .25)
    pieces.append(_annular_piece(
        "hip_flounce", "hip_flounce", 4, "white lightweight woven; blue edge trim separately",
        hip_w, flounce_depth, math.pi / 2,
        common_notes + [
            "Four quarter-ring gores form a short circular hip flounce, not a pleated skirt.",
            "Each inner seam matches one torso hem quarter; the four sewn inner edges equal the fitted shell hip perimeter.",
            "Continue the center-back opening through one gore join as needed for dressing; closure and lining are not engineered.",
            "Hang bias fabric before leveling the hem. Edge-trim width and asymmetric styling remain unmodeled.",
            "Curves are 32-segment polylines; sew the printed line rather than substituting a different-radius arc.",
        ], {"total_attachment_length_mm": hip_w * 4}))

    bell_top = m["upper_arm"] + 40
    bell_extra = m["upper_arm"] * .70
    bell_depth = m["arm_length"] * .44
    # Solve the sampled chord perimeter difference, not an uncalibrated arc.
    steps = 32
    ratio = bell_extra / (2 * steps * bell_depth)
    if ratio >= 1:
        raise ValueError("Arm measurements cannot form the bell-sleeve sector")
    bell_angle = 2 * steps * math.asin(ratio)
    if bell_angle >= math.pi:
        raise ValueError("Arm measurements require an unsupported bell angle; fit a custom sleeve")
    pieces.append(_annular_piece(
        "bell_sleeve", "upper_sleeve", 2, "sky-blue medium-weight woven",
        bell_top, bell_depth, bell_angle,
        common_notes + [
            "Detached upper bell sleeve: sew its equal radial side seams; do not join its hem to the forearm tube.",
            "Upper edge includes 40 mm ease. Retention, lining, white inserts and circular arm-device mounts need separate mock-ups.",
            "Upper sleeve overlaps the independent forearm sleeve; inferred arm segmentation must be fitted with bent elbows.",
        ], {"upper_arm_ease_mm": 40.0, "hem_circumference_mm": bell_top + bell_extra}))

    forearm_length = m["arm_length"] * .59
    forearm_top = m["upper_arm"] * .80 + 20
    wrist_width = m["wrist"] + 30
    inset = (forearm_top - wrist_width) / 2
    forearm_poly = [[0, 0], [forearm_top, 0],
                    [inset + wrist_width, forearm_length], [inset, forearm_length]]
    vent = min(50.0, forearm_length * .2)
    t = (forearm_length - vent) / forearm_length
    side_left_end = [inset * t, forearm_length - vent]
    side_right_end = [forearm_top - inset * t, forearm_length - vent]
    pieces.append(_piece(
        "forearm_sleeve", "forearm_sleeve", 2, "black stretch fabric; stretch direction across arm",
        forearm_poly,
        {"upper_opening": forearm_poly[:2], "wrist_attachment": forearm_poly[2:4],
         "side_left": [forearm_poly[0], side_left_end],
         "side_right": [forearm_poly[1], side_right_end],
         "vent_left": [side_left_end, forearm_poly[3]],
         "vent_right": [side_right_end, forearm_poly[2]]},
        [[forearm_top / 2, 25], [forearm_top / 2, forearm_length - 25]],
        common_notes + [
            "Independent tapered forearm tube. Upper circumference is inferred from upper arm, not a measured elbow circumference.",
            "No negative ease is assumed. Test actual stretch/recovery and measure elbow, hand and forearm before seeking a close fit.",
            "Leave the marked wrist vent open for the cuff fastening; finish its allowances after the toile is fitted.",
        ], {"inferred_upper_circumference_mm": forearm_top, "wrist_attachment_length_mm": wrist_width,
            "wrist_ease_mm": 30.0, "vent_length_vertical_mm": vent,
            "inferred_forearm_length_mm": forearm_length}, mirrored_pairs=1))

    cuff_overlap, cuff_height = 20.0, 60.0
    cuff_poly = _rectangle(wrist_width + cuff_overlap, cuff_height)
    pieces.append(_piece(
        "wrist_cuff", "cuff", 2, "white woven with suitable interfacing",
        cuff_poly, {"attachment": [[0, cuff_height], [wrist_width, cuff_height]],
                    "fold": [[0, cuff_height / 2], [wrist_width + cuff_overlap, cuff_height / 2]],
                    "closure_overlap_start": [[wrist_width, 0], [wrist_width, cuff_height]]},
        [[20, cuff_height / 2], [wrist_width - 20, cuff_height / 2]],
        common_notes + [
            "Fold lengthwise; 30 mm finished cuff plus 20 mm fastening extension.",
            "Attachment length excludes the closure extension and matches the forearm sleeve wrist edge exactly.",
            "Fastener type and placement require a hand-through and circulation check on the toile.",
        ], {"attachment_length_mm": wrist_width, "closure_overlap_mm": cuff_overlap,
            "finished_height_mm": cuff_height / 2}))

    neck_ease, neck_overlap, neck_height = 20.0, 20.0, 28.0
    neck_opening = m["neck"] + neck_ease
    neck_width = neck_opening + neck_overlap
    pieces.append(_piece(
        "neckband", "neckband", 2, "white woven: one outer and one facing",
        _rectangle(neck_width, neck_height),
        {"lower_edge": [[0, neck_height], [neck_width, neck_height]],
         "closure_overlap_start": [[neck_opening, 0], [neck_opening, neck_height]]},
        [[20, neck_height / 2], [neck_width - 20, neck_height / 2]],
        common_notes + [
            "Independent straight neckband with outer and facing; it does not attach to the torso draft.",
            "20 mm neck ease and 20 mm overlap are starting hypotheses. Fit comfortably and use a quick-release closure.",
            "Shaped collar contours, ornament mount and tie attachment are not mechanically engineered.",
        ], {"finished_closed_circumference_mm": neck_opening, "neck_ease_mm": neck_ease,
            "closure_overlap_mm": neck_overlap, "finished_height_mm": neck_height}))

    tie_length = m["front_waist_length"] * .48
    tie_width = m["neck"] * .19
    tie_poly = [[tie_width * .32, 0], [tie_width * .68, 0],
                [tie_width, tie_length * .78], [tie_width * .50, tie_length],
                [0, tie_length * .78]]
    pieces.append(_piece(
        "necktie", "tie", 2, "yellow woven: front and facing",
        tie_poly, {"mounting_tab": tie_poly[:2]},
        [[tie_width / 2, tie_length * .15], [tie_width / 2, tie_length * .80]],
        common_notes + [
            "Two-layer decorative tapered tie blade; proportions are inferred rather than traced.",
            "Fit a removable mounting tab to the independent neckband after fitting; leave a turning opening.",
        ], {"finished_length_mm": tie_length, "maximum_width_mm": tie_width}))

    insert_width, insert_depth = m["hip"] * .14, m["height"] * .044
    insert_poly = [[0, 0], [insert_width * .60, insert_depth * .18],
                   [insert_width, insert_depth * .65], [insert_width * .70, insert_depth],
                   [0, insert_depth * .62]]
    pieces.append(_piece(
        "hip_insert", "hip_insert", 4, "yellow woven: paired fronts and facings",
        insert_poly, {"mounting_edge": [insert_poly[-1], insert_poly[0]]},
        [[insert_width * .22, insert_depth * .30], [insert_width * .22, insert_depth * .60]],
        common_notes + [
            "Two mirrored decorative hip fins, each with a facing; four cuts total.",
            "Mounting position, angle, ties and red ornaments must be located on the fitted torso. No automatic mating seam is claimed.",
        ], {"maximum_width_mm": insert_width, "maximum_depth_mm": insert_depth}, mirrored_pairs=2))
    return pieces


def seam_graph(patterns: list[dict]) -> list[dict]:
    """Return auditable matched joins, with physical-copy multiplicities.

    A half pattern cut on fold supplies two copies of its displayed side/top/
    hem seams. ``multiplicity`` counts those physical seams, not cut patterns.
    ``ease_ratio`` is required a-length / b-length; all current joins are 1:1.
    Lining/closure installation and independent accessory mounting are outside
    these length contracts.  Overlay edges are explicitly labeled as overlays.
    """
    by_id = {p["id"]: p for p in patterns}
    if len(by_id) != len(patterns):
        raise ValueError("Pattern IDs must be unique")
    specifications = [
        ("torso_sides", "torso_front", "side", "torso_back", "side", 2, "join",
         "Two side seams; the cut-on-fold front supplies a left and right seam."),
        ("front_band_overlay", "torso_front", "top", "upper_band_front", "top_attachment", 2, "overlay",
         "Two mirrored halves of one cut-on-fold front. Baste color overlay after fitting."),
        ("back_band_overlay", "torso_back", "top", "upper_band_back", "top_attachment", 2, "overlay",
         "One overlay for each of the two mirrored back panels."),
        ("band_sides", "upper_band_front", "side", "upper_band_back", "side", 2, "join",
         "Join together with, or in the same position as, the corresponding torso side seams."),
        ("front_flounce", "torso_front", "hem", "hip_flounce", "attachment", 2, "join",
         "Two front hem quarters to two of the four flounce gores, without gathering."),
        ("back_flounce", "torso_back", "hem", "hip_flounce", "attachment", 2, "join",
         "Two back hem quarters to the remaining two flounce gores, without gathering."),
        ("flounce_gores", "hip_flounce", "side_start", "hip_flounce", "side_end", 4, "join_with_opening",
         "Four adjacent gore joins form the ring; reserve part of the center-back join for the selected closure."),
        ("upper_sleeve_sides", "bell_sleeve", "side_start", "bell_sleeve", "side_end", 2, "join",
         "One radial seam on each independent detached upper sleeve."),
        ("forearm_sides", "forearm_sleeve", "side_left", "forearm_sleeve", "side_right", 2, "join",
         "Join each tube only to the vent stop. The wrist-vent edges stay separate."),
        ("cuff_attachment", "forearm_sleeve", "wrist_attachment", "wrist_cuff", "attachment", 2, "join",
         "One cuff per tube; the marked cuff extension is excluded from this matching seam."),
        ("front_darts", "torso_front", "dart_left", "torso_front", "dart_right", 2, "dart",
         "Two internal diamond darts on the complete front. Fold, sew, and press; never cut their legs."),
        ("back_darts", "torso_back", "dart_left", "torso_back", "dart_right", 2, "dart",
         "One internal diamond dart per back half; no cutting along dart legs."),
    ]
    result = []
    for join_id, a_id, a_seam, b_id, b_seam, count, operation, note in specifications:
        try:
            a_length = polyline_length(by_id[a_id]["seams"][a_seam])
            b_length = polyline_length(by_id[b_id]["seams"][b_seam])
        except KeyError as exc:
            raise ValueError(f"Missing pattern or seam required for {join_id}: {exc}") from exc
        if a_length <= 0 or b_length <= 0:
            raise ValueError(f"Join {join_id} has an empty sewing edge")
        if not math.isclose(a_length, b_length, rel_tol=0, abs_tol=.01):
            raise ValueError(f"Join {join_id} does not match within 0.01 mm")
        result.append({
            "id": join_id,
            "a": {"piece_id": a_id, "seam": a_seam},
            "b": {"piece_id": b_id, "seam": b_seam},
            "multiplicity": count, "length_a_mm": round(a_length, 6),
            "length_b_mm": round(b_length, 6), "ease_ratio": 1.0,
            "operation": operation, "notes": note,
        })
    return result


def construction_openings(patterns: list[dict]) -> list[dict]:
    """Edges intentionally left free or fitted later; no false mating claims."""
    specifications = [
        ("torso_back", "center_back", "closure", "Fit a center-back closure; opening length and fastening are not specified."),
        ("torso_front", "center_fold", "fold", "Place on folded fabric; never join or cut through the fold."),
        ("upper_band_front", "lower_edge", "overlay_finish", "Turn under or face the free overlay edge after the toile is fitted."),
        ("upper_band_back", "lower_edge", "overlay_finish", "Turn under or face the free overlay edge after the toile is fitted."),
        ("hip_flounce", "hem", "hem", "Free circular hem, not a sewing partner to another fabric component."),
        ("bell_sleeve", "attachment", "open_retention", "Independent upper-arm opening. Retention needs a fitted elastic/strap design."),
        ("bell_sleeve", "hem", "hem", "Free upper-sleeve hem overlaps the forearm sleeve without attaching to it."),
        ("forearm_sleeve", "upper_opening", "open_retention", "Independent forearm opening; infer no join to the bell sleeve."),
        ("forearm_sleeve", "vent_left", "vent", "Finish and leave open for the cuff fastening."),
        ("forearm_sleeve", "vent_right", "vent", "Finish and leave open for the cuff fastening."),
        ("wrist_cuff", "closure_overlap_start", "closure_mark", "Fastener location needs a hand-through and circulation check."),
        ("neckband", "closure_overlap_start", "closure_mark", "Fit a comfortable, quick-release closure; band is independent of torso."),
        ("necktie", "mounting_tab", "mount_after_fitting", "Place a removable tie mount on the fitted neckband; exact location is unspecified."),
        ("hip_insert", "mounting_edge", "mount_after_fitting", "Locate decorative fins on the fitted torso; no matched attachment seam is asserted."),
    ]
    by_id = {p["id"]: p for p in patterns}
    result = []
    for piece_id, seam, operation, note in specifications:
        if piece_id not in by_id or seam not in by_id[piece_id]["seams"]:
            raise ValueError(f"Missing construction edge: {piece_id}.{seam}")
        result.append({"piece_id": piece_id, "seam": seam,
                       "operation": operation, "notes": note})
    return result
