"""Unit tests for the agent-tool allowlist and argument validation."""

import unittest

from aurix.agent_tools import TOOL_DEFINITIONS, execute_tool, ollama_tools, openai_tools


class AgentToolTests(unittest.TestCase):
    def test_openai_and_ollama_have_the_same_tool_names(self):
        expected = {item["name"] for item in TOOL_DEFINITIONS}
        self.assertEqual({item["name"] for item in openai_tools()}, expected)
        self.assertEqual(
            {item["function"]["name"] for item in ollama_tools()},
            expected,
        )

    def test_every_tool_schema_disallows_extra_fields(self):
        for tool in TOOL_DEFINITIONS:
            self.assertFalse(tool["parameters"].get("additionalProperties", True))

    def test_unknown_tool_is_rejected(self):
        self.assertIn("recusada", execute_tool("run_shell", {"command": "whoami"}).lower())

    def test_open_app_rejects_unallowlisted_application(self):
        result = execute_tool("open_application", {"application": "powershell_admin"})
        self.assertTrue("permitidas" in result or "recusada" in result.lower())

    def test_open_website_rejects_non_http_scheme(self):
        result = execute_tool("open_website", {"url": "file:///C:/Windows/win.ini"})
        self.assertIn("recusada", result.lower())

    def test_create_note_requires_title_and_content(self):
        result = execute_tool("create_note", {"title": "", "content": ""})
        self.assertIn("não criei", result.lower())


if __name__ == "__main__":
    unittest.main()
