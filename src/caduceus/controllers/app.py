"""
Aplicação

Liga as peças: lê uma tecla, atualiza a navegação e redesenha, até o utilizador sair. Uma opção
com ação corre logo ao ser escolhida, com a barra de progresso, e o resultado aparece no fim.
"""

import time

from rich.console import Console
from rich.live import Live

from caduceus.config import PROGRESS_REFRESH_SECONDS
from caduceus.controllers.keys import read_key
from caduceus.controllers.navigation import Navigation, complete, press
from caduceus.maintenance.actions import Step
from caduceus.ui.i18n import Texts
from caduceus.ui.render import open_display, show, show_progress


def _run_action(display: Live, texts: Texts, navigation: Navigation) -> Navigation:
    if navigation.running is None:
        return navigation
    last_shown = 0.0

    def report(step: Step) -> None:
        nonlocal last_shown
        now = time.monotonic()
        if now - last_shown >= PROGRESS_REFRESH_SECONDS:
            last_shown = now
            show_progress(display, texts, navigation, step)

    return complete(navigation, navigation.running(report))


def run(console: Console, texts: Texts) -> None:
    navigation = Navigation()
    with open_display(console, texts, navigation) as display:
        while not navigation.finished:
            navigation = _run_action(display, texts, press(navigation, read_key()))
            show(display, texts, navigation)
