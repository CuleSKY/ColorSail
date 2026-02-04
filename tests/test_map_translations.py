import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("APP_SECRET_KEY", "test-secret")

import app as app_module


class MapTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.trans_file = os.path.join(cls.temp_dir, "map_translations.json")
        app_module.TRANS_FILE = cls.trans_file

    def setUp(self):
        app_module.MAP_TRANS_CACHE = {}
        app_module.MAP_TRANS_NORMALIZED = {}
        app_module.MAP_TRANS_DIRTY = False
        app_module.MAP_TRANS_LAST_WRITE = 0
        if os.path.exists(self.trans_file):
            os.remove(self.trans_file)

    def test_ensure_creates_entry(self):
        entry = app_module.ensure_map_translation_entry("ze_downstairs")
        self.assertEqual(entry, {"zh_cn": "", "zh_tw": ""})
        self.assertIn("ze_downstairs", app_module.MAP_TRANS_CACHE)
        self.assertTrue(app_module.MAP_TRANS_DIRTY)

    def test_update_fills_zh_cn_and_tw(self):
        app_module.ensure_map_translation_entry("ze_downstairs")
        updated = app_module.update_map_translation_entry("ze_downstairs", "萌新爱下楼")
        self.assertTrue(updated)
        entry = app_module.MAP_TRANS_CACHE["ze_downstairs"]
        self.assertEqual(entry["zh_cn"], "萌新爱下楼")
        self.assertTrue(entry["zh_tw"])

    def test_update_does_not_overwrite_existing(self):
        app_module.MAP_TRANS_CACHE = {
            "ze_downstairs": {"zh_cn": "手工中文", "zh_tw": "手工繁體"}
        }
        updated = app_module.update_map_translation_entry("ze_downstairs", "别的中文")
        self.assertFalse(updated)
        entry = app_module.MAP_TRANS_CACHE["ze_downstairs"]
        self.assertEqual(entry["zh_cn"], "手工中文")
        self.assertEqual(entry["zh_tw"], "手工繁體")

    def test_atomic_flush_writes_json(self):
        app_module.MAP_TRANS_CACHE = {
            "ze_test": {"zh_cn": "", "zh_tw": ""}
        }
        app_module.MAP_TRANS_DIRTY = True
        original_replace = app_module.os.replace
        called = {"value": False}

        def spy_replace(src, dst):
            called["value"] = True
            return original_replace(src, dst)

        with mock.patch.object(app_module.os, "replace", side_effect=spy_replace):
            wrote = app_module.maybe_flush_map_translations(force=True)

        self.assertTrue(wrote)
        self.assertTrue(called["value"])
        with open(self.trans_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertIn("ze_test", data)


if __name__ == "__main__":
    unittest.main()
