import json,tempfile,unittest,hashlib
from pathlib import Path
from clothforge.pipeline import build
from clothforge.contracts import analyze_images
ROOT=Path(__file__).resolve().parents[1]
class PipelineTest(unittest.TestCase):
 def test_all_outputs(self):
  spec=json.loads((ROOT/'examples/neutral.analysis.json').read_text())
  for profile in json.loads((ROOT/'examples/profiles.json').read_text()):
   with tempfile.TemporaryDirectory() as d:
    m=build(spec,profile,d)
    self.assertGreater(m['pattern_count'],5);self.assertEqual(m['rigid_count'],3)
    for name,sha in m['files_sha256'].items():self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),sha)
    self.assertTrue((Path(d)/'patterns_1to1.pdf').read_bytes().startswith(b'%PDF'))
    self.assertTrue((Path(d)/'instructions_zh.pdf').read_bytes().startswith(b'%PDF'))
 def test_fixture_not_vision(self):
  with self.assertRaisesRegex(ValueError,'not image analysis'):
   analyze_images([ROOT/'examples/neutral_fixture.svg'],'replay',ROOT/'examples/neutral.analysis.json')
 def test_independent_waist(self):
  from clothforge.patterns import generate_patterns
  p=json.loads((ROOT/'examples/profiles.json').read_text())[0]
  a=generate_patterns(p);p['waist']+=80;b=generate_patterns(p)
  pa={x['id']:x for x in a};pb={x['id']:x for x in b}
  self.assertNotEqual(pa['torso_front']['outline'],pb['torso_front']['outline'])
  self.assertEqual(pa['forearm_sleeve']['outline'],pb['forearm_sleeve']['outline'])
 def test_rebuild_refuses_existing_outputs(self):
  spec=json.loads((ROOT/'examples/neutral.analysis.json').read_text());profile=json.loads((ROOT/'examples/profiles.json').read_text())[0]
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'unrelated.txt').write_text('preserve')
   with self.assertRaises(FileExistsError):build(spec,profile,d)
   self.assertEqual((Path(d)/'unrelated.txt').read_text(),'preserve')
 def test_override_requires_review(self):
  from clothforge.contracts import apply_override
  spec=apply_override(json.loads((ROOT/'examples/neutral.analysis.json').read_text()),'torso','material','stretch fabric');profile=json.loads((ROOT/'examples/profiles.json').read_text())[0]
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Engineering review'):build(spec,profile,d)
   self.assertEqual(list(Path(d).iterdir()),[])
 def test_purchase_excludes_geometry(self):
  import csv
  spec=json.loads((ROOT/'examples/neutral.analysis.json').read_text());profile=json.loads((ROOT/'examples/profiles.json').read_text())[0]
  next(c for c in spec['components'] if c['id']=='torso')['status']='purchase'
  with tempfile.TemporaryDirectory() as d:
   build(spec,profile,d)
   self.assertFalse((Path(d)/'torso_front.svg').exists())
   rows=list(csv.DictReader((Path(d)/'bom.csv').read_text().splitlines()));row=next(r for r in rows if r['component_id']=='torso');self.assertEqual(row['cut_quantity'],'0');self.assertEqual(row['files'],'')
