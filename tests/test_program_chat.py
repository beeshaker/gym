import json
import pytest
from unittest.mock import patch
from django.urls import reverse

from workouts.models import Exercise, Program, ProgramDay, ProgramExercise
from workouts.coach import CoachError


def make_exercise(name='Bench Press', muscle_group='Chest',
                  category='push', equipment='barbell'):
    return Exercise.objects.create(
        name=name, muscle_group=muscle_group, category=category,
        equipment=equipment, movement_type='compound',
    )


def make_program_with_day(exercise):
    prog = Program.objects.create(name='Test Program', description='', is_active=True)
    day = ProgramDay.objects.create(program=prog, name='Push', order=1)
    ProgramExercise.objects.create(program_day=day, exercise=exercise, order=1)
    return prog, day


@pytest.mark.django_db
def test_program_chat_valid_message_returns_reply(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    with patch('workouts.views.get_program_chat_reply', return_value='Rest 90 seconds.'):
        response = verified_client.post(
            reverse('gym_program_chat', args=[day.id]),
            data=json.dumps({'message': 'How long should I rest?', 'history': []}),
            content_type='application/json',
        )
    assert response.status_code == 200
    assert json.loads(response.content)['reply'] == 'Rest 90 seconds.'


@pytest.mark.django_db
def test_program_chat_missing_message_returns_400(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    response = verified_client.post(
        reverse('gym_program_chat', args=[day.id]),
        data=json.dumps({'history': []}),
        content_type='application/json',
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_program_chat_inactive_program_returns_404(verified_client):
    ex = make_exercise()
    prog = Program.objects.create(name='Inactive', description='', is_active=False)
    day = ProgramDay.objects.create(program=prog, name='Day 1', order=1)
    ProgramExercise.objects.create(program_day=day, exercise=ex, order=1)
    response = verified_client.post(
        reverse('gym_program_chat', args=[day.id]),
        data=json.dumps({'message': 'hello'}),
        content_type='application/json',
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_program_chat_coach_error_returns_422(verified_client):
    from workouts.coach import CoachError
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    with patch('workouts.views.get_program_chat_reply', side_effect=CoachError('timeout')):
        response = verified_client.post(
            reverse('gym_program_chat', args=[day.id]),
            data=json.dumps({'message': 'hello'}),
            content_type='application/json',
        )
    assert response.status_code == 422
    assert 'error' in json.loads(response.content)


@pytest.mark.django_db
def test_program_chat_get_returns_405(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_chat', args=[day.id]))
    assert response.status_code == 405
