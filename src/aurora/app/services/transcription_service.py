"""Speech-to-text service backed by faster-whisper.

The Whisper model is loaded lazily and reused. faster-whisper is an optional
dependency (the ``voice`` extra); if it is missing, a clear configuration error
is raised rather than crashing at import time. A ``transcriber`` callable may be
injected for testing without loading a model.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Callable

from aurora.app.core.exceptions import ConfigurationError, TranscriptionError
from aurora.app.core.logging import get_logger

_logger = get_logger("services.transcription")

# A test seam: (audio_bytes, suffix) -> transcript text.
Transcriber = Callable[[bytes, str], str]


class TranscriptionService:
    """Transcribe recorded audio to text."""

    def __init__(
        self, model_size: str = "base", transcriber: Transcriber | None = None
    ) -> None:
        self._model_size = model_size
        self._transcriber = transcriber
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ConfigurationError(
                    "Voice transcription is unavailable. Install the 'voice' extra "
                    "(pip install faster-whisper)."
                ) from exc
            _logger.info("loading_whisper", extra={"model": self._model_size})
            self._model = WhisperModel(
                self._model_size, device="cpu", compute_type="int8"
            )
        return self._model

    def _run(self, audio: bytes, suffix: str) -> str:
        model = self._load()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(audio)
            path = handle.name
        try:
            segments, _ = model.transcribe(path, beam_size=1)
            return " ".join(seg.text.strip() for seg in segments).strip()
        finally:
            os.unlink(path)

    async def transcribe(self, audio: bytes, suffix: str = ".webm") -> str:
        """Return the transcript of ``audio`` (raw bytes of a recorded clip)."""
        if not audio:
            raise TranscriptionError("No audio was provided")
        if self._transcriber is not None:
            return self._transcriber(audio, suffix)
        try:
            return await asyncio.to_thread(self._run, audio, suffix)
        except ConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as structured error
            raise TranscriptionError(f"Transcription failed: {exc}") from exc
