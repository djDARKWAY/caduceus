"""
Administrador

Diz se o Caduceus corre com privilégios de administrador.
"""

import ctypes


def is_admin() -> bool:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())
