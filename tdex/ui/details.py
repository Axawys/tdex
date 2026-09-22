"""Построение текстовых блоков с описанием утилит и категорий.

Используется и боковой панелью, и окном информации (клавиша i).
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from .. import system
from ..catalog import Tool
from .text import text_width, truncate, wrap
from .widgets import Line

if TYPE_CHECKING:
    from .app import App

LABEL_WIDTH = 11


def marker(app: "App", tool: Tool, status: system.Status | None = None) -> tuple[str, int]:
    status = status or app.status.get(tool)
    th = app.theme
    if status.kind == system.INSTALLED:
        return "●", th.ok
    if status.kind == system.BUILTIN:
        return "◆", th.builtin
    return "○", th.missing


def status_text(status: system.Status) -> str:
    return {
        system.INSTALLED: "Установлена",
        system.BUILTIN: "Встроенная команда оболочки",
        system.MISSING: "Не установлена",
    }[status.kind]


def paragraph(text: str, width: int, attr: int = 0, indent: int = 0) -> list[Line]:
    return [[(" " * indent + part, attr)] for part in wrap(text, width - indent)]


def field(label: str, value: str, width: int, value_attr: int = 0, label_attr: int = 0) -> list[Line]:
    """«Метка:  значение» с переносом значения под значение, а не под метку."""
    label_col = max(LABEL_WIDTH, text_width(label) + 1)
    parts = wrap(value, max(8, width - label_col))
    lines: list[Line] = [[(label.ljust(label_col), label_attr), (parts[0], value_attr)]]
    lines.extend([[(" " * label_col + part, value_attr)] for part in parts[1:]])
    return lines


def install_lines(app: "App", tool: Tool, width: int, indent: int = 2) -> list[Line]:
    th = app.theme
    lines: list[Line] = []
    if not tool.install:
        return lines
    labels = {key: system.install_label(key) + ":" for key in tool.install}
    label_col = max(text_width(label) for label in labels.values()) + 2
    for key, command in tool.install.items():
        mine = system.key_matches_family(key, app.family)
        label_attr = th.accent if mine else th.heading & ~th.bold
        cmd_attr = th.bold if mine else 0
        suffix = [("  ← ваша система", th.dim)] if mine else []
        if indent + label_col + text_width(command) <= width:
            lines.append([(" " * indent + labels[key].ljust(label_col), label_attr), (command, cmd_attr)] + suffix)
        else:
            lines.append([(" " * indent + labels[key], label_attr)] + suffix)
            lines.extend(paragraph(command, width, cmd_attr, indent + 2))
    return lines


def tool_lines(app: "App", tool: Tool, width: int, *, status: system.Status | None = None,
               title: bool = False) -> list[Line]:
    th = app.theme
    status = status or app.status.get(tool)
    lines: list[Line] = []
    if title:
        lines.append([(truncate(tool.name, width), th.heading)])
        lines.append([])
    lines.extend(paragraph(tool.description, width))
    lines.append([])

    command = tool.command
    if tool.aliases:
        command += f"  (или {', '.join(tool.aliases)})"
    lines.extend(field("Команда:", command, width, th.bold))
    if status.resolution:
        lines.extend(field("Путь:", status.resolution.path, width))
    lines.extend(field("Категория:", tool.category, width))
    lines.extend(field("Режим:", tool.mode.upper(), width))
    symbol, attr = marker(app, tool, status)
    lines.extend(field("Статус:", f"{symbol} {status_text(status)}", width, attr))
    if tool.args:
        lines.extend(field("Аргументы:", shlex.join(tool.args), width))
    if tool.url:
        lines.extend(field("Сайт:", tool.url, width))
    if tool.notes:
        lines.append([])
        lines.extend(paragraph(tool.notes, width, th.accent))

    if tool.install:
        lines.append([])
        lines.append([("Установка:", th.heading)])
        lines.extend(install_lines(app, tool, width))
    return lines


def category_lines(app: "App", mode: str, category: str, width: int) -> list[Line]:
    th = app.theme
    tools = app.catalog.tools_in(mode, category)
    available, total = app.status.count(tools)
    lines: list[Line] = [
        [(truncate(category, width), th.heading)],
        [(f"Доступно: {available} из {total}", th.dim)],
        [],
    ]
    name_w = min(max(text_width(t.name) for t in tools), 18) if tools else 0
    for tool in tools:
        symbol, attr = marker(app, tool)
        name = truncate(tool.name, name_w).ljust(name_w)
        rest = width - name_w - 4
        line: Line = [(symbol + " ", attr), (name, 0)]
        if rest > 6:
            line.append(("  " + truncate(tool.description, rest), th.dim))
        lines.append(line)
    return lines
