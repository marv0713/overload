import unittest

from youtube_to_wechat.youtube_channel import (
    ChannelVideo,
    select_eligible_videos_for_source,
    select_latest_eligible_video,
)


class YoutubeChannelSelectionTests(unittest.TestCase):
    def test_selects_first_long_unprocessed_video(self):
        videos = [
            ChannelVideo(
                video_id="short1",
                title="Short update",
                url="https://www.youtube.com/watch?v=short1",
                duration_seconds=120,
                published_at="2026-05-17",
            ),
            ChannelVideo(
                video_id="old_long",
                title="Already processed long video",
                url="https://www.youtube.com/watch?v=old_long",
                duration_seconds=1800,
                published_at="2026-05-16",
            ),
            ChannelVideo(
                video_id="new_long",
                title="Fresh long video",
                url="https://www.youtube.com/watch?v=new_long",
                duration_seconds=1200,
                published_at="2026-05-15",
            ),
        ]

        selected = select_latest_eligible_video(
            videos,
            min_duration_seconds=600,
            processed_video_ids={"old_long"},
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.video_id, "new_long")

    def test_returns_none_when_no_video_matches_policy(self):
        selected = select_latest_eligible_video(
            [
                ChannelVideo(
                    video_id="short1",
                    title="Short update",
                    url="https://www.youtube.com/watch?v=short1",
                    duration_seconds=300,
                    published_at="2026-05-17",
                )
            ],
            min_duration_seconds=600,
            processed_video_ids=set(),
        )

        self.assertIsNone(selected)

    def test_new_source_only_selects_latest_eligible_video(self):
        videos = [
            ChannelVideo(
                video_id="newest",
                title="Newest eligible",
                url="https://www.youtube.com/watch?v=newest",
                duration_seconds=900,
                published_at="2026-05-17",
            ),
            ChannelVideo(
                video_id="older",
                title="Older eligible",
                url="https://www.youtube.com/watch?v=older",
                duration_seconds=1200,
                published_at="2026-05-10",
            ),
        ]

        selected = select_eligible_videos_for_source(
            videos,
            min_duration_seconds=600,
            processed_video_ids=set(),
            source_seen_before=False,
        )

        self.assertEqual([video.video_id for video in selected], ["newest"])

    def test_existing_source_selects_unprocessed_eligible_videos_oldest_first(self):
        videos = [
            ChannelVideo(
                video_id="newest",
                title="Newest eligible",
                url="https://www.youtube.com/watch?v=newest",
                duration_seconds=900,
                published_at="2026-05-17",
            ),
            ChannelVideo(
                video_id="middle",
                title="Middle eligible",
                url="https://www.youtube.com/watch?v=middle",
                duration_seconds=900,
                published_at="2026-05-12",
            ),
            ChannelVideo(
                video_id="oldest",
                title="Oldest eligible",
                url="https://www.youtube.com/watch?v=oldest",
                duration_seconds=900,
                published_at="2026-05-10",
            ),
        ]

        selected = select_eligible_videos_for_source(
            videos,
            min_duration_seconds=600,
            processed_video_ids={"middle"},
            source_seen_before=True,
        )

        self.assertEqual([video.video_id for video in selected], ["oldest", "newest"])

    def test_existing_source_stops_at_latest_processed_video_in_channel_order(self):
        videos = [
            ChannelVideo(
                video_id="newest-after-last-processed",
                title="Newest after last processed",
                url="https://www.youtube.com/watch?v=newest-after-last-processed",
                duration_seconds=900,
            ),
            ChannelVideo(
                video_id="middle-after-last-processed",
                title="Middle after last processed",
                url="https://www.youtube.com/watch?v=middle-after-last-processed",
                duration_seconds=900,
            ),
            ChannelVideo(
                video_id="last-processed",
                title="Last processed",
                url="https://www.youtube.com/watch?v=last-processed",
                duration_seconds=900,
            ),
            ChannelVideo(
                video_id="older-before-last-processed",
                title="Older before last processed",
                url="https://www.youtube.com/watch?v=older-before-last-processed",
                duration_seconds=900,
            ),
        ]

        selected = select_eligible_videos_for_source(
            videos,
            min_duration_seconds=600,
            processed_video_ids={"last-processed"},
            source_seen_before=True,
            stop_at_video_ids={"last-processed"},
        )

        self.assertEqual(
            [video.video_id for video in selected],
            ["newest-after-last-processed", "middle-after-last-processed"],
        )


if __name__ == "__main__":
    unittest.main()
