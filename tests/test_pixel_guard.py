"""PNG 样本保护检查不依赖 Pillow 或全局包。"""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
def png(width,height,pixels,channels=4):
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 raw=b''.join(b'\0'+pixels[y*width*channels:(y+1)*width*channels] for y in range(height))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6 if channels==4 else 2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
class PixelGuardTests(unittest.TestCase):
 def module(self):
  spec=importlib.util.spec_from_file_location('pixel_guard',ROOT/'skills/photocraft-use/scripts/pixel_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 def test_outside_change_is_allowed_but_protected_change_refuses(self):
  m=self.module();a=bytes([100,20,40,255])*6;b=bytearray(a);b[4:8]=bytes([0,0,0,255]);regions=[{'id':'left','rect':[0,0,1,2]}]
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'a.png').write_bytes(png(3,2,a));(root/'b.png').write_bytes(png(3,2,b));report=m.compare(root/'a.png',root/'b.png',regions)
   self.assertEqual(report['regions'][0]['changedPixels'],0);self.assertEqual(report['regions'][0]['beforeSha256'],report['regions'][0]['afterSha256'])
   b[0]=0;(root/'b.png').write_bytes(png(3,2,b))
   with self.assertRaisesRegex(ValueError,'protected_region_changed'):m.compare(root/'a.png',root/'b.png',regions)
 def test_regions_are_closed_unique_positive_integer_rectangles(self):
  m=self.module()
  for value in [[],[{'id':'left','rect':[0,0,0,1]}],[{'id':'left','rect':[True,0,1,1]}],[{'id':'a','rect':[0,0,1,1],'extra':1}],[{'id':'a','rect':[0,0,1,1]},{'id':'a','rect':[0,0,1,1]}]]:
   with self.assertRaisesRegex(ValueError,'protected_regions_invalid'):m.validate(value)
 def test_corrupt_png_dimension_change_and_out_of_bounds_fail_closed(self):
  m=self.module();regions=[{'id':'area','rect':[0,0,2,2]}]
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);a=root/'a.png';b=root/'b.png';a.write_bytes(png(2,2,bytes([1,2,3,255])*4));b.write_bytes(png(1,2,bytes([1,2,3,255])*2))
   with self.assertRaisesRegex(ValueError,'protected_canvas_changed'):m.compare(a,b,regions)
   b.write_bytes(a.read_bytes())
   with self.assertRaisesRegex(ValueError,'protected_region_bounds'):m.compare(a,b,[{'id':'outside','rect':[1,0,2,1]}])
   content=bytearray(a.read_bytes());content[-1]^=1;a.write_bytes(content)
   with self.assertRaisesRegex(ValueError,'protected_png_crc'):m.compare(a,b,regions)
 def test_rgb_is_compared_as_opaque_rgba(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);a=root/'a.png';b=root/'b.png';a.write_bytes(png(1,1,bytes([1,2,3]),3));b.write_bytes(png(1,1,bytes([1,2,3,255])))
   self.assertEqual(m.compare(a,b,[{'id':'p','rect':[0,0,1,1]}])['regions'][0]['changedPixels'],0)
 def test_all_png_scanline_filters_decode_known_rgba_samples(self):
  m=self.module();expected=bytes(range(10,170,10));rows={0:[list(expected[:8]),list(expected[8:])],1:[[10,20,30,40,40,40,40,40],[90,100,110,120,40,40,40,40]],2:[list(expected[:8]),[80]*8],3:[[10,20,30,40,45,50,55,60],[85,90,95,100,60,60,60,60]],4:[[10,20,30,40,40,40,40,40],[80,80,80,80,40,40,40,40]]}
  def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'image.png'
   for mode,scanlines in rows.items():
    content=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(bytes([mode])+bytes(row) for row in scanlines)))+chunk(b'IEND',b'');path.write_bytes(content)
    self.assertEqual(m.decode(path)[2],expected,mode)
 def test_workflow_requires_source_before_installing_or_writing_output(self):
  spec=importlib.util.spec_from_file_location('protected_workflow',ROOT/'skills/photocraft-use/scripts/workflow.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);plan={'document':{'width':20,'height':20},'operations':[],'protectedRegions':[{'id':'keep','rect':[0,0,10,10]}]}
   with self.assertRaisesRegex(ValueError,'protected_source_required'):m.execute(plan,root/'output',runtime_home=root/'runtime')
   self.assertFalse((root/'runtime').exists());self.assertFalse((root/'output').exists())

if __name__=='__main__':unittest.main()
