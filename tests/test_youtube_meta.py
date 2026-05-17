import unittest

from youtube_to_wechat.youtube_meta import extract_video_id


class ExtractVideoIdTests(unittest.TestCase):
    def test_extracts_video_id_from_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=6C7FjGs22g8"),
            "6C7FjGs22g8",
        )

    def test_extracts_video_id_from_short_url(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/6C7FjGs22g8?si=abc"),
            "6C7FjGs22g8",
        )

    def test_rejects_non_youtube_url(self):
        with self.assertRaises(ValueError):
            extract_video_id("https://example.com/watch?v=6C7FjGs22g8")


if __name__ == "__main__":
    unittest.main()
