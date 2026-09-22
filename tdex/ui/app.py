"""Главный цикл TUI: отрисовка рамки, стек экранов, модальные окна и запуск программ."""

from __future__ import annotations

import curses
from pathlib import Path

from .. import APP_NAME, launcher, system
from ..catalog import MODES, Catalog, Tool
from .dialogs import Dialog, HelpDialog, InfoDialog, MessageDialog, NotInstalledDialog, ArgsDialog
from .keys import read_key
from .screens import CategoryScreen, Screen, SearchScreen
from .text import text_width, truncate
from .theme import Theme
from .widgets import border_label, box, put, separator

TITLE = "TERMINAL TOOLS"
MIN_WIDTH, MIN_HEIGHT = 44, 14


class App:
    def __init__(self, stdscr, catalog: Catalog, *, mode: str = "user", catalog_paths: list[Path] = ()):
        self.stdscr = stdscr
        self.catalog = catalog
        self.catalog_paths = list(catalog_paths)
        self.mode = mode
        self.theme = Theme()
        self.status = system.StatusCache()
        self.status.scan(catalog.tools)
        self.family = system.detect_family()
        # У каждого режима свой стек экранов: Tab возвращает туда, где вы были.
        self.stacks: dict[str, list[Screen]] = {m: [CategoryScreen(m)] for m in MODES}
        self.dialog: Dialog | None = None
        self.message: tuple[str, int] | None = None
        self.running = True

    # --- главный цикл ------------------------------------------------------------

    def run(self) -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.stdscr.keypad(True)
        try:
            curses.set_escdelay(25)
        except (AttributeError, curses.error):
            pass
        while self.running:
            self.draw()
            key = read_key(self.stdscr)
            if not key:
                continue
            if key == "resize":
                curses.update_lines_cols()
                continue
            self.message = None
            self.dispatch(key)

    def dispatch(self, key: str) -> None:
        if self.dialog is not None:
            self.dialog.handle(self, key)
            return
        height, width = self.stdscr.getmaxyx()
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            if key in ("q", "esc"):
                self.running = False
            return
        if self.screen.handle(self, key):
            return
        if key in ("tab", "btab"):
            self.toggle_mode()
        elif key == "/":
            self.open_search()
        elif key in ("?", "f1"):
            self.show_dialog(HelpDialog())
        elif key in ("r", "ctrl-l"):
            self.rescan()
            self.stdscr.clear()
            self.notify("Статусы программ обновлены", self.theme.ok)
        elif key == "esc":
            self.pop()
        elif key == "q":
            self.running = False

    # --- навигация -----------------------------------------------------------------

    @property
    def stack(self) -> list[Screen]:
        return self.stacks[self.mode]

    @property
    def screen(self) -> Screen:
        return self.stack[-1]

    def push(self, screen: Screen) -> None:
        self.stack.append(screen)

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()

    def toggle_mode(self) -> None:
        current = self.screen
        self.mode = "system" if self.mode == "user" else "user"
        if isinstance(current, SearchScreen):
            # Поиск «переезжает» в новый режим вместе с запросом.
            self.stack[:] = [s for s in self.stack if not isinstance(s, SearchScreen)]
            current.set_mode(self.mode)
            self.push(current)

    def open_search(self) -> None:
        if isinstance(self.screen, SearchScreen):
            self.screen.focus = "input"
        else:
            self.push(SearchScreen(self.mode))

    def show_dialog(self, dialog: Dialog) -> None:
        self.dialog = dialog

    def close_dialog(self) -> None:
        self.dialog = None

    def notify(self, text: str, attr: int = 0) -> None:
        self.message = (text, attr)

    def rescan(self) -> None:
        self.status.scan(self.catalog.tools)

    # --- действия с утилитами ------------------------------------------------------

    def show_info(self, tool: Tool) -> None:
        self.show_dialog(InfoDialog(tool))

    def activate(self, tool: Tool, prompt: bool | None = None) -> None:
        """Enter на утилите: встроенные — справка, отсутствующие — окно установки."""
        if tool.builtin:
            self.show_builtin_help(tool)
            return
        resolution = system.resolve(tool)
        if resolution is None:
            self.rescan()
            self.show_dialog(NotInstalledDialog(tool))
            return
        if prompt if prompt is not None else tool.prompt_args:
            self.show_dialog(ArgsDialog(tool, resolution))
            return
        self.launch(tool, list(tool.args))

    def launch(self, tool: Tool, args: list[str]) -> None:
        # Повторная проверка прямо перед запуском: статус мог измениться,
        # пока пользователь смотрел на меню или вводил аргументы.
        resolution = system.resolve(tool)
        if resolution is None:
            self.rescan()
            self.show_dialog(NotInstalledDialog(tool))
            return
        result = launcher.run(self.stdscr, [resolution.name, *args], resolution.path, pause=tool.pause)
        self.rescan()
        self._report(tool.name, result)

    def _report(self, name: str, result: launcher.LaunchResult) -> None:
        th = self.theme
        if result.error:
            self.show_dialog(MessageDialog("Ошибка запуска", f"Не удалось запустить {name}.\n\n{result.error}", error=True))
        elif result.signal_name:
            self.notify(f"{name}: {result.describe()}", th.accent)
        elif result.returncode:
            self.notify(f"{name} завершилась с кодом {result.returncode}", th.error)
        else:
            self.notify(f"{name} завершила работу", th.ok)

    def show_builtin_help(self, tool: Tool) -> None:
        bash = system.find_executable("bash")
        if bash is None:
            self.show_dialog(MessageDialog(
                tool.name, f"{tool.name} — встроенная команда оболочки. Её нельзя запустить как "
                "отдельную программу; используйте её в своей оболочке.\n\nbash не найден, "
                "поэтому справку показать нельзя."))
            return
        # Имя команды передаётся позиционным параметром, а не подставляется в код.
        argv = ["bash", "-c", 'help -- "$1"', APP_NAME, tool.command]
        result = launcher.run(self.stdscr, argv, bash, pause=True)
        if result.error or result.returncode:
            self._report(f"help {tool.command}", result)
        else:
            self.notify(f"{tool.name} — встроенная команда оболочки, используйте её в своём shell", self.theme.accent)

    def open_man(self, tool: Tool) -> None:
        man = system.find_executable("man")
        if man is None:
            self.show_dialog(MessageDialog("man", "Программа man не установлена.", error=True))
            return
        result = launcher.run(self.stdscr, ["man", "--", tool.command], man, pause=False)
        if result.error:
            self._report("man", result)
        elif result.returncode:
            self.notify(f"Нет man-страницы для {tool.command}", self.theme.error)

    # --- отрисовка ------------------------------------------------------------------

    def draw(self) -> None:
        win = self.stdscr
        win.erase()
        height, width = win.getmaxyx()
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            self._draw_too_small(height, width)
        else:
            self._draw_frame(height, width)
            self.screen.draw(self, win, 4, 1, height - 7, width - 2)
            self._draw_hints(height - 2, width)
            if self.dialog is not None:
                self.dialog.draw(self, win)
        win.noutrefresh()
        curses.doupdate()

    def _draw_too_small(self, height: int, width: int) -> None:
        lines = ["Окно терминала слишком маленькое", f"сейчас {width}×{height}, нужно {MIN_WIDTH}×{MIN_HEIGHT}", "q — выход"]
        top = max(0, height // 2 - 1)
        for i, line in enumerate(lines):
            line = truncate(line, width)
            put(self.stdscr, top + i, max(0, (width - text_width(line)) // 2), line, self.theme.accent if i == 0 else 0)

    def _draw_frame(self, height: int, width: int) -> None:
        win, th = self.stdscr, self.theme
        box(win, 0, 0, height, width, th.border)
        separator(win, 3, 0, width, th.border)
        separator(win, height - 3, 0, width, th.border)

        put(win, 1, (width - text_width(TITLE)) // 2, TITLE, th.title)
        badge = f" [ {self.mode.upper()} MODE ] "
        put(win, 2, (width - text_width(badge)) // 2, badge, th.user if self.mode == "user" else th.system)
        other = "SYSTEM" if self.mode == "user" else "USER"
        hint = f"Tab → {other}"
        if width >= 2 * text_width(hint) + text_width(badge) + 8:
            put(win, 2, width - 2 - text_width(hint), hint, th.dim)
            put(win, 1, width - 2 - len(APP_NAME), APP_NAME, th.dim)

        available, total = self.status.count(self.catalog.tools_for_mode(self.mode))
        counter = f"установлено {available} из {total}"
        crumb_w = width - text_width(counter) - 10
        border_label(win, 3, 2, self.screen.breadcrumb(self), th.heading, crumb_w)
        if crumb_w > 10:
            border_label(win, 3, width - text_width(counter) - 4, counter, th.dim, text_width(counter) + 2)

        if self.message:
            text, attr = self.message
            border_label(win, height - 3, 2, text, attr, width - 6)
        elif self.family:
            label = system.install_label(self.family)
            border_label(win, height - 3, width - text_width(label) - 4, label, th.dim, width)

    def _draw_hints(self, y: int, width: int) -> None:
        win, th = self.stdscr, self.theme
        x, limit = 2, width - 2
        for key, label in self.screen.hints(self):
            end = x + text_width(key) + 3 + text_width(label)
            if end > limit:
                break
            put(win, y, x, f" {key} ", th.key)
            put(win, y, x + text_width(key) + 3, label)
            x = end + 2
