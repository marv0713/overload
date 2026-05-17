import unittest
from unittest.mock import MagicMock, patch

from youtube_to_wechat.extractor import (
    BaseExtractor,
    ExtractorError,
    GeminiExtractor,
    OpinionResult,
    _parse_opinion_json,
)


_VALID_JSON = """{
  "summary": "一句话摘要",
  "opinions": ["观点一", "观点二"],
  "key_points": ["要点一"],
  "review_notes": []
}"""


class TestOpinionResult(unittest.TestCase):
    def test_defaults(self):
        r = OpinionResult()
        self.assertEqual(r.opinions, [])
        self.assertEqual(r.summary, "")
        self.assertEqual(r.key_points, [])
        self.assertEqual(r.review_notes, [])

    def test_populated(self):
        r = OpinionResult(opinions=["a", "b"], summary="s", key_points=["k"])
        self.assertEqual(len(r.opinions), 2)
        self.assertEqual(r.summary, "s")


class TestParseOpinionJson(unittest.TestCase):
    def test_parses_valid_json(self):
        result = _parse_opinion_json(_VALID_JSON)
        self.assertEqual(result.summary, "一句话摘要")
        self.assertEqual(result.opinions, ["观点一", "观点二"])
        self.assertEqual(result.key_points, ["要点一"])
        self.assertEqual(result.review_notes, [])

    def test_strips_markdown_fence(self):
        fenced = f"```json\n{_VALID_JSON}\n```"
        result = _parse_opinion_json(fenced)
        self.assertEqual(result.summary, "一句话摘要")

    def test_strips_plain_fence(self):
        fenced = f"```\n{_VALID_JSON}\n```"
        result = _parse_opinion_json(fenced)
        self.assertEqual(result.summary, "一句话摘要")

    def test_invalid_json_returns_error_result(self):
        result = _parse_opinion_json("not json at all")
        self.assertIn("JSON 解析失败", result.summary)
        self.assertTrue(len(result.review_notes) > 0)

    def test_missing_fields_use_defaults(self):
        result = _parse_opinion_json('{"summary": "only summary"}')
        self.assertEqual(result.summary, "only summary")
        self.assertEqual(result.opinions, [])


class TestBaseExtractor(unittest.TestCase):
    def test_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseExtractor()  # type: ignore[abstract]

    def test_concrete_subclass_works(self):
        class DummyExtractor(BaseExtractor):
            def extract(self, transcript: str, meta: dict) -> OpinionResult:
                return OpinionResult(summary="dummy")

        e = DummyExtractor()
        result = e.extract("some text", {})
        self.assertEqual(result.summary, "dummy")


class TestGeminiExtractor(unittest.TestCase):
    def test_empty_transcript_returns_early(self):
        extractor = GeminiExtractor(api_key="fake-key")
        result = extractor.extract("   ", {"title": "test"})
        self.assertIn("transcript 为空", result.review_notes[0])

    def test_missing_api_key_raises(self):
        import os

        extractor = GeminiExtractor(api_key=None)
        original = os.environ.pop("GEMINI_API_KEY", None)
        try:
            extractor.api_key = None
            with self.assertRaises(ExtractorError) as ctx:
                extractor.extract("some transcript", {"title": "t"})
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        finally:
            if original is not None:
                os.environ["GEMINI_API_KEY"] = original


    def test_extract_parses_gemini_response(self):
        """extract() calls Gemini and parses JSON from the response."""
        fake_response = MagicMock()
        fake_response.text = _VALID_JSON

        fake_models = MagicMock()
        fake_models.generate_content.return_value = fake_response

        fake_client_instance = MagicMock()
        fake_client_instance.models = fake_models

        fake_genai = MagicMock()
        fake_genai.Client.return_value = fake_client_instance

        import sys
        import types

        google_stub = types.ModuleType("google")
        google_stub.genai = fake_genai  # type: ignore[attr-defined]

        extractor = GeminiExtractor(api_key="fake-key")

        with patch.dict(sys.modules, {"google": google_stub, "google.genai": fake_genai}):
            result = extractor.extract("transcript text", {"title": "Video Title"})

        self.assertEqual(result.summary, "一句话摘要")
        self.assertEqual(result.opinions, ["观点一", "观点二"])
        fake_models.generate_content.assert_called_once()

    def test_api_exception_raises_extractor_error(self):
        import sys, types

        fake_models = MagicMock()
        fake_models.generate_content.side_effect = RuntimeError("quota exceeded")

        fake_client_instance = MagicMock()
        fake_client_instance.models = fake_models

        fake_genai = MagicMock()
        fake_genai.Client.return_value = fake_client_instance

        google_stub = types.ModuleType("google")
        google_stub.genai = fake_genai

        extractor = GeminiExtractor(api_key="fake-key")

        with patch.dict(sys.modules, {"google": google_stub, "google.genai": fake_genai}):
            with self.assertRaises(ExtractorError):
                extractor.extract("some text", {})


if __name__ == "__main__":
    unittest.main()
