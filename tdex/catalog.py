"""Загрузка, проверка и поиск по каталогу утилит.

Каталог — это JSON-файл вида ``{"tools": [...]}`` (или просто список записей).
Модуль ничего не знает об интерфейсе: он только превращает JSON в объекты
``Tool`` и отвечает на вопросы «какие категории есть в режиме» и «что
подходит под запрос».
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

MODES = ("user", "system")
REQUIRED_FIELDS = ("name", "command", "mode", "category", "description", "install")

# Имя исполняемого файла: без пробелов и спецсимволов оболочки.
# Аргументы задаются отдельным полем "args", конвейеры не поддерживаются намеренно.
_COMMAND_RE = re.compile(r"^[^\s|&;<>()$`\\\"']+$")


class CatalogError(Exception):
    """Ошибка чтения или проверки файла каталога."""


@dataclass(frozen=True)
class Tool:
    name: str
    command: str
    mode: str
    category: str
    description: str
    install: dict[str, str] = field(hash=False, compare=False)
    aliases: tuple[str, ...] = ()
    args: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    builtin: bool = False
    pause: bool = False
    prompt_args: bool = False
    notes: str = ""
    url: str = ""
    source: str = field(default="", compare=False)

    @property
    def key(self) -> tuple[str, str]:
        return (self.mode, self.name)

    @property
    def executables(self) -> tuple[str, ...]:
        """Имена исполняемых файлов в порядке предпочтения."""
        return (self.command, *self.aliases)


def _where(source: str, index: int, name: Any = None) -> str:
    label = f"{source}: запись #{index + 1}"
    if isinstance(name, str) and name:
        label += f" ({name})"
    return label


def _str_list(raw: dict, key: str, where: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CatalogError(f"{where}: поле '{key}' должно быть списком строк")
    return tuple(value)


def _bool(raw: dict, key: str, default: bool, where: str) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise CatalogError(f"{where}: поле '{key}' должно быть true или false")
    return value


def parse_tool(raw: Any, source: str, index: int) -> Tool:
    """Проверяет одну запись каталога и превращает её в ``Tool``."""
    if not isinstance(raw, dict):
        raise CatalogError(f"{_where(source, index)}: запись должна быть объектом")
    where = _where(source, index, raw.get("name"))

    missing = [k for k in REQUIRED_FIELDS if k not in raw]
    if missing:
        raise CatalogError(f"{where}: нет обязательных полей: {', '.join(missing)}")

    for key in ("name", "command", "mode", "category", "description"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise CatalogError(f"{where}: поле '{key}' должно быть непустой строкой")

    mode = raw["mode"].strip().lower()
    if mode not in MODES:
        raise CatalogError(f"{where}: неизвестный режим '{raw['mode']}' (допустимо: {', '.join(MODES)})")

    aliases = _str_list(raw, "aliases", where)
    for cmd in (raw["command"], *aliases):
        if not _COMMAND_RE.match(cmd):
            raise CatalogError(
                f"{where}: '{cmd}' не похоже на имя исполняемого файла; "
                "аргументы указываются в поле 'args'"
            )

    install = raw["install"]
    if not isinstance(install, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in install.items()
    ):
        raise CatalogError(f"{where}: поле 'install' должно быть объектом {{система: команда}}")

    builtin = _bool(raw, "builtin", False, where)
    if not install and not builtin:
        raise CatalogError(f"{where}: не указано ни одной команды установки")

    for key in ("notes", "url"):
        if not isinstance(raw.get(key, ""), str):
            raise CatalogError(f"{where}: поле '{key}' должно быть строкой")

    # Системные утилиты почти всегда требуют аргументов и печатают результат
    # и выходят, поэтому для них по умолчанию спрашиваем аргументы и ждём Enter.
    is_system = mode == "system"
    return Tool(
        name=raw["name"].strip(),
        command=raw["command"].strip(),
        mode=mode,
        category=raw["category"].strip(),
        description=raw["description"].strip(),
        install=dict(install),
        aliases=aliases,
        args=_str_list(raw, "args", where),
        tags=_str_list(raw, "tags", where),
        builtin=builtin,
        pause=_bool(raw, "pause", is_system, where),
        prompt_args=_bool(raw, "prompt_args", is_system, where),
        notes=raw.get("notes", "").strip(),
        url=raw.get("url", "").strip(),
        source=source,
    )


def load_file(path: str | os.PathLike) -> list[Tool]:
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise CatalogError(f"{path}: файл не найден") from None
    except OSError as exc:
        raise CatalogError(f"{path}: {exc.strerror}") from None
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{path}: ошибка JSON в строке {exc.lineno}, столбце {exc.colno}: {exc.msg}") from None

    if isinstance(data, dict):
        entries = data.get("tools")
    else:
        entries = data
    if not isinstance(entries, list):
        raise CatalogError(f"{path}: ожидается список записей или объект с ключом 'tools'")
    return [parse_tool(raw, str(path), i) for i, raw in enumerate(entries)]


def builtin_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "catalog.json"


def user_catalog_paths() -> list[Path]:
    """Пользовательские дополнения: $XDG_CONFIG_HOME/tdex/catalog.d/*.json."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    directory = Path(base) / "tdex" / "catalog.d"
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.json") if p.is_file())


def normalize(text: str) -> str:
    return text.casefold().replace("ё", "е")


class Catalog:
    def __init__(self, tools: Iterable[Tool]):
        # Более поздняя запись с тем же (mode, name) заменяет раннюю,
        # сохраняя её место — так пользовательские файлы переопределяют встроенный.
        by_key: dict[tuple[str, str], Tool] = {}
        for tool in tools:
            by_key[tool.key] = tool
        self.tools: list[Tool] = list(by_key.values())

    @classmethod
    def load(cls, paths: Iterable[str | os.PathLike]) -> "Catalog":
        tools: list[Tool] = []
        for path in paths:
            tools.extend(load_file(path))
        return cls(tools)

    def __len__(self) -> int:
        return len(self.tools)

    def tools_for_mode(self, mode: str) -> list[Tool]:
        return [t for t in self.tools if t.mode == mode]

    def categories(self, mode: str) -> list[str]:
        """Категории режима в порядке первого появления в каталоге."""
        seen: dict[str, None] = {}
        for tool in self.tools_for_mode(mode):
            seen.setdefault(tool.category, None)
        return list(seen)

    def tools_in(self, mode: str, category: str) -> list[Tool]:
        return [t for t in self.tools if t.mode == mode and t.category == category]

    def search(self, mode: str, query: str) -> list[Tool]:
        """Ищет по имени, команде, тегам, категории и описанию в пределах режима.

        Запрос разбивается на слова; каждое слово должно где-то встретиться.
        Совпадения по имени ранжируются выше, чем по описанию.
        """
        terms = normalize(query).split()
        if not terms:
            return []
        scored = []
        for order, tool in enumerate(self.tools_for_mode(mode)):
            score = _score(tool, terms)
            if score is not None:
                scored.append((-score, order, tool))
        scored.sort(key=lambda item: (item[0], item[1]))
        return [tool for _, _, tool in scored]


def _score(tool: Tool, terms: list[str]) -> int | None:
    name = normalize(tool.name)
    commands = [normalize(c) for c in tool.executables]
    tags = [normalize(t) for t in tool.tags]
    category = normalize(tool.category)
    text = normalize(tool.description + " " + tool.notes)

    total = 0
    for term in terms:
        if term == name or term in commands:
            best = 100
        elif name.startswith(term) or any(c.startswith(term) for c in commands):
            best = 60
        elif term in name or any(term in c for c in commands):
            best = 40
        elif term in tags:
            best = 30
        elif any(term in t for t in tags):
            best = 25
        elif term in category:
            best = 15
        elif term in text:
            best = 10
        else:
            return None
        total += best
    return total
