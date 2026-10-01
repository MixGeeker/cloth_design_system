import tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader
from clothforge.export import svg_pattern,pattern_pdf
class ExportTest(unittest.TestCase):
 def test_real_units_and_page_box(self):
  p={'id':'test','quantity':1,'outline':[[0,0],[300,0],[300,500],[0,500]],'stitchline':[[10,10],[290,10],[290,490],[10,490]],'grainline':[[150,100],[150,400]],'seams':{}}
  with tempfile.TemporaryDirectory() as d:
   svg_pattern(p,Path(d)/'p.svg');pattern_pdf([p],Path(d)/'p.pdf','A')
   root=ET.parse(Path(d)/'p.svg').getroot();self.assertEqual(root.attrib['width'],'340.0000mm');self.assertEqual(root.attrib['height'],'585.0000mm')
   page=PdfReader(Path(d)/'p.pdf').pages[0];self.assertAlmostEqual(float(page.mediabox.width)*25.4/72,340,places=3);self.assertAlmostEqual(float(page.mediabox.height)*25.4/72,585,places=3)
   squares=[r for r in root.findall('{http://www.w3.org/2000/svg}rect') if r.attrib.get('width')=='20'];self.assertEqual(len(squares),1)
