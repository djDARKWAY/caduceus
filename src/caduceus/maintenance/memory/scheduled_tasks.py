r"""
Tarefas agendadas de arranque

Lista as tarefas do Agendador de Tarefas do Windows que correm quando o Windows arranca ou quando o
utilizador inicia sessão, e deixa desligá-las e ligá-las outra vez. É por aqui que arrancam muitos
atualizadores e programas que não aparecem nos programas de arranque. A lista vem do PowerShell
(`Get-ScheduledTask`), e ligar ou desligar faz-se com o `schtasks /Change`. Desligar não apaga a
tarefa. As tarefas da Microsoft e do Windows (pasta `\Microsoft`) ficam de fora. Exige
administrador.
"""

import base64
import json
import os
import subprocess
from dataclasses import dataclass

from caduceus.maintenance.actions import Action, Outcome, Report
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.memory.process_memory import memory_by_executable
from caduceus.maintenance.memory.startup_programs import UPDATER_WORDS, memory_of

_POWERSHELL = r"%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe"
_SCHTASKS = r"%WINDIR%\System32\schtasks.exe"
_TIMEOUT_SECONDS = 60
_LIST_SCRIPT = """
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\\Microsoft\\*' } |
  ForEach-Object {
  $kinds = @($_.Triggers | ForEach-Object { $_.CimClass.CimClassName })
  $logon = $kinds -contains 'MSFT_TaskLogonTrigger'
  if ($logon -or ($kinds -contains 'MSFT_TaskBootTrigger')) {
    $action = $_.Actions | Select-Object -First 1
    $command = if ($action) { ("$($action.Execute) $($action.Arguments)").Trim() } else { '' }
    [pscustomobject]@{
      Name = $_.TaskName; Folder = $_.TaskPath; Enabled = ($_.State -ne 'Disabled')
      Trigger = $(if ($logon) { 'logon' } else { 'boot' }); Command = $command
    }
  }
}
ConvertTo-Json -InputObject @($tasks) -Compress
"""


@dataclass
class TaskEntry:
    name: str
    folder: str  # a pasta do Agendador onde a tarefa está (por exemplo, `\ASUS\`)
    command: str
    trigger: str  # `logon` (ao iniciar sessão) ou `boot` (ao arrancar o Windows)
    enabled: bool
    memory_bytes: int | None  # None se o programa da tarefa não está em execução

    @property
    def full_name(self) -> str:
        return self.folder + self.name

    @property
    def needs_safe_mode_off(self) -> bool:
        """Só as tarefas de atualização se podem desligar sem risco; as restantes (segurança, VPN,
        controladores) exigem o Modo seguro desligado."""
        return not any(word in self.full_name.lower() for word in UPDATER_WORDS)


def parse_tasks(output: str, running: dict[str, int]) -> list[TaskEntry]:
    """As tarefas que o PowerShell listou, ordenadas pelo nome, de A a Z."""
    try:
        records = json.loads(output)
    except json.JSONDecodeError:
        return []  # sem lista legível, o menu mostra que não há tarefas
    if not isinstance(records, list):
        return []
    entries = [
        TaskEntry(
            name=str(record["Name"]),
            folder=str(record["Folder"]),
            command=str(record.get("Command", "")),
            trigger="boot" if record.get("Trigger") == "boot" else "logon",
            enabled=bool(record.get("Enabled", True)),
            memory_bytes=memory_of(str(record.get("Command", "")), running),
        )
        for record in records
        if isinstance(record, dict) and "Name" in record and "Folder" in record
    ]
    return sorted(entries, key=lambda entry: entry.name.casefold())


def list_scheduled_tasks() -> list[TaskEntry]:
    script = base64.b64encode(_LIST_SCRIPT.encode("utf-16-le")).decode("ascii")
    try:
        result = subprocess.run(
            [
                os.path.expandvars(_POWERSHELL),
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                script,
            ],
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []  # sem o PowerShell, o menu mostra que não há tarefas
    if result.returncode != 0:
        return []
    return parse_tasks(result.stdout.decode("utf-8", errors="replace"), memory_by_executable())


def toggle_task(entry: TaskEntry) -> Action:
    """A ação que liga a tarefa se estiver desligada e a desliga se estiver ligada."""

    def toggle(_report: Report) -> Outcome:
        if not is_admin():
            return Outcome(0, 0, admin_required=(entry.name,))
        switch = "/DISABLE" if entry.enabled else "/ENABLE"
        try:
            result = subprocess.run(
                [os.path.expandvars(_SCHTASKS), "/Change", "/TN", entry.full_name, switch],
                capture_output=True,
                timeout=_TIMEOUT_SECONDS,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return Outcome(0, 0, failures=(entry.name,))
        if result.returncode != 0:
            return Outcome(0, 0, failures=(entry.name,))
        entry.enabled = not entry.enabled
        return Outcome(0, 0)

    return toggle
