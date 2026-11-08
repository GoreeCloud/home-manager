"""Compatibility bridge for the imported Assist pipeline audio processors.

The upstream 1.x native packages expose Process10ms, while newer versions
expose process_10ms. Preserve legacy processing while validating the newer
return value before changing any upstream dependency version pins.

This module has no external imports and does not load native audio libraries.
"""

from collections.abc import Callable
from typing import Any, cast


def process_vad_chunk(vad: object, audio: bytes) -> float:
    """Return VAD speech probability using the available supported API."""
    modern = getattr(vad, "process_10ms", None)
    if callable(modern):
        return cast(Callable[[bytes], float], modern)(audio)

    legacy = getattr(vad, "Process10ms", None)
    if callable(legacy):
        return cast(Callable[[bytes], float], legacy)(audio)

    raise TypeError("VAD implementation exposes neither supported 10ms method")


def process_speex_chunk(processor: object, audio: bytes) -> bytes:
    """Normalize the old .audio result and the new bytes return format."""
    modern = getattr(processor, "process_10ms", None)
    if callable(modern):
        result = cast(Callable[[bytes], Any], modern)(audio)
        if not isinstance(result, bytes):
            raise TypeError("modern Speex processor returned non-bytes audio")
        return result

    legacy = getattr(processor, "Process10ms", None)
    if callable(legacy):
        result = cast(Callable[[bytes], Any], legacy)(audio)
        processed = getattr(result, "audio", None)
        if not isinstance(processed, bytes):
            raise TypeError("legacy Speex processor returned non-bytes audio")
        return processed

    raise TypeError("Speex implementation exposes neither supported 10ms method")
