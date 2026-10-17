"""Tests for the AURIX brain fast path and model-independent commands."""

import unittest
from unittest.mock import patch

from aurix.brain import AssistantBrain, _simple_local_command
from aurix.commands import ParsedCommand


class AssistantBrainTests(unittest.TestCase):
    def test_simple_open_app_is_executed_without_a_model_provider(self):
        brain = AssistantBrain()
        brain.provider = "none"
        with patch("aurix.brain.execute_command", return_value="Abrindo Spotify.") as execute:
            result = brain.respond("Abra o Spotify")
        self.assertEqual(result, "Abrindo Spotify.")
        execute.assert_called_once_with(ParsedCommand("open_app", "spotify"))

    def test_compound_open_request_is_not_treated_as_a_simple_command(self):
        self.assertIsNone(_simple_local_command("Abra o Spotify e toque minha playlist favorita"))

    def test_compound_search_with_summary_request_uses_the_model(self):
        self.assertIsNone(_simple_local_command("Pesquise sobre inteligência artificial e me explique os resultados"))

    def test_simple_date_command_has_a_fast_path(self):
        self.assertEqual(_simple_local_command("Que horas são?").name, "time")


if __name__ == "__main__":
    unittest.main()
