"""
Interface

Só desenho: o cabeçalho, o menu atual, o aviso e a linha de teclas de controlo.
"""

from rich import box
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from caduceus import __version__
from caduceus.config import (
    DETAIL_GAP,
    DETAIL_STYLE,
    DETAIL_WIDTH,
    PROGRESS_WIDTH,
    SELECTED_STYLE,
)
from caduceus.controllers.menus import Menu, MenuItem
from caduceus.controllers.navigation import Navigation
from caduceus.maintenance.actions import Outcome, Step
from caduceus.ui.assets import LOGO_LINES, NAME_LINES, NAME_WIDTH
from caduceus.ui.i18n import Texts
from caduceus.ui.palette import ACCENT, WARNING

VERSION_LABEL = f"v{__version__}"

HINTS = (
    ("↑", "hint.up"),
    ("↓", "hint.down"),
    ("ENTER", "hint.select"),
    ("BACKSPACE", "hint.back"),
    ("Q", "hint.quit"),
)

OUTCOME_HINTS = (("ENTER", "hint.back"),)

_BODY_PADDING = (1, 0, 0, 2)


def _render_header(texts: Texts) -> RenderableType:
    tagline = texts["app.tagline"]
    info_line = f"{tagline} {VERSION_LABEL:>{NAME_WIDTH - len(tagline) - 1}}"
    banner = Group(
        Text("\n".join(NAME_LINES), style=ACCENT, no_wrap=True),
        Text(""),
        Text(info_line, style=ACCENT, no_wrap=True),
    )
    header = Table.grid(padding=(0, 4))
    header.add_column(vertical="middle")
    header.add_column()
    header.add_row(Text("\n".join(LOGO_LINES), style=ACCENT), banner)
    return header


def _render_option(label: str, is_selected: bool) -> Text:
    return Text(f" {label} ", style=SELECTED_STYLE if is_selected else "")


def _render_detail(texts: Texts, item: MenuItem) -> RenderableType:
    if item.description_key is None:
        return Text("")
    # A linha em branco alinha a descrição com a primeira opção, por baixo do título
    return Group(Text(""), Text(texts[item.description_key], style=DETAIL_STYLE))


def _render_menu(texts: Texts, menu: Menu, selected_index: int) -> RenderableType:
    options = [Text(texts[menu.title_key], style=f"bold {ACCENT}")]
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


def _render_hints(texts: Texts, shown: tuple[tuple[str, str], ...] = HINTS) -> RenderableType:
    hints = Text()
    for position, (key_label, text_key) in enumerate(shown):
        if position:
            hints.append("   ")
        hints.append(key_label, style=f"bold {ACCENT}")
        hints.append(f" {texts[text_key]}")
    return Padding(hints, _BODY_PADDING)


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    value = size / 1024
    for unit in ("KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _render_progress(texts: Texts, title: str, step: Step) -> RenderableType:
    bar = Table.grid(padding=(0, 0, 0, 2))
    bar.add_row(
        ProgressBar(
            total=step.total,
            completed=step.done,
            width=PROGRESS_WIDTH,
            complete_style=ACCENT,
            finished_style=ACCENT,
        ),
        Text(f"{step.done * 100 // step.total}%"),
    )
    current = texts[step.text_key].format(**step.values)
    body = Group(
        Text(title, style=f"bold {ACCENT}"),
        Text(""),
        bar,
        Text(""),
        Text(current, style=DETAIL_STYLE, no_wrap=True, overflow="ellipsis"),
    )
    return Padding(body, _BODY_PADDING)


def _render_breakdown(texts: Texts, outcome: Outcome) -> RenderableType:
    table = Table(box=box.SIMPLE_HEAD, header_style=f"bold {ACCENT}", pad_edge=False)
    table.add_column(texts["result.category"], no_wrap=True)
    table.add_column(texts["result.items"], justify="right")
    table.add_column(texts["result.freed"], justify="right")
    for row in outcome.rows:
        label = texts[row.label_key].format(**row.values)
        table.add_row(label, str(row.items), format_size(row.bytes_freed))
    table.add_section()
    table.add_row(
        Text(texts["result.total"], style="bold"),
        Text(str(outcome.items), style="bold"),
        Text(format_size(outcome.bytes_freed), style="bold"),
    )
    return table


def _render_outcome(texts: Texts, title: str, outcome: Outcome) -> RenderableType:
    lines = [
        Text(title, style=f"bold {ACCENT}"),
        Text(""),
        Text(texts["result.done"]),
        _render_breakdown(texts, outcome),
    ]
    for label_key, places in (
        ("result.admin", outcome.admin_required),
        ("result.failures", outcome.failures),
    ):
        if places:
            lines += [Text(""), Text(texts[label_key], style=WARNING)]
            lines += [Text(f"  {place}", style=WARNING, no_wrap=True) for place in places]
    return Padding(Group(*lines), _BODY_PADDING)


def _frame(
    texts: Texts, body: RenderableType, hints: tuple[tuple[str, str], ...] = HINTS
) -> RenderableType:
    return Group(_render_header(texts), body, _render_hints(texts, hints))


def render_screen(texts: Texts, navigation: Navigation) -> RenderableType:
    if navigation.notice:
        return _frame(texts, _render_notice(texts))
    if navigation.outcome is not None:
        title = texts[navigation.item.label_key]
        return _frame(texts, _render_outcome(texts, title, navigation.outcome), OUTCOME_HINTS)
    return _frame(texts, _render_menu(texts, navigation.menu, navigation.index))


def render_progress(texts: Texts, navigation: Navigation, step: Step) -> RenderableType:
    body = _render_progress(texts, texts[navigation.item.label_key], step)
    return Group(_render_header(texts), body)


def open_display(console: Console, texts: Texts, navigation: Navigation) -> Live:
    return Live(
        render_screen(texts, navigation),
        console=console,
        screen=True,
        auto_refresh=False,
    )


def show(display: Live, texts: Texts, navigation: Navigation) -> None:
    display.update(render_screen(texts, navigation), refresh=True)


def show_progress(display: Live, texts: Texts, navigation: Navigation, step: Step) -> None:
    display.update(render_progress(texts, navigation, step), refresh=True)
