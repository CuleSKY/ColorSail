import os
import unittest

from tools.map_sidecar import cn_fetcher


class CnFetcherParseTests(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "exg_maplist_sample.html",
        )

    def _load_fixture(self) -> str:
        with open(self.fixture_path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_parse_maplist_entries(self):
        entries = cn_fetcher.parse_maplist(self._load_fixture())

        self.assertGreaterEqual(len(entries), 2)
        first = entries[0]
        second = entries[1]

        self.assertEqual(first.map, "ze_test_map")
        self.assertEqual(first.name_zh, "测试地图")
        self.assertEqual(first.difficulty, "困难")
        self.assertEqual(first.tags, ["冒险", "解谜"])
        self.assertEqual(first.cooldown["duration_raw"], "60")
        self.assertEqual(first.cooldown["deadline"], "2024/05/01 12:00")
        self.assertEqual(first.workshop["id"], "123456789")
        self.assertEqual(
            first.workshop["url"],
            "https://steamcommunity.com/sharedfiles/filedetails/?id=123456789",
        )

        self.assertEqual(second.map, "ze_second_map")
        self.assertEqual(second.name_zh, "第二张图")
        self.assertEqual(second.difficulty, "未标注")
        self.assertEqual(second.tags, [])
        self.assertEqual(second.cooldown["duration_raw"], "")
        self.assertIsNone(second.cooldown["deadline"])
        self.assertEqual(second.achievement, "")

        cn_fetcher.validate_entries(entries)

    def test_workshop_id_extraction(self):
        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=987654321"
        self.assertEqual(cn_fetcher.workshop_id_from_url(url), "987654321")


if __name__ == "__main__":
    unittest.main()
