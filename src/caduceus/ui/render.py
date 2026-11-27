"""
Interface

Só desenho: o cabeçalho, o menu atual, o aviso e a linha de teclas de controlo.
"""

from rich import box
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from caduceus import __version__
from caduceus.config import (
    CLEANUP_MIN_AGE_HOURS,
    CONFIRM_WIDTH,
    DETAIL_GAP,
    DETAIL_STYLE,
    DETAIL_WIDTH,
    LOG_MIN_AGE_HOURS,
    MAX_LISTED_PLACES,
    MENU_WIDTH,
    PROGRESS_REFRESH_RATE,
    PROGRESS_WIDTH,
    SELECTED_STYLE,
    STARTUP_VISIBLE_ROWS,
)
from caduceus.controllers.menus import MenuItem
from caduceus.controllers.navigation import Navigation, is_blocked
from caduceus.maintenance.actions import Outcome, Step
from caduceus.settings import Settings
from caduceus.ui.assets import LOGO_LINES, NAME_LINES, NAME_WIDTH
from caduceus.ui.i18n import Texts
from caduceus.ui.palette import ACCENT, DANGER, WARNING

VERSION_LABEL = f"v{__version__}"

HINTS = (
    ("↑", "hint.up"),
    ("↓", "hint.down"),
    ("ENTER", "hint.select"),
    ("BACKSPACE", "hint.back"),
)

OUTCOME_HINTS = (("ENTER", "hint.back"),)
NOTICE_HINTS = (("BACKSPACE", "hint.back"),)
CONFIRM_HINTS = (("ENTER", "hint.confirm"), ("BACKSPACE", "hint.cancel"))

NOT_COUNTED = "—"
RUN_ALL_MARK = "►"
BULLET = "•"

_BODY_PADDING = (1, 0, 0, 2)
# Linhas da tabela antes da primeira opção: a em branco, os títulos das colunas e o separador
_TABLE_HEADER_LINES = 3
# Larguras fixas das colunas da lista com células, para não mudarem ao deslocar a lista
_NAME_WIDTH = 28
_STATE_WIDTH = 5
# O aviso de administrador fica ao nível dos títulos das colunas (a segunda linha do menu)
_TABLE_WARNING_LINE = 2


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


def item_label(texts: Texts, item: MenuItem) -> str:
    return item.label if item.label is not None else texts[item.label_key]


def _is_on(item: MenuItem, settings: Settings) -> bool | None:
    """O estado ligado/desligado que a opção mostra, ou None se a opção não tem estado."""
    if item.setting is not None:
        return bool(getattr(settings, item.setting))
    return item.state() if item.state is not None else None


def _render_option(
    texts: Texts, item: MenuItem, is_selected: bool, settings: Settings, blocked: bool = False
) -> Text:
    style = "dim" if blocked else (SELECTED_STYLE if is_selected else "")
    option = Text(f" {item_label(texts, item)} ", style=style)
    is_on = _is_on(item, settings)
    if is_on is not None:
        option.append(
            texts["setting.on" if is_on else "setting.off"],
            style=ACCENT if is_on else DANGER,
        )
        option.append(" ")
    option.pad_right(max(0, MENU_WIDTH - option.cell_len))
    return option


def _render_description(description: str) -> list[RenderableType]:
    """Cada linha da descrição; as que começam por um marcador quebram com recuo, alinhadas com o
    texto que vem depois do marcador."""
    lines: list[RenderableType] = []
    for line in description.splitlines():
        if not line.startswith(f"{BULLET} "):
            lines.append(Text(line, style=DETAIL_STYLE))
            continue
        item = Table.grid(padding=(0, 1, 0, 0))
        item.add_column(no_wrap=True)
        item.add_column(overflow="fold")
        item.add_row(Text(BULLET, style=DETAIL_STYLE), Text(line[2:], style=DETAIL_STYLE))
        lines.append(item)
    return lines


def _render_detail(
    texts: Texts, item: MenuItem, warning_line: int, description_line: int
) -> RenderableType:
    """A descrição, a começar em `description_line`, e o aviso de administrador (se houver) em
    `warning_line`, contadas a partir do título do menu."""
    if item.description_key is None:
        return Text("")
    lines: list[RenderableType] = [Text("") for _ in range(warning_line)]
    if item.admin is not None:
        lines.append(Text(texts[item.admin.value], style=WARNING))
    lines += [Text("") for _ in range(description_line - len(lines))]
    description = texts[item.description_key].format(
        cleanup_age=CLEANUP_MIN_AGE_HOURS, log_age=LOG_MIN_AGE_HOURS, **item.description_values
    )
    lines += _render_description(description)
    return Group(*lines)


def format_estimate(estimate: int | None) -> str:
    if estimate is None:
        return NOT_COUNTED
    return f"~{format_size(estimate)}" if estimate else format_size(0)


