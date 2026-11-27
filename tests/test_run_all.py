from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.run_all import run_all


def test_every_action_runs_in_order_and_the_outcome_has_one_row_each() -> None:
    order: list[str] = []

    def first(_report: Report) -> Outcome:
        order.append("first")
        return Outcome(2, 100, failures=("a",), admin_required=("b",))

    def second(_report: Report) -> Outcome:
        order.append("second")
        return Outcome(0, 50, rows=(Row("x", None, 50),))

    outcome = run_all([("one", False, first), ("two", True, second)])(lambda _: None)

    assert order == ["first", "second"]
    assert (outcome.items, outcome.bytes_freed) == (2, 150)
    assert (outcome.failures, outcome.admin_required) == (("a",), ("b",))
    assert outcome.rows == (
        Row("one", 2, 100),
        Row("two", None, 50, needs_admin=True),
    )


def test_each_action_fills_its_own_part_of_the_progress_of_the_whole_sequence() -> None:
    def halves(report: Report) -> Outcome:
        report(Step("s", 0, 2))
        report(Step("s", 1, 2))
        return Outcome(0, 0)

    steps: list[Step] = []

    run_all([("a", False, halves), ("b", False, halves)])(steps.append)

    done = [step.done for step in steps]
    assert {step.total for step in steps} == {2000}
    assert done == [0, 500, 1000, 1500]
