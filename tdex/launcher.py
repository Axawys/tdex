"""Запуск внешних программ с временной передачей им терминала.

Программа запускается напрямую через ``subprocess`` (execve), без оболочки:
аргументы передаются списком и никогда не склеиваются в строку.
"""

from __future__ import annotations

import curses
import os
import shlex
import signal
import subprocess
import sys
from dataclasses import dataclass

try:
    import termios
except ImportError:  # pragma: no cover - не-POSIX платформы
    termios = None  # type: ignore[assignment]


@dataclass(frozen=True)
class LaunchResult:
    returncode: int | None
    error: str | None = None

    @property
    def signal_name(self) -> str | None:
        if self.returncode is not None and self.returncode < 0:
            try:
                return signal.Signals(-self.returncode).name
            except ValueError:
                return f"сигнал {-self.returncode}"
        return None

    def describe(self) -> str:
        if self.error:
            return self.error
        if self.signal_name:
            return f"прервано ({self.signal_name})"
        return f"код завершения {self.returncode}"


def _save_tty():
    if termios is None or not sys.stdin.isatty():
        return None
    try:
        return termios.tcgetattr(sys.stdin.fileno())
    except termios.error:
        return None


def _restore_tty(saved) -> None:
    # Упавшая программа может оставить терминал в raw-режиме или без эха.
    if saved is None:
        return
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved)
    except termios.error:
        pass


def _spawn(argv: list[str], executable: str) -> LaunchResult:
    try:
        proc = subprocess.Popen(argv, executable=executable)
    except FileNotFoundError:
        return LaunchResult(None, f"исполняемый файл не найден: {executable}")
    except PermissionError:
        return LaunchResult(None, f"нет прав на запуск: {executable}")
    except OSError as exc:
        return LaunchResult(None, f"не удалось запустить {executable}: {exc.strerror or exc}")

    # Ctrl+C и Ctrl+\ предназначены запущенной программе, а не каталогу.
    # Обработчики меняем после fork, чтобы потомок унаследовал стандартные.
    old_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
    old_quit = signal.signal(signal.SIGQUIT, signal.SIG_IGN)
    try:
        returncode = proc.wait()
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGQUIT, old_quit)
    return LaunchResult(returncode)


def _styled(text: str, sgr: str) -> str:
    if sys.stdout.isatty() and "NO_COLOR" not in os.environ:
        return f"\033[{sgr}m{text}\033[0m"
    return text


def _wait_for_enter(result: LaunchResult) -> None:
    print("\n" + _styled(f"[tdex] {result.describe()}. Нажмите Enter, чтобы вернуться в каталог…", "1;36"),
          end="", flush=True)
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print()


def _sync_terminal_size(stdscr) -> None:
    """Размер терминала мог измениться, пока работала внешняя программа."""
    try:
        cols, rows = os.get_terminal_size(sys.__stdout__.fileno())
    except (OSError, ValueError, AttributeError):
        return
    if curses.is_term_resized(rows, cols):
        curses.resizeterm(rows, cols)


def run(stdscr, argv: list[str], executable: str, *, pause: bool) -> LaunchResult:
    """Приостанавливает curses, запускает программу и возвращает управление в TUI."""
    curses.def_prog_mode()
    curses.endwin()
    saved = _save_tty()
    try:
        if pause:
            print(_styled(f"$ {shlex.join(argv)}", "1;33"), flush=True)
        result = _spawn(argv, executable)
        _restore_tty(saved)
        if pause and not result.error:
            _wait_for_enter(result)
        return result
    finally:
        _restore_tty(saved)
        curses.reset_prog_mode()
        _sync_terminal_size(stdscr)
        stdscr.clear()  # полная перерисовка: экран сейчас занят выводом программы
        curses.flushinp()
