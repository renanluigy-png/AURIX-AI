"""Explicit, validated tools the AURIX AI agent is allowed to use."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from aurix.commands import APP_DISPLAY_NAMES, APP_TARGETS, ParsedCommand, execute_command

APP_ENUM = sorted(APP_TARGETS)
FOLDER_ENUM = ["desktop", "documents", "downloads"]

# Responses API function definitions. Strict schemas make the model's arguments
# predictable; execute_tool validates them again before doing anything.
TOOL_DEFINITIONS = [
    {
        "name": "open_application",
        "description": "Open an installed, allowlisted desktop application when the user asks. Do not claim success until the tool returns it.",
        "parameters": {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "enum": APP_ENUM,
                    "description": "Canonical ID of the application to open.",
                }
            },
            "required": ["application"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_web",
        "description": "Open a browser search for information the user asked to look up online.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A concise web search query."}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "open_website",
        "description": "Open a specific public HTTP or HTTPS website that the user explicitly requested.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "A complete http or https URL."}
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_current_datetime",
        "description": "Get the current local date, time, and timezone offset on this computer.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "open_known_folder",
        "description": "Open one of the user's standard folders; never accept an arbitrary path.",
        "parameters": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "enum": FOLDER_ENUM,
                    "description": "One of desktop, documents, downloads.",
                }
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_note",
        "description": "Create a new UTF-8 text note in Documents/AURIX Notes. Use this when the user asks to save or write something to a note. Existing notes are never overwritten.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the note."},
                "content": {"type": "string", "description": "Full text to save in the note."},
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
    },
]


def openai_tools() -> list[dict]:
    """Format our function tools for the OpenAI Responses API."""
    return [
        {
            "type": "function",
            "name": item["name"],
            "description": item["description"],
            "parameters": item["parameters"],
            "strict": True,
        }
        for item in TOOL_DEFINITIONS
    ]


def ollama_tools() -> list[dict]:
    """Format the same tools for Ollama's /api/chat endpoint."""
    return [
        {
            "type": "function",
            "function": {
                "name": item["name"],
                "description": item["description"],
                "parameters": item["parameters"],
            },
        }
        for item in TOOL_DEFINITIONS
    ]


def _standard_folders() -> dict[str, Path]:
    home = Path.home()
    return {
        "desktop": home / "Desktop",
        "documents": home / "Documents",
        "downloads": home / "Downloads",
    }


def execute_tool(name: str, arguments: dict) -> str:
    """Run exactly one registered tool after checking its name and arguments."""
    if not isinstance(arguments, dict):
        return "Ação recusada: os argumentos precisam ser um objeto."

    known = {item["name"]: item for item in TOOL_DEFINITIONS}
    spec = known.get(name)
    if spec is None:
        return "Ação recusada: ferramenta desconhecida."

    params = spec["parameters"]
    expected = set(params.get("properties", {}))
    required = set(params.get("required", []))
    received = set(arguments)
    if received - expected or not required.issubset(received):
        return "Ação recusada: argumentos inválidos para essa ferramenta."

    if name == "open_application":
        app_id = arguments["application"]
        if app_id not in APP_TARGETS:
            return "Esse aplicativo não está na lista de ações permitidas."
        return execute_command(ParsedCommand("open_app", app_id))

    if name == "search_web":
        query = str(arguments["query"]).strip()
        if not query:
            return "A pesquisa não foi aberta porque a consulta está vazia."
        if len(query) > 300:
            return "A pesquisa não foi aberta: limite de 300 caracteres."
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
        return f"Abri uma pesquisa no navegador por: {query}"

    if name == "open_website":
        raw_url = str(arguments["url"]).strip()
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            return "URL recusada. Só posso abrir um endereço público HTTP ou HTTPS válido."
        if len(raw_url) > 2048:
            return "URL recusada: endereço muito longo."
        webbrowser.open(raw_url)
        return f"Solicitei ao navegador a abertura de {parsed.netloc}."

    if name == "get_current_datetime":
        now = datetime.now().astimezone()
        return f"Data local: {now:%d/%m/%Y}; hora local: {now:%H:%M:%S}; fuso: {now:%z}."

    if name == "open_known_folder":
        key = str(arguments["folder"])
        folders = _standard_folders()
        folder = folders.get(key)
        if folder is None:
            return "Pasta recusada: escolha desktop, documents ou downloads."
        if not folder.exists():
            return f"A pasta padrão {key} ainda não existe neste perfil do Windows."
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)], shell=False)
            else:
                subprocess.Popen(["xdg-open", str(folder)], shell=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return f"Não consegui abrir a pasta: {exc}"
        return f"Abri a pasta {folder}."

    if name == "create_note":
        title = str(arguments["title"]).strip()
        content = str(arguments["content"]).strip()
        if not title or not content:
            return "Não criei a nota: título e conteúdo são obrigatórios."
        if len(title) > 100 or len(content) > 20000:
            return "Não criei a nota: o título pode ter até 100 caracteres e o texto até 20.000."
        slug = re.sub(r"[^\w -]", "", title, flags=re.UNICODE).strip()
        slug = re.sub(r"[\s-]+", "-", slug).strip("-")[:70] or "nota"
        folder = Path.home() / "Documents" / "AURIX Notes"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = folder / f"{timestamp}-{slug}.txt"
            path.write_text(content + "\n", encoding="utf-8", newline="\n")
        except OSError as exc:
            return f"Não consegui salvar a nota: {exc}"
        return f"Nota salva em {path}. Uma nota nova foi criada; arquivos existentes não foram alterados."

    return "Ação recusada: ferramenta ainda não implementada."
