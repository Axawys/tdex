"""Чтение клавиш и приведение их к коротким именам ('up', 'enter', 'esc', 'a', ...)."""

from __future__ import annotations

import curses

_SPECIAL = {
    curses.KEY_UP: "up",
    curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
    curses.KEY_HOME: "home",
    curses.KEY_END: "end",
    curses.KEY_PPAGE: "pgup",
    curses.KEY_NPAGE: "pgdn",
    curses.KEY_ENTER: "enter",
    curses.KEY_BACKSPACE: "backspace",
    curses.KEY_DC: "delete",
    curses.KEY_BTAB: "btab",
    curses.KEY_RESIZE: "resize",
    curses.KEY_F1: "f1",
}

_CONTROL = {
    "\n": "enter",
    "\r": "enter",
    "\t": "tab",
    "\x1b": "esc",
    "\x7f": "backspace",
    "\x08": "backspace",
    "\x01": "ctrl-a",
    "\x05": "ctrl-e",
    "\x0b": "ctrl-k",
    "\x0c": "ctrl-l",
    "\x15": "ctrl-u",
    "\x17": "ctrl-w",
}


def read_key(win) -> str:
    """Возвращает имя клавиши, печатный символ или '' для игнорируемого ввода."""
    try:
        key = win.get_wch()
    except curses.error:
        return ""
    if isinstance(key, int):
        return _SPECIAL.get(key, "")
    if key in _CONTROL:
        return _CONTROL[key]
    if len(key) == 1 and key.isprintable():
        return key
    return ""


def is_printable(key: str) -> bool:
    return len(key) == 1 and key.isprintable()
