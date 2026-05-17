import unittest

from youtube_to_wechat.compare import render_comparison_md
from youtube_to_wechat.extractor import OpinionResult


_META = {
    "title": "测试视频",
    "webpage_url": "https://www.youtube.com/watch?v=test123",
}

_OPINIONS_A = OpinionResult(
    summary="字幕路径摘要",
    opinions=["观点 A1", "观点 A2", "观点 A3"],
    key_points=["要点 A1", "要点 A2"],
    review_notes=["存疑 A1"],
)

_OPINIONS_B = OpinionResult(
    summary="音频路径摘要",
    opinions=["观点 B1", "观点 B2"],
    key_points=["要点 B1"],
    review_notes=[],
)


class TestRenderComparisonMd(unittest.TestCase):
    def _render(self, **kwargs) -> str:
        defaults = dict(
            meta=_META,
            subtitle_transcript="字幕文本示例 " * 20,
            audio_transcript="音频转写文本 " * 20,
            subtitle_opinions=_OPINIONS_A,
            audio_opinions=_OPINIONS_B,
        )
        defaults.update(kwargs)
        return render_comparison_md(**defaults)

    def test_contains_title(self):
        md = self._render()
        self.assertIn("测试视频", md)

    def test_contains_url(self):
        md = self._render()
        self.assertIn("https://www.youtube.com/watch?v=test123", md)

    def test_contains_both_section_headers(self):
        md = self._render()
        self.assertIn("路径 A", md)
        self.assertIn("路径 B", md)

    def test_contains_opinion_content(self):
        md = self._render()
        self.assertIn("字幕路径摘要", md)
        self.assertIn("音频路径摘要", md)
        self.assertIn("观点 A1", md)
        self.assertIn("观点 B1", md)

    def test_contains_comparison_table(self):
        md = self._render()
        self.assertIn("对比速览", md)
        # Table should show correct opinion counts
        self.assertIn("3", md)  # subtitle: 3 opinions
        self.assertIn("2", md)  # audio: 2 opinions

    def test_subtitle_error_shown(self):
        md = self._render(subtitle_opinions=None, subtitle_error="字幕不可用")
        self.assertIn("字幕不可用", md)
        self.assertIn("❌", md)

    def test_audio_error_shown(self):
        md = self._render(audio_opinions=None, audio_error="音频下载失败")
        self.assertIn("音频下载失败", md)

    def test_both_none_still_renders(self):
        """Report renders even when both paths produced no results."""
        md = render_comparison_md(
            meta=_META,
            subtitle_transcript="",
            audio_transcript="",
            subtitle_opinions=None,
            audio_opinions=None,
        )
        self.assertIn("路径 A", md)
        self.assertIn("路径 B", md)

    def test_transcript_preview_truncated(self):
        long_text = "word " * 500
        md = self._render(subtitle_transcript=long_text)
        self.assertIn("…", md)

    def test_empty_transcript_shows_placeholder(self):
        md = self._render(audio_transcript="")
        self.assertIn("无 transcript", md)

    def test_review_notes_marked_with_warning(self):
        md = self._render()
        self.assertIn("⚠️", md)
        self.assertIn("存疑 A1", md)


if __name__ == "__main__":
    unittest.main()
