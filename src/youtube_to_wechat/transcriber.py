"""Transcript artifact producers for audio transcription.

Usage::

    from youtube_to_wechat.transcriber import FasterWhisperTranscriber

    t = FasterWhisperTranscriber(model_size="base")
    text = t.transcribe(Path("audio.m4a"))

To add a new backend, subclass ``BaseTranscriber`` and implement
``transcribe(audio_path: Path) -> str``.  The returned text is one possible
transcript artifact origin: ``audio-transcription``.  Caption files and blog
body extraction produce the same kind of normalized text through other source
adapters.
"""
import abc
from pathlib import Path
from typing import Optional


class BaseTranscriber(abc.ABC):
    """Plugin interface for audio-to-text transcription.

    Each backend must implement :meth:`transcribe` which accepts a local audio
    file path and returns plain text.  The text format should be compatible with
    the output of :func:`~youtube_to_wechat.cleaner.clean_vtt` — consecutive
    lines separated by ``\\n``, no timestamps or markup.
    """

    @abc.abstractmethod
    def transcribe(self, audio_path: Path) -> str:
        """Transcribe a local audio file and return plain text.

        Args:
            audio_path: Path to the local audio file (any format supported by
                the underlying backend, e.g. .m4a, .webm, .mp3).

        Returns:
            Plain-text transcript with lines joined by ``\\n``.

        Raises:
            TranscriberError: On backend-specific failures.
        """


class TranscriberError(RuntimeError):
    """Raised when transcription fails."""


class FasterWhisperTranscriber(BaseTranscriber):
    """Local transcription via ``faster-whisper`` (free, no API key needed).

    ``faster-whisper`` is a reimplementation of OpenAI Whisper using
    CTranslate2 for efficient CPU and GPU inference.  The first call to
    :meth:`transcribe` loads the model into memory; subsequent calls reuse it.

    Args:
        model_size: Whisper model variant.  Ordered by accuracy / cost:
            ``"tiny"`` < ``"base"`` < ``"small"`` < ``"medium"`` < ``"large-v3"``.
            Default is ``"base"`` (~140 MB, good balance for podcast content).
        language: BCP-47 language code hint (e.g. ``"zh"`` or ``"en"``).
            ``None`` lets Whisper auto-detect.
        device: Compute device — ``"cpu"`` (default, works everywhere) or
            ``"cuda"`` for NVIDIA GPUs.
        compute_type: CTranslate2 quantisation.  ``"int8"`` works on CPU
            without accuracy loss for most content.

    Example::

        t = FasterWhisperTranscriber(model_size="small", language="zh")
        text = t.transcribe(Path("podcast.m4a"))
    """

    def __init__(
        self,
        model_size: str = "base",
        language: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model = None  # lazy-loaded on first transcribe call

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # noqa: PLC0415
            except ImportError as exc:
                raise TranscriberError(
                    "faster-whisper is not installed. "
                    "Install it with: pip install faster-whisper"
                ) from exc
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio using the local Whisper model.

        Args:
            audio_path: Path to the local audio file.

        Returns:
            Plain-text transcript joined by newlines.

        Raises:
            TranscriberError: If ``faster-whisper`` is not installed or the
                model fails to run on the given file.
        """
        model = self._load_model()
        try:
            segments, _info = model.transcribe(
                str(audio_path),
                language=self.language,
                beam_size=5,
            )
            lines = [seg.text.strip() for seg in segments if seg.text.strip()]
        except Exception as exc:  # noqa: BLE001
            raise TranscriberError(f"faster-whisper transcription failed: {exc}") from exc
        return "\n".join(lines)
