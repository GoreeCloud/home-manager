"""Compatibility bridge for the imported Assist pipeline audio processors.

The upstream 1.x native packages expose Process10ms, while newer versions
expose process_10ms. Preserve legacy processing while validating the newer
return value before changing any upstream dependency version pins.

This module has no external imports and does not load native audio libraries.
"""

from collections.abc import Callable
from typing import Any, cast

# 10 ms of 16 kHz, 16-bit, single-channel PCM. The newer native Speex
# binding copies this many bytes without its own input-length guard.
_FRAME_BYTES = 320


def _require_frame(audio: bytes) -> None:
    if not isinstance(audio, bytes):
        raise TypeError("Assist audio frame must be bytes")
    if len(audio) != _FRAME_BYTES:
        raise ValueError("Assist audio frame must contain exactly 320 bytes")


def _require_processed_frame(audio: bytes) -> bytes:
    if len(audio) != _FRAME_BYTES:
        raise ValueError("Speex processor returned an invalid 10ms frame size")
    return audio


def process_vad_chunk(vad: object, audio: bytes) -> float:
    """Return VAD speech probability using the available supported API."""
    _require_frame(audio)
    modern = getattr(vad, "process_10ms", None)
    if callable(modern):
        return cast(Callable[[bytes], float], modern)(audio)

    legacy = getattr(vad, "Process10ms", None)
    if callable(legacy):
        return cast(Callable[[bytes], float], legacy)(audio)

    raise TypeError("VAD implementation exposes neither supported 10ms method")


def process_speex_chunk(processor: object, audio: bytes) -> bytes:
    """Normalize the old .audio result and the new bytes return format."""
    _require_frame(audio)
    modern = getattr(processor, "process_10ms", None)
    if callable(modern):
        result = cast(Callable[[bytes], Any], modern)(audio)
        if not isinstance(result, bytes):
            raise TypeError("modern Speex processor returned non-bytes audio")
        return _require_processed_frame(result)

    legacy = getattr(processor, "Process10ms", None)
    if callable(legacy):
        result = cast(Callable[[bytes], Any], legacy)(audio)
        processed = getattr(result, "audio", None)
        if not isinstance(processed, bytes):
            raise TypeError("legacy Speex processor returned non-bytes audio")
        return _require_processed_frame(processed)

    raise TypeError("Speex implementation exposes neither supported 10ms method")
