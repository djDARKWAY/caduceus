r"""
Apagar o Windows.old

Apaga a instalação anterior do Windows (C:\Windows.old), o que tira a possibilidade de voltar à
versão anterior. Não apaga nada por conta própria: pede ao Limpeza de Disco do Windows
(`cleanmgr`) que corra só o seu tratamento "Instalações anteriores do Windows", que sabe tratar das
permissões e das junções da pasta. O Caduceus só liga esse tratamento, num perfil que nenhum outro
use (o `/sagerun` corre todos os tratamentos ligados nesse perfil), espera e desliga-o. O espaço
libertado mede-se pela diferença de espaço livre no disco do sistema. Exige administrador.
"""

import os
import re
import shutil
import subprocess
import time
import winreg
from pathlib import Path

from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.cleaner import folder_size

_FOLDER = r"%SystemDrive%\Windows.old"
_CLEANMGR = r"%WINDIR%\System32\cleanmgr.exe"
_HANDLERS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches"
_HANDLER_KEY = _HANDLERS_KEY + r"\Previous Installations"
_PROFILE_FLAGS = re.compile(r"StateFlags(\d{4})")
_PROFILES = range(6471, 10000)  # os números de perfil do `/sagerun` têm quatro dígitos
_FLAG_RUN_HANDLER = 2
_POLL_SECONDS = 0.2
# Grupo de processos próprio: o Ctrl+C não chega ao Limpeza de Disco, que não deve ser interrompido
_NO_CONTROLS = subprocess.CREATE_NEW_PROCESS_GROUP


def _profiles_in_use() -> set[int]:
    """Os perfis de limpeza que algum tratamento do Limpeza de Disco já tem ligado."""
    used: set[int] = set()
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HANDLERS_KEY) as handlers:
        for handler_index in range(winreg.QueryInfoKey(handlers)[0]):
            with winreg.OpenKey(handlers, winreg.EnumKey(handlers, handler_index)) as handler:
                for value_index in range(winreg.QueryInfoKey(handler)[1]):
                    match = _PROFILE_FLAGS.fullmatch(winreg.EnumValue(handler, value_index)[0])
                    if match:
                        used.add(int(match.group(1)))
    return used


def free_profile(used: set[int]) -> int:
    """O primeiro perfil que nenhum tratamento usa: o `/sagerun` corre todos os que o tiverem."""
    for profile in _PROFILES:
        if profile not in used:
            return profile
    raise OSError("sem perfis de limpeza livres")


def _run_cleanmgr(report: Report) -> None:
    profile = free_profile(_profiles_in_use())
    flags = f"StateFlags{profile:04d}"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HANDLER_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, flags, 0, winreg.REG_DWORD, _FLAG_RUN_HANDLER)
        try:
            process = subprocess.Popen(
                [os.path.expandvars(_CLEANMGR), f"/sagerun:{profile}"],
                stdin=subprocess.DEVNULL,
                creationflags=_NO_CONTROLS,
            )
            while process.poll() is None:
                report(Step("windows_old.step", 0, 0))
                time.sleep(_POLL_SECONDS)
        finally:
            winreg.DeleteValue(key, flags)


def estimate_windows_old() -> int | None:
    folder = Path(os.path.expandvars(_FOLDER))
    if not folder.is_dir():
        return 0
    return folder_size(folder) if is_admin() else None


def clean_windows_old(report: Report) -> Outcome:
    folder = Path(os.path.expandvars(_FOLDER))
    if not folder.is_dir():
        return Outcome(0, 0)
    if not is_admin():
        return Outcome(0, 0, admin_required=(str(folder),))
    free_before = shutil.disk_usage(folder.anchor).free
    try:
        _run_cleanmgr(report)
    except OSError:
        return Outcome(0, 0, failures=(str(folder),))
    if folder.exists():
        return Outcome(0, 0, failures=(str(folder),))
    freed = max(0, shutil.disk_usage(folder.anchor).free - free_before)
    return Outcome(0, freed, rows=(Row("category.windows_old", None, freed, needs_admin=True),))
