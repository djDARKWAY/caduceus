"""
Ações

Os tipos comuns a todas as ações da Manutenção manual: o passo em curso (para a barra de
progresso), o resultado (com uma linha por categoria) e a forma de uma ação. Cada ação vive num
ficheiro de `maintenance/free_space/`, `maintenance/memory/` ou `maintenance/apps/`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    text_key: str
    done: int
    total: int  # 0 quando não se sabe quanto falta: a barra mostra só que há trabalho em curso
    values: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Row:
    label_key: str
    items: int | None  # None quando a ação não sabe quantos itens removeu
    bytes_freed: int
    values: Mapping[str, str] = field(default_factory=dict)
    needs_admin: bool = False


@dataclass(frozen=True)
class Outcome:
    items: int
    bytes_freed: int
    failures: tuple[str, ...] = ()
    admin_required: tuple[str, ...] = ()
    rows: tuple[Row, ...] = ()
    quit_after: bool = False  # a ação pede que o Caduceus feche (por exemplo, ao reabrir)
    notice: str | None = None  # a chave de um aviso a mostrar em vez do resultado

    @property
    def items_counted(self) -> bool:
        """Falso quando a ação não sabe quantos itens removeu (todas as linhas sem contagem)."""
        return not self.rows or any(row.items is not None for row in self.rows)


Report = Callable[[Step], None]
Action = Callable[[Report], Outcome]
Estimator = Callable[[], int | None]  # bytes que a ação deve libertar, ou None se não se sabe
