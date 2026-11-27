"""
Caduceus

Ponto de entrada (`python -m caduceus`): mostra o menu principal até o utilizador sair.
"""

import os

from rich.console import Console

from caduceus.config import DEFAULT_LANGUAGE
from caduceus.i18n import load_texts
from caduceus.ui import MainMenuOption, run_main_menu, wait_for_key


def main() -> None:
    """Limpa a consola e corre o menu principal.

    As opções ainda sem ecrã mostram um aviso e voltam ao menu.
    """
    os.system("cls")
    console = Console()
    texts = load_texts(DEFAULT_LANGUAGE)
    while run_main_menu(console, texts) is not MainMenuOption.EXIT:
        console.print(texts["menu.not_available"])
        wait_for_key()


if __name__ == "__main__":
    main()
