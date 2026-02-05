import json
import os
import tempfile
import unittest

os.environ.setdefault("APP_SECRET_KEY", "test-secret")

import app as app_module


class ExgMaplistLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_static = app_module.app.static_folder
        cls.temp_dir = tempfile.mkdtemp()
        cls.data_dir = os.path.join(cls.temp_dir, "data")
        os.makedirs(cls.data_dir, exist_ok=True)
        sample_path = os.path.join(os.path.dirname(__file__), "maplist_normalized.json")
        with open(sample_path, "r", encoding="utf-8") as handle:
            cls.sample_data = json.load(handle)
        cls.sample_entry = cls.sample_data[0]
        maplist_path = os.path.join(cls.data_dir, "maplist_normalized.json")
        with open(maplist_path, "w", encoding="utf-8") as handle:
            json.dump(cls.sample_data, handle, ensure_ascii=False, indent=2)
        app_module.app.static_folder = cls.temp_dir

    @classmethod
    def tearDownClass(cls):
        app_module.app.static_folder = cls.original_static

    def test_loader_resolves_map_metadata(self):
        app_module.refresh_local_caches(force=True)
        map_key = self.sample_entry["map"]
        entry = app_module.get_exg_maplist_entry(map_key)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name_zh"], self.sample_entry["name_zh"])
        self.assertEqual(entry["workshop"], self.sample_entry["workshop"])
        self.assertEqual(entry["cooldown"], self.sample_entry["cooldown"])


if __name__ == "__main__":
    unittest.main()
