#!/usr/bin/env python3
"""Bounded regression checks; synthetic photos are removed after the test run."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageOps
import render as r


class PostersTest(unittest.TestCase):
    def setUp(self):
        root=Path.cwd()/'work'
        root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='memory-fragment-test-',dir=root)
        self.folder=Path(self.tmp.name).absolute()
        yy,xx=np.indices((640,960))
        pixels=np.stack((xx%256,yy%256,(xx+yy)%256),axis=2).astype(np.uint8)
        self.photo=self.folder/'中文照片.png'
        Image.fromarray(pixels).save(self.photo)
        self.item={'path':str(self.photo),'name':'中文/测试','crop_box':[0,0,960,640],'fragment_center':[.01,.99]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_layouts_and_masks(self):
        for count in (1,2,5,10):
            for style in r.STYLES:
                with self.subTest(count=count,style=style):
                    alpha,info=r.masks(count,style)
                    self.assertEqual(len(info['cells']),count)
                    self.assertEqual(len(alpha),count+1)
                    self.assertTrue(r.connected_cells(info['cells']))
                    self.assertLessEqual(info['assembly_size'][0],r.W*.7)
                    self.assertLessEqual(info['assembly_size'][1],r.H*.6)
                    self.assertTrue(np.all(alpha.astype(np.uint32).sum(axis=0)==255))
                    if count>1:
                        # Real shared curved edges have mixed piece coverage.
                        self.assertTrue(np.any(((alpha[:-1]>0)&(alpha[:-1]<255)).sum(axis=0)>1))
                    if count==10:
                        self.assertEqual(info['cells'][-2:],[(2,1),(2,2)])

    def test_rotated_portrait_and_edge_focus_render(self):
        oriented=self.folder/'旋转照片.jpg'
        with Image.open(self.photo) as image:
            exif=Image.Exif(); exif[274]=6
            image.save(oriented,exif=exif)
        with r.open_photo(oriented) as image:
            self.assertEqual(image.size,(640,960))
            with Image.open(oriented) as raw:
                self.assertTrue(np.array_equal(np.asarray(image),np.asarray(ImageOps.exif_transpose(raw).convert('RGB'))))
        other={'path':str(oriented),'name':'竖幅','crop_box':[0,300,640,300+640/1.5],'fragment_center':[.99,.01]}
        outcome=r.render({'photos':[self.item,other]},self.folder/'outputs')
        self.assertEqual(outcome['image_count'],6)
        result=Path(outcome['output'])
        self.assertEqual(len(list(result.rglob('*.png'))),6)
        report=json.loads((result/'制作检查.json').read_text())
        self.assertEqual(report['status'],'complete')
        for version in report['versions']:
            for photo in version['photos']:
                self.assertNotEqual(photo['edge_adjustment'],[0,0])
                self.assertNotIn('/',photo['file'])
                sx,sy,x1,y1=photo['source_box_in_lower_half']
                tx,ty,tx1,ty1=photo['top_box']
                self.assertEqual((x1-sx,y1-sy),(tx1-tx,ty1-ty))
                self.assertEqual(photo['hole_box'],[sx,sy+r.HALF,x1,y1+r.HALF])

    def test_invalid_inputs_leave_no_output(self):
        invalid=[
            {'photos':[]},
            {'photos':[dict(self.item,path=str(self.folder/'missing.png'))]},
            {'photos':[dict(self.item,crop_box=[0,0,961,640])]},
            {'photos':[dict(self.item,crop_box=[0,0,960,500])]},
            {'photos':[dict(self.item,fragment_center=[float('nan'),.5])]},
            {'photos':[self.item],'styles':['puzzle','puzzle']},
            {'photos':[self.item],'styles':[]},
        ]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(r.PosterError):
                r.render(config,self.folder/'should-not-exist')
        self.assertFalse((self.folder/'should-not-exist').exists())
        self.assertFalse(list(self.folder.glob('.*制作中*')))

    def test_duplicate_output_preserves_previous(self):
        target=self.folder/'output'; target.mkdir()
        (target/'prior.txt').write_text('keep')
        for suffix in ('-v2','-v3'):
            stage=self.folder/'stage'; stage.mkdir()
            (stage/'new.txt').write_text(suffix)
            actual=r.publish(stage,target)
            self.assertEqual(actual.name,'output'+suffix)
            self.assertEqual((actual/'new.txt').read_text(),suffix)
        self.assertEqual((target/'prior.txt').read_text(),'keep')

    def test_failed_validation_is_not_published(self):
        target=self.folder/'failed'
        with patch.object(r,'render_style',side_effect=r.PosterError('injected check failure')):
            with self.assertRaises(r.PosterError):
                r.render({'photos':[self.item],'styles':['puzzle']},target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.folder.glob('.failed-制作中-*')))


if __name__=='__main__':
    unittest.main(verbosity=2)