def _render_estimates_table(texts: Texts, navigation: Navigation) -> RenderableType:
    table = Table(
        box=box.SIMPLE_HEAD, pad_edge=False, header_style=f"bold {ACCENT}", padding=(0, 2, 0, 0)
    )
    table.add_column(texts["table.action"], no_wrap=True, min_width=MENU_WIDTH)
    table.add_column(texts["table.gain"], justify="right", no_wrap=True)
    items = navigation.menu.items
    total = sum(
        navigation.estimates.get(item.label_key) or 0
        for item in items
        if not is_blocked(navigation, item)
    )
    for position, item in enumerate(items):
        selected = position == navigation.index
        if item.runs_all:
            table.add_section()
            style = f"bold white on {ACCENT}" if selected else f"bold {ACCENT}"
            title = Text(f" {RUN_ALL_MARK} {item_label(texts, item)}")
            table.add_row(title, format_estimate(total), style=style)
            continue
        blocked = is_blocked(navigation, item)
        estimate = navigation.estimates.get(item.label_key)
        table.add_row(
            Text(f" {item_label(texts, item)}"),
            format_estimate(estimate),
            style=SELECTED_STYLE if selected else ("dim" if blocked else ""),
        )
    return table


def _cell_text(texts: Texts, cell: int | str | None) -> str:
    return texts[cell] if isinstance(cell, str) else format_estimate(cell)


