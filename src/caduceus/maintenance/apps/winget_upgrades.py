"""
Atualizar aplicações

Lista as aplicações com versão nova que o `winget` conhece (a versão atual e a mais recente) e
atualiza as que o utilizador escolher, uma a uma ou todas. A lista vem do `winget upgrade`, cuja
tabela se lê pelas posições dos títulos das colunas (os títulos mudam com o idioma do Windows, as
posições não). Cada atualização corre em silêncio (`winget upgrade --id`), por isso o resultado diz
o que foi atualizado e o que falhou. Alguns instaladores pedem o UAC por conta própria; o Caduceus
não precisa de administrador.
"""

import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from caduceus.maintenance.actions import Action, Outcome, Report, Row
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
_NAME, _ID, _CURRENT, _AVAILABLE = range(4)


@dataclass(frozen=True)
class UpgradableApp:
    name: str
    package_id: str
    version: str  # a versão instalada
    available: str  # a versão mais recente


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
        cell = [
            line[start:end].strip() for start, end in zip(starts, [*starts[1:], None], strict=True)
        ]
        if cell[_NAME] and _PACKAGE_ID.fullmatch(cell[_ID]):
            apps.append(UpgradableApp(cell[_NAME], cell[_ID], cell[_CURRENT], cell[_AVAILABLE]))
    return apps


def list_upgradable() -> list[UpgradableApp]:
    """As aplicações com atualização, ou nenhuma se o `winget` não existe ou não responde."""
    winget = shutil.which("winget")
    if winget is None:
        return []
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
    return parse_upgradable(result.stdout.decode("utf-8", errors="replace"))


def update_apps(apps: Sequence[UpgradableApp]) -> Action:
    """A ação que atualiza as aplicações dadas, uma a uma, e diz o que atualizou e o que falhou."""

    def update(report: Report) -> Outcome:
        winget = shutil.which("winget")
        if winget is None:
            return Outcome(0, 0, failures=tuple(app.name for app in apps))
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

    return update
