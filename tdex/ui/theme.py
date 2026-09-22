"""Цвета и атрибуты. Без поддержки цвета (или при NO_COLOR) — только bold/reverse/dim."""

from __future__ import annotations

import curses
import os

_PAIRS = {
    # имя: (цвет текста, цвет фона); None — фон терминала по умолчанию
    "title": (curses.COLOR_CYAN, None),
    "user": (curses.COLOR_BLACK, curses.COLOR_GREEN),
    "system": (curses.COLOR_BLACK, curses.COLOR_YELLOW),
    "ok": (curses.COLOR_GREEN, None),
    "missing": (curses.COLOR_RED, None),
    "builtin": (curses.COLOR_YELLOW, None),
    "border": (curses.COLOR_BLUE, None),
    "key": (curses.COLOR_BLACK, curses.COLOR_CYAN),
    "selected": (curses.COLOR_BLACK, curses.COLOR_CYAN),
    "error": (curses.COLOR_RED, None),
    "accent": (curses.COLOR_YELLOW, None),
    "heading": (curses.COLOR_CYAN, None),
    "input": (curses.COLOR_WHITE, curses.COLOR_BLUE),
}

_MONO = {
    "title": curses.A_BOLD,
    "user": curses.A_REVERSE | curses.A_BOLD,
    "system": curses.A_REVERSE | curses.A_BOLD,
    "ok": curses.A_BOLD,
    "missing": curses.A_DIM,
    "builtin": curses.A_NORMAL,
    "border": curses.A_NORMAL,
    "key": curses.A_REVERSE,
    "selected": curses.A_REVERSE,
    "error": curses.A_BOLD,
    "accent": curses.A_BOLD,
    "heading": curses.A_BOLD,
    "input": curses.A_UNDERLINE,
}

_EXTRA = {"title": curses.A_BOLD, "user": curses.A_BOLD, "system": curses.A_BOLD,
          "selected": curses.A_BOLD, "error": curses.A_BOLD, "heading": curses.A_BOLD}


class Theme:
    def __init__(self) -> None:
        self.attrs: dict[str, int] = dict(_MONO)
        if "NO_COLOR" in os.environ or not curses.has_colors():
            return
        try:
            curses.start_color()
        except curses.error:
            return
        background = curses.COLOR_BLACK
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            pass
        for number, (name, (fg, bg)) in enumerate(_PAIRS.items(), start=1):
            if number >= curses.COLOR_PAIRS:
                break
            try:
                curses.init_pair(number, fg, background if bg is None else bg)
            except curses.error:
                continue
            self.attrs[name] = curses.color_pair(number) | _EXTRA.get(name, 0)

    def __getattr__(self, name: str) -> int:
        try:
            return self.__dict__["attrs"][name]
        except KeyError:
            raise AttributeError(name) from None

    dim = curses.A_DIM
    bold = curses.A_BOLD
    normal = curses.A_NORMAL
