import pytest
from workouts.repeat import session_category


class FakeExercise:
    def __init__(self, category):
        self.category = category


class FakeWE:
    def __init__(self, category):
        self.exercise = FakeExercise(category)


def test_session_category_push():
    wes = [FakeWE('push'), FakeWE('push'), FakeWE('push'), FakeWE('pull')]
    assert session_category(wes) == 'push'


def test_session_category_tie():
    wes = [FakeWE('push'), FakeWE('push'), FakeWE('pull'), FakeWE('pull')]
    result = session_category(wes)
    assert result in ('push', 'pull')  # deterministic but either is valid


def test_session_category_empty():
    assert session_category([]) is None
