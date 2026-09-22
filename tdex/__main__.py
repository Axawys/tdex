"""Точка входа: разбор аргументов командной строки и запуск TUI."""

from __future__ import annotations

import argparse
import curses
import locale
import os
import sys
from pathlib import Path

from . import APP_NAME, __version__, system
from .catalog import MODES, Catalog, CatalogError, builtin_catalog_path, user_catalog_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Интерактивный TUI-каталог консольных приложений и системных утилит.",
    )
    parser.add_argument("-c", "--catalog", action="append", type=Path, metavar="FILE",
                        help="использовать указанный JSON-каталог вместо встроенного (можно несколько раз)")
    parser.add_argument("--no-user-catalog", action="store_true",
                        help="не подключать файлы из ~/.config/tdex/catalog.d/")
    parser.add_argument("-m", "--mode", choices=MODES,
                        help="начальный режим TUI (по умолчанию user); для --list — какой режим вывести")
    parser.add_argument("-l", "--list", action="store_true",
                        help="вывести каталог со статусами установки и выйти (без TUI)")
    parser.add_argument("--check", action="store_true", help="проверить файлы каталога и выйти")
    parser.add_argument("-V", "--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser


def catalog_paths(args: argparse.Namespace) -> list[Path]:
    if args.catalog:
        return list(args.catalog)
    paths = [builtin_catalog_path()]
    if not args.no_user_catalog:
        paths.extend(user_catalog_paths())
    return paths


def print_list(catalog: Catalog, modes: list[str]) -> None:
    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    green, red, yellow, bold, reset = (("\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m")
                                       if color else ("",) * 5)
    marks = {system.INSTALLED: f"{green}●{reset}", system.MISSING: f"{red}○{reset}",
             system.BUILTIN: f"{yellow}◆{reset}"}
    for mode in modes:
        print(f"{bold}[ {mode.upper()} MODE ]{reset}")
        for category in catalog.categories(mode):
            print(f"  {bold}{category}{reset}")
            for tool in catalog.tools_in(mode, category):
                status = system.check(tool)
                where = status.resolution.path if status.resolution else ""
                print(f"    {marks[status.kind]} {tool.name:<16} {where}")
        print()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = catalog_paths(args)
    try:
        catalog = Catalog.load(paths)
    except CatalogError as exc:
        print(f"{APP_NAME}: ошибка каталога: {exc}", file=sys.stderr)
        return 2
    if not catalog.tools:
        print(f"{APP_NAME}: каталог пуст", file=sys.stderr)
        return 2

    if args.check:
        for mode in MODES:
            tools = catalog.tools_for_mode(mode)
            print(f"{mode}: {len(tools)} утилит в {len(catalog.categories(mode))} категориях")
        print("Каталог корректен.")
        return 0
    if args.list:
        print_list(catalog, [args.mode] if args.mode else list(MODES))
        return 0

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(f"{APP_NAME}: нужен интерактивный терминал (используйте --list для вывода в файл)", file=sys.stderr)
        return 1

    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")

    from .ui.app import App  # curses-часть импортируется только при запуске TUI

    try:
        curses.wrapper(lambda stdscr: App(stdscr, catalog, mode=args.mode or "user", catalog_paths=paths).run())
    except KeyboardInterrupt:
        pass
    except curses.error as exc:
        print(f"{APP_NAME}: ошибка терминала: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
