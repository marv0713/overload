import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.process_sources import collect_source_candidates, process_source, process_video_url
from youtube_to_wechat.processed_store import ProcessedStore
from youtube_to_wechat.source_config import SourceConfig
from youtube_to_wechat.youtube_channel import ChannelVideo


class ProcessSourcesTests(unittest.TestCase):
    @patch("scripts.process_sources.write_article")
    @patch("scripts.process_sources.GeminiWriter")
    @patch("scripts.process_sources.load_writer_profile")
    @patch("scripts.process_sources.fetch_transcript")
    @patch("scripts.process_sources.fetch_info")
    def test_process_video_url_can_generate_article_with_source_writer_profile(
        self,
        fetch_info,
        fetch_transcript,
        load_profile,
        writer_cls,
        write_article,
    ):
        fetch_info.return_value = {"title": "Demo Video", "url": "https://www.youtube.com/watch?v=abc123"}
        fetch_transcript.return_value = "Transcript body"
        load_profile.return_value.name = "market-commentary"
        load_profile.return_value.prompt = "Market prompt"
        writer = writer_cls.return_value
        writer.write.return_value.markdown = "# Generated Article"
        writer.write.return_value.title = "Generated Article"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir, run = process_video_url(
                url="https://www.youtube.com/watch?v=abc123",
                output_base=Path(temp_dir),
                skip_audio=True,
                generate_article=True,
                writer_profile="market-commentary",
                writer_profile_dir=Path("config/writer_profiles"),
            )

        self.assertEqual(run["article_status"], "ok")
        self.assertEqual(output_dir.name, "abc123")
        load_profile.assert_called_once_with("market-commentary", Path("config/writer_profiles"))
        writer_cls.assert_called_once()
        writer.write.assert_called_once_with("Transcript body", fetch_info.return_value)
        write_article.assert_called_once()

    @patch("scripts.process_sources.fetch_channel_videos")
    def test_collect_candidates_sorts_by_source_priority_then_published_at(self, fetch_videos):
        high_priority = SourceConfig(
            type="youtube_channel",
            name="High Priority",
            url="https://www.youtube.com/@high",
            priority=10,
        )
        low_priority = SourceConfig(
            type="youtube_channel",
            name="Low Priority",
            url="https://www.youtube.com/@low",
            priority=50,
        )

        def videos_for(url, limit, no_check_certificates):
            if "high" in url:
                return [
                    ChannelVideo(
                        video_id="high-new",
                        title="High New",
                        url="https://www.youtube.com/watch?v=high-new",
                        duration_seconds=900,
                        published_at="2026-05-17",
                    ),
                    ChannelVideo(
                        video_id="high-old",
                        title="High Old",
                        url="https://www.youtube.com/watch?v=high-old",
                        duration_seconds=900,
                        published_at="2026-05-10",
                    ),
                ]
            return [
                ChannelVideo(
                    video_id="low-old",
                    title="Low Old",
                    url="https://www.youtube.com/watch?v=low-old",
                    duration_seconds=900,
                    published_at="2026-05-01",
                )
            ]

        fetch_videos.side_effect = videos_for
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")
            store.record_source_scan("High Priority", "high-priority", [])
            store.record_source_scan("Low Priority", "low-priority", [])

            candidates = collect_source_candidates(
                sources=[low_priority, high_priority],
                store=store,
                channel_limit=5,
                no_check_certificates=False,
            )

        self.assertEqual(
            [candidate.video.video_id for candidate in candidates],
            ["high-old", "high-new", "low-old"],
        )

    @patch("scripts.process_sources.process_video_url")
    @patch("scripts.process_sources.fetch_channel_videos")
    def test_process_source_uses_source_slug_output_dir_and_records_scan(self, fetch_videos, process_video):
        source = SourceConfig(
            type="youtube_channel",
            name="Demo Channel",
            url="https://www.youtube.com/@demo",
        )
        video = ChannelVideo(
            video_id="abc123",
            title="Demo Long Video",
            url="https://www.youtube.com/watch?v=abc123",
            duration_seconds=900,
            published_at="2026-05-17",
        )
        fetch_videos.return_value = [video]
        process_video.return_value = (
            Path("outputs/youtube/demo-channel/abc123"),
            {"status": "ok"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProcessedStore(Path(temp_dir) / "processed.json")

            processed = process_source(
                source=source,
                store=store,
                output_base=Path("outputs/youtube"),
                channel_limit=5,
                no_check_certificates=False,
                dry_run=False,
            )

        self.assertEqual(processed, 1)
        process_video.assert_called_once()
        self.assertEqual(process_video.call_args.kwargs["output_base"], Path("outputs/youtube/demo-channel"))
        self.assertTrue(store.is_processed("abc123"))
        self.assertEqual(store.source_record("demo-channel")["latest_videos"][0]["video_id"], "abc123")
        self.assertEqual(store.processing_record("abc123")["writer_profile"], "alchemy-research")


if __name__ == "__main__":
    unittest.main()
