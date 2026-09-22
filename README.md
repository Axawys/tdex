# tdex — Terminal Tools

**English** | [Русский](README.ru.md)

An interactive TUI catalog of console applications and system CLI utilities for Linux.
It shows what is installed (●) and what is not (○), launches programs by handing them the
terminal, and brings you back to the catalog when they exit. For missing programs it shows
install commands for Arch, Debian/Ubuntu and Fedora — **it never installs anything itself**.

```
┌──────────────────────────────────────────────────────────────┐
│                        TERMINAL TOOLS                   tdex │
│                        [ USER MODE ]            Tab → SYSTEM │
├─ Категории ─────────────────────┬─── установлено 14 из 81 ───┤
│ > Мониторинг               2/5  │ Мониторинг                 │
│   Информация о системе     1/4  │ Доступно: 2 из 5           │
│   Файловые менеджеры       1/5  │ ● btop    Интерактивный …  │
│   ...                           │ ○ atop    Мониторинг …     │
├─────────────────────────────────┴──────────────── Arch Linux ┤
│  ↑↓  Навигация   Enter  Выбрать   Tab  Режим   /  Поиск  ... │
└──────────────────────────────────────────────────────────────┘
```

> The interface and the bundled catalog are in Russian. English search keywords work
> too, because every catalog entry has English `tags` (`monitor`, `editor`, `archive`, …).

The catalog has two modes, switched with `Tab`:

- **USER** — full-featured console/TUI applications: monitoring, file managers, editors,
  git, containers, network, browsers, databases, multiplexers, games and more (81 programs).
- **SYSTEM** — standard CLI utilities: file system, text processing, processes, disks,
  permissions, archives, network, systemd, environment, terminal (91 utilities).

## Requirements

- Linux, Python 3.10+ (standard library only: `curses`, `json`, `subprocess`, `shutil`)
- a UTF-8 terminal, at least 44×14

## Installation

The recommended way to install is with [pipx](https://pipx.pypa.io/):

```sh
git clone https://github.com/Axawys/tdex.git && cd tdex && pipx install .
```

This installs the `tdex` command into `~/.local/bin`; then just run `tdex`.
To update later: `git pull && pipx install --force .` (from the `tdex` directory).

Running without installation, from the cloned directory:

```sh
python3 -m tdex          # from the project directory
./tdex.sh                # same, from anywhere; keeps your working directory
```

Command-line options:

| Option | Purpose |
|---|---|
| `-m user\|system` | initial mode |
| `-c FILE` | use another JSON catalog (may be repeated) |
| `--no-user-catalog` | do not load `~/.config/tdex/catalog.d/*.json` |
| `-l`, `--list` | print the catalog with install status, no TUI |
| `--check` | validate catalog files |

## Keys

| Key | Action |
|---|---|
| `↑` `↓` / `j` `k`, `PgUp` `PgDn`, `Home` `End` | move through the list |
| `Enter` / `→` | open a category / launch a program |
| `Esc` / `←` / `Backspace` | go back |
| `Tab` | switch USER ↔ SYSTEM (each mode keeps its own position) |
| `i` | detailed information about the program |
| `a` | launch with custom arguments |
| `m` | open the man page |
| `/` | search within the current mode |
| `r` | re-check what is installed |
| `?` / `F1` | help |
| `q` / `Ctrl+C` | quit |

In search, typed characters go into the query; `↓` or `Enter` moves focus to the results,
where `Enter`, `i`, `a`, `m` work; `/` returns to editing the query. `Tab` in search carries
the same query over to the other mode.

## How programs are launched

- Availability is checked against `$PATH` (`shutil.which`, the equivalent of `command -v`)
  on startup, after every launch, on `r`, and **once more right before launching**.
- Programs are started with `subprocess.Popen([...])` and no shell: arguments are passed as
  a list and never concatenated into a string. `sudo` is never invoked.
- While a program runs, curses is suspended (`endwin`); `Ctrl+C` and `Ctrl+\` go to the
  program, not to the catalog. Afterwards the terminal settings are restored, a changed
  window size is picked up, and the interface is redrawn.
- Utilities that print their output and exit immediately (`ls`, `fastfetch`, …) are marked
  `"pause": true` — tdex waits for Enter so the output can be read.
- For entries with `"prompt_args": true` (the default for every SYSTEM utility) `Enter` opens
  an argument field prefilled with the defaults. Quotes are parsed shell-style (`shlex`) and a
  leading `~` is expanded, but `*`, `|`, `>`, `$VAR` are not.
- Shell builtins (`cd`, `export`, `jobs`, …) cannot run as separate processes, so for them
  `Enter` shows `help <command>` from bash.

## The catalog

The catalog lives in [`tdex/data/catalog.json`](tdex/data/catalog.json) and is fully separate
from the UI: categories and their order come from the file. To add programs without touching
the bundled catalog, drop a JSON file into `~/.config/tdex/catalog.d/` — entries with the same
`mode` + `name` replace the bundled ones.

```json
{
  "tools": [
    {
      "name": "btop",
      "command": "btop",
      "mode": "user",
      "category": "Мониторинг",
      "description": "Интерактивный мониторинг процессов и ресурсов системы",
      "tags": ["monitor", "process", "cpu"],
      "install": {
        "arch": "sudo pacman -S btop",
        "debian": "sudo apt install btop",
        "fedora": "sudo dnf install btop"
      }
    }
  ]
}
```

Required fields: `name`, `command`, `mode` (`user` / `system`), `category`, `description`,
`install`. Optional fields:

| Field | Purpose |
|---|---|
| `aliases` | alternative executable names (`bat` → `batcat` on Debian) |
| `args` | default arguments (list of strings) |
| `tags` | search keywords |
| `pause` | wait for Enter after exit (default `true` for SYSTEM) |
| `prompt_args` | ask for arguments before launching (default `true` for SYSTEM) |
| `builtin` | shell builtin |
| `notes`, `url` | extra information shown in the `i` window |

Keys in `install` are free-form; known labels are `arch`, `aur`, `debian`, `fedora`, `cargo`,
`go`, `pip`, `snap`, `flatpak`, `nix`, `other`. The line for your distribution (detected from
`/etc/os-release`) is highlighted. Install commands are indicative — package names may differ
between distribution releases.

`python3 -m tdex --check` validates the files and reports errors with the entry number.

## Project layout

```
tdex/
  catalog.py      loading, validation and search
  system.py       executable lookup, status, distribution detection
  launcher.py     running programs and returning to the TUI
  data/catalog.json
  ui/
    app.py        main loop, screen stack, actions
    screens.py    screens: categories, tool list, search
    dialogs.py    windows: info, "not installed", arguments, help
    details.py    text blocks describing tools and categories
    widgets.py    frames, scrolling lists, input field
    text.py       terminal cell width, wrapping
    theme.py      colors (honors NO_COLOR)
    keys.py       key input
tests/            unit tests: python3 -m unittest discover -s tests -t .
```

## License

Distributed under the [GNU General Public License v3.0 or later](LICENSE).
