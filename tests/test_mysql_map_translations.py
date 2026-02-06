import os
import unittest

os.environ.setdefault("APP_SECRET_KEY", "test-secret")

import app as app_module


class MySQLMapTranslationTests(unittest.TestCase):
    def test_normalize_map_name_workshop(self):
        result = app_module.normalize_map_name("workshop/12345/ze_map.bsp")
        self.assertEqual(result, "ze_map")

    def test_resolve_map_translation_falls_back_to_key(self):
        map_cn, map_tw = app_module.resolve_mysql_map_translation("ze_missing", {"name_zh_cn": "", "name_zh_tw": ""})
        self.assertEqual(map_cn, "ze_missing")
        self.assertEqual(map_tw, "ze_missing")

    def test_resolve_map_translation_tw_from_cn(self):
        map_cn, map_tw = app_module.resolve_mysql_map_translation(
            "ze_downstairs",
            {"name_zh_cn": "萌新爱下楼", "name_zh_tw": ""}
        )
        self.assertEqual(map_cn, "萌新爱下楼")
        self.assertEqual(map_tw, app_module.convert_to_tw("萌新爱下楼"))


if __name__ == "__main__":
    unittest.main()
