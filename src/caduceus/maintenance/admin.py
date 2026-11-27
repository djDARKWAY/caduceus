"""
Administrador

Diz se o Caduceus corre com privilégios de administrador e, se não corre, reabre-o com eles: o
Windows mostra o seu pedido de confirmação (UAC) e, se o utilizador aceitar, abre uma nova consola
como administrador, onde o Caduceus recomeça. O programa atual só fecha depois de a nova consola
abrir; se o utilizador recusar, nada muda.
"""

import ctypes
import os
import sys

from caduceus.maintenance.actions import Outcome, Report

_RUN_AS = "runas"
_SHOW_NORMAL = 1
_SHELL_EXECUTE_FAILED = 32  # o ShellExecute devolve um valor maior do que este quando consegue

_shell_execute = ctypes.windll.shell32.ShellExecuteW


def is_admin() -> bool:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def restart_as_administrator(_report: Report) -> Outcome:
    result = _shell_execute(None, _RUN_AS, sys.executable, "-m caduceus", os.getcwd(), _SHOW_NORMAL)
    if result > _SHELL_EXECUTE_FAILED:
        return Outcome(0, 0, quit_after=True)
    return Outcome(0, 0, notice="notice.restart_cancelled")
