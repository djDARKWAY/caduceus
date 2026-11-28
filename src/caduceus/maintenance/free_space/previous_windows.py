r"""
Apagar os ficheiros do Windows anterior

Junta as duas limpezas que tiram a possibilidade de voltar atrás depois de uma atualização do
Windows: a instalação anterior (`C:\Windows.old`) e os restos do instalador (`$WINDOWS.~BT` e
`$Windows.~WS`). Corre primeiro os restos do instalador, porque é essa que se recusa a limpar
enquanto o Windows Setup está a decorrer: nesse caso não corre nada, e o aviso explica porquê.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.install_leftovers import (
    clean_install_leftovers,
    estimate_install_leftovers,
)
from caduceus.maintenance.free_space.windows_old import clean_windows_old, estimate_windows_old


def estimate_previous_windows() -> int | None:
    old, leftovers = estimate_windows_old(), estimate_install_leftovers()
    return None if old is None or leftovers is None else old + leftovers


def clean_previous_windows(report: Report) -> Outcome:
    leftovers = clean_install_leftovers(report)
    if leftovers.notice is not None:
        return leftovers
    old = clean_windows_old(report)
    return Outcome(
        old.items + leftovers.items,
        old.bytes_freed + leftovers.bytes_freed,
        failures=(*old.failures, *leftovers.failures),
        admin_required=(*old.admin_required, *leftovers.admin_required),
        rows=(*old.rows, *leftovers.rows),
    )
