"""
Aplicações da Microsoft Store

Lista as aplicações da Store instaladas para o utilizador (as do sistema ficam de fora) e deixa
repará-las ou repô-las. Reparar volta a registar a aplicação a partir dos ficheiros que ela já tem
(`Add-AppxPackage -Register`), o que corrige uma aplicação que deixou de abrir e não toca nos dados.
Repor corre o `Reset-AppxPackage`, que apaga os dados e as definições locais da aplicação e a deixa
como acabada de instalar, sem a desinstalar. A lista vem do PowerShell (`Get-AppxPackage`).
"""

import json
import re
from dataclasses import dataclass

from caduceus.maintenance.actions import Action, Outcome, Report, Row
from caduceus.maintenance.powershell import POWERSHELL_FROM_SYSTEM32, run_powershell
from caduceus.maintenance.system_tool import run_system_tool

_FULL_NAME = re.compile(r"[\w.~-]+")  # os nomes completos dos pacotes só têm estes caracteres
_LIST_SCRIPT = """
$apps = Get-AppxPackage -PackageTypeFilter Main |
  Where-Object { -not $_.IsFramework -and $_.SignatureKind -ne 'System' -and $_.InstallLocation } |
  ForEach-Object {
    [pscustomobject]@{ Name = $_.Name; FullName = $_.PackageFullName; Version = "$($_.Version)" }
  }
ConvertTo-Json -InputObject @($apps) -Compress
"""
_PACKAGE_LOOKUP = (
    "$ErrorActionPreference = 'Stop'; "
    "$package = Get-AppxPackage | Where-Object {{ $_.PackageFullName -eq '{full_name}' }}; "
)
_REPAIR_SCRIPT = _PACKAGE_LOOKUP + (
    "Add-AppxPackage -DisableDevelopmentMode "
    "-Register (Join-Path $package.InstallLocation 'AppxManifest.xml')"
)
_RESET_SCRIPT = _PACKAGE_LOOKUP + "Reset-AppxPackage -Package $package.PackageFullName"


@dataclass(frozen=True)
class StoreApp:
    name: str
    full_name: str
    version: str


def parse_store_apps(output: str) -> list[StoreApp]:
    """As aplicações que o PowerShell listou, ordenadas pelo nome, de A a Z."""
    try:
        records = json.loads(output)
    except json.JSONDecodeError:
        return []  # sem lista legível, o menu mostra que não há aplicações
    if not isinstance(records, list):
        return []
    apps = [
        StoreApp(str(record["Name"]), str(record["FullName"]), str(record.get("Version", "")))
        for record in records
        if isinstance(record, dict)
        and "Name" in record
        and _FULL_NAME.fullmatch(str(record.get("FullName", "")))
    ]
    return sorted(apps, key=lambda app: app.name.casefold())


def list_store_apps() -> list[StoreApp]:
    output = run_powershell(_LIST_SCRIPT)
    return parse_store_apps(output) if output is not None else []


def _package_action(app: StoreApp, script: str, step_key: str, row_key: str) -> Action:
    def run(report: Report) -> Outcome:
        command = [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script.format(full_name=app.full_name),
        ]
        done = run_system_tool(
            POWERSHELL_FROM_SYSTEM32, command, report, step_key, values={"name": app.name}
        )
        if not done:
            return Outcome(0, 0, failures=(app.name,))
        return Outcome(1, 0, rows=(Row(row_key, 1, 0, {"name": app.name}),))

    return run


def repair_store_app(app: StoreApp) -> Action:
    """A ação que volta a registar a aplicação, sem tocar nos dados dela."""
    return _package_action(app, _REPAIR_SCRIPT, "apps.repair.step", "category.repaired_app")


def reset_store_app(app: StoreApp) -> Action:
    """A ação que apaga os dados e as definições locais da aplicação, sem a desinstalar."""
    return _package_action(app, _RESET_SCRIPT, "apps.reset.step", "category.reset_app")
