"""
Caduceus

Ponto de entrada (`python -m caduceus`): limpa a consola e corre a aplicação.
"""

import os

from rich.console import Console

from caduceus.config import DEFAULT_LANGUAGE
from caduceus.controllers.app import run
from caduceus.ui.i18n import load_texts
from caduceus.ui.window import fix_console_size


def main() -> None:
    fix_console_size()
    os.system("cls")
    run(Console(), load_texts(DEFAULT_LANGUAGE))


if __name__ == "__main__":
    main()
