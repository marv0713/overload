import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from youtube_to_wechat.transcriber import (
    BaseTranscriber,
    FasterWhisperTranscriber,
    TranscriberError,
)


class TestBaseTranscriber(unittest.TestCase):
    def test_is_abstract(self):
        """BaseTranscriber cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseTranscriber()  # type: ignore[abstract]

    def test_concrete_subclass_works(self):
        class DummyTranscriber(BaseTranscriber):
            def transcribe(self, audio_path: Path) -> str:
                return "hello world"

        t = DummyTranscriber()
        self.assertEqual(t.transcribe(Path("any.mp3")), "hello world")


class TestFasterWhisperTranscriber(unittest.TestCase):
    def test_default_attributes(self):
        t = FasterWhisperTranscriber()
        self.assertEqual(t.model_size, "base")
        self.assertIsNone(t.language)
        self.assertEqual(t.device, "cpu")
        self.assertEqual(t.compute_type, "int8")

    def test_custom_attributes(self):
        t = FasterWhisperTranscriber(model_size="small", language="zh", device="cpu")
        self.assertEqual(t.model_size, "small")
        self.assertEqual(t.language, "zh")

    def test_transcribe_returns_joined_segments(self):
        """transcribe() joins non-empty segment texts with newlines."""
        fake_segment_1 = MagicMock()
        fake_segment_1.text = "  Hello world  "
        fake_segment_2 = MagicMock()
        fake_segment_2.text = "  Second line  "
        fake_segment_empty = MagicMock()
        fake_segment_empty.text = "   "

        fake_model = MagicMock()
        fake_model.transcribe.return_value = (
            iter([fake_segment_1, fake_segment_empty, fake_segment_2]),
            MagicMock(),  # info
        )

        t = FasterWhisperTranscriber()
        t._model = fake_model  # inject pre-loaded model

        result = t.transcribe(Path("audio.m4a"))
        self.assertEqual(result, "Hello world\nSecond line")
        fake_model.transcribe.assert_called_once_with(
            "audio.m4a", language=None, beam_size=5
        )

    def test_import_error_raises_transcriber_error(self):
        """Missing faster-whisper gives a clear TranscriberError."""
        t = FasterWhisperTranscriber()

        with patch.dict("sys.modules", {"faster_whisper": None}):
            with self.assertRaises(TranscriberError) as ctx:
                t._load_model()

        self.assertIn("faster-whisper", str(ctx.exception))

    def test_backend_exception_wrapped(self):
        """Exceptions from the model are wrapped in TranscriberError."""
        fake_model = MagicMock()
        fake_model.transcribe.side_effect = RuntimeError("CUDA OOM")

        t = FasterWhisperTranscriber()
        t._model = fake_model

        with self.assertRaises(TranscriberError):
            t.transcribe(Path("audio.m4a"))


if __name__ == "__main__":
    unittest.main()
