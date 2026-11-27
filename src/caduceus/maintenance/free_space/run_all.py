"""
Correr todas as limpezas

Junta várias ações numa só: corre-as uma a seguir à outra e devolve um resultado com uma linha por
ação. A barra de progresso é a da sequência inteira, e cada ação preenche a sua parte.
"""

from collections.abc import Sequence
from dataclasses import replace

from caduceus.maintenance.actions import Action, Outcome, Report, Row, Step

_STAGE_SIZE = 1000  # resolução da barra: cada ação ocupa 1000 passos dos que a barra tem


def _within_stage(report: Report, index: int, count: int) -> Report:
    def scaled(step: Step) -> None:
        inside = step.done * _STAGE_SIZE // step.total if step.total else 0
        report(replace(step, done=index * _STAGE_SIZE + inside, total=count * _STAGE_SIZE))

    return scaled


def _summary(label_key: str, needs_admin: bool, outcome: Outcome) -> Row:
    items = outcome.items if outcome.items_counted else None
    return Row(label_key, items, outcome.bytes_freed, needs_admin=needs_admin)


def run_all(stages: Sequence[tuple[str, bool, Action]]) -> Action:
    """Cada etapa é (chave do nome, exige administrador, ação)."""

    def run(report: Report) -> Outcome:
        outcomes = [
            (label_key, needs_admin, action(_within_stage(report, index, len(stages))))
            for index, (label_key, needs_admin, action) in enumerate(stages)
        ]
        return Outcome(
            items=sum(outcome.items for _, _, outcome in outcomes),
            bytes_freed=sum(outcome.bytes_freed for _, _, outcome in outcomes),
            failures=tuple(place for _, _, outcome in outcomes for place in outcome.failures),
            admin_required=tuple(
                place for _, _, outcome in outcomes for place in outcome.admin_required
            ),
            rows=tuple(_summary(*stage) for stage in outcomes),
        )

    return run
