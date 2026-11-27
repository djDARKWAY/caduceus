"""
Interface

Só desenho: o cabeçalho, o menu atual, o aviso e a linha de teclas de controlo.
"""

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from caduceus import __version__
from caduceus.branding import BANNER_LINES, BANNER_WIDTH, ICON_LINES
from caduceus.config import ACCENT_STYLE, DETAIL_GAP, DETAIL_STYLE, DETAIL_WIDTH, SELECTED_STYLE
from caduceus.i18n import Texts
from caduceus.menus import Menu, MenuItem
from caduceus.navigation import Navigation

VERSION_LABEL = f"v{__version__}"

HINTS = (
    ("↑", "hint.up"),
    ("↓", "hint.down"),
    ("ENTER", "hint.select"),
    ("BACKSPACE", "hint.back"),
    ("Q", "hint.quit"),
)

_BODY_PADDING = (1, 0, 0, 2)


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


def _render_detail(texts: Texts, item: MenuItem) -> RenderableType:
    if item.description_key is None:
        return Text("")
    # A linha em branco alinha a descrição com a primeira opção, por baixo do título
    return Group(Text(""), Text(texts[item.description_key], style=DETAIL_STYLE))


def _render_menu(texts: Texts, menu: Menu, selected_index: int) -> RenderableType:
    options = [Text(texts[menu.title_key], style=f"bold {ACCENT_STYLE}")]
    for position, item in enumerate(menu.items):
        if item.quits:
            options.append(Text(""))
        options.append(_render_option(texts[item.label_key], position == selected_index))
    layout = Table.grid(padding=(0, 0, 0, DETAIL_GAP))
    layout.add_column(no_wrap=True)
    layout.add_column(max_width=DETAIL_WIDTH)
    layout.add_row(Group(*options), _render_detail(texts, menu.items[selected_index]))
    return Padding(layout, _BODY_PADDING)


def _render_notice(texts: Texts) -> RenderableType:
    return Padding(Text(texts["menu.not_available"]), _BODY_PADDING)


def _render_hints(texts: Texts) -> RenderableType:
    hints = Text()
    for position, (key_label, text_key) in enumerate(HINTS):
        if position:
            hints.append("   ")
        hints.append(key_label, style=f"bold {ACCENT_STYLE}")
        hints.append(f" {texts[text_key]}")
    return Padding(hints, _BODY_PADDING)


def render_screen(texts: Texts, navigation: Navigation) -> RenderableType:
    if navigation.notice:
        body = _render_notice(texts)
    else:
        body = _render_menu(texts, navigation.menu, navigation.index)
    return Group(_render_header(texts), body, _render_hints(texts))


def open_display(console: Console, texts: Texts, navigation: Navigation) -> Live:
    return Live(
        render_screen(texts, navigation),
        console=console,
        screen=True,
        auto_refresh=False,
    )


def show(display: Live, texts: Texts, navigation: Navigation) -> None:
    display.update(render_screen(texts, navigation), refresh=True)
