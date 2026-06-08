import pytest
from django.urls import reverse

from workouts.models import (
    Exercise, Program, ProgramDay, ProgramExercise,
    WorkoutExercise, WorkoutSession,
)


def make_exercise(name='Bench Press', muscle_group='Chest',
                  category='push', equipment='barbell', movement_type='compound'):
    return Exercise.objects.create(
        name=name, muscle_group=muscle_group, category=category,
        equipment=equipment, movement_type=movement_type,
    )


@pytest.mark.django_db
def test_program_start_saves_planned_rest_seconds(verified_client):
    ex = make_exercise()
    verified_client.post(reverse('gym_program_start'), {
        'name': 'Monday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60',
        f'reps_{ex.id}_1': '10',
        f'rest_{ex.id}': '90',
    })
    we = WorkoutExercise.objects.get(session__name='Monday Push')
    assert we.planned_rest_seconds == 90


@pytest.mark.django_db
def test_program_start_without_rest_field_saves_none(verified_client):
    ex = make_exercise()
    verified_client.post(reverse('gym_program_start'), {
        'name': 'Tuesday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60',
        f'reps_{ex.id}_1': '10',
    })
    we = WorkoutExercise.objects.get(session__name='Tuesday Push')
    assert we.planned_rest_seconds is None


@pytest.mark.django_db
def test_add_set_redirect_includes_timer_param(verified_client):
    session = WorkoutSession.objects.create(name='Test', status='active')
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=session, exercise=ex, order=1)
    response = verified_client.post(
        reverse('gym_add_set', args=[session.id, we.id]),
        {'weight_kg': '60', 'reps': '10'},
    )
    assert response.status_code == 302
    assert f'timer={we.id}' in response['Location']


@pytest.mark.django_db
def test_add_exercise_quick_log_planned_rest_is_null(verified_client):
    session = WorkoutSession.objects.create(name='Quick', status='active')
    ex = make_exercise()
    verified_client.post(
        reverse('gym_add_exercise', args=[session.id]),
        {'exercise_id': str(ex.id)},
    )
    we = WorkoutExercise.objects.get(session=session)
    assert we.planned_rest_seconds is None
