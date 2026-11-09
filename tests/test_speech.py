"""Offline unit tests for AURIX local speech helpers."""

import hashlib
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import aurix.speech as speech

from aurix.speech import (
    build_phoneme_chunks,
    filter_supported_ipa,
    normalize_speech_text,
    sha256_file,
)


class SpeechHelperTests(unittest.TestCase):
    def test_normalize_speech_text_collapses_whitespace(self):
        self.assertEqual(
            normalize_speech_text("  Olá\n\tAURIX   tudo bem?  "),
            "Olá AURIX tudo bem?",
        )

    def test_normalize_speech_text_respects_limit(self):
        self.assertEqual(normalize_speech_text("abcdefgh", limit=5), "abcde")

    def test_normalize_speech_text_handles_empty_values(self):
        self.assertEqual(normalize_speech_text("  \n "), "")

    def test_sha256_file_streams_expected_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.bin"
            path.write_bytes(b"aurix-local-voice")
            self.assertEqual(
                sha256_file(path),
                hashlib.sha256(b"aurix-local-voice").hexdigest(),
            )

    def test_filter_supported_ipa_removes_syllable_separator_and_normalizes_nasal_vowels(self):
        vocab = {" ": 0, "ˈ": 1, "a": 2, "\u0303": 3, "ʊ": 4, "ɾ": 5}
        self.assertEqual(
            filter_supported_ipa("ˈɐ· ˈgatʊ ã", vocab),
            "ˈ ˈaʊ a\u0303",
        )

    def test_build_phoneme_chunks_preserves_word_boundaries(self):
        vocab = {" ": 0, "a": 1, "b": 2, "c": 3}
        self.assertEqual(
            build_phoneme_chunks("ab c ab", vocab, max_tokens=5),
            [[1, 2, 0, 3], [1, 2]],
        )

    def test_build_phoneme_chunks_splits_long_words_without_overflow(self):
        vocab = {character: index for index, character in enumerate("abcd")}
        chunks = build_phoneme_chunks("abcdabcd", vocab, max_tokens=3)
        self.assertEqual(chunks, [[0, 1, 2], [3, 0, 1], [2, 3]])

    def test_build_phoneme_chunks_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            build_phoneme_chunks("a", {"a": 1}, max_tokens=0)

    def test_synthesis_failure_still_schedules_model_release(self):
        with patch.dict("sys.modules", {"numpy": types.ModuleType("numpy")}), patch.object(
            speech, "_engine", object()
        ), patch.object(speech, "_make_audio", side_effect=RuntimeError("phonemizer failed")), patch.object(
            speech, "_schedule_engine_release"
        ) as schedule_release:
            with self.assertRaisesRegex(RuntimeError, "phonemizer failed"):
                speech.synthesize_to_wav("Olá AURIX", Path(tempfile.gettempdir()) / "never-created.wav")
        schedule_release.assert_called_once()

    def test_synthesis_failure_without_loaded_model_does_not_schedule_release(self):
        with patch.dict("sys.modules", {"numpy": types.ModuleType("numpy")}), patch.object(
            speech, "_engine", None
        ), patch.object(speech, "_make_audio", side_effect=RuntimeError("model unavailable")), patch.object(
            speech, "_schedule_engine_release"
        ) as schedule_release:
            with self.assertRaisesRegex(RuntimeError, "model unavailable"):
                speech.synthesize_to_wav("Olá AURIX", Path(tempfile.gettempdir()) / "never-created.wav")
        schedule_release.assert_not_called()


if __name__ == "__main__":
    unittest.main()
