"""Работа с шириной строк в ячейках терминала (кириллица, CJK, эмодзи)."""

from __future__ import annotations

import unicodedata


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    code = ord(ch)
    if code < 32 or 0x7F <= code < 0xA0:
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def text_width(text: str) -> int:
    return sum(char_width(ch) for ch in text)


def truncate(text: str, width: int, ellipsis: str = "…") -> str:
    """Обрезает строку до ``width`` ячеек, добавляя многоточие при обрезке."""
    if width <= 0:
        return ""
    if text_width(text) <= width:
        return text
    limit = width - text_width(ellipsis)
    if limit < 0:
        ellipsis, limit = "", width
    out, used = [], 0
    for ch in text:
        w = char_width(ch)
        if used + w > limit:
            break
        out.append(ch)
        used += w
    return "".join(out) + ellipsis


def pad(text: str, width: int) -> str:
    text = truncate(text, width)
    return text + " " * (width - text_width(text))


def _split_long(word: str, width: int) -> list[str]:
    parts, current, used = [], [], 0
    for ch in word:
        w = char_width(ch)
        if used + w > width and current:
            parts.append("".join(current))
            current, used = [], 0
        current.append(ch)
        used += w
    if current:
        parts.append("".join(current))
    return parts


def wrap(text: str, width: int) -> list[str]:
    """Перенос по словам с учётом ширины символов; явные переводы строк сохраняются."""
    width = max(1, width)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line, used = "", 0
        for word in words:
            ww = text_width(word)
            if ww > width:
                if line:
                    lines.append(line)
                chunks = _split_long(word, width)
                lines.extend(chunks[:-1])
                line, used = chunks[-1], text_width(chunks[-1])
            elif not line:
                line, used = word, ww
            elif used + 1 + ww <= width:
                line += " " + word
                used += 1 + ww
            else:
                lines.append(line)
                line, used = word, ww
        lines.append(line)
    return lines
