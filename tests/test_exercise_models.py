import pytest
from django.db import IntegrityError
from workouts.models import Exercise, ExerciseAlias


def make_exercise(**kwargs):
    defaults = dict(
        name='Bench Press',
        muscle_group='Chest',
        category='push',
        equipment='barbell',
        movement_type='compound',
        default_min_reps=8,
        default_max_reps=12,
        default_sets=3,
        default_increment=2.5,
    )
    defaults.update(kwargs)
    return Exercise.objects.create(**defaults)


@pytest.mark.django_db
def test_exercise_str():
    ex = make_exercise()
    assert str(ex) == 'Bench Press'


@pytest.mark.django_db
def test_exercise_defaults():
    ex = make_exercise()
    assert ex.is_active is True
    assert ex.default_sets == 3


@pytest.mark.django_db
def test_exercise_name_unique():
    make_exercise()
    with pytest.raises(IntegrityError):
        make_exercise()


@pytest.mark.django_db
def test_alias_str():
    ex = make_exercise()
    alias = ExerciseAlias.objects.create(exercise=ex, alias='bench')
    assert str(alias) == 'bench → Bench Press'


@pytest.mark.django_db
def test_alias_unique_together():
    ex = make_exercise()
    ExerciseAlias.objects.create(exercise=ex, alias='bench')
    with pytest.raises(IntegrityError):
        ExerciseAlias.objects.create(exercise=ex, alias='bench')


@pytest.mark.django_db
def test_alias_cascade_delete():
    ex = make_exercise()
    ExerciseAlias.objects.create(exercise=ex, alias='bench')
    ex.delete()
    assert ExerciseAlias.objects.count() == 0
