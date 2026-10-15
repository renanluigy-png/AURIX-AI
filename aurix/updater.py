"""Check trusted GitHub Releases and download verified AURIX Windows updates."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal

from aurix.build_info import APP_VERSION
from aurix.config import APP_DATA_DIR
from aurix.versioning import is_newer_version

REPOSITORY = "renanluigy-png/AURIX-AI"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
INSTALLER_ASSET_NAME = "AURIX-AI-Setup.exe"
MAX_INSTALLER_BYTES = 1024 * 1024 * 1024


def _request(url: str, *, timeout: float = 6.0) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AURIX-AI-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )


def _trusted_asset(release: dict) -> tuple[str, str]:
    """Return the published installer URL and an optional GitHub SHA-256 digest."""
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ValueError("A publicação não contém uma lista de arquivos.")

    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") != INSTALLER_ASSET_NAME:
            continue
        url = str(asset.get("browser_download_url") or "")
        expected_prefix = f"https://github.com/{REPOSITORY}/releases/download/"
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc.casefold() != "github.com"
            or not parsed.path.startswith(f"/{REPOSITORY}/releases/download/")
            or not url.startswith(expected_prefix)
            or parsed.username
            or parsed.password
        ):
            raise ValueError("O endereço do instalador não pertence ao repositório oficial.")
        digest = str(asset.get("digest") or "")
        if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
            digest = ""
        return url, digest
    raise ValueError("Não encontrei AURIX-AI-Setup.exe na versão publicada.")


class UpdateCheckWorker(QThread):
    """Checks the latest stable GitHub release without blocking the user interface."""

    update_available = Signal(str, str, str, str, str)
    up_to_date = Signal(str)
    check_failed = Signal(str)

    def run(self) -> None:
        try:
            with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=6) as response:
                release = json.loads(response.read().decode("utf-8"))
            if not isinstance(release, dict):
                raise ValueError("Resposta de publicação inválida.")

            tag = str(release.get("tag_name") or "")
            remote_version = tag[1:] if tag.lower().startswith("v") else tag
            if not is_newer_version(remote_version, APP_VERSION):
                self.up_to_date.emit(APP_VERSION)
                return

            asset_url, digest = _trusted_asset(release)
            name = str(release.get("name") or f"AURIX AI {tag}")
            notes = str(release.get("body") or "").strip()
            self.update_available.emit(remote_version, name, notes[:5000], asset_url, digest)
        except urllib.error.HTTPError as exc:
            message = (
                "Ainda não existe uma versão publicada para o atualizador."
                if exc.code == 404
                else f"O GitHub respondeu com HTTP {exc.code}."
            )
            logging.info("Update check unavailable: %s", message)
            self.check_failed.emit(message)
        except Exception as exc:
            logging.info("Update check failed: %s", exc)
            self.check_failed.emit(str(exc).splitlines()[0][:240])


class UpdateDownloadWorker(QThread):
    """Download the user's chosen installer from an official release URL."""

    progress_changed = Signal(int)
    download_ready = Signal(str)
    download_failed = Signal(str)
    download_cancelled = Signal()

    def __init__(self, url: str, digest: str = "", parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self.digest = digest
        self.destination = APP_DATA_DIR / "updates" / INSTALLER_ASSET_NAME

    def run(self) -> None:
        temporary = self.destination.with_suffix(".exe.download")
        try:
            expected_prefix = f"https://github.com/{REPOSITORY}/releases/download/"
            parsed = urlparse(self.url)
            if (
                parsed.scheme != "https"
                or parsed.netloc.casefold() != "github.com"
                or not parsed.path.startswith(f"/{REPOSITORY}/releases/download/")
                or not self.url.startswith(expected_prefix)
            ):
                raise ValueError("O download não veio de uma publicação oficial do AURIX.")

            self.destination.parent.mkdir(parents=True, exist_ok=True)
            bytes_written = 0
            sha256 = hashlib.sha256()
            with urllib.request.urlopen(_request(self.url, timeout=15), timeout=15) as response:
                length_text = response.headers.get("Content-Length")
                total = int(length_text) if length_text and length_text.isdigit() else 0
                if total > MAX_INSTALLER_BYTES:
                    raise ValueError("O instalador é maior que o limite permitido.")
                with temporary.open("wb") as output:
                    while True:
                        if self.isInterruptionRequested():
                            raise InterruptedError("Download cancelado pelo usuário.")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        bytes_written += len(chunk)
                        if bytes_written > MAX_INSTALLER_BYTES:
                            raise ValueError("O download excedeu o limite permitido.")
                        output.write(chunk)
                        sha256.update(chunk)
                        if total:
                            self.progress_changed.emit(min(100, int(bytes_written * 100 / total)))

            if self.isInterruptionRequested():
                raise InterruptedError("Download cancelado pelo usuário.")
            if bytes_written < 1024 * 1024:
                raise ValueError("O arquivo baixado é menor do que o esperado.")
            with temporary.open("rb") as downloaded:
                if downloaded.read(2) != b"MZ":
                    raise ValueError("O arquivo baixado não parece ser um executável Windows válido.")

            if self.digest:
                expected = self.digest.split(":", 1)[1].lower()
                if sha256.hexdigest().lower() != expected:
                    raise ValueError("A verificação SHA-256 do instalador falhou. O arquivo não será executado.")

            os.replace(temporary, self.destination)
            self.progress_changed.emit(100)
            self.download_ready.emit(str(self.destination))
        except InterruptedError:
            self.download_cancelled.emit()
        except Exception as exc:
            logging.exception("AURIX update download failed")
            self.download_failed.emit(str(exc).splitlines()[0][:300])
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
