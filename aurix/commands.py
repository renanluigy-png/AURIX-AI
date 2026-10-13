"""Safe, deterministic local commands.

Only the actions declared in APP_ALIASES and parse_command can be executed.
This module intentionally does not expose an arbitrary shell or Python executor.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unicodedata
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    argument: str = ""


@dataclass(frozen=True)
class AppTarget:
    kind: str
    value: str
    fallback_url: str = ""


APP_ALIASES: dict[str, str] = {
    "visual studio code": "vscode",
    "google chrome": "chrome",
    "microsoft edge": "edge",
    "explorador de arquivos": "explorer",
    "bloco de notas": "notepad",
    "calculadora": "calculator",
    "vs code": "vscode",
    "vscode": "vscode",
    "whatsapp": "whatsapp",
    "spotify": "spotify",
    "discord": "discord",
    "chrome": "chrome",
    "navegador": "browser",
    "browser": "browser",
    "edge": "edge",
    "explorador": "explorer",
    "pastas": "explorer",
    "notepad": "notepad",
    "calculator": "calculator",
    "terminal": "terminal",
    "powershell": "terminal",
}

APP_TARGETS: dict[str, AppTarget] = {
    "spotify": AppTarget("uri", "spotify:", "https://open.spotify.com/"),
    "whatsapp": AppTarget("uri", "whatsapp://", "https://web.whatsapp.com/"),
    "discord": AppTarget("uri", "discord://", "https://discord.com/app"),
    "browser": AppTarget("url", "https://www.google.com/"),
    "chrome": AppTarget("executable", "chrome"),
    "edge": AppTarget("executable", "msedge"),
    "vscode": AppTarget("executable", "code"),
    "explorer": AppTarget("executable", "explorer.exe"),
    "notepad": AppTarget("executable", "notepad.exe"),
    "calculator": AppTarget("executable", "calc.exe"),
    "terminal": AppTarget("executable", "wt.exe"),
}

APP_DISPLAY_NAMES = {
    "spotify": "Spotify",
    "whatsapp": "WhatsApp",
    "discord": "Discord",
    "browser": "navegador",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "vscode": "Visual Studio Code",
    "explorer": "Explorador de Arquivos",
    "notepad": "Bloco de Notas",
    "calculator": "Calculadora",
    "terminal": "Terminal do Windows",
}


def normalize_text(text: str) -> str:
    """Lowercase and remove accents for robust Portuguese command matching."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", unaccented).strip(" \t\r\n.,!?;:")


def _clean_argument(value: str) -> str:
    value = value.strip(" \t\r\n.,!?;:")
    value = re.sub(r"\s+(?:por favor|para mim)$", "", value, flags=re.IGNORECASE)
    return value.strip()


def parse_command(text: str) -> ParsedCommand | None:
    """Recognize a small set of safe local actions from Portuguese or English."""
    normalized = normalize_text(text)
    if not normalized:
        return None

    if re.search(r"\b(que horas sao|horas sao|hora atual|what time is it)\b", normalized):
        return ParsedCommand("time")
    if re.search(r"\b(qual e a data|data de hoje|que dia e hoje|what is the date)\b", normalized):
        return ParsedCommand("date")

    open_match = re.match(
        r"^(?:por favor[,]?\s+)?(?:abra|abrir|abre|inicie|iniciar|inicia|execute|executa|lance|lancar|open|start)\s+"
        r"(?:(?:o|a|os|as)\s+)?(?:(?:aplicativo|app|programa)\s+)?(.+)$",
        normalized,
    )
    if open_match:
        requested = _clean_argument(open_match.group(1))
        for alias in sorted(APP_ALIASES, key=len, reverse=True):
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", requested):
                return ParsedCommand("open_app", APP_ALIASES[alias])
        return None

    search_match = re.match(
        r"^(?:pesquise|pesquisar|pesquisa|procure|procurar|busque|buscar|search)\s+"
        r"(?:(?:por|sobre|na internet|na web|for)\s+)?(.+)$",
        normalized,
    )
    if search_match:
        query = _clean_argument(search_match.group(1))
        if query:
            return ParsedCommand("search_web", query)

    return None


def execute_command(command: ParsedCommand) -> str:
    """Execute a parsed command from the explicit allowlist."""
    if command.name == "time":
        return f"Agora são {datetime.now().strftime('%H:%M')}."
    if command.name == "date":
        return f"Hoje é {datetime.now().strftime('%d/%m/%Y')}."
    if command.name == "search_web":
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(command.argument))
        return f"Pesquisei por “{command.argument}” no navegador."
    if command.name == "open_app":
        return _open_app(command.argument)
    return "Esse comando não está disponível por segurança."


def _resolve_executable(name: str) -> str | None:
    discovered = shutil.which(name)
    if discovered:
        return discovered
    if sys.platform != "win32":
        return None

    local = Path(os.getenv("LOCALAPPDATA", ""))
    program_files = Path(os.getenv("PROGRAMFILES", r"C:\Program Files"))
    program_files_x86 = Path(os.getenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    candidates: dict[str, list[Path]] = {
        "chrome": [
            program_files / "Google/Chrome/Application/chrome.exe",
            program_files_x86 / "Google/Chrome/Application/chrome.exe",
            local / "Google/Chrome/Application/chrome.exe",
        ],
        "msedge": [
            program_files / "Microsoft/Edge/Application/msedge.exe",
            program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
        ],
        "code": [
            local / "Programs/Microsoft VS Code/Code.exe",
            program_files / "Microsoft VS Code/Code.exe",
        ],
    }
    for candidate in candidates.get(name, []):
        if candidate.is_file():
            return str(candidate)

    if name.lower() in {"explorer.exe", "notepad.exe", "calc.exe", "wt.exe"}:
        return name
    return None


def _open_app(name: str) -> str:
    target = APP_TARGETS.get(name)
    if target is None:
        return "Esse aplicativo não está na lista de aplicativos permitidos."

    try:
        if target.kind == "url":
            webbrowser.open(target.value)
        elif target.kind == "uri":
            if sys.platform == "win32":
                try:
                    os.startfile(target.value)  # type: ignore[attr-defined]
                except OSError:
                    if target.fallback_url:
                        webbrowser.open(target.fallback_url)
                    else:
                        raise
            elif target.fallback_url:
                webbrowser.open(target.fallback_url)
            else:
                webbrowser.open(target.value)
        elif target.kind == "executable":
            executable = _resolve_executable(target.value)
            if executable is None:
                return (
                    f"Não encontrei {APP_DISPLAY_NAMES[name]} instalado. "
                    "Confira a instalação ou o PATH do aplicativo."
                )
            subprocess.Popen([executable], shell=False, close_fds=True)
        else:
            return "O tipo de ação não é permitido."
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Não consegui abrir {APP_DISPLAY_NAMES[name]}: {exc}"

    return f"Abrindo {APP_DISPLAY_NAMES[name]}."
