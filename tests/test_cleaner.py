import unittest

from youtube_to_wechat.cleaner import clean_vtt


class CleanVttTests(unittest.TestCase):
    def test_removes_vtt_timestamps_and_deduplicates_lines(self):
        raw = """WEBVTT

00:00:00.000 --> 00:00:01.000
Hello world

00:00:01.000 --> 00:00:02.000
Hello world
This is useful

00:00:02.000 --> 00:00:03.000
[Music]
"""

        self.assertEqual(clean_vtt(raw), "Hello world\nThis is useful")

    def test_removes_inline_vtt_tags(self):
        raw = """WEBVTT

00:00:00.000 --> 00:00:01.000
<c.colorE5E5E5>Hello</c> <00:00:00.500>there
"""

        self.assertEqual(clean_vtt(raw), "Hello there")


if __name__ == "__main__":
    unittest.main()
