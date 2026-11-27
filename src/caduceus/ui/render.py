"""
Interface

Só desenho: o cabeçalho, o menu atual, o aviso e a linha de teclas de controlo.
"""

import shutil

from rich import box
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
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
    PROGRESS_WIDTH,
    SELECTED_STYLE,
    STARTUP_VISIBLE_ROWS,
    WINDOW_LINES,
)
from caduceus.controllers.menus import MenuItem, item_label
from caduceus.controllers.navigation import (
    Navigation,
    Sort,
    blocked_by_present_administrator,
    blocked_by_safe_mode,
    column_count,
    display_order,
    has_state_column,
    is_blocked,
)
from caduceus.maintenance.actions import Outcome, Step
from caduceus.settings import Settings
from caduceus.ui.assets import LOGO_LINES, LOGO_WIDTH, NAME_LINES, NAME_WIDTH
from caduceus.ui.i18n import Texts
from caduceus.ui.palette import ACCENT, ACCENT_DARK, DANGER, WARNING

VERSION_LABEL = f"v{__version__}"

HINTS = (
    ("↑", "hint.up"),
    ("↓", "hint.down"),
    ("ENTER", "hint.select"),
    ("BACKSPACE", "hint.back"),
)

SORT_HINT_KEY = "hint.sort"
OUTCOME_HINTS = (("ENTER", "hint.back"),)
NOTICE_HINTS = (("BACKSPACE", "hint.back"),)
CONFIRM_HINTS = (("ENTER", "hint.confirm"), ("BACKSPACE", "hint.cancel"))

NOT_COUNTED = "—"
RUN_ALL_MARK = "►"
RUN_FAST_MARK = "»"
BULLET = "•"

_BODY_PADDING = (1, 0, 0, 2)
_HINTS_PADDING = (0, 0, 0, 2)
_CONFIRM_PADDING = (1, 2)
_PANEL_BORDER_LINES = 2
_CONFIRM_TITLE_LINES = 2  # o título da opção e a linha em branco por baixo
_CONFIRM_GAP_LINES = 1  # linha livre entre o quadro e as teclas
_BOTTOM_MARGIN = 1  # linha livre por baixo das teclas (com texto, senão o Layout desenha um painel)
_MODE_KEYS = ("mode.normal", "mode.administrator")
_HEADER_PADDING = (1, 0, 0, 2)  # uma linha livre por cima e o mesmo recuo do corpo à esquerda
_HEADER_LINES = (
    max(len(LOGO_LINES) + 1, len(NAME_LINES) + 2) + _HEADER_PADDING[0]
)  # logótipo e modo, ou nome e versão
# Linhas da tabela antes da primeira opção: a em branco, os títulos das colunas e o separador
_TABLE_HEADER_LINES = 3
# Larguras fixas das colunas da lista com células, para não mudarem ao deslocar a lista
_NAME_WIDTH = 26
_STATE_WIDTH = 5
_COLUMN_PADDING = 2  # espaço à direita de cada coluna das tabelas
_SORT_MARKS = {False: "▲", True: "▼"}  # ordem crescente e decrescente
_SORT_MARK_WIDTH = 2  # o espaço e a seta que se juntam ao título da coluna ordenada
# O aviso de administrador fica ao nível dos títulos das colunas (a segunda linha do menu)
_TABLE_WARNING_LINE = 2


def _render_header(texts: Texts, administrator: bool) -> RenderableType:
    tagline = texts["app.tagline"]
    info_line = f"{tagline} {VERSION_LABEL:>{NAME_WIDTH - len(tagline) - 1}}"
    mode = texts["mode.administrator" if administrator else "mode.normal"]
    banner = Group(
        Text("\n".join(NAME_LINES), style=ACCENT, no_wrap=True),
        Text(""),
        Text(info_line, style=ACCENT, no_wrap=True),
    )
    # A coluna do logótipo tem a largura do modo mais comprido, para o nome não mudar de sítio
    logo_width = max(LOGO_WIDTH, *(len(texts[key]) for key in _MODE_KEYS))
    logo = Group(
        Text("\n".join(LOGO_LINES), style=ACCENT, no_wrap=True),
        Text(mode.center(logo_width), style=ACCENT_DARK, no_wrap=True),
    )
    header = Table.grid(padding=(0, 4))
    header.add_column(width=logo_width)
    header.add_column()
    header.add_row(logo, banner)
    return Padding(header, _HEADER_PADDING)


def _column_title(title: str, column: int, sort: Sort | None) -> str:
    if sort is not None and sort.column == column:
        return f"{title} {_SORT_MARKS[sort.descending]}"
    return title


