import json
import pytest
from django.urls import reverse
from django.utils import timezone

from workouts.models import Exercise, Program, ProgramDay, ProgramExercise, WorkoutSession


def make_exercise(name='Bench Press', muscle_group='Chest', category='push', equipment='barbell'):
    return Exercise.objects.create(
        name=name, muscle_group=muscle_group, category=category,
        equipment=equipment, movement_type='compound',
    )


def make_program_with_day(exercise):
    prog = Program.objects.create(name='Test Program', description='For tests', is_active=True)
    day = ProgramDay.objects.create(program=prog, name='Push', order=1)
    ProgramExercise.objects.create(program_day=day, exercise=exercise, order=1)
    return prog, day


@pytest.mark.django_db
def test_program_day_list_returns_200(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_days', args=[prog.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_program_day_list_shows_day_names(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_days', args=[prog.id]))
    assert b'Push' in response.content


@pytest.mark.django_db
def test_program_preview_returns_200(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_preview', args=[day.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_program_preview_contains_exercise_name(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_preview', args=[day.id]))
    assert b'Bench Press' in response.content


@pytest.mark.django_db
def test_program_swap_options_returns_json(verified_client):
    ex = make_exercise(name='Bench Press', equipment='barbell')
    make_exercise(name='DB Press', equipment='dumbbell')  # same muscle group
    response = verified_client.get(reverse('gym_program_swap', args=[ex.id]))
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'alternatives' in data
    assert isinstance(data['alternatives'], list)


@pytest.mark.django_db
def test_program_swap_excludes_original_exercise(verified_client):
    ex = make_exercise(name='Bench Press')
    response = verified_client.get(reverse('gym_program_swap', args=[ex.id]))
    data = json.loads(response.content)
    ids = [a['id'] for a in data['alternatives']]
    assert ex.id not in ids


@pytest.mark.django_db
def test_program_start_creates_session(verified_client):
    ex = make_exercise()
    response = verified_client.post(reverse('gym_program_start'), {
        'name': 'Wednesday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60',
        f'reps_{ex.id}_1': '10',
    })
    assert response.status_code == 302
    assert WorkoutSession.objects.filter(name='Wednesday Push', status='active').exists()


@pytest.mark.django_db
def test_program_start_creates_sets(verified_client):
    ex = make_exercise()
    verified_client.post(reverse('gym_program_start'), {
        'name': 'Wednesday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60', f'reps_{ex.id}_1': '10',
        f'weight_{ex.id}_2': '60', f'reps_{ex.id}_2': '10',
        f'weight_{ex.id}_3': '60', f'reps_{ex.id}_3': '10',
    })
    session = WorkoutSession.objects.get(name='Wednesday Push')
    we = session.workout_exercises.first()
    assert we.sets.count() == 3


@pytest.mark.django_db
def test_log_home_shows_programs(verified_client):
    ex = make_exercise()
    make_program_with_day(ex)
    response = verified_client.get(reverse('gym_log_home'))
    assert b'Programs' in response.content
