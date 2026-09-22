"""Примитивы отрисовки: безопасный вывод, рамки, прокручиваемые списки, поле ввода."""

from __future__ import annotations

import curses
from dataclasses import dataclass, field

from .text import char_width, text_width, truncate

# Строка с разметкой: последовательность (текст, атрибут).
Segment = tuple[str, int]
Line = list[Segment]


def put(win, y: int, x: int, text: str, attr: int = 0, width: int | None = None) -> int:
    """Выводит текст, обрезая его по краю окна (или по ``width``). Возвращает ширину выведенного."""
    height, max_x = win.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= max_x:
        return 0
    limit = max_x - x if width is None else min(width, max_x - x)
    text = truncate(text, limit, ellipsis="")
    if not text:
        return 0
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        # Запись в правый нижний угол окна двигает курсор за пределы и
        # вызывает ошибку, хотя символ при этом выводится.
        pass
    return text_width(text)


def put_line(win, y: int, x: int, line: Line, width: int) -> None:
    for text, attr in line:
        if width <= 0:
            break
        used = put(win, y, x, text, attr, width)
        x += used
        width -= used


def fill(win, y: int, x: int, width: int, attr: int = 0) -> None:
    if width > 0:
        put(win, y, x, " " * width, attr)


def box(win, y: int, x: int, height: int, width: int, attr: int = 0) -> None:
    if height < 2 or width < 2:
        return
    put(win, y, x, "┌" + "─" * (width - 2) + "┐", attr)
    for row in range(y + 1, y + height - 1):
        put(win, row, x, "│", attr)
        put(win, row, x + width - 1, "│", attr)
    put(win, y + height - 1, x, "└" + "─" * (width - 2) + "┘", attr)


def separator(win, y: int, x: int, width: int, attr: int = 0) -> None:
    put(win, y, x, "├" + "─" * (width - 2) + "┤", attr)


def border_label(win, y: int, x: int, text: str, attr: int, max_width: int) -> int:
    """Надпись, врезанная в горизонтальную линию рамки: ``─ текст ─``."""
    if max_width < 5 or not text:
        return 0
    return put(win, y, x, f" {truncate(text, max_width - 2)} ", attr)


def clear_rect(win, y: int, x: int, height: int, width: int) -> None:
    for row in range(y, y + height):
        fill(win, row, x, width)


@dataclass
class ListState:
    """Выделенный элемент и прокрутка списка."""

    index: int = 0
    offset: int = 0
    count: int = 0

    def set_count(self, count: int) -> None:
        self.count = count
        self.index = max(0, min(self.index, count - 1))

    def move(self, delta: int) -> None:
        if self.count:
            self.index = max(0, min(self.count - 1, self.index + delta))

    def home(self) -> None:
        self.index = 0

    def end(self) -> None:
        self.index = max(0, self.count - 1)

    def scroll_into_view(self, height: int) -> None:
        height = max(1, height)
        if self.index < self.offset:
            self.offset = self.index
        elif self.index >= self.offset + height:
            self.offset = self.index - height + 1
        self.offset = max(0, min(self.offset, max(0, self.count - height)))

    def handle(self, key: str, page: int) -> bool:
        """Общие клавиши навигации. Возвращает True, если клавиша обработана."""
        actions = {
            "up": lambda: self.move(-1), "k": lambda: self.move(-1),
            "down": lambda: self.move(1), "j": lambda: self.move(1),
            "pgup": lambda: self.move(-max(1, page)), "pgdn": lambda: self.move(max(1, page)),
            "home": self.home, "g": self.home,
            "end": self.end, "G": self.end,
        }
        action = actions.get(key)
        if action is None:
            return False
        action()
        return True


def draw_scroll_marks(win, top: int, bottom: int, x: int, state: ListState, height: int, attr: int) -> None:
    if state.offset > 0:
        put(win, top, x, "▲", attr)
    if state.offset + height < state.count:
        put(win, bottom, x, "▼", attr)


@dataclass
class LineEdit:
    """Однострочное поле ввода с курсором и горизонтальной прокруткой."""

    text: str = ""
    cursor: int = field(default=-1)

    def __post_init__(self) -> None:
        if self.cursor < 0 or self.cursor > len(self.text):
            self.cursor = len(self.text)

    def set(self, text: str) -> None:
        self.text = text
        self.cursor = len(text)

    def handle(self, key: str) -> bool:
        """Обрабатывает клавиши редактирования; True, если текст или курсор изменились."""
        if len(key) == 1 and key.isprintable():
            self.text = self.text[: self.cursor] + key + self.text[self.cursor:]
            self.cursor += 1
        elif key == "backspace":
            if self.cursor > 0:
                self.text = self.text[: self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
        elif key == "delete":
            self.text = self.text[: self.cursor] + self.text[self.cursor + 1:]
        elif key == "left":
            self.cursor = max(0, self.cursor - 1)
        elif key == "right":
            self.cursor = min(len(self.text), self.cursor + 1)
        elif key in ("home", "ctrl-a"):
            self.cursor = 0
        elif key in ("end", "ctrl-e"):
            self.cursor = len(self.text)
        elif key == "ctrl-u":
            self.text = self.text[self.cursor:]
            self.cursor = 0
        elif key == "ctrl-k":
            self.text = self.text[: self.cursor]
        elif key == "ctrl-w":
            head = self.text[: self.cursor].rstrip()
            cut = head.rfind(" ") + 1
            self.text = self.text[:cut] + self.text[self.cursor:]
            self.cursor = cut
        else:
            return False
        return True

    def draw(self, win, y: int, x: int, width: int, attr: int, cursor_attr: int, focused: bool = True) -> None:
        if width <= 0:
            return
        fill(win, y, x, width, attr)
        # Первый видимый символ выбираем так, чтобы курсор оставался в поле.
        start = 0
        while text_width(self.text[start: self.cursor]) > width - 1:
            start += 1
        visible = truncate(self.text[start:], width, ellipsis="")
        put(win, y, x, visible, attr)
        if focused:
            cx = x + text_width(self.text[start: self.cursor])
            under = self.text[self.cursor] if self.cursor < len(self.text) else " "
            if char_width(under) == 0:
                under = " "
            put(win, y, cx, under, cursor_attr)
