"""Geometry and seam-contract tests; these cannot establish garment fit."""

import copy
import json
import math
import unittest

from clothforge.patterns import (
    MEASUREMENT_KEYS, generate_patterns, offset_polygon, polygon_area,
    seam_graph, construction_openings,
    polygon_is_simple, polyline_length,
)


PROFILE = dict(height=1650, bust=880, waist=680, hip=940, shoulder=390,
               neck=340, back_waist_length=400, front_waist_length=420,
               arm_length=560, upper_arm=280, wrist=155, waist_to_knee=580,
               head=550)


class PatternTests(unittest.TestCase):
    def setUp(self):
        self.pieces = {p["id"]: p for p in generate_patterns(PROFILE)}

    def assertSeamEqual(self, left_id, left_seam, right_id, right_seam):
        left = polyline_length(self.pieces[left_id]["seams"][left_seam])
        right = polyline_length(self.pieces[right_id]["seams"][right_seam])
        self.assertAlmostEqual(left, right, delta=0.00001)

    def test_contract_and_serialization(self):
        expected = {"torso_front", "torso_back", "upper_band_front", "upper_band_back",
                    "hip_flounce", "bell_sleeve", "forearm_sleeve", "wrist_cuff",
                    "neckband", "necktie", "hip_insert"}
        self.assertEqual(set(self.pieces), expected)
        for p in self.pieces.values():
            for key in ("id", "component_id", "quantity", "material", "outline",
                        "stitchline", "seams", "grainline", "notes", "dimensions"):
                self.assertIn(key, p)
            self.assertIsInstance(p["quantity"], int)
            self.assertGreater(p["quantity"], 0)
            self.assertEqual(p["units"], "mm")
            self.assertEqual(len(p["stitchline"]), len(p["seam_allowances"]))
            self.assertNotEqual(p["outline"][0], p["outline"][-1])
            self.assertEqual(p["draft_status"], "unfitted_engineering_interpretation")
            self.assertIn("toile", " ".join(p["notes"]).lower())
        json.dumps(list(self.pieces.values()), allow_nan=False)

    def test_simple_positive_polygons_and_cut_area(self):
        for p in self.pieces.values():
            with self.subTest(piece=p["id"]):
                for key in ("outline", "stitchline"):
                    self.assertTrue(polygon_is_simple(p[key]), key)
                    self.assertTrue(all(math.isfinite(v) and v >= -0.000001
                                        for xy in p[key] for v in xy))
                self.assertGreater(abs(polygon_area(p["outline"])),
                                   abs(polygon_area(p["stitchline"])))

    def test_mating_torso_and_band_seams(self):
        self.assertSeamEqual("torso_front", "side", "torso_back", "side")
        for suffix in ("front", "back"):
            self.assertSeamEqual("torso_" + suffix, "top",
                                 "upper_band_" + suffix, "top_attachment")
            self.assertSeamEqual("torso_" + suffix, "hem", "hip_flounce", "attachment")
            self.assertSeamEqual("torso_" + suffix, "dart_left",
                                 "torso_" + suffix, "dart_right")
        self.assertSeamEqual("upper_band_front", "side", "upper_band_back", "side")

    def test_flounce_perimeter_and_gores(self):
        p = self.pieces["hip_flounce"]
        self.assertEqual(p["quantity"], 4)
        self.assertAlmostEqual(polyline_length(p["seams"]["attachment"]) * 4,
                               PROFILE["hip"] + 80, delta=0.00001)
        self.assertSeamEqual("hip_flounce", "side_start", "hip_flounce", "side_end")
        self.assertNotIn("pleat", p["dimensions"])

    def test_sleeve_and_cuff_contract(self):
        self.assertSeamEqual("bell_sleeve", "side_start", "bell_sleeve", "side_end")
        self.assertSeamEqual("forearm_sleeve", "side_left", "forearm_sleeve", "side_right")
        self.assertSeamEqual("forearm_sleeve", "wrist_attachment", "wrist_cuff", "attachment")
        bell = self.pieces["bell_sleeve"]
        self.assertAlmostEqual(polyline_length(bell["seams"]["attachment"]),
                               PROFILE["upper_arm"] + 40, delta=0.00001)
        self.assertAlmostEqual(polyline_length(bell["seams"]["hem"]),
                               PROFILE["upper_arm"] * 1.7 + 40, delta=0.00001)

    def test_fold_is_not_given_seam_allowance(self):
        front = self.pieces["torso_front"]
        self.assertTrue(front["cut_on_fold"])
        self.assertEqual(front["quantity"], 1)
        self.assertEqual(front["seam_allowances"][-1], 0)
        fold_x = front["seams"]["center_fold"][0][0]
        self.assertAlmostEqual(min(p[0] for p in front["outline"]), fold_x)
        self.assertEqual(self.pieces["torso_back"]["quantity"], 2)
        self.assertEqual(self.pieces["torso_back"]["seam_allowances"][-1], 15)

    def test_true_allowance_not_radial_scaling(self):
        square = [[0, 0], [100, 0], [100, 50], [0, 50]]
        self.assertEqual([[round(x, 6), round(y, 6)] for x, y in offset_polygon(square, [10, 10, 10, 10])],
                         [[-10, -10], [110, -10], [110, 60], [-10, 60]])
        fold = offset_polygon(square, [10, 10, 15, 0])
        self.assertEqual([[round(x, 6), round(y, 6)] for x, y in fold], [[0, -10], [110, -10], [110, 65], [0, 65]])
        clockwise = offset_polygon(list(reversed(square)), [10] * 4)
        self.assertEqual({tuple(round(v, 6) for v in xy) for xy in clockwise},
                         {tuple(round(v, 6) for v in xy) for xy in offset_polygon(square, [10] * 4)})

    def test_sloping_edge_offset_distance(self):
        triangle = [[0, 0], [100, 0], [50, 100]]
        cut = offset_polygon(triangle, [10] * 3)
        for i, (a, b) in enumerate(zip(triangle, triangle[1:] + triangle[:1])):
            q = cut[i]
            distance = abs((b[0] - a[0]) * (q[1] - a[1]) -
                           (b[1] - a[1]) * (q[0] - a[0])) / math.dist(a, b)
            self.assertAlmostEqual(distance, 10)

    def test_invalid_inputs_fail_explicitly(self):
        for value in (0, -3, float("nan"), float("inf"), True, "880"):
            invalid = dict(PROFILE, bust=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                generate_patterns(invalid)
        for key in MEASUREMENT_KEYS:
            invalid = dict(PROFILE)
            del invalid[key]
            with self.subTest(missing=key), self.assertRaisesRegex(ValueError, key):
                generate_patterns(invalid)
        with self.assertRaisesRegex(ValueError, "Neck"):
            generate_patterns(dict(PROFILE, neck=900))
        with self.assertRaisesRegex(ValueError, "millimetre"):
            generate_patterns([])

    def test_reject_bad_offset_geometry(self):
        with self.assertRaises(ValueError):
            offset_polygon([[0, 0], [10, 10], [0, 10], [10, 0]], [1] * 4)
        with self.assertRaises(ValueError):
            offset_polygon([[0, 0], [10, 0], [10, 10]], [-1, 1, 1])
        with self.assertRaises(ValueError):
            offset_polygon([[0, 0], [10, 0], [10, 10]], [1, 1])

    def test_distinct_profiles_remain_simple_and_matched(self):
        examples = [
            dict(PROFILE, height=1500, bust=760, waist=620, hip=820, shoulder=345,
                 back_waist_length=350, front_waist_length=375, arm_length=500,
                 upper_arm=250, wrist=145, waist_to_knee=520),
            dict(PROFILE, height=1850, bust=1160, waist=1020, hip=1230, shoulder=470,
                 neck=430, back_waist_length=470, front_waist_length=495,
                 arm_length=660, upper_arm=390, wrist=195, waist_to_knee=660),
            dict(PROFILE, bust=980, waist=1010, hip=1080),
        ]
        for profile in examples:
            self.pieces = {p["id"]: p for p in generate_patterns(profile)}
            for p in self.pieces.values():
                self.assertTrue(polygon_is_simple(p["outline"]), p["id"])
                self.assertTrue(polygon_is_simple(p["stitchline"]), p["id"])
            self.test_mating_torso_and_band_seams()
            self.assertSeamEqual("forearm_sleeve", "wrist_attachment", "wrist_cuff", "attachment")

    def test_deterministic_and_input_not_mutated(self):
        before = copy.deepcopy(PROFILE)
        self.assertEqual(generate_patterns(PROFILE), generate_patterns(PROFILE))
        self.assertEqual(PROFILE, before)

    def test_individual_measurement_changes_do_not_flat_scale_everything(self):
        larger_hips = {p["id"]: p for p in generate_patterns(dict(PROFILE, hip=1040))}
        self.assertEqual(self.pieces["wrist_cuff"], larger_hips["wrist_cuff"])
        self.assertEqual(self.pieces["neckband"], larger_hips["neckband"])
        self.assertNotEqual(self.pieces["hip_flounce"], larger_hips["hip_flounce"])
        self.assertEqual(self.pieces["torso_front"]["dimensions"]["bust_quarter_mm"],
                         larger_hips["torso_front"]["dimensions"]["bust_quarter_mm"])

    def test_seam_graph_references_lengths_and_multiplicity(self):
        graph = seam_graph(list(self.pieces.values()))
        self.assertEqual(len(graph), 12)
        self.assertEqual(len({edge["id"] for edge in graph}), len(graph))
        for edge in graph:
            self.assertGreater(edge["multiplicity"], 0)
            self.assertAlmostEqual(edge["length_a_mm"], edge["length_b_mm"], delta=.00001)
            self.assertEqual(edge["ease_ratio"], 1.0)
            for endpoint in ("a", "b"):
                self.assertIn(edge[endpoint]["seam"],
                              self.pieces[edge[endpoint]["piece_id"]]["seams"])
        openings = construction_openings(list(self.pieces.values()))
        self.assertTrue(any(p["operation"] == "closure" for p in openings))
        self.assertTrue(any(p["piece_id"] == "bell_sleeve" and p["seam"] == "hem"
                            for p in openings))
        broken = copy.deepcopy(list(self.pieces.values()))
        next(p for p in broken if p["id"] == "wrist_cuff")["seams"]["attachment"][1][0] += 1
        with self.assertRaisesRegex(ValueError, "cuff_attachment"):
            seam_graph(broken)

    def test_broad_shoulders_are_an_explicit_unmodeled_limit(self):
        broad = {p["id"]: p for p in generate_patterns(dict(PROFILE, shoulder=490))}
        for name in ("torso_front", "torso_back"):
            self.assertEqual(self.pieces[name]["stitchline"], broad[name]["stitchline"])
            self.assertFalse(broad[name]["dimensions"]["shoulder_geometry_modeled"])
            self.assertEqual(broad[name]["dimensions"]["shoulder_input_mm"], 490)
            self.assertIn("Broad-shoulder fit is UNVALIDATED", " ".join(broad[name]["notes"]))

    def test_generic_component_mapping(self):
        expected = {"torso", "upper_band", "hip_flounce", "upper_sleeve",
                    "forearm_sleeve", "cuff", "neckband", "tie", "hip_insert"}
        self.assertEqual({p["component_id"] for p in self.pieces.values()}, expected)
        self.assertNotIn("Luo Tianyi", json.dumps(list(self.pieces.values())))


if __name__ == "__main__":
    unittest.main()
