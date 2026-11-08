"""Dependency-free Assist audio bridge tests with synthetic processors only.

No imported Home Assistant modules or third-party native extensions are loaded.
The integration call sites and existing dependency pins are inspected as text.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "homeassistant/components/assist_pipeline/audio_compat.py"
SPEC = importlib.util.spec_from_file_location("home_manager_assist_audio_bridge", SOURCE)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
PCM = bytes(320)


class LegacyVad:
    def Process10ms(self, audio: bytes) -> float:
        assert audio == PCM
        return -1.0


class ModernVad:
    def process_10ms(self, audio: bytes) -> float:
        assert audio == PCM
        return 0.75


class LegacySpeex:
    def Process10ms(self, audio: bytes) -> SimpleNamespace:
        assert audio == PCM
        return SimpleNamespace(audio=bytes([17]) * 320)


class ModernSpeex:
    def process_10ms(self, audio: bytes) -> bytes:
        assert audio == PCM
        return bytes([23]) * 320


class HomeManagerAssistAudioCompatibilityTests(unittest.TestCase):
    def test_legacy_vad_warmup_preserved(self) -> None:
        self.assertEqual(bridge.process_vad_chunk(LegacyVad(), PCM), -1.0)

    def test_modern_vad_probability_preserved(self) -> None:
        self.assertEqual(bridge.process_vad_chunk(ModernVad(), PCM), 0.75)

    def test_vad_prefers_modern_if_both_methods_exist(self) -> None:
        class Both(LegacyVad, ModernVad):
            pass

        self.assertEqual(bridge.process_vad_chunk(Both(), PCM), 0.75)

    def test_legacy_speex_audio_field_preserved(self) -> None:
        self.assertEqual(bridge.process_speex_chunk(LegacySpeex(), PCM), bytes([17]) * 320)

    def test_modern_speex_bytes_preserved(self) -> None:
        self.assertEqual(bridge.process_speex_chunk(ModernSpeex(), PCM), bytes([23]) * 320)

    def test_speex_prefers_modern_if_both_methods_exist(self) -> None:
        class Both(LegacySpeex, ModernSpeex):
            pass

        self.assertEqual(bridge.process_speex_chunk(Both(), PCM), bytes([23]) * 320)

    def test_missing_methods_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            bridge.process_vad_chunk(object(), PCM)
        with self.assertRaises(TypeError):
            bridge.process_speex_chunk(object(), PCM)

    def test_incorrect_speex_payload_is_rejected(self) -> None:
        class ModernInvalid:
            def process_10ms(self, audio: bytes) -> str:
                return "not PCM bytes"

        class LegacyInvalid:
            def Process10ms(self, audio: bytes) -> SimpleNamespace:
                return SimpleNamespace(audio="not PCM bytes")

        with self.assertRaisesRegex(TypeError, "modern Speex"):
            bridge.process_speex_chunk(ModernInvalid(), PCM)
        with self.assertRaisesRegex(TypeError, "legacy Speex"):
            bridge.process_speex_chunk(LegacyInvalid(), PCM)

    def test_short_and_long_frames_rejected_before_native_call(self) -> None:
        class UnsafeNative:
            def __init__(self) -> None:
                self.called = False

            def process_10ms(self, audio: bytes) -> bytes:
                self.called = True
                return bytes(320)

        for size in (0, 1, 319, 321, 4096):
            with self.subTest(size=size):
                for entry in (bridge.process_vad_chunk, bridge.process_speex_chunk):
                    native = UnsafeNative()
                    with self.assertRaisesRegex(ValueError, "exactly 320"):
                        entry(native, bytes(size))
                    self.assertFalse(native.called, "invalid frame reached native extension")

    def test_wrong_frame_type_rejected(self) -> None:
        class Native:
            def process_10ms(self, audio: bytes) -> bytes:
                self.fail("must not invoke native method")

        for entry in (bridge.process_vad_chunk, bridge.process_speex_chunk):
            with self.assertRaisesRegex(TypeError, "must be bytes"):
                entry(Native(), "x" * 320)

    def test_short_speex_output_is_rejected(self) -> None:
        class ModernTruncated:
            def process_10ms(self, audio: bytes) -> bytes:
                return bytes(319)

        class LegacyTruncated:
            def Process10ms(self, audio: bytes) -> SimpleNamespace:
                return SimpleNamespace(audio=bytes(321))

        for native in (ModernTruncated(), LegacyTruncated()):
            with self.assertRaisesRegex(ValueError, "invalid 10ms frame"):
                bridge.process_speex_chunk(native, PCM)

    def test_boundary_rule_is_not_optional_python_assertion(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("if len(audio) != _FRAME_BYTES:", source)
        self.assertIn("_require_frame(audio)", source)
        self.assertNotIn("assert len(audio)", source)

    def test_noncallable_modern_attribute_uses_legacy(self) -> None:
        class LegacyWithShadow(LegacyVad):
            process_10ms = None

        self.assertEqual(bridge.process_vad_chunk(LegacyWithShadow(), PCM), -1.0)

    def test_imported_core_calls_bridge_and_pins_are_unchanged(self) -> None:
        consumer = (ROOT / "homeassistant/components/assist_pipeline/audio_enhancer.py").read_text(encoding="utf-8")
        self.assertIn("process_vad_chunk(self.vad, audio)", consumer)
        self.assertIn("process_speex_chunk(self.audio_processor, audio)", consumer)
        pins = {
            "requirements.txt",
            "requirements_all.txt",
            "homeassistant/package_constraints.txt",
            "homeassistant/components/assist_pipeline/manifest.json",
        }
        for name in pins:
            source = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIn("pymicro-vad==1.0.1", source)
                self.assertIn("pyspeex-noise==1.0.2", source)


if __name__ == "__main__":
    unittest.main()
