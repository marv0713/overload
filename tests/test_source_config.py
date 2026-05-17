import json
import tempfile
import unittest
from pathlib import Path

from youtube_to_wechat.source_config import load_source_config


class SourceConfigTests(unittest.TestCase):
    def test_loads_youtube_channel_sources_with_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.json"
            path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "type": "youtube_channel",
                                "name": "Unrivaled Investing",
                                "url": "https://www.youtube.com/@unrivaled",
                            }
                        ]
                    }
                )
            )

            config = load_source_config(path)

        self.assertEqual(len(config.sources), 1)
        source = config.sources[0]
        self.assertEqual(source.type, "youtube_channel")
        self.assertEqual(source.name, "Unrivaled Investing")
        self.assertEqual(source.min_duration_seconds, 600)
        self.assertEqual(source.writer_profile, "alchemy-research")
        self.assertEqual(source.compare_evaluation, "none")
        self.assertEqual(source.series, "炼金投研")
        self.assertEqual(source.priority, 100)
        self.assertTrue(source.enabled)

    def test_loads_series_priority_and_writer_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.json"
            path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "type": "youtube_channel",
                                "name": "Motley Fool",
                                "url": "https://www.youtube.com/@MotleyFool/videos",
                                "series": "炼金投研",
                                "priority": 20,
                                "writer_profile": "market-commentary",
                            }
                        ]
                    }
                )
            )

            config = load_source_config(path)

        source = config.sources[0]
        self.assertEqual(source.series, "炼金投研")
        self.assertEqual(source.priority, 20)
        self.assertEqual(source.writer_profile, "market-commentary")


if __name__ == "__main__":
    unittest.main()
