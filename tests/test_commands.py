"""Unit tests for safe command parsing; no microphone or GUI needed."""

import unittest

from aurix.commands import ParsedCommand, normalize_text, parse_command


class CommandParsingTests(unittest.TestCase):
    def test_removes_portuguese_accents(self):
        self.assertEqual(normalize_text("Pesquise café"), "pesquise cafe")

    def test_opens_spotify(self):
        self.assertEqual(parse_command("Abre o Spotify"), ParsedCommand("open_app", "spotify"))

    def test_opens_whatsapp(self):
        self.assertEqual(
            parse_command("Por favor, abra o WhatsApp."),
            ParsedCommand("open_app", "whatsapp"),
        )

    def test_opens_vscode(self):
        self.assertEqual(parse_command("Inicie o VS Code"), ParsedCommand("open_app", "vscode"))

    def test_time_command(self):
        self.assertEqual(parse_command("Que horas são?"), ParsedCommand("time"))

    def test_date_command(self):
        self.assertEqual(parse_command("Qual é a data de hoje?"), ParsedCommand("date"))

    def test_search_command(self):
        self.assertEqual(
            parse_command("Pesquise por documentação do Python"),
            ParsedCommand("search_web", "documentacao do python"),
        )

    def test_unknown_command_is_not_executed(self):
        self.assertIsNone(parse_command("execute format c:"))

    def test_arbitrary_shell_is_not_a_command(self):
        self.assertIsNone(parse_command("abra cmd e apague todos os arquivos"))


if __name__ == "__main__":
    unittest.main()
