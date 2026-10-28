import json
import tempfile
import unittest
from pathlib import Path

from utils.config_loader import ConfigError, load_config


class ConfigLoaderTests(unittest.TestCase):
    def load_payload(self, payload: object):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_config(path)

    def test_empty_rules_and_defaults_are_valid_for_template(self):
        config = self.load_payload({"rules": []})
        self.assertEqual(config.rules, ())
        self.assertTrue(config.ignore_outgoing)
        self.assertEqual(config.rate_limit.delay_seconds, 1.0)

    def test_loads_route_and_normalizes_filter_values(self):
        config = self.load_payload(
            {
                "rules": [
                    {
                        "sources": [-100123, "@source_name"],
                        "destinations": ["destination_name"],
                        "filters": {
                            "keywords": [" Gold ", ""],
                            "keyword_mode": "all",
                            "media_types": ["PHOTO", "media"],
                            "ignore_bots": True,
                        },
                    }
                ]
            }
        )
        rule = config.rules[0]
        self.assertEqual(rule.name, "rule-1")
        self.assertEqual(rule.sources, (-100123, "source_name"))
        self.assertEqual(rule.filters.keywords, ("Gold",))
        self.assertEqual(rule.filters.media_types, ("photo", "media"))
        self.assertTrue(rule.filters.ignore_bots)

    def test_rejects_unsupported_media_filter(self):
        with self.assertRaises(ConfigError):
            self.load_payload(
                {
                    "rules": [
                        {"sources": [1], "destinations": [2], "filters": {"media_types": ["sticker"]}}
                    ]
                }
            )

    def test_rejects_empty_source_list(self):
        with self.assertRaises(ConfigError):
            self.load_payload({"rules": [{"sources": [], "destinations": [2]}]})


if __name__ == "__main__":
    unittest.main()
