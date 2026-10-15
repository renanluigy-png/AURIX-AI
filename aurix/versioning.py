"""Dependency-free helpers for comparing AURIX release versions."""

from __future__ import annotations

import re


def version_key(value: str) -> tuple[int, ...]:
    """Parse the numeric prefix of a version such as v1.12.0; invalid values return ()."""
    match = re.match(r"^\s*[vV]?(\d+(?:\.\d+)*)", str(value))
    if not match:
        return ()
    try:
        return tuple(int(part) for part in match.group(1).split("."))
    except ValueError:
        return ()


def is_newer_version(remote: str, current: str) -> bool:
    """Return true only when remote is a valid, strictly newer numeric version."""
    remote_key = version_key(remote)
    current_key = version_key(current)
    if not remote_key or not current_key:
        return False
    width = max(len(remote_key), len(current_key))
    remote_key += (0,) * (width - len(remote_key))
    current_key += (0,) * (width - len(current_key))
    return remote_key > current_key
