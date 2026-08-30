import pytest

from desktop_pet.model import ActionCycle


def test_action_cycle_peek_does_not_advance_and_commit_advances_once() -> None:
    cycle = ActionCycle()

    assert cycle.peek() == "jump"
    assert cycle.peek() == "jump"
    cycle.commit("jump")

    assert cycle.peek() == "squash"


def test_action_cycle_mismatched_commit_is_deterministic_and_does_not_advance() -> None:
    cycle = ActionCycle()

    with pytest.raises(ValueError, match="expected 'shake'.*current action is 'jump'"):
        cycle.commit("shake")

    assert cycle.peek() == "jump"


def test_action_cycle_next_remains_peek_commit_compatibility_sugar() -> None:
    cycle = ActionCycle()

    assert [cycle.next() for _ in range(4)] == ["jump", "squash", "shake", "jump"]
