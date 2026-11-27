"""
Aplicação

Liga as peças: lê uma tecla, atualiza a navegação e redesenha, até o utilizador sair.
"""

from rich.console import Console

from caduceus.i18n import Texts
from caduceus.keys import read_key
from caduceus.navigation import Navigation, press
from caduceus.ui import open_display, show


def run(console: Console, texts: Texts) -> None:
    """Corre o Caduceus até o utilizador sair.

    Args:
        console: consola onde desenhar.
        texts: textos da interface no idioma ativo.
    """
    navigation = Navigation()
    with open_display(console, texts, navigation) as display:
        while not navigation.finished:
            navigation = press(navigation, read_key())
            show(display, texts, navigation)
