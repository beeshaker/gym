import json
import pytest
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone

from workouts.models import Exercise, WorkoutSession, WorkoutExercise, WorkoutSet


def make_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_active_session():
    return WorkoutSession.objects.create(name='Test Session', status='active')


def add_exercise_to_session(session, exercise):
    return WorkoutExercise.objects.create(session=session, exercise=exercise, order=1)


@pytest.mark.django_db
def test_coach_view_returns_200(verified_client):
    session = make_active_session()
    response = verified_client.get(reverse('gym_coach', args=[session.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_coach_view_404_on_complete_session(verified_client):
    session = WorkoutSession.objects.create(
        name='Done', status='complete', completed_at=timezone.now()
    )
    response = verified_client.get(reverse('gym_coach', args=[session.id]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_coach_view_contains_exercise_name(verified_client):
    exercise = make_exercise()
    session = make_active_session()
    add_exercise_to_session(session, exercise)
    response = verified_client.get(reverse('gym_coach', args=[session.id]))
    assert b'Bench Press' in response.content


@pytest.mark.django_db
@patch('workouts.views.get_ollama_tips')
def test_coach_tips_returns_json(mock_tips, verified_client):
    exercise = make_exercise()
    session = make_active_session()
    add_exercise_to_session(session, exercise)
    mock_tips.return_value = {'Bench Press': 'Great lift today!'}
    response = verified_client.post(reverse('gym_coach_tips', args=[session.id]))
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'tips' in data


@pytest.mark.django_db
@patch('workouts.views.get_ollama_tips')
def test_coach_tips_422_on_ollama_failure(mock_tips, verified_client):
    from workouts.coach import CoachError
    session = make_active_session()
    mock_tips.side_effect = CoachError('Ollama timed out')
    response = verified_client.post(reverse('gym_coach_tips', args=[session.id]))
    assert response.status_code == 422
    assert b'error' in response.content
