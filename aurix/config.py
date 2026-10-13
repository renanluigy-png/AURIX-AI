"""User settings, environment loading, and Windows startup integration."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Support both launching from the checkout and Windows startup with a different CWD.
_ENV_FILE = Path.cwd() / ".env"
if not _ENV_FILE.is_file():
    _ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(_ENV_FILE, override=False)

APP_NAME = "AURIX AI"
APP_DATA_DIR = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "AurixAI"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
LOG_PATH = APP_DATA_DIR / "aurix.log"


@dataclass
class Settings:
    """Persisted, non-secret user preferences."""

    wake_word_enabled: bool = True
    tts_enabled: bool = True
    start_with_windows: bool = False
    wake_threshold: float = 0.55

    @classmethod
    def load(cls) -> "Settings":
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            raw: dict[str, Any] = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        allowed = set(cls.__dataclass_fields__)
        values = {key: value for key, value in raw.items() if key in allowed}
        try:
            settings = cls(**values)
            env_threshold = os.getenv("AURIX_WAKE_THRESHOLD")
            settings.wake_threshold = max(
                0.1,
                min(0.95, float(env_threshold if env_threshold is not None else settings.wake_threshold)),
            )
            return settings
        except (TypeError, ValueError):
            return cls()

    def save(self) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = SETTINGS_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(SETTINGS_PATH)


def _startup_command() -> str:
    """Run the source checkout directly; pythonw keeps a console window hidden."""
    current = Path(sys.executable)
    windowless = current.with_name("pythonw.exe")
    executable = windowless if sys.platform == "win32" and windowless.exists() else current
    launcher = PROJECT_ROOT / "run_aurix.py"
    if launcher.is_file():
        return f'"{executable}" "{launcher}"'
    return f'"{executable}" -m aurix'


def is_start_with_windows_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AURIX AI")
        return str(value) == _startup_command()
    except (OSError, ImportError):
        return False


def set_start_with_windows(enabled: bool) -> tuple[bool, str]:
    """Add or remove the current-user startup entry; never requires admin rights."""
    if sys.platform != "win32":
        return False, "A inicialização automática só é configurada no Windows."

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, "AURIX AI", 0, winreg.REG_SZ, _startup_command())
            else:
                try:
                    winreg.DeleteValue(key, "AURIX AI")
                except FileNotFoundError:
                    pass
        return True, "Preferência de inicialização atualizada."
    except (OSError, ImportError) as exc:
        return False, f"Não foi possível atualizar a inicialização: {exc}"
