"""STL topology and open attachment geometry checks, using only unittest."""
import collections
import json
import math
import tempfile
import unittest
from pathlib import Path

from clothforge.rigid import _normal, _ornament_mesh, generate_rigid


class RigidMeshTests(unittest.TestCase):
    def setUp(self):
        self.vertices, self.faces = _ornament_mesh(80, 26, 3.2, 23, 5.5,
                                                 corner_radius=8)

    def test_mesh_is_closed_consistently_wound_manifold(self):
        edges = collections.Counter()
        directed = collections.Counter()
        for a, b, c in self.faces:
            for edge in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted(edge))] += 1
                directed[edge] += 1
            self.assertAlmostEqual(sum(v * v for v in _normal(
                self.vertices[a], self.vertices[b], self.vertices[c])), 1)
        self.assertTrue(all(count == 2 for count in edges.values()))
        self.assertTrue(all(directed[(b, a)] == count for (a, b), count in directed.items()))
        # A closed solid with one through-slot is genus 1, Euler characteristic 0.
        self.assertEqual(len(self.vertices) - len(edges) + len(self.faces), 0)
        volume = 0.0
        for a, b, c in self.faces:
            p, q, r = [self.vertices[i] for i in (a, b, c)]
            volume += (p[0] * (q[1] * r[2] - q[2] * r[1]) +
                       p[1] * (q[2] * r[0] - q[0] * r[2]) +
                       p[2] * (q[0] * r[1] - q[1] * r[0])) / 6
        self.assertGreater(volume, 4500)
        self.assertLess(volume, 80 * 26 * 3.2)

    def test_slot_is_actual_open_geometry(self):
        # No triangle in projection may contain a point in the central clear slot.
        for x, y in ((0, 0), (9, 0), (-9, 0), (0, 1.5), (0, -1.5)):
            for face in self.faces:
                a, b, c = [self.vertices[i] for i in face]
                determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(determinant) < 1e-10:
                    continue
                u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
                v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
                self.assertFalse(u >= -1e-9 and v >= -1e-9 and u + v <= 1 + 1e-9,
                                 "Slot has a face blocking its open area")

    def test_dimensions_and_actual_rounded_edges(self):
        bounds = [max(v[i] for v in self.vertices) - min(v[i] for v in self.vertices)
                  for i in range(3)]
        for actual, expected in zip(bounds, (80, 26, 3.2)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(len(set(round(v[2], 8) for v in self.vertices)), 10)
        bottom = [v for v in self.vertices if v[2] == 0]
        self.assertLess(max(v[0] for v in bottom), 40)

    def test_generate_records_and_stl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = generate_rigid({"upper_arm": 270, "neck": 330}, root)
            self.assertEqual(len(records), 3)
            self.assertEqual(json.loads((root / "rigid_manifest.json").read_text())["parts"], records)
            for record in records:
                stl = (root / record["file"]).read_text(encoding="ascii")
                self.assertEqual(stl.count("facet normal"), record["triangle_count"])
                self.assertTrue(stl.startswith("solid "))
                self.assertIn("through-slot", record["mount_notes"])
                self.assertGreater(record["min_ligament_mm"], 4)
                self.assertIn("not verified", record["hypothesis"])

    def test_circular_production_meshes_remain_manifold_and_outward(self):
        for diameter, sw, sh, sy, thickness in ((76, 20, 5.5, 22, 3.2), (32, 7, 3, 8, 2.8)):
            for scale in (.8, 1.0, 1.2):
                vertices, faces = _ornament_mesh(diameter * scale, diameter * scale,
                    thickness, sw * scale, sh * scale, corner_radius=7 * scale,
                    slot_radius=scale, slot_y=sy * scale, circular=True)
                edges = collections.Counter()
                for face in faces:
                    a, b, c = face
                    edges.update(tuple(sorted(edge)) for edge in ((a, b), (b, c), (c, a)))
                    points = [vertices[i] for i in face]
                    normal = _normal(*points)
                    if all(abs(p[2]) < 1e-9 for p in points):
                        self.assertLess(normal[2], 0)
                    if all(abs(p[2] - thickness) < 1e-9 for p in points):
                        self.assertGreater(normal[2], 0)
                        # A ray at the mounting-slot centre must miss every cap triangle.
                        a, b, c = points
                        x, y = 0, sy * scale
                        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
                        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
                        self.assertFalse(u >= 0 and v >= 0 and u + v <= 1)
                self.assertTrue(all(count == 2 for count in edges.values()))
                self.assertEqual(len(vertices) - len(edges) + len(faces), 0)
                self.assertAlmostEqual(max(v[0] for v in vertices) - min(v[0] for v in vertices), diameter * scale)
                self.assertAlmostEqual(max(v[1] for v in vertices) - min(v[1] for v in vertices), diameter * scale)

    def test_measurement_scaling(self):
        with tempfile.TemporaryDirectory() as directory:
            records = generate_rigid({"upper_arm": 297, "neck": 363}, Path(directory))
            self.assertEqual(records[0]["bbox_mm"], [83.6, 83.6, 3.2])
            self.assertEqual(records[2]["bbox_mm"], [35.2, 35.2, 2.8])

    def test_invalid_dimensions_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True, "560"):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    generate_rigid({"upper_arm": value}, Path(directory))
        with self.assertRaises(ValueError):
            _ornament_mesh(20, 20, 1, 10, 5, corner_radius=4)


if __name__ == "__main__":
    unittest.main()