def _visible_rows(count: int, index: int) -> range:
    """As linhas da lista que cabem no ecrã, com a selecionada lá dentro (a meio, se possível)."""
    start = min(max(index - STARTUP_VISIBLE_ROWS // 2, 0), max(count - STARTUP_VISIBLE_ROWS, 0))
    return range(start, min(start + STARTUP_VISIBLE_ROWS, count))


def _render_cells_table(texts: Texts, navigation: Navigation) -> RenderableType:
    """Os menus cujas opções têm colunas (os programas de arranque): nome, estado e as células."""
    menu = navigation.menu
    table = Table(
        box=box.SIMPLE_HEAD, pad_edge=False, header_style=f"bold {ACCENT}", padding=(0, 2, 0, 0)
    )
    table.add_column(texts["table.program"], no_wrap=True, overflow="ellipsis", width=_NAME_WIDTH)
    table.add_column(texts["table.state"], no_wrap=True, width=_STATE_WIDTH)
    for column_key, width in menu.columns:
        table.add_column(texts[column_key], justify="right", no_wrap=True, width=width)
    rows = _visible_rows(len(menu.items), navigation.index)
    for position in rows:
        item = menu.items[position]
        selected = position == navigation.index
        is_on = _is_on(item, navigation.settings)
        state = Text("" if is_on is None else texts["setting.on" if is_on else "setting.off"])
        if not selected and is_on is not None:
            state.stylize(ACCENT if is_on else DANGER)
        cells = [_cell_text(texts, cell) for cell in item.cells]
        cells += [""] * (len(menu.columns) - len(cells))
        blocked = is_blocked(navigation, item)
        table.add_row(
            Text(f" {item_label(texts, item)}"),
            state,
            *cells,
            style=SELECTED_STYLE if selected else ("dim" if blocked else ""),
        )
    title = texts[menu.title_key]
    if len(rows) < len(menu.items):
        title += f"  ({rows.start + 1}-{rows.stop} / {len(menu.items)})"
    return Group(Text(title, style=f"bold {ACCENT}"), table)


def _render_options(texts: Texts, navigation: Navigation) -> tuple[RenderableType, int]:
    """As opções do menu e as linhas que ocupam antes da primeira (para alinhar a descrição)."""
    if navigation.menu.columns:
        return _render_cells_table(texts, navigation), _TABLE_HEADER_LINES
    title = Text(texts[navigation.menu.title_key], style=f"bold {ACCENT}")
    if any(item.estimate is not None for item in navigation.menu.items):
        return Group(title, _render_estimates_table(texts, navigation)), _TABLE_HEADER_LINES
    options = [title]
    for position, item in enumerate(navigation.menu.items):
        if item.quits:
            options.append(Text(""))
        is_selected = position == navigation.index
        blocked = is_blocked(navigation, item)
        options.append(_render_option(texts, item, is_selected, navigation.settings, blocked))
    return Group(*options), 0


def _render_menu(texts: Texts, navigation: Navigation) -> RenderableType:
    options, header_lines = _render_options(texts, navigation)
    layout = Table.grid(padding=(0, 0, 0, DETAIL_GAP))
    layout.add_column(no_wrap=True)
    layout.add_column(max_width=DETAIL_WIDTH)
    first_option_line = 1 + header_lines
    if header_lines:
        # Com tabela, a descrição fica sempre na primeira linha e o aviso nos títulos das colunas
        warning_line, description_line = _TABLE_WARNING_LINE, first_option_line
    else:
        warning_line = first_option_line
        description_line = first_option_line + (2 if navigation.item.admin is not None else 0)
    detail = _render_detail(texts, navigation.item, warning_line, description_line)
    layout.add_row(options, detail)
    return Padding(layout, _BODY_PADDING)


def _render_notice(texts: Texts, notice: str) -> RenderableType:
    return Padding(Text(texts[notice]), _BODY_PADDING)


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
    progress_bar = ProgressBar(
        total=step.total or None,
        completed=step.done,
        width=PROGRESS_WIDTH,
        pulse=not step.total,
        complete_style=ACCENT,
        finished_style=ACCENT,
    )
    percentage = Text(f"{step.done * 100 // step.total}%" if step.total else "")
    bar.add_row(progress_bar, percentage, Spinner("dots", style=ACCENT))
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
        label = Text(texts[row.label_key].format(**row.values))
        if row.needs_admin:
            label.append(f" {texts['admin.tag']}", style=WARNING)
        items = NOT_COUNTED if row.items is None else str(row.items)
        table.add_row(label, items, format_size(row.bytes_freed))
    table.add_section()
    nothing_counted = not outcome.items_counted
    table.add_row(
        Text(texts["result.total"], style="bold"),
        Text(NOT_COUNTED if nothing_counted else str(outcome.items), style="bold"),
        Text(format_size(outcome.bytes_freed), style="bold"),
    )
    return table


def _render_unfinished(texts: Texts, outcome: Outcome) -> RenderableType | None:
    """O que ficou por limpar (sem administrador ou por falha), por grupo, ou None se nada ficou."""
    lines: list[RenderableType] = []
    for label_key, places in (
        ("result.admin", outcome.admin_required),
        ("result.failures", outcome.failures),
    ):
        if not places:
            continue
        if lines:
            lines.append(Text(""))
        lines.append(Text(texts[label_key], style=WARNING))
        lines += [
            Text(f"  {place}", style=WARNING, no_wrap=True, overflow="ellipsis")
            for place in places[:MAX_LISTED_PLACES]
        ]
        if len(places) > MAX_LISTED_PLACES:
            more = texts["result.more"].format(count=len(places) - MAX_LISTED_PLACES)
            lines.append(Text(more, style=WARNING))
    return Group(*lines) if lines else None


def _render_outcome(texts: Texts, title: str, outcome: Outcome) -> RenderableType:
    body: RenderableType = _render_breakdown(texts, outcome)
    unfinished = _render_unfinished(texts, outcome)
    if unfinished is not None:
        # A lista fica à direita da tabela, a começar ao nível dos títulos das colunas
        layout = Table.grid(padding=(0, 0, 0, DETAIL_GAP))
        layout.add_column(no_wrap=True)
        layout.add_column(max_width=DETAIL_WIDTH)
        layout.add_row(body, Group(Text(""), unfinished))
        body = layout
    return Padding(Group(Text(title, style=f"bold {ACCENT}"), body), _BODY_PADDING)


def _render_confirmation(
    texts: Texts, navigation: Navigation, item: MenuItem, confirm_key: str
) -> RenderableType:
    warning: list[RenderableType] = [Text(texts[confirm_key], style="bold")]
    skipped = [
        item_label(texts, other)
        for other in navigation.menu.items
        if item.runs_all and is_blocked(navigation, other)
    ]
    if skipped:
        warning += [Text(""), Text(texts["confirm.skipped"], style=WARNING)]
        warning += [Text(f"  {BULLET} {name}", style=WARNING) for name in skipped]
    panel = Panel(
        Group(*warning),
        title=Text(f" {texts['confirm.title']} ", style=f"bold {DANGER}"),
        border_style=DANGER,
        box=box.HEAVY,
        padding=(1, 2),
        width=CONFIRM_WIDTH,
    )
    title = Text(item_label(texts, item), style=f"bold {ACCENT}")
    return Padding(Group(title, Text(""), panel), _BODY_PADDING)


def _frame(
    texts: Texts, body: RenderableType, hints: tuple[tuple[str, str], ...] = HINTS
) -> RenderableType:
    return Group(_render_header(texts), body, _render_hints(texts, hints))


def render_screen(texts: Texts, navigation: Navigation) -> RenderableType:
    if navigation.notice is not None:
        return _frame(texts, _render_notice(texts, navigation.notice), NOTICE_HINTS)
    confirm_key = navigation.item.confirm_key
    if navigation.confirming and confirm_key is not None:
        return _frame(
            texts,
            _render_confirmation(texts, navigation, navigation.item, confirm_key),
            CONFIRM_HINTS,
        )
    if navigation.outcome is not None:
        title = item_label(texts, navigation.item)
        return _frame(texts, _render_outcome(texts, title, navigation.outcome), OUTCOME_HINTS)
    return _frame(texts, _render_menu(texts, navigation))


def render_progress(texts: Texts, navigation: Navigation, step: Step) -> RenderableType:
    title = (
        texts[navigation.menu.title_key]
        if navigation.estimating
        else item_label(texts, navigation.item)
    )
    body = _render_progress(texts, title, step)
    return Group(_render_header(texts), body)


def open_display(console: Console, texts: Texts, navigation: Navigation) -> Live:
    return Live(
        render_screen(texts, navigation),
        console=console,
        screen=True,
        refresh_per_second=PROGRESS_REFRESH_RATE,
    )


def show(display: Live, texts: Texts, navigation: Navigation) -> None:
    display.update(render_screen(texts, navigation), refresh=True)


def show_progress(display: Live, texts: Texts, navigation: Navigation, step: Step) -> None:
    display.update(render_progress(texts, navigation, step), refresh=True)
