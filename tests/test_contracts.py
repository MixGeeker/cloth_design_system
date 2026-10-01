import json,tempfile,unittest
from pathlib import Path
from clothforge.contracts import *

ROOT=Path(__file__).resolve().parents[1]
class ContractsTest(unittest.TestCase):
 def test_profiles(self):
  for p in json.loads((ROOT/'examples/profiles.json').read_text()):validate_profile(p)
 def test_missing_images(self):
  with self.assertRaises(ValueError):analyze_images([])
 def test_live_fail_closed(self):
  with tempfile.NamedTemporaryFile() as f:
   f.write(b'not a model input');f.flush()
   with self.assertRaisesRegex(RuntimeError,'NOT_CONFIGURED'):analyze_images([f.name])
 def test_units(self):
  p=json.loads((ROOT/'examples/profiles.json').read_text())[0];p['units']='cm'
  with self.assertRaises(ValueError):validate_profile(p)
 def test_override_invalidates(self):
  s={'components':[{'id':'x','material':'cotton'}]}; t=apply_override(s,'x','material','linen')
  self.assertEqual(s['components'][0]['material'],'cotton');self.assertTrue(t['outputs_invalidated'])
 def test_replay_exact_bytes_only(self):
  import hashlib
  spec=json.loads((ROOT/'examples/neutral.analysis.json').read_text());spec['mode']='authored_reference_replay'
  with tempfile.TemporaryDirectory() as d:
   image=Path(d)/'ref.png';image.write_bytes(b'explicit-test-image-bytes')
   spec['references'][0]['sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
   fixture=Path(d)/'analysis.json';fixture.write_text(json.dumps(spec))
   self.assertEqual(analyze_images([image],'replay',fixture)['mode'],'authored_reference_replay')
   image.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'checksum mismatch'):analyze_images([image],'replay',fixture)
 def test_provenance_integrity(self):
  spec=json.loads((ROOT/'examples/neutral.analysis.json').read_text())
  spec['components'][0]['observations'][0]['reference_id']='missing'
  with self.assertRaisesRegex(ValueError,'Unknown observation'):validate_analysis(spec)
