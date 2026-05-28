import pytest
from workouts.coach import recommend, get_ollama_tips, CoachError


class FakeExercise:
    def __init__(self):
        self.default_min_reps = 8
        self.default_max_reps = 12
        self.default_sets = 3
        self.default_increment = 2.5


class FakeSet:
    def __init__(self, weight_kg, reps):
        self.weight_kg = weight_kg
        self.reps = reps


EX = FakeExercise()


def test_recommend_no_history():
    rec = recommend(EX, [])
    assert rec['action'] == 'start'
    assert rec['last_weight'] is None
    assert rec['last_reps'] is None
    assert rec['last_sets_count'] == 0
    assert rec['target_weight'] == 0.0
    assert rec['target_reps_min'] == 8
    assert rec['target_reps_max'] == 12


def test_recommend_all_max_reps():
    sets = [FakeSet(60.0, 12), FakeSet(60.0, 12), FakeSet(60.0, 12)]
    rec = recommend(EX, sets)
    assert rec['action'] == 'increase'
    assert rec['target_weight'] == 62.5
    assert rec['last_weight'] == 60.0


def test_recommend_hold():
    sets = [FakeSet(60.0, 10), FakeSet(60.0, 10), FakeSet(60.0, 9)]
    rec = recommend(EX, sets)
    assert rec['action'] == 'hold'
    assert rec['target_weight'] == 60.0
    assert rec['last_reps'] == 9


def test_recommend_deload():
    sets = [FakeSet(60.0, 10), FakeSet(60.0, 7), FakeSet(60.0, 6)]
    rec = recommend(EX, sets)
    assert rec['action'] == 'deload'
    assert rec['target_weight'] == 57.5


def test_recommend_last_weight_is_max():
    sets = [FakeSet(60.0, 10), FakeSet(60.0, 10), FakeSet(62.5, 8)]
    rec = recommend(EX, sets)
    assert rec['last_weight'] == 62.5


def test_recommend_last_reps_is_min():
    sets = [FakeSet(60.0, 12), FakeSet(60.0, 10), FakeSet(60.0, 8)]
    rec = recommend(EX, sets)
    assert rec['last_reps'] == 8
