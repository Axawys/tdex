#!/bin/sh
# Запуск tdex из каталога исходников без установки (рабочий каталог не меняется).
PYTHONPATH="$(cd "$(dirname "$0")" && pwd)${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m tdex "$@"
