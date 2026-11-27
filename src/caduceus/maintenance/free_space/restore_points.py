"""
Apagar os pontos de restauro

Apaga todos os pontos de restauro e as cópias de sombra (Shadow Copies) do disco do sistema com o
comando oficial do Windows, `vssadmin delete shadows /for=C: /all /quiet`. Depois disto já não é
possível voltar atrás com um ponto de restauro, nem recuperar versões anteriores de ficheiros. O
espaço libertado mede-se pela diferença de espaço livre no disco do sistema. Exige administrador.
"""

from caduceus.maintenance.actions import Outcome, Report, Row
from caduceus.maintenance.admin import is_admin
from caduceus.maintenance.system_tool import free_bytes, run_system_tool, system_drive


def clean_restore_points(report: Report) -> Outcome:
    drive = system_drive()
    if not is_admin():
        return Outcome(0, 0, admin_required=(drive,))
    free_before = free_bytes()
    try:
        succeeded = run_system_tool(
            "vssadmin.exe",
            ["delete", "shadows", f"/for={drive}", "/all", "/quiet"],
            report,
            "cleanup.restore_points.step",
        )
    except OSError:
        succeeded = False
    if not succeeded:
        return Outcome(0, 0, failures=(drive,))
    freed = max(0, free_bytes() - free_before)
    return Outcome(0, freed, rows=(Row("category.restore_points", None, freed, needs_admin=True),))
