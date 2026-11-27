"""
Aplicação

Liga as peças: lê uma tecla, atualiza a navegação e redesenha, até o utilizador sair. Uma opção
com ação corre logo ao ser escolhida, com a barra de progresso, e o resultado aparece no fim. Os
menus com estimativas calculam-nas ao abrir (e a da ação que acabou de correr), também com a barra
de progresso. Enquanto algo corre nenhum controlo funciona: as teclas carregadas são descartadas e
o Ctrl+C é ignorado. As definições mudadas pelo utilizador guardam-se logo.
"""

import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

from rich.console import Console
from rich.live import Live

from caduceus.config import PROGRESS_REFRESH_SECONDS
from caduceus.controllers.keys import discard_pending_keys, read_key
from caduceus.controllers.navigation import (
    SETTINGS_NOT_SAVED_NOTICE,
    Navigation,
    complete,
    finish_estimates,
    press,
)
from caduceus.maintenance.actions import Step
from caduceus.maintenance.admin import is_admin
from caduceus.settings import load_settings, save_settings
from caduceus.ui.i18n import Texts
from caduceus.ui.render import open_display, show, show_progress


@contextmanager
def _no_controls() -> Iterator[None]:
    previous_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        discard_pending_keys()


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

    with _no_controls():
        show_progress(display, texts, navigation, Step("action.step", 0, 0))
        outcome = navigation.running(report)
    return complete(navigation, outcome)


def _run_estimates(display: Live, texts: Texts, navigation: Navigation) -> Navigation:
    if not navigation.estimating:
        return navigation
    pending = [
        (item.label_key, item.estimate)
        for item in navigation.menu.items
        if item.label_key in navigation.to_estimate and item.estimate is not None
    ]
    estimates: dict[str, int | None] = {}
    with _no_controls():
        for done, (label_key, estimate) in enumerate(pending):
            step = Step("estimate.step", done, len(pending), {"name": texts[label_key]})
            show_progress(display, texts, navigation, step)
            estimates[label_key] = estimate()
    return finish_estimates(navigation, estimates)


def run(console: Console, texts: Texts) -> None:
    navigation = Navigation(settings=load_settings(), administrator=is_admin())
    with open_display(console, texts, navigation) as display:
        while not navigation.finished:
            updated = press(navigation, read_key())
            if updated.settings != navigation.settings and not save_settings(updated.settings):
                updated = replace(updated, notice=SETTINGS_NOT_SAVED_NOTICE)
            navigation = _run_estimates(display, texts, _run_action(display, texts, updated))
            show(display, texts, navigation)
