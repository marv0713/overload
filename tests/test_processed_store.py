import tempfile
import unittest
from pathlib import Path

from youtube_to_wechat.processed_store import ProcessedStore, slugify_source_name
from youtube_to_wechat.youtube_channel import ChannelVideo


class ProcessedStoreTests(unittest.TestCase):
    def test_slugifies_source_name_for_paths_and_store_keys(self):
        self.assertEqual(slugify_source_name("Unrivaled Investing"), "unrivaled-investing")
        self.assertEqual(slugify_source_name("Value Investing with Sven Carlin"), "value-investing-with-sven-carlin")

    def test_marks_video_as_processed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")

            self.assertFalse(store.is_processed("abc123"))
            store.mark_processed(
                "abc123",
                source_name="Demo Channel",
                source_slug="demo-channel",
                title="Demo Video",
                url="https://www.youtube.com/watch?v=abc123",
                output_dir="outputs/youtube/demo-channel/abc123",
                status="ok",
            )

            reloaded = ProcessedStore(Path(temp_dir) / "processed.json")
            self.assertTrue(reloaded.is_processed("abc123"))
            record = reloaded.processing_record("abc123")
            self.assertEqual(record["source_slug"], "demo-channel")
            self.assertEqual(record["output_dir"], "outputs/youtube/demo-channel/abc123")

    def test_records_latest_videos_per_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")
            self.assertFalse(store.has_source("demo-channel"))
            store.record_source_scan(
                source_name="Demo Channel",
                source_slug="demo-channel",
                videos=[
                    ChannelVideo(
                        video_id="new1",
                        title="Newest video",
                        url="https://www.youtube.com/watch?v=new1",
                        duration_seconds=900,
                    )
                ],
            )

            reloaded = ProcessedStore(Path(temp_dir) / "processed.json")
            self.assertTrue(reloaded.has_source("demo-channel"))
            source = reloaded.source_record("demo-channel")
            self.assertEqual(source["name"], "Demo Channel")
            self.assertEqual(source["latest_videos"][0]["video_id"], "new1")

    def test_allocates_series_issue_numbers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")

            self.assertEqual(store.allocate_issue("炼金投研"), "No.001")
            self.assertEqual(store.allocate_issue("炼金投研"), "No.002")

            reloaded = ProcessedStore(Path(temp_dir) / "processed.json")
            self.assertEqual(reloaded.allocate_issue("炼金投研"), "No.003")

    def test_processed_record_can_include_series_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")
            store.mark_processed(
                "abc123",
                source_name="Demo Channel",
                source_slug="demo-channel",
                title="Demo Video",
                url="https://www.youtube.com/watch?v=abc123",
                output_dir="outputs/youtube/demo-channel/abc123",
                status="ok",
                series="炼金投研",
                issue="No.001",
                writer_profile="deep-stock-analysis",
                ticker="MELI",
                cover_hook="拉美电商龙头，跌出来的机会？",
            )

            record = store.processing_record("abc123")
            self.assertEqual(record["series"], "炼金投研")
            self.assertEqual(record["issue"], "No.001")
            self.assertEqual(record["writer_profile"], "deep-stock-analysis")
            self.assertEqual(record["ticker"], "MELI")
            self.assertIn("拉美", record["cover_hook"])

    def test_returns_processed_video_ids_for_one_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")
            store.mark_processed(
                "unrivaled1",
                source_name="Unrivaled Investing",
                source_slug="unrivaled-investing",
                title="Unrivaled Video",
                url="https://www.youtube.com/watch?v=unrivaled1",
                output_dir="outputs/youtube/unrivaled-investing/unrivaled1",
                status="ok",
            )
            store.mark_processed(
                "sven1",
                source_name="Sven",
                source_slug="sven",
                title="Sven Video",
                url="https://www.youtube.com/watch?v=sven1",
                output_dir="outputs/youtube/sven/sven1",
                status="ok",
            )

            self.assertEqual(
                store.processed_video_ids_for_source("unrivaled-investing"),
                {"unrivaled1"},
            )


if __name__ == "__main__":
    unittest.main()
