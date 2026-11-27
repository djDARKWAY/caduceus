"""
Caduceus

Ponto de entrada (`python -m caduceus`): limpa a consola e corre a aplicação.
"""

from rich.console import Console

from caduceus.config import DEFAULT_LANGUAGE
from caduceus.controllers.app import run
from caduceus.ui.i18n import load_texts
from caduceus.ui.window import close_launching_shell, fix_console_size


def main() -> None:
    fix_console_size()
    console = Console()
    console.clear()
    if run(console, load_texts(DEFAULT_LANGUAGE)):
        close_launching_shell()


if __name__ == "__main__":
    main()
