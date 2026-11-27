"""
Limpar o histórico recente

Apaga os atalhos de documentos recentes e o histórico das Jump Lists do utilizador. Mantém as
pastas fixadas no Acesso rápido e os itens fixados nas Jump Lists, que são escolhas do utilizador
e não histórico. Apaga os comandos de «Executar» do registo, contando os comandos sem contar o
valor que guarda a sua ordem.
"""

import winreg
from dataclasses import replace

from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.free_space.cleaner import Location, clean_locations

_RECENT = r"%APPDATA%\Microsoft\Windows\Recent"
_QUICK_ACCESS_PINS = "f01b4d95cf55d32a.automaticDestinations-ms"  # pastas fixadas no Acesso rápido
_RUN_MRU = r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU"
LOCATIONS = (
    Location(_RECENT, "cleanup.recent_history.documents", "*.lnk", 0, files_only=True),
    Location(
        _RECENT + r"\AutomaticDestinations",
        "cleanup.recent_history.jump_lists",
        "*.automaticDestinations-ms",
        0,
        files_only=True,
        keep=(_QUICK_ACCESS_PINS,),
    ),
)


def _clear_run_mru() -> tuple[int, bool]:
    count, failed = 0, False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_MRU, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE
        ) as key:
            names = [winreg.EnumValue(key, i)[0] for i in range(winreg.QueryInfoKey(key)[1])]
            for name in names:
                order = name.casefold() == "mrulist"
                if not (order or (len(name) == 1 and "a" <= name.casefold() <= "z")):
                    continue
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    continue  # o Explorer já apagou o valor
                except OSError:
                    failed = True
                    continue
                count += not order
    except FileNotFoundError:
        return count, failed
    except OSError:
        return count, True
    return count, failed


def clear_recent_history(report: Report) -> Outcome:
    outcome = clean_locations(LOCATIONS, report)
    report(Step("cleanup.recent_history.step", 0, 0))
    count, failed = _clear_run_mru()
    return replace(
        outcome,
        items=outcome.items + count,
        failures=(*outcome.failures, rf"HKCU\{_RUN_MRU}") if failed else outcome.failures,
        rows=(*outcome.rows, Row("cleanup.recent_history.run_commands", count, 0)),
    )
