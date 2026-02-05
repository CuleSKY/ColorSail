import json
import os
import unittest

from tools.normalize_maplist_from_html import MAP_RE


class MaplistNormalizedContractTests(unittest.TestCase):
    def setUp(self):
        self.sample_path = os.path.join(
            os.path.dirname(__file__),
            "maplist_normalized.json",
        )

    def test_sample_is_valid_and_matches_schema(self):
        with open(self.sample_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        required_keys = {
            "map",
            "name_zh",
            "difficulty",
            "tags",
            "cooldown",
            "achievement",
            "workshop",
        }
        for entry in data:
            self.assertIsInstance(entry, dict)
            self.assertTrue(required_keys.issubset(entry.keys()))
            self.assertIsInstance(entry["map"], str)
            self.assertRegex(entry["map"], MAP_RE)
            self.assertIsInstance(entry["name_zh"], str)
            self.assertIsInstance(entry["difficulty"], str)
            self.assertIsInstance(entry["tags"], list)
            self.assertTrue(all(isinstance(tag, str) for tag in entry["tags"]))

            cooldown = entry["cooldown"]
            self.assertIsInstance(cooldown, dict)
            self.assertIsInstance(cooldown.get("duration_raw", ""), str)
            deadline = cooldown.get("deadline")
            self.assertTrue(deadline is None or isinstance(deadline, str))

            workshop = entry["workshop"]
            self.assertIsInstance(workshop, dict)
            self.assertIsInstance(workshop.get("id", ""), str)
            self.assertIsInstance(workshop.get("url", ""), str)


if __name__ == "__main__":
    unittest.main()