def _column_width(title: str, width: int) -> int:
    """A largura da coluna, com espaço para a seta, para a tabela não mexer ao ordenar."""
    return max(width, len(title) + _SORT_MARK_WIDTH)


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
            style=ACCENT,
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
        box=box.SIMPLE_HEAD,
        pad_edge=False,
        header_style=f"bold {ACCENT}",
        padding=(0, _COLUMN_PADDING, 0, 0),
    )
    sort = navigation.sort
    gain_title = texts["table.gain"]
    table.add_column(
        _column_title(texts["table.action"], 0, sort), no_wrap=True, min_width=MENU_WIDTH
    )
    table.add_column(
        _column_title(gain_title, 1, sort),
        justify="right",
        no_wrap=True,
        min_width=_column_width(gain_title, 0),
    )
    items = navigation.menu.items
    for index in display_order(navigation):
        item = items[index]
        selected = index == navigation.index
        if item.runs_all:
            total = sum(
                navigation.estimates.get(other.label_key) or 0
                for other in items
                if not is_blocked(navigation, other) and not (item.skips_slow and other.slow)
            )
            if not items[index - 1].runs_all:
                table.add_section()
            weight = "" if item.skips_slow else "bold "
            style = f"bold white on {ACCENT}" if selected else f"{weight}{ACCENT}"
            mark = RUN_FAST_MARK if item.skips_slow else RUN_ALL_MARK
            title = Text(f" {mark} {item_label(texts, item)}")
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


def _state_cell(texts: Texts, item: MenuItem, settings: Settings, selected: bool) -> Text:
    is_on = _is_on(item, settings)
    state = Text("" if is_on is None else texts["setting.on" if is_on else "setting.off"])
    if not selected and is_on is not None:
        state.stylize(ACCENT if is_on else DANGER)
    return state


def _add_cells_columns(table: Table, texts: Texts, navigation: Navigation) -> None:
    menu, sort = navigation.menu, navigation.sort
    state_title = texts["table.state"]
    state_width = _column_width(state_title, _STATE_WIDTH)
    has_state = has_state_column(menu)
    # Sem a coluna do estado, o nome fica com o espaço dela, e a tabela mantém a largura
    name_width = _NAME_WIDTH if has_state else _NAME_WIDTH + state_width + _COLUMN_PADDING
    table.add_column(
        _column_title(texts["table.program"], 0, sort),
        no_wrap=True,
        overflow="ellipsis",
        width=name_width,
    )
    first_cell_column = 1
    if has_state:
        table.add_column(_column_title(state_title, 1, sort), no_wrap=True, width=state_width)
        first_cell_column = 2
    for offset, (column_key, width) in enumerate(menu.columns):
        title = texts[column_key]
        table.add_column(
            _column_title(title, first_cell_column + offset, sort),
            justify="right",
            no_wrap=True,
            width=_column_width(title, width),
        )


def _render_cells_table(texts: Texts, navigation: Navigation) -> RenderableType:
    """Os menus cujas opções têm colunas (os programas de arranque): nome, estado (se as opções o
    tiverem) e as células."""
    menu = navigation.menu
    table = Table(
        box=box.SIMPLE_HEAD,
        pad_edge=False,
        header_style=f"bold {ACCENT}",
        padding=(0, _COLUMN_PADDING, 0, 0),
    )
    _add_cells_columns(table, texts, navigation)
    has_state = has_state_column(menu)
    order = display_order(navigation)
    for position in _visible_rows(len(order), order.index(navigation.index)):
        index = order[position]
        item = menu.items[index]
        selected = index == navigation.index
        state = [_state_cell(texts, item, navigation.settings, selected)] if has_state else []
        cells = [_cell_text(texts, cell) for cell in item.cells]
        cells += [""] * (len(menu.columns) - len(cells))
        blocked = is_blocked(navigation, item)
        table.add_row(
            Text(f" {item_label(texts, item)}"),
            *state,
            *cells,
            style=SELECTED_STYLE if selected else ("dim" if blocked else ""),
        )
    found = sum(item.action is not None for item in menu.items)
    return Group(_menu_title(texts, navigation, found), table)


def _menu_title(texts: Texts, navigation: Navigation, count: int | None = None) -> Text:
    """O título do menu (com a contagem, se houver) e, a esbatido, porque há opções esbatidas."""
    title = texts[navigation.menu.title_key] + ("" if count is None else f" ({count})")
    text = Text(title, style=f"bold {ACCENT}")
    items = navigation.menu.items
    reasons = [
        texts[key]
        for key, blocked in (("blocked.safe_mode", blocked_by_safe_mode),)
        if any(blocked(navigation, item) for item in items)
    ]
    if reasons:
        text.append("  " + " · ".join(reasons), style=DETAIL_STYLE)
    return text


def _render_options(texts: Texts, navigation: Navigation) -> tuple[RenderableType, int]:
    """As opções do menu e as linhas que ocupam antes da primeira (para alinhar a descrição)."""
    if navigation.menu.columns:
        return _render_cells_table(texts, navigation), _TABLE_HEADER_LINES
    title = _menu_title(texts, navigation)
    if any(item.estimate is not None for item in navigation.menu.items):
        return Group(title, _render_estimates_table(texts, navigation)), _TABLE_HEADER_LINES
    options = [title]
    for position, item in enumerate(navigation.menu.items):
        if blocked_by_present_administrator(navigation, item):
            continue  # reabrir como administrador não aparece a quem já o é
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
    return Padding(hints, _HINTS_PADDING)


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
        pulse_style=ACCENT,
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


