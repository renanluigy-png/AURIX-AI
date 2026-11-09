"""Offline tests for AURIX local speech helpers."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from aurix.speech import is_valid_voice_config, normalize_speech_text, sha256_file


class SpeechHelperTests(unittest.TestCase):
    def test_normalize_speech_text_collapses_whitespace(self):
        self.assertEqual(normalize_speech_text("  Olá\n\tAURIX   tudo bem?  "), "Olá AURIX tudo bem?")

    def test_normalize_speech_text_respects_limit(self):
        self.assertEqual(normalize_speech_text("abcdefgh", limit=5), "abcde")

    def test_normalize_speech_text_handles_empty_values(self):
        self.assertEqual(normalize_speech_text("  \n "), "")

    def test_sha256_file_streams_expected_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.bin"
            path.write_bytes(b"aurix-local-voice")
            self.assertEqual(sha256_file(path), hashlib.sha256(b"aurix-local-voice").hexdigest())

    def test_valid_voice_config_requires_sample_rate_and_phoneme_map(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice.onnx.json"
            path.write_text(json.dumps({
                "audio": {"sample_rate": 22050},
                "phoneme_id_map": {"_": [0], "a": [1]},
                "language": {"code": "pt_BR"},
            }), encoding="utf-8")
            self.assertTrue(is_valid_voice_config(path))

    def test_invalid_voice_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice.onnx.json"
            path.write_text(json.dumps({
                "audio": {"sample_rate": 16000},
                "phoneme_id_map": {},
                "language": {"code": "pt_BR"},
            }), encoding="utf-8")
            self.assertFalse(is_valid_voice_config(path))


if __name__ == "__main__":
    unittest.main()
