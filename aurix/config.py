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

    wake_word_enabled: bool = False
    tts_enabled: bool = True
    start_with_windows: bool = False
    wake_threshold: float = 0.55
    first_run_complete: bool = False
    llm_provider: str = "ollama"
    ollama_model: str = "qwen2.5:7b"
    model_migrated: bool = False
    speech_provider: str = "vosk"
    vosk_model_path: str = ""

    @classmethod
    def load(cls) -> "Settings":
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            raw: Any = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except (OSError, json.JSONDecodeError):
            raw = {}
        allowed = set(cls.__dataclass_fields__)
        values = {key: value for key, value in raw.items() if key in allowed}

        if values.get("ollama_model") == "llama3.2" and not values.get("model_migrated", False):
            values["ollama_model"] = "qwen2.5:7b"
            values["model_migrated"] = True
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
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    current = Path(sys.executable)
    windowless = current.with_name("pythonw.exe")
    executable = windowless if sys.platform == "win32" and windowless.exists() else current
    launcher = PROJECT_ROOT / "run_aurix.py"
    if launcher.is_file():
        return f'"{executable}" "{launcher}" --background'
    return f'"{executable}" -m aurix --background'


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


def configure_runtime_settings(settings: Settings) -> None:
    """Load preferences and retrieve API credentials from the OS credential store."""
    os.environ["AURIX_LLM_PROVIDER"] = settings.llm_provider
    os.environ["AURIX_OLLAMA_MODEL"] = settings.ollama_model or "llama3.2"
    os.environ["AURIX_SPEECH_PROVIDER"] = settings.speech_provider or "vosk"
    if settings.vosk_model_path:
        os.environ["AURIX_VOSK_MODEL_PATH"] = settings.vosk_model_path
    else:
        os.environ.pop("AURIX_VOSK_MODEL_PATH", None)

    if settings.llm_provider == "openai":
        try:
            import keyring

            secret = keyring.get_password("AURIX AI", "openai_api_key")
            if secret:
                os.environ["OPENAI_API_KEY"] = secret
        except Exception:
            # Keep an explicitly supplied environment/.env key as a development fallback.
            pass
