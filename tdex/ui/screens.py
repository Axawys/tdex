"""Экраны каталога: категории, список утилит категории и поиск.

Экран отвечает за свою область тела окна; рамку, заголовок и подсказки
рисует приложение.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..catalog import Tool
from . import details
from .keys import is_printable
from .text import pad, text_width, truncate
from .widgets import Line, LineEdit, ListState, draw_scroll_marks, fill, put, put_line

if TYPE_CHECKING:
    from .app import App

Hints = list[tuple[str, str]]

# Ширина, начиная с которой справа показывается панель подробностей.
SPLIT_MIN_WIDTH = 84


def split_width(width: int) -> int | None:
    """Ширина левой колонки или None, если окно слишком узкое для двух колонок."""
    if width < SPLIT_MIN_WIDTH:
        return None
    return max(34, min(48, width * 2 // 5))


def draw_divider(app: "App", win, y: int, x: int, height: int) -> None:
    th = app.theme
    put(win, y - 1, x, "┬", th.border)
    for row in range(y, y + height):
        put(win, row, x, "│", th.border)
    put(win, y + height, x, "┴", th.border)


def draw_panel(win, y: int, x: int, height: int, width: int, lines: list[Line], more_attr: int) -> None:
    for row, line in enumerate(lines[:height]):
        put_line(win, y + row, x, line, width)
    if len(lines) > height and height > 0:
        fill(win, y + height - 1, x, width)
        put(win, y + height - 1, x, "…", more_attr)


def draw_tool_rows(app: "App", win, y: int, x: int, height: int, width: int, tools: list[Tool],
                   state: ListState, *, show_category: bool = False, show_description: bool = True,
                   focused: bool = True) -> None:
    th = app.theme
    state.set_count(len(tools))
    state.scroll_into_view(height)
    name_w = min(max((text_width(t.name) for t in tools), default=4), 20)
    cat_w = min(max((text_width(t.category) for t in tools), default=0), 22) if show_category else 0

    for row in range(height):
        index = state.offset + row
        if index >= len(tools):
            break
        tool = tools[index]
        selected = focused and index == state.index
        base = th.selected if selected else 0
        ry = y + row
        if selected:
            fill(win, ry, x, width, base)
        symbol, symbol_attr = details.marker(app, tool)
        cx = x + 1
        cx += put(win, ry, cx, "> " if selected else "  ", base)
        cx += put(win, ry, cx, symbol + " ", base if selected else symbol_attr)
        cx += put(win, ry, cx, pad(tool.name, name_w), base | th.bold if selected else 0)
        remaining = x + width - 2 - cx
        if show_category and remaining > 8:
            cx += put(win, ry, cx, "  " + pad(tool.category, min(cat_w, remaining - 2)),
                      base if selected else th.heading & ~th.bold)
            remaining = x + width - 2 - cx
        if show_description and remaining > 8:
            put(win, ry, cx, "  " + truncate(tool.description, remaining - 2), base if selected else th.dim)
    draw_scroll_marks(win, y, y + height - 1, x + width - 1, state, height, th.dim)


class Screen:
    def breadcrumb(self, app: "App") -> str:
        raise NotImplementedError

    def hints(self, app: "App") -> Hints:
        raise NotImplementedError

    def draw(self, app: "App", win, y: int, x: int, height: int, width: int) -> None:
        raise NotImplementedError

    def handle(self, app: "App", key: str) -> bool:
        return False


class CategoryScreen(Screen):
    def __init__(self, mode: str):
        self.mode = mode
        self.list = ListState()
        self.page = 10

    def categories(self, app: "App") -> list[str]:
        return app.catalog.categories(self.mode)

    def breadcrumb(self, app: "App") -> str:
        return "Категории"

    def hints(self, app: "App") -> Hints:
        return [("↑↓", "Навигация"), ("Enter", "Выбрать"), ("Tab", "Режим"), ("/", "Поиск"),
                ("?", "Справка"), ("q", "Выход")]

    def draw(self, app: "App", win, y: int, x: int, height: int, width: int) -> None:
        th = app.theme
        categories = self.categories(app)
        left = split_width(width)
        list_w = left if left else width
        list_y, list_h = y + 1, height - 2
        self.page = list_h
        self.list.set_count(len(categories))
        self.list.scroll_into_view(list_h)

        if not categories:
            put(win, list_y, x + 2, "В этом режиме каталог пуст.", th.dim)
        for row in range(list_h):
            index = self.list.offset + row
            if index >= len(categories):
                break
            category = categories[index]
            selected = index == self.list.index
            base = th.selected if selected else 0
            ry = list_y + row
            if selected:
                fill(win, ry, x, list_w, base)
            available, total = app.status.count(app.catalog.tools_in(self.mode, category))
            counter = f"{available}/{total}"
            name_w = list_w - 6 - text_width(counter) - 2
            put(win, ry, x + 1, ("> " if selected else "  ") + pad(category, name_w), base | th.bold if selected else 0)
            put(win, ry, x + list_w - 2 - text_width(counter), counter, base if selected else th.dim)
        draw_scroll_marks(win, list_y, list_y + list_h - 1, x + list_w - 1, self.list, list_h, th.dim)

        if left and categories:
            draw_divider(app, win, y, x + left, height)
            panel_x, panel_w = x + left + 2, width - left - 3
            lines = details.category_lines(app, self.mode, categories[self.list.index], panel_w)
            draw_panel(win, list_y, panel_x, list_h, panel_w, lines, th.dim)

    def handle(self, app: "App", key: str) -> bool:
        if self.list.handle(key, self.page):
            return True
        if key in ("enter", "right", "l"):
            categories = self.categories(app)
            if categories:
                app.push(ToolListScreen(self.mode, categories[self.list.index]))
            return True
        return False


class ToolListScreen(Screen):
    def __init__(self, mode: str, category: str):
        self.mode = mode
        self.category = category
        self.list = ListState()
        self.page = 10

    def tools(self, app: "App") -> list[Tool]:
        return app.catalog.tools_in(self.mode, self.category)

    def selected(self, app: "App") -> Tool | None:
        tools = self.tools(app)
        return tools[self.list.index] if tools else None

    def breadcrumb(self, app: "App") -> str:
        return f"Категории › {self.category}"

    def hints(self, app: "App") -> Hints:
        return [("↑↓", "Навигация"), ("Enter", "Запуск"), ("i", "Инфо"), ("a", "Аргументы"),
                ("Esc", "Назад"), ("/", "Поиск"), ("Tab", "Режим"), ("?", "Справка"), ("q", "Выход")]

    def draw(self, app: "App", win, y: int, x: int, height: int, width: int) -> None:
        th = app.theme
        tools = self.tools(app)
        left = split_width(width)
        list_y, list_h = y + 1, height - 2
        self.page = list_h
        draw_tool_rows(app, win, list_y, x, list_h, left or width, tools, self.list,
                       show_description=left is None)
        if left and tools:
            draw_divider(app, win, y, x + left, height)
            panel_x, panel_w = x + left + 2, width - left - 3
            lines = details.tool_lines(app, tools[self.list.index], panel_w, title=True)
            draw_panel(win, list_y, panel_x, list_h, panel_w, lines, th.dim)

    def handle(self, app: "App", key: str) -> bool:
        if self.list.handle(key, self.page):
            return True
        tool = self.selected(app)
        if key in ("esc", "left", "h", "backspace"):
            app.pop()
        elif tool is None:
            return False
        elif key in ("enter", "right", "l"):
            app.activate(tool)
        elif key == "a":
            app.activate(tool, prompt=True)
        elif key == "i":
            app.show_info(tool)
        elif key == "m":
            app.open_man(tool)
        else:
            return False
        return True


class SearchScreen(Screen):
    """Глобальный поиск по утилитам текущего режима.

    Два состояния фокуса: строка ввода (буквы идут в запрос) и список
    результатов (работают обычные клавиши списка, включая i и q).
    """

    def __init__(self, mode: str, query: str = ""):
        self.mode = mode
        self.edit = LineEdit(query)
        self.list = ListState()
        self.focus = "input"
        self.page = 10
        self._cache: tuple[str, str, list[Tool]] | None = None

    def results(self, app: "App") -> list[Tool]:
        key = (self.mode, self.edit.text)
        if self._cache is None or self._cache[:2] != key:
            self._cache = (*key, app.catalog.search(self.mode, self.edit.text))
        return self._cache[2]

    def selected(self, app: "App") -> Tool | None:
        results = self.results(app)
        return results[self.list.index] if results else None

    def breadcrumb(self, app: "App") -> str:
        return "Поиск"

    def hints(self, app: "App") -> Hints:
        if self.focus == "input":
            return [("Ввод", "Запрос"), ("↓/Enter", "К результатам"), ("Tab", "Режим"),
                    ("Ctrl+U", "Очистить"), ("Esc", "Закрыть")]
        return [("↑↓", "Навигация"), ("Enter", "Запуск"), ("i", "Инфо"), ("a", "Аргументы"),
                ("/", "Изменить запрос"), ("Esc", "Закрыть"), ("q", "Выход")]

    def draw(self, app: "App", win, y: int, x: int, height: int, width: int) -> None:
        th = app.theme
        label = " Поиск: "
        put(win, y, x + 1, label, th.heading)
        field_x = x + 1 + text_width(label)
        self.edit.draw(win, y, field_x, x + width - 2 - field_x, th.input, th.selected,
                       focused=self.focus == "input")

        results = self.results(app)
        if not self.edit.text.strip():
            info = "Введите название, описание, категорию или тег (например: monitor, редактор, git)"
        elif results:
            info = f"Найдено: {len(results)} в режиме {self.mode.upper()}"
        else:
            info = f"Ничего не найдено в режиме {self.mode.upper()}. Tab — искать в другом режиме"
        put(win, y + 1, x + 2, truncate(info, width - 4), th.dim)

        left = split_width(width)
        list_y, list_h = y + 3, height - 4
        self.page = list_h
        draw_tool_rows(app, win, list_y, x, list_h, left or width, results, self.list,
                       show_category=True, show_description=left is None,
                       focused=self.focus == "list")
        put(win, y + 2, x - 1, "├" + "─" * width + "┤", th.border)
        if left and results:
            draw_divider(app, win, y + 3, x + left, height - 3)
            put(win, y + 2, x + left, "┼", th.border)
            panel_x, panel_w = x + left + 2, width - left - 3
            lines = details.tool_lines(app, results[self.list.index], panel_w, title=True)
            draw_panel(win, list_y, panel_x, list_h, panel_w, lines, th.dim)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.list = ListState()

    def handle(self, app: "App", key: str) -> bool:
        if self.focus == "input":
            return self._handle_input(app, key)
        return self._handle_list(app, key)

    def _handle_input(self, app: "App", key: str) -> bool:
        if key == "esc":
            app.pop()
        elif key in ("enter", "down", "pgdn"):
            if self.results(app):
                self.focus = "list"
                self.list.home()
        elif key in ("up", "pgup"):
            pass
        elif self.edit.handle(key):
            self.list = ListState()
        else:
            # Tab, ? и прочее обрабатываются приложением. Печатные символы
            # (включая q и /) всегда попадают в запрос.
            return is_printable(key)
        return True

    def _handle_list(self, app: "App", key: str) -> bool:
        if key == "up" and self.list.index == 0:
            self.focus = "input"
            return True
        if self.list.handle(key, self.page):
            return True
        tool = self.selected(app)
        if key == "esc":
            app.pop()
        elif key in ("/", "backspace"):
            self.focus = "input"
            if key == "backspace":
                self.edit.handle(key)
        elif tool is None:
            return False
        elif key in ("enter", "right", "l"):
            app.activate(tool)
        elif key == "a":
            app.activate(tool, prompt=True)
        elif key == "i":
            app.show_info(tool)
        elif key == "m":
            app.open_man(tool)
        else:
            return False
        return True
