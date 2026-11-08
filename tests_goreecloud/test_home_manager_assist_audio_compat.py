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
        return SimpleNamespace(audio=b"legacy")


class ModernSpeex:
    def process_10ms(self, audio: bytes) -> bytes:
        assert audio == PCM
        return b"modern"


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
        self.assertEqual(bridge.process_speex_chunk(LegacySpeex(), PCM), b"legacy")

    def test_modern_speex_bytes_preserved(self) -> None:
        self.assertEqual(bridge.process_speex_chunk(ModernSpeex(), PCM), b"modern")

    def test_speex_prefers_modern_if_both_methods_exist(self) -> None:
        class Both(LegacySpeex, ModernSpeex):
            pass

        self.assertEqual(bridge.process_speex_chunk(Both(), PCM), b"modern")

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