def _confirm_content_lines() -> int:
    """As linhas de conteúdo do quadro que o corpo comporta na altura real do terminal."""
    reserved = (
        _HEADER_LINES
        + 1  # as teclas
        + _BOTTOM_MARGIN
        + _BODY_PADDING[0]
        + _CONFIRM_TITLE_LINES
        + _CONFIRM_GAP_LINES
        + _PANEL_BORDER_LINES
        + 2 * _CONFIRM_PADDING[0]
    )
    return shutil.get_terminal_size((CONFIRM_WIDTH, WINDOW_LINES)).lines - reserved


def _fit_in_panel(warning: list[RenderableType], lines: list[Text]) -> list[RenderableType]:
    """As linhas que cabem por baixo do aviso, com uma linha livre até às teclas; se não couberem
    todas, as últimas são trocadas por «...»."""
    inner_width = CONFIRM_WIDTH - 2 - 2 * _CONFIRM_PADDING[1]
    used = len(Console(width=inner_width).render_lines(Group(*warning), pad=False))
    free = _confirm_content_lines() - used
    if len(lines) <= free:
        return list(lines)
    return [*lines[: max(free - 1, 0)], Text("  ...", style=WARNING)]


def _render_confirmation(
    texts: Texts, navigation: Navigation, item: MenuItem, confirm_key: str
) -> RenderableType:
    warning: list[RenderableType] = [Text(texts[confirm_key], style="bold")]
    skipped = [
        Text(f"  {BULLET} {item_label(texts, other)}", style=WARNING)
        for other in navigation.menu.items
        if item.runs_all and is_blocked(navigation, other) and not (item.skips_slow and other.slow)
    ]
    if skipped:
        warning += [Text(""), Text(texts["confirm.skipped"], style=WARNING)]
        warning += _fit_in_panel(warning, skipped)
    panel = Panel(
        Group(*warning),
        title=Text(f" {texts['confirm.title']} ", style=f"bold {ACCENT}"),
        border_style=ACCENT,
        box=box.HEAVY,
        padding=_CONFIRM_PADDING,
        width=CONFIRM_WIDTH,
    )
    title = Text(item_label(texts, item), style=f"bold {ACCENT}")
    return Padding(Group(title, Text(""), panel), _BODY_PADDING)


def _menu_hints(navigation: Navigation) -> tuple[tuple[str, str], ...]:
    """As teclas do menu; as tabelas juntam as das colunas (1 a N), que só nelas funcionam."""
    columns = column_count(navigation.menu)
    return (*HINTS, (f"1-{columns}", SORT_HINT_KEY)) if columns else HINTS


def _frame(
    texts: Texts,
    navigation: Navigation,
    body: RenderableType,
    hints: tuple[tuple[str, str], ...] = HINTS,
) -> RenderableType:
    # O cabeçalho no topo e as teclas na penúltima linha, por mais que o corpo cresça ou encolha
    layout = Layout()
    layout.split_column(
        Layout(_render_header(texts, navigation.administrator), size=_HEADER_LINES),
        Layout(body),
        Layout(_render_hints(texts, hints), size=1),
        Layout(Text(" "), size=_BOTTOM_MARGIN),
    )
    return layout


def render_screen(texts: Texts, navigation: Navigation) -> RenderableType:
    if navigation.notice is not None:
        return _frame(texts, navigation, _render_notice(texts, navigation.notice), NOTICE_HINTS)
    confirm_key = navigation.item.confirm_key
    if navigation.confirming and confirm_key is not None:
        return _frame(
            texts,
            navigation,
            _render_confirmation(texts, navigation, navigation.item, confirm_key),
            CONFIRM_HINTS,
        )
    if navigation.outcome is not None:
        title = item_label(texts, navigation.item)
        return _frame(
            texts, navigation, _render_outcome(texts, title, navigation.outcome), OUTCOME_HINTS
        )
    return _frame(texts, navigation, _render_menu(texts, navigation), _menu_hints(navigation))


def render_progress(texts: Texts, navigation: Navigation, step: Step) -> RenderableType:
    title = (
        texts[navigation.menu.title_key]
        if navigation.estimating
        else item_label(texts, navigation.item)
    )
    body = _render_progress(texts, title, step)
    return Group(_render_header(texts, navigation.administrator), body)


def open_display(console: Console, texts: Texts, navigation: Navigation) -> Live:
    return Live(
        render_screen(texts, navigation),
        console=console,
        screen=True,
        auto_refresh=False,  # só se redesenha quando algo muda: a consola clássica pisca se não
    )


def show(display: Live, texts: Texts, navigation: Navigation) -> None:
    display.update(render_screen(texts, navigation), refresh=True)


def show_progress(display: Live, texts: Texts, navigation: Navigation, step: Step) -> None:
    display.update(render_progress(texts, navigation, step), refresh=True)
