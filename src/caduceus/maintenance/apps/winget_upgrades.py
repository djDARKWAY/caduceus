"""
Atualizar aplicações

Atualiza, uma a uma, as aplicações com versão nova que o `winget` conhece. A lista vem do
`winget upgrade`, cuja tabela se lê pelas posições dos títulos das colunas (os títulos mudam com o
idioma do Windows, as posições não), e só interessa o ID de cada aplicação. Cada atualização corre
em silêncio (`winget upgrade --id`), por isso o resultado diz o que foi atualizado e o que falhou.
Alguns instaladores pedem o UAC por conta própria; o Caduceus não precisa de administrador.
"""

import ctypes
import re
import shutil
import subprocess
from dataclasses import dataclass

from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.system_tool import run_system_tool

_LIST_ARGUMENTS = ("upgrade", "--accept-source-agreements", "--disable-interactivity")
_UPGRADE_ARGUMENTS = (
    "upgrade",
    "--exact",
    "--silent",
    "--disable-interactivity",
    "--accept-package-agreements",
    "--accept-source-agreements",
    "--id",
)
_LIST_TIMEOUT_SECONDS = 120
_NO_APPLICABLE_UPGRADE = 0x8A15002B  # a aplicação já não tem atualização por fazer
_HEADER_COLUMN = re.compile(r"\S+(?: \S+)*")  # um título pode ter espaços simples; as colunas, dois
_SEPARATOR = re.compile(r"-{10,}")
_PACKAGE_ID = re.compile(r"[A-Za-z0-9][\w.+-]*")
_MIN_COLUMNS = 4  # nome, ID, versão e versão disponível (a origem pode faltar)


@dataclass(frozen=True)
class UpgradableApp:
    name: str
    package_id: str


def _output_encoding() -> str:
    """Sem consola, o `winget` escreve na página de códigos OEM e não em UTF-8."""
    return f"cp{ctypes.windll.kernel32.GetOEMCP()}"


def parse_upgradable(output: str) -> list[UpgradableApp]:
    """As aplicações da tabela do `winget upgrade`; a tabela acaba na primeira linha vazia."""
    lines = [line.rsplit("\r", 1)[-1].rstrip() for line in output.splitlines()]
    separator = next((i for i, line in enumerate(lines) if _SEPARATOR.fullmatch(line)), None)
    if separator is None or separator == 0:
        return []
    starts = [match.start() for match in _HEADER_COLUMN.finditer(lines[separator - 1])]
    if len(starts) < _MIN_COLUMNS:
        return []
    apps: list[UpgradableApp] = []
    for line in lines[separator + 1 :]:
        if not line.strip():
            break
        name = line[starts[0] : starts[1]].strip()
        package_id = line[starts[1] : starts[2]].strip()
        if name and _PACKAGE_ID.fullmatch(package_id):
            apps.append(UpgradableApp(name, package_id))
    return apps


def list_upgradable(winget: str) -> list[UpgradableApp]:
    try:
        result = subprocess.run(
            [winget, *_LIST_ARGUMENTS],
            capture_output=True,
            timeout=_LIST_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []  # sem lista legível, não há nada que se saiba atualizar
    return parse_upgradable(result.stdout.decode(_output_encoding(), errors="replace"))


def update_all_apps(report: Report) -> Outcome:
    """A ação que atualiza todas as aplicações com atualização, uma a uma."""
    winget = shutil.which("winget")
    if winget is None:
        return Outcome(0, 0, notice="notice.winget_missing")
    report(Step("apps.update.checking", 0, 0))
    apps = list_upgradable(winget)
    if not apps:
        return Outcome(0, 0, notice="notice.apps_up_to_date")
    rows: list[Row] = []
    failures: list[str] = []
    for position, app in enumerate(apps, start=1):
        values = {"name": app.name, "position": f"{position}/{len(apps)}"}
        updated = run_system_tool(
            winget,
            [*_UPGRADE_ARGUMENTS, app.package_id],
            report,
            "apps.update.step",
            success_codes=(0, _NO_APPLICABLE_UPGRADE),
            reports_percent=True,
            values=values,
        )
        if updated:
            rows.append(Row("category.updated_app", 1, 0, {"name": app.name}))
        else:
            failures.append(app.name)
    return Outcome(len(rows), 0, failures=tuple(failures), rows=tuple(rows))
