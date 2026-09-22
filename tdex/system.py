"""Взаимодействие с системой: поиск исполняемых файлов и определение дистрибутива."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .catalog import Tool

INSTALLED = "installed"
MISSING = "missing"
BUILTIN = "builtin"


@dataclass(frozen=True)
class Resolution:
    """Найденный исполняемый файл: имя, под которым он найден, и полный путь."""

    name: str
    path: str


@dataclass(frozen=True)
class Status:
    kind: str
    resolution: Resolution | None = None

    @property
    def available(self) -> bool:
        return self.kind != MISSING


def find_executable(name: str) -> str | None:
    """Аналог ``command -v`` для внешних команд: ищет исполняемый файл в $PATH."""
    return shutil.which(name)


def resolve(tool: Tool) -> Resolution | None:
    """Проверяет наличие утилиты прямо сейчас, без кэша."""
    for name in tool.executables:
        path = find_executable(name)
        if path:
            return Resolution(name, path)
    return None


def check(tool: Tool) -> Status:
    if tool.builtin:
        return Status(BUILTIN)
    resolution = resolve(tool)
    return Status(INSTALLED, resolution) if resolution else Status(MISSING)


class StatusCache:
    """Статусы для отрисовки списков.

    Используется только для отображения ●/○; перед запуском наличие команды
    всегда проверяется заново через ``resolve``.
    """

    def __init__(self) -> None:
        self._statuses: dict[tuple[str, str], Status] = {}

    def scan(self, tools: list[Tool]) -> None:
        self._statuses = {tool.key: check(tool) for tool in tools}

    def get(self, tool: Tool) -> Status:
        status = self._statuses.get(tool.key)
        if status is None:
            status = self._statuses[tool.key] = check(tool)
        return status

    def count(self, tools: list[Tool]) -> tuple[int, int]:
        """(доступно, всего) для набора утилит."""
        return sum(1 for t in tools if self.get(t).available), len(tools)


# --- дистрибутивы ------------------------------------------------------------

_FAMILIES = {
    "arch": {"arch", "manjaro", "endeavouros", "garuda", "artix", "cachyos", "arcolinux"},
    "debian": {"debian", "ubuntu", "linuxmint", "pop", "elementary", "kali", "raspbian", "zorin", "neon"},
    "fedora": {"fedora", "rhel", "centos", "rocky", "almalinux", "nobara", "ultramarine"},
}

# К какому семейству относятся «дополнительные» способы установки.
_KEY_FAMILY = {"aur": "arch"}

INSTALL_LABELS = {
    "arch": "Arch Linux",
    "aur": "Arch Linux (AUR)",
    "debian": "Debian/Ubuntu",
    "fedora": "Fedora",
    "cargo": "Cargo (Rust)",
    "go": "Go",
    "pip": "pip / pipx",
    "npm": "npm",
    "snap": "Snap",
    "flatpak": "Flatpak",
    "nix": "Nix",
    "other": "Другое",
}


def parse_os_release(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip("\"'")
    return result


def detect_family(os_release: str | Path = "/etc/os-release") -> str | None:
    """Возвращает 'arch', 'debian', 'fedora' или None, если семейство неизвестно."""
    try:
        info = parse_os_release(Path(os_release).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    ids = [info.get("ID", "").lower(), *info.get("ID_LIKE", "").lower().split()]
    for ident in ids:
        for family, members in _FAMILIES.items():
            if ident == family or ident in members:
                return family
    return None


def install_label(key: str) -> str:
    return INSTALL_LABELS.get(key, key.capitalize())


def key_matches_family(key: str, family: str | None) -> bool:
    return family is not None and _KEY_FAMILY.get(key, key) == family
