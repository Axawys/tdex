"""Модальные окна: информация, «не установлено», аргументы запуска, справка, сообщения."""

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

from .. import system
from ..catalog import Tool
from . import details
from .text import text_width, truncate, wrap
from .widgets import Line, LineEdit, border_label, box, clear_rect, put, put_line

if TYPE_CHECKING:
    from .app import App

Hints = list[tuple[str, str]]


class Dialog:
    title = ""
    max_width = 70

    def __init__(self) -> None:
        self.scroll = 0
        self.max_scroll = 0

    # --- переопределяемое ------------------------------------------------------

    def body(self, app: "App", width: int) -> list[Line]:
        return []

    def footer(self, app: "App") -> Hints:
        return [("Esc", "Закрыть")]

    def extra_height(self) -> int:
        """Строки под телом, которые не прокручиваются (например, поле ввода)."""
        return 0

    def draw_extra(self, app: "App", win, y: int, x: int, width: int) -> None:
        pass

    def handle(self, app: "App", key: str) -> None:
        if not self.scroll_key(key):
            app.close_dialog()

    # --- общее -------------------------------------------------------------------

    def scroll_key(self, key: str) -> bool:
        if self.max_scroll == 0:
            return False
        steps = {"up": -1, "k": -1, "down": 1, "j": 1, "pgup": -10, "pgdn": 10}
        if key not in steps:
            return False
        self.scroll = max(0, min(self.max_scroll, self.scroll + steps[key]))
        return True

    def draw(self, app: "App", win) -> None:
        th = app.theme
        screen_h, screen_w = win.getmaxyx()
        width = min(self.max_width, screen_w - 4)
        inner = width - 4
        lines = self.body(app, inner)
        extra = self.extra_height()
        # рамка(2) + пустые строки сверху и перед подсказкой(2) + подсказка(1)
        chrome = 5 + extra
        height = min(len(lines) + chrome, screen_h - 2)
        visible = max(0, height - chrome)
        self.max_scroll = max(0, len(lines) - visible)
        self.scroll = min(self.scroll, self.max_scroll)

        y = (screen_h - height) // 2
        x = (screen_w - width) // 2
        clear_rect(win, y, x, height, width)
        box(win, y, x, height, width, th.border)
        title = truncate(self.title, width - 8)
        border_label(win, y, x + (width - text_width(title) - 2) // 2, title, th.heading, width - 4)

        for row, line in enumerate(lines[self.scroll: self.scroll + visible]):
            put_line(win, y + 2 + row, x + 2, line, inner)
        if self.scroll > 0:
            put(win, y + 1, x + width - 2, "▲", th.dim)
        if self.scroll < self.max_scroll:
            put(win, y + 2 + visible - 1, x + width - 2, "▼", th.dim)

        self.draw_extra(app, win, y + 2 + visible, x + 2, inner)
        draw_hints(app, win, y + height - 2, x + 2, inner, self.footer(app))


def draw_hints(app: "App", win, y: int, x: int, width: int, hints: Hints) -> None:
    """Подсказки вида «[Enter] Запустить  [Esc] Назад»; не влезающие отбрасываются."""
    th = app.theme
    used = 0
    for key, label in hints:
        chunk = text_width(key) + 3 + text_width(label) + 2
        if used + chunk - 2 > width:
            break
        put(win, y, x + used, f"[{key}]", th.accent)
        put(win, y, x + used + text_width(key) + 3, label)
        used += chunk


class MessageDialog(Dialog):
    def __init__(self, title: str, text: str, error: bool = False):
        super().__init__()
        self.title = title
        self.text = text
        self.error = error

    def body(self, app: "App", width: int) -> list[Line]:
        attr = app.theme.error if self.error else 0
        return details.paragraph(self.text, width, attr)

    def footer(self, app: "App") -> Hints:
        return [("любая клавиша", "Закрыть")]


class InfoDialog(Dialog):
    def __init__(self, tool: Tool):
        super().__init__()
        self.tool = tool
        self.title = tool.name
        # Статус проверяется в момент открытия окна, а не берётся из кэша.
        self.status = system.check(tool)

    def body(self, app: "App", width: int) -> list[Line]:
        return details.tool_lines(app, self.tool, width, status=self.status)

    def footer(self, app: "App") -> Hints:
        if self.tool.builtin:
            return [("Enter", "Справка"), ("Esc", "Назад"), ("m", "man")]
        return [("Enter", "Запустить"), ("Esc", "Назад"), ("a", "Аргументы"), ("m", "man")]

    def handle(self, app: "App", key: str) -> None:
        if self.scroll_key(key):
            return
        if key == "enter":
            app.close_dialog()
            app.activate(self.tool)
        elif key == "a" and not self.tool.builtin:
            app.close_dialog()
            app.activate(self.tool, prompt=True)
        elif key == "m":
            app.close_dialog()
            app.open_man(self.tool)
        elif key in ("esc", "q", "i", "backspace", "left", "h"):
            app.close_dialog()


class NotInstalledDialog(Dialog):
    title = "Утилита не установлена"

    def __init__(self, tool: Tool):
        super().__init__()
        self.tool = tool

    def body(self, app: "App", width: int) -> list[Line]:
        th = app.theme
        tool = self.tool
        lines: list[Line] = details.paragraph(f"{tool.name} не найден в системе.", width, th.error)
        lines.append([])
        lines.extend(details.field("Команда:", tool.command, width, th.bold))
        if tool.aliases:
            lines.extend(details.field("Также:", ", ".join(tool.aliases), width))
        lines.append([])
        lines.append([("Установка:", th.heading)])
        lines.append([])
        for key, command in tool.install.items():
            mine = system.key_matches_family(key, app.family)
            label: Line = [("  " + system.install_label(key) + ":", th.accent if mine else th.bold)]
            if mine:
                label.append(("  ← ваша система", th.dim))
            lines.append(label)
            lines.extend(details.paragraph(command, width, th.bold if mine else 0, indent=4))
            lines.append([])
        if tool.notes:
            lines.extend(details.paragraph(tool.notes, width, th.accent))
            lines.append([])
        lines.extend(details.paragraph("Команды установки не выполняются автоматически — "
                                       "скопируйте нужную и запустите сами.", width, th.dim))
        return lines

    def footer(self, app: "App") -> Hints:
        return [("любая клавиша", "Вернуться")]


class ArgsDialog(Dialog):
    """Ввод аргументов перед запуском. Команда выполняется без оболочки."""

    max_width = 76

    def __init__(self, tool: Tool, resolution: system.Resolution):
        super().__init__()
        self.tool = tool
        self.resolution = resolution
        self.title = f"Запуск: {tool.name}"
        self.edit = LineEdit(shlex.join(tool.args))
        self.error = ""

    def body(self, app: "App", width: int) -> list[Line]:
        th = app.theme
        lines = details.field("Файл:", self.resolution.path, width, th.bold)
        lines.append([])
        lines.extend(details.paragraph(
            "Аргументы разбираются по правилам кавычек shell, но программа запускается "
            "напрямую, без оболочки: *, |, >, $VAR не раскрываются (~ в начале аргумента раскрывается).",
            width, th.dim))
        if self.tool.notes:
            lines.append([])
            lines.extend(details.paragraph(self.tool.notes, width, th.accent))
        return lines

    def extra_height(self) -> int:
        return 3

    def draw_extra(self, app: "App", win, y: int, x: int, width: int) -> None:
        th = app.theme
        prompt = f"$ {self.resolution.name} "
        prompt = truncate(prompt, max(4, width // 2))
        used = put(win, y + 1, x, prompt, th.accent)
        self.edit.draw(win, y + 1, x + used, width - used, th.input, th.selected)
        if self.error:
            put(win, y + 2, x, truncate(self.error, width), th.error)

    def footer(self, app: "App") -> Hints:
        return [("Enter", "Запустить"), ("Esc", "Отмена"), ("Ctrl+U", "Очистить")]

    def handle(self, app: "App", key: str) -> None:
        if key == "esc":
            app.close_dialog()
        elif key == "enter":
            try:
                args = parse_args(self.edit.text)
            except ValueError as exc:
                self.error = f"Ошибка разбора аргументов: {exc}"
                return
            app.close_dialog()
            app.launch(self.tool, args)
        elif self.edit.handle(key):
            self.error = ""


def parse_args(text: str) -> list[str]:
    """Разбор строки аргументов без участия оболочки."""
    args = shlex.split(text)
    return [os.path.expanduser(a) if a == "~" or a.startswith("~/") else a for a in args]


class HelpDialog(Dialog):
    title = "Справка"
    max_width = 72

    SECTIONS = [
        ("Навигация", [
            ("↑ ↓  j k", "перемещение по списку"),
            ("PgUp PgDn", "на страницу вверх / вниз"),
            ("Home End  g G", "в начало / в конец списка"),
            ("Enter  →", "выбрать категорию / запустить программу"),
            ("Esc  ←  Backspace", "вернуться назад"),
            ("Tab", "переключить режим USER / SYSTEM"),
        ]),
        ("Действия", [
            ("i", "информация о выбранной программе"),
            ("a", "запустить с вводом аргументов"),
            ("m", "открыть man-страницу"),
            ("/", "поиск по текущему режиму"),
            ("r", "заново проверить установленные программы"),
            ("?  F1", "эта справка"),
            ("q", "выход"),
        ]),
        ("Поиск", [
            ("Ввод текста", "фильтр по имени, описанию, категории, тегам"),
            ("↓  Enter", "перейти к результатам"),
            ("/", "вернуться к редактированию запроса"),
            ("Ctrl+U  Ctrl+W", "очистить строку / удалить слово"),
        ]),
    ]

    def body(self, app: "App", width: int) -> list[Line]:
        th = app.theme
        key_w = 20
        lines: list[Line] = []
        for title, rows in self.SECTIONS:
            lines.append([(title, th.heading)])
            for keys, text in rows:
                parts = wrap(text, max(10, width - key_w - 2))
                lines.append([("  " + keys.ljust(key_w), th.accent), (parts[0], 0)])
                lines.extend([[(" " * (key_w + 2) + part, 0)] for part in parts[1:]])
            lines.append([])
        lines.append([("Обозначения", th.heading)])
        lines.append([("  ● ", th.ok), ("установлена (найдена в $PATH)", 0)])
        lines.append([("  ○ ", th.missing), ("не установлена", 0)])
        lines.append([("  ◆ ", th.builtin), ("встроенная команда оболочки (Enter — справка help)", 0)])
        lines.append([])
        lines.append([("Каталог", th.heading)])
        for path in app.catalog_paths:
            lines.extend(details.paragraph(str(path), width, th.dim, indent=2))
        return lines

    def footer(self, app: "App") -> Hints:
        return [("↑↓", "Прокрутка"), ("любая клавиша", "Закрыть")]
