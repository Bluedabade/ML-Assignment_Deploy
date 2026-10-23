"""Deterministic educational guidance, using counts only and no real model/media."""
import ast
import copy
import csv
import io
from pathlib import Path
import unittest
from urllib.parse import urlparse

from skn_app.config import CLASSES, MAPPING, PROFILES
from skn_app.media import csv_bytes
from skn_app.skincare_guidance import (SKINCARE_GUIDANCE, NUTRIENTS, NUTRITION_REFERENCES,
    MEDICAL_DISCLAIMER, NUTRITION_DISCLAIMER, RETINOID_CAUTION, detected_classes, guidance_topics)


class GuidanceTests(unittest.TestCase):
    def test_acne_only(self):
        self.assertEqual(detected_classes({'acne': 1}), ('acne',))

    def test_wrinkle_only(self):
        self.assertEqual(detected_classes({'wrinkle': 2}), ('wrinkle',))

    def test_dark_spot_only(self):
        self.assertEqual(detected_classes({'dark_spot': 3}), ('dark_spot',))

    def test_enlarged_pore_only(self):
        self.assertEqual(detected_classes({'enlarged_pore': 4}), ('enlarged_pore',))

    def test_multiple_classes_canonical_order_once_and_no_mutation(self):
        counts = {'enlarged_pore': 50, 'acne': 10, 'wrinkle': 5}
        before = copy.deepcopy(counts)
        self.assertEqual(guidance_topics(counts), ('acne', 'wrinkle', 'enlarged_pore'))
        self.assertEqual(counts, before)

    def test_no_detection_and_missing_counts(self):
        for counts in ({}, dict.fromkeys(CLASSES, 0), None, [], 'acne'):
            self.assertEqual(detected_classes(counts), ())

    def test_unknown_class_is_ignored_never_remapped(self):
        self.assertEqual(detected_classes({'normal_skin': 1, 'blackhead': 3, 0: 1, '0': 1}), ())
        self.assertEqual(detected_classes({'unknown': 8, 'dark_spot': 1}), ('dark_spot',))

    def test_invalid_counts_are_not_detections(self):
        for value in (-1, 0, False, True, '1', None, float('nan'), float('inf')):
            self.assertEqual(detected_classes({'acne': value}), ())

    def test_original_class_ids_and_profiles_unchanged(self):
        self.assertEqual(CLASSES, ('acne', 'wrinkle', 'dark_spot', 'enlarged_pore'))
        self.assertEqual(tuple(SKINCARE_GUIDANCE), CLASSES)
        self.assertEqual(MAPPING, {'Acne':'acne', 'Wrinkles':'wrinkle', 'Dark Spots':'dark_spot', 'Open Pores':'enlarged_pore'})
        self.assertEqual(PROFILES['Balanced'], dict.fromkeys(CLASSES, .25))
        self.assertEqual(tuple(PROFILES['Precision-focused'].values()), (.25, .45, .275, .30))

    def test_csv_schema_and_bytes_unchanged_by_guidance(self):
        row = dict(timestamp_seconds=0., class_name='acne', confidence=.8, x1=1, y1=2, x2=3, y2=4)
        before = csv_bytes([row]);guidance_topics({'acne': 1})
        self.assertEqual(csv_bytes([row]), before)
        self.assertEqual(next(csv.reader(io.StringIO(before.decode('utf-8-sig')))),
                         ['timestamp_seconds','class_name','confidence','x1','y1','x2','y2'])

    def test_complete_structure_and_traceable_https_sources(self):
        required = {'title_th','description','daily_care','skincare_ingredients','nutrition',
                    'exercise_lifestyle','cautions','when_to_seek_professional_care','references'}
        for entry in SKINCARE_GUIDANCE.values():
            self.assertEqual(set(entry), required)
            self.assertTrue(all(entry.values()))
            for title, url in entry['references']:
                self.assertTrue(title);self.assertEqual(urlparse(url).scheme, 'https')
                self.assertEqual(urlparse(url).hostname, 'www.aad.org')
        self.assertEqual(len(NUTRIENTS), 5)
        for _, url in NUTRITION_REFERENCES:self.assertEqual(urlparse(url).scheme, 'https')

    def test_disclaimers_and_pregnancy_cautions(self):
        self.assertIn('ไม่ใช่การวินิจฉัยโรค', MEDICAL_DISCLAIMER)
        self.assertIn('ไม่สามารถระบุได้ว่าร่างกายขาด', NUTRITION_DISCLAIMER)
        self.assertIn('ไม่ใช่ผลการประเมินภาวะโภชนาการ', NUTRITION_DISCLAIMER)
        for name in ('wrinkle', 'enlarged_pore'):
            self.assertIn(RETINOID_CAUTION, SKINCARE_GUIDANCE[name]['cautions'])
        self.assertIn('วางแผนตั้งครรภ์', RETINOID_CAUTION)

    def test_counts_never_change_advice_into_severity_or_dosage(self):
        self.assertEqual(guidance_topics({'acne': 1}), guidance_topics({'acne': 10000}))
        text = repr(SKINCARE_GUIDANCE)
        for claim in ('คุณขาดวิตามิน', 'คุณขาดสารอาหาร', 'รับประทานยา', 'รับประทานวิตามินวันละ'):
            self.assertNotIn(claim, text)

    def test_static_module_has_no_model_network_or_media_imports(self):
        path = Path(__file__).resolve().parents[1]/'skn_app/skincare_guidance.py'
        tree = ast.parse(path.read_text(encoding='utf8'))
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(modules, {'collections.abc', 'numbers', 'config'})
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(imports, {'math'})

    def test_showcase_is_explicit_and_never_fabricates_counts(self):
        counts = {};before = copy.deepcopy(counts)
        self.assertEqual(guidance_topics(counts, showcase=True), CLASSES)
        self.assertEqual(guidance_topics(counts), ())
        self.assertEqual(counts, before)


if __name__ == '__main__':unittest.main()
