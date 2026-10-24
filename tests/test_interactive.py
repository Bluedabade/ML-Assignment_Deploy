"""Synthetic candidates only. Model/SDK weights and external network are forbidden."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from skn_app.config import CLASSES, PROFILES
from skn_app.runtime import ModelRuntime
from skn_app.media import process_image
from skn_app.skincare_guidance import guidance_topics
from skn_app.presentation import (CUSTOM,CACHE_SLOT,filter_detections,summarize_counts,
    render_annotated,build_image_result,display_thresholds,make_image_cache,get_image_cache,candidate_cache_key)


def rows():
    return [dict(class_name=name,confidence=score,x1=10+i*20,y1=25,x2=25+i*20,y2=45)
            for i,(name,score) in enumerate([('acne',.9),('wrinkle',.3),('enlarged_pore',.15),('enlarged_pore',.35)])]


def data():
    output=io.BytesIO();Image.new('RGB',(120,80),'white').save(output,format='PNG');return output.getvalue()


class InteractiveTests(unittest.TestCase):
    def test_threshold_010(self):self.assertEqual(len(filter_detections(rows(),.1)),4)
    def test_threshold_025(self):self.assertEqual(len(filter_detections(rows(),.25)),3)
    def test_threshold_030(self):self.assertEqual(len(filter_detections(rows(),.3)),3)
    def test_threshold_090(self):self.assertEqual(len(filter_detections(rows(),.9)),1)

    def test_empty_and_multiple_classes(self):
        self.assertEqual(summarize_counts([]),dict.fromkeys(CLASSES,0))
        self.assertEqual(summarize_counts(rows())['enlarged_pore'],2)

    def test_pore015_and035_are_real_scores_not_changed(self):
        source=rows();before=copy.deepcopy(source)
        self.assertEqual([r['confidence'] for r in filter_detections(source,.25) if r['class_name']=='enlarged_pore'],[.35])
        self.assertEqual(source,before)

    def test_profiles_are_per_class_not_global(self):
        self.assertEqual(display_thresholds('Balanced'),PROFILES['Balanced'])
        self.assertEqual(display_thresholds('Precision-focused'),PROFILES['Precision-focused'])
        self.assertEqual(len(filter_detections(rows(),display_thresholds('Precision-focused'))),2)
        self.assertEqual(display_thresholds(CUSTOM,.1),dict.fromkeys(CLASSES,.1))

    def test_image_csv_counts_and_guidance_consistency(self):
        image=Image.new('RGB',(120,80),'white')
        for threshold in (.1,.25,.3,.9):
            result=build_image_result(image,rows(),display_thresholds(CUSTOM,threshold))
            exported=list(csv.DictReader(io.StringIO(result['csv_bytes'].decode('utf-8-sig'))))
            self.assertEqual(len(exported),sum(result['counts'].values()))
            self.assertEqual([r['class_name'] for r in exported],[r['class_name'] for r in result['predictions']])
            self.assertEqual(set(guidance_topics(result['counts'])),{r['class_name'] for r in result['predictions']})
            self.assertEqual(Image.open(io.BytesIO(result['image_bytes'])).size,image.size)

    def test_opacity_compositing_label_modes_and_original_preserved(self):
        image=Image.new('RGB',(120,80),'white');before=image.tobytes();source=rows();prior=copy.deepcopy(source)
        low=render_annotated(image,source,.1,'none');high=render_annotated(image,source,1.,'none')
        self.assertNotEqual(low.getpixel((50,35)),high.getpixel((50,35)))
        outputs=[render_annotated(image,source,.65,mode).tobytes() for mode in ('class_percent','percent','none')]
        self.assertEqual(len(set(outputs)),3)
        self.assertEqual(image.tobytes(),before);self.assertEqual(source,prior)

    def test_removed_boxes_do_not_leave_ghost_pixels(self):
        image=Image.new('RGB',(120,80),'white')
        low=build_image_result(image,rows(),.1,label_mode='none')
        high=build_image_result(image,rows(),.25,label_mode='none')
        self.assertNotEqual(Image.open(io.BytesIO(low['image_bytes'])).getpixel((50,35)),(255,255,255))
        self.assertEqual(Image.open(io.BytesIO(high['image_bytes'])).getpixel((50,35)),(255,255,255))

    def test_cache_identity_ignores_display_settings_and_binds_kind_model(self):
        a=candidate_cache_key(data());self.assertEqual(a,candidate_cache_key(data()))
        self.assertNotEqual(a,candidate_cache_key(data(),'video'))
        self.assertNotEqual(a,candidate_cache_key(data()+b'x'))
        with patch.dict('skn_app.presentation.INFERENCE_IDENTITY',{'weights_sha256':'different'}):
            self.assertNotEqual(a,candidate_cache_key(data()))

    def test_file_change_invalidates_cache(self):
        cache=make_image_cache(data(),{'candidates':rows()},100)
        state={CACHE_SLOT:cache}
        self.assertIsNone(get_image_cache(state,candidate_cache_key(data()+b'x'),101))
        self.assertNotIn(CACHE_SLOT,state)

    def test_ttl_and_session_isolation_and_reset(self):
        one={CACHE_SLOT:make_image_cache(data(),{'candidates':rows()},100)}
        two={CACHE_SLOT:make_image_cache(data(),{'candidates':[]},100)}
        self.assertIsNotNone(get_image_cache(one,now=699.9))
        self.assertIsNone(get_image_cache(one,now=700))
        self.assertEqual(len(get_image_cache(two,now=101)['candidates']),0)
        two.pop(CACHE_SLOT);self.assertIsNone(get_image_cache(two,now=101))

    def test_cache_copies_candidates_and_drops_nonessential_metadata(self):
        source=dict(candidates=rows(),api_key='dummy-unused',image_bytes=b'old-render',csv_bytes=b'old-csv')
        one=make_image_cache(data(),source,100);two=make_image_cache(data(),source,100)
        one['candidates'][0]['confidence']=.1
        self.assertEqual(two['candidates'][0]['confidence'],.9)
        self.assertEqual(source['candidates'][0]['confidence'],.9)
        self.assertNotIn('api_key',one['metadata']);self.assertNotIn('image_bytes',one['metadata'])
        self.assertNotIn('csv_bytes',one['metadata'])

    def test_cloud_adapter_transports_candidates_with_one_call(self):
        from skn_app.cloud_adapter import CloudAdapter
        class Runtime:
            model_loads=0;load_seconds=.0;inference_calls=0
            def load(self):pass
            def predict_candidates(self,image):self.inference_calls+=1;return rows(),.01
        adapter=CloudAdapter(lambda name:None);adapter.runtime=Runtime()
        with patch('skn_app.media.guard_memory'):result=adapter.process_media(data(),'image','Balanced')
        self.assertEqual(len(result['candidates']),4)
        self.assertEqual(result['counts']['enlarged_pore'],1)
        self.assertEqual(adapter.runtime.inference_calls,1)
        self.assertFalse(adapter.lock.locked())

    def test_local_adapter_preserves_candidate_json(self):
        from skn_app.local_adapter import LocalAdapter
        adapter=LocalAdapter()
        def write(line):
            request=json.loads(line);folder=Path(request['folder'])
            (folder/'annotated.png').write_bytes(data());(folder/'detections.csv').write_bytes(b'class_name\n')
            adapter.messages.put(dict(event='result',job_id=request['job_id'],result=dict(candidates=rows(),counts={})))
        process=types.SimpleNamespace(stdin=types.SimpleNamespace(write=write,flush=lambda:None))
        with patch.object(adapter,'_start',side_effect=lambda:setattr(adapter,'process',process)):
            result=adapter.process_media(data(),'image','Balanced')
        adapter.process=None
        self.assertEqual(result['candidates'],rows())

    def test_inference_once_then_all_controls_do_not_call_it(self):
        runtime=ModelRuntime('cloud',lambda:(_ for _ in ()).throw(AssertionError('NO_AUTH')))
        calls=[]
        class Model:
            class_names=['Acne','Wrinkles','Open Pores']
            def __call__(self,image,**settings):
                calls.append(settings)
                return [types.SimpleNamespace(class_id=np.array([0,1,2,2]),confidence=np.array([.9,.3,.15,.35]),
                                              xyxy=np.array([[r[k] for k in ('x1','y1','x2','y2')] for r in rows()]))]
        runtime.model=Model()
        try:
            with patch('skn_app.media.guard_memory'):
                initial=process_image(data(),runtime,'Balanced')
            self.assertEqual(len(initial['candidates']),4);self.assertEqual(len(initial['predictions']),3)
            cache=make_image_cache(data(),initial,100)
            for profile in ('Balanced','Precision-focused',CUSTOM):
                for threshold in (.1,.25,.3,.9):
                    for opacity in (.1,.65,1.):
                        for labels in ('class_percent','percent','none'):
                            build_image_result(Image.open(io.BytesIO(cache['original_bytes'])),cache['candidates'],display_thresholds(profile,threshold),opacity,labels)
            self.assertEqual(len(calls),1);self.assertEqual(runtime.inference_calls,1);self.assertEqual(runtime.model_loads,0)
        finally:runtime.close()

    def test_worker_protocol_transports_low_confidence_candidates(self):
        from skn_app import worker
        class Runtime:
            model_loads=0;load_seconds=0.;inference_calls=0
            def load(self):pass
            def predict_candidates(self,image):self.inference_calls+=1;return rows(),.01
            def close(self):pass
        with tempfile.TemporaryDirectory(prefix='skn-job-') as name:
            folder=Path(name).resolve();(folder/'upload.bin').write_bytes(data())
            request=dict(folder=str(folder),kind='image',profile='Balanced',job_id='0'*32)
            output=io.StringIO()
            with patch.object(worker,'ModelRuntime',return_value=Runtime()),patch('sys.stdin',io.StringIO(json.dumps(request)+'\n')),patch('sys.stdout',output),patch('skn_app.media.guard_memory'):
                worker.main()
            message=json.loads(output.getvalue())
            self.assertEqual(message['event'],'result');self.assertEqual(len(message['result']['candidates']),4)
            self.assertTrue((folder/'annotated.png').is_file())


if __name__=='__main__':unittest.main()


class PreviewUXTests(unittest.TestCase):
    def test_portrait_contained_without_mutation(self):
        from skn_app.presentation import preview_thumbnail
        original=Image.new('RGB',(600,1800),'white')
        before=original.tobytes();preview=preview_thumbnail(original)
        self.assertEqual(preview.size,(160,480));self.assertEqual(original.size,(600,1800))
        self.assertEqual(original.tobytes(),before)

    def test_landscape_contained(self):
        from skn_app.presentation import preview_thumbnail
        self.assertEqual(preview_thumbnail(Image.new('RGB',(2400,1200))).size,(960,480))

    def test_small_image_not_upscaled(self):
        from skn_app.presentation import preview_thumbnail
        self.assertEqual(preview_thumbnail(Image.new('RGB',(80,60))).size,(80,60))

    def test_export_keeps_original_dimensions(self):
        from skn_app.presentation import preview_thumbnail
        original=Image.new('RGB',(600,1800));preview_thumbnail(original)
        view=build_image_result(original,[],display_thresholds('Balanced'))
        self.assertEqual(Image.open(io.BytesIO(view['image_bytes'])).size,original.size)

    def test_preview_invalid_size(self):
        from skn_app.presentation import preview_thumbnail
        with self.assertRaises(ValueError):preview_thumbnail(Image.new('RGB',(20,20)),(0,40))
