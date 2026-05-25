import pytest
from workouts.models import Exercise, WorkoutSession, WorkoutExercise, WorkoutSet


def make_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_session(**kwargs):
    defaults = {'name': 'Monday Push'}
    defaults.update(kwargs)
    return WorkoutSession.objects.create(**defaults)


@pytest.mark.django_db
def test_session_str():
    s = make_session()
    assert 'Monday Push' in str(s)


@pytest.mark.django_db
def test_session_defaults():
    s = make_session()
    assert s.status == 'active'
    assert s.completed_at is None


@pytest.mark.django_db
def test_session_ordering():
    s1 = make_session(name='First')
    s2 = make_session(name='Second')
    sessions = list(WorkoutSession.objects.all())
    assert sessions[0] == s2  # newest first


@pytest.mark.django_db
def test_workout_exercise_str():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    assert 'Bench Press' in str(we)
    assert 'Monday Push' in str(we)


@pytest.mark.django_db
def test_workout_set_str():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    ws = WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    assert '60' in str(ws)
    assert '10' in str(ws)


@pytest.mark.django_db
def test_cascade_delete_session_removes_exercises_and_sets():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    s.delete()
    assert WorkoutExercise.objects.count() == 0
    assert WorkoutSet.objects.count() == 0


@pytest.mark.django_db
def test_cascade_delete_workout_exercise_removes_sets():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    we.delete()
    assert WorkoutSet.objects.count() == 0
