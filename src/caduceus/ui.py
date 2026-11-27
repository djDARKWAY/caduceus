"""
Interface

Menus interativos do terminal, navegados com as setas.
"""

import msvcrt
from enum import Enum

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from caduceus import __version__
from caduceus.branding import BANNER_LINES, BANNER_WIDTH, ICON_LINES
from caduceus.config import ACCENT_STYLE, SELECTED_STYLE
from caduceus.i18n import Texts

VERSION_LABEL = f"v{__version__}"


class Key(Enum):
    UP = "up"
    DOWN = "down"
    ENTER = "enter"
    BACK = "back"
    QUIT = "quit"
    OTHER = "other"


class MainMenuOption(Enum):
    """Opções do menu principal. O valor é a chave do texto no ficheiro de idioma."""

    SCAN = "menu.scan"
    MAINTENANCE = "menu.maintenance"
    SETTINGS = "menu.settings"
    EXIT = "menu.exit"


HINTS = (
    ("↑", "hint.up"),
    ("↓", "hint.down"),
    ("ENTER", "hint.select"),
    ("BACKSPACE", "hint.back"),
    ("Q", "hint.quit"),
)

_EXTENDED_KEYS = {"H": Key.UP, "P": Key.DOWN}
_CHAR_KEYS = {"\r": Key.ENTER, "\x08": Key.BACK, "q": Key.QUIT, "Q": Key.QUIT, "\x03": Key.QUIT}


def read_key() -> Key:
    """Espera por uma tecla e devolve a que interessa ao menu (as outras dão `Key.OTHER`).

    Q e Ctrl+C contam ambos como `Key.QUIT`.
    """
    char = msvcrt.getwch()
    if char in ("\x00", "\xe0"):
        return _EXTENDED_KEYS.get(msvcrt.getwch(), Key.OTHER)
    return _CHAR_KEYS.get(char, Key.OTHER)


def wait_for_key() -> None:
    """Espera por qualquer tecla."""
    read_key()


def next_index(index: int, key: Key, count: int) -> int:
    """Devolve a posição seguinte do menu, dando a volta nas pontas.

    Args:
        index: posição atual.
        key: tecla premida.
        count: número de opções do menu.

    Returns:
        A nova posição (a mesma, se a tecla não for uma seta).
    """
    if key is Key.UP:
        return (index - 1) % count
    if key is Key.DOWN:
        return (index + 1) % count
    return index


def _render_header(texts: Texts) -> RenderableType:
    tagline = texts["app.tagline"]
    info_line = f"{tagline} {VERSION_LABEL:>{BANNER_WIDTH - len(tagline) - 1}}"
    banner = Group(
        Text("\n".join(BANNER_LINES), style=ACCENT_STYLE, no_wrap=True),
        Text(""),
        Text(info_line, style=ACCENT_STYLE, no_wrap=True),
    )
    header = Table.grid(padding=(0, 4))
    header.add_column(vertical="middle")
    header.add_column()
    header.add_row(Text("\n".join(ICON_LINES), style=ACCENT_STYLE), banner)
    return header


def _render_option(label: str, is_selected: bool) -> Text:
    return Text(f" {label} ", style=SELECTED_STYLE if is_selected else "")


def _render_menu(texts: Texts, selected: MainMenuOption) -> RenderableType:
    lines = [Text(texts["menu.title"], style=f"bold {ACCENT_STYLE}")]
    for option in MainMenuOption:
        if option is MainMenuOption.EXIT:
            lines.append(Text(""))
        lines.append(_render_option(texts[option.value], option is selected))
    return Padding(Group(*lines), (1, 0, 0, 2))


def _render_hints(texts: Texts) -> RenderableType:
    hints = Text()
    for position, (key_label, text_key) in enumerate(HINTS):
        if position:
            hints.append("   ")
        hints.append(key_label, style=f"bold {ACCENT_STYLE}")
        hints.append(f" {texts[text_key]}")
    return Padding(hints, (1, 0, 0, 2))


def _render_screen(texts: Texts, body: RenderableType) -> RenderableType:
    """Moldura comum a todos os ecrãs: cabeçalho, conteúdo e teclas de controlo."""
    return Group(_render_header(texts), body, _render_hints(texts))


def render_main_menu(texts: Texts, selected: MainMenuOption) -> RenderableType:
    """Monta o ecrã do menu principal, com uma opção selecionada."""
    return _render_screen(texts, _render_menu(texts, selected))


def run_main_menu(console: Console, texts: Texts) -> MainMenuOption:
    """Mostra o menu principal e espera até o utilizador escolher uma opção.

    Args:
        console: consola onde o menu é desenhado.
        texts: textos da interface no idioma ativo.

    Returns:
        A opção escolhida. Q e Ctrl+C contam como `MainMenuOption.EXIT`.
    """
    options = list(MainMenuOption)
    index = 0
    with Live(
        render_main_menu(texts, options[index]),
        console=console,
        screen=True,
        auto_refresh=False,
    ) as live:
        while True:
            key = read_key()
            if key is Key.ENTER:
                return options[index]
            if key is Key.QUIT:
                return MainMenuOption.EXIT
            index = next_index(index, key, len(options))
            live.update(render_main_menu(texts, options[index]), refresh=True)
