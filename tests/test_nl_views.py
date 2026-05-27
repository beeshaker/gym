import json
import pytest
from unittest.mock import patch, Mock
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


PARSED_JSON = json.dumps({
    'exercises': [
        {'name': 'Bench Press', 'sets': [
            {'weight_kg': 60.0, 'reps': 10},
            {'weight_kg': 60.0, 'reps': 9},
        ]}
    ],
    'source': 'rules',
})


@pytest.mark.django_db
@patch('workouts.views.parse')
def test_nl_parse_returns_json(mock_parse, verified_client):
    make_exercise()
    session = make_active_session()
    mock_parse.return_value = {
        'exercises': [{'name': 'Bench Press', 'sets': [{'weight_kg': 60.0, 'reps': 10}]}],
        'source': 'rules',
    }
    response = verified_client.post(
        reverse('gym_nl_parse', args=[session.id]),
        {'text': 'bench press 3x10 60kg'},
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'exercises' in data


@pytest.mark.django_db
def test_nl_parse_invalid_session_404(verified_client):
    response = verified_client.post(
        reverse('gym_nl_parse', args=[9999]), {'text': 'bench 3x10 60kg'}
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_nl_parse_complete_session_404(verified_client):
    session = WorkoutSession.objects.create(
        name='Done', status='complete', completed_at=timezone.now()
    )
    response = verified_client.post(
        reverse('gym_nl_parse', args=[session.id]), {'text': 'bench 3x10 60kg'}
    )
    assert response.status_code == 404


@pytest.mark.django_db
@patch('workouts.views.parse')
def test_nl_parse_unparseable_returns_422(mock_parse, verified_client):
    from workouts.nl_parser import NLParseError
    session = make_active_session()
    mock_parse.side_effect = NLParseError('Could not parse')
    response = verified_client.post(
        reverse('gym_nl_parse', args=[session.id]), {'text': 'asdfghjkl'}
    )
    assert response.status_code == 422
    assert b'error' in response.content


@pytest.mark.django_db
def test_nl_confirm_creates_workout_exercise(verified_client):
    make_exercise()
    session = make_active_session()
    verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    assert WorkoutExercise.objects.filter(session=session).exists()


@pytest.mark.django_db
def test_nl_confirm_creates_sets(verified_client):
    make_exercise()
    session = make_active_session()
    verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    we = WorkoutExercise.objects.get(session=session)
    set_numbers = list(WorkoutSet.objects.filter(workout_exercise=we).values_list('set_number', flat=True))
    assert set_numbers == [1, 2]


@pytest.mark.django_db
def test_nl_confirm_redirects(verified_client):
    make_exercise()
    session = make_active_session()
    response = verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    assert response.status_code == 302
    assert str(session.id) in response['Location']


@pytest.mark.django_db
def test_nl_confirm_invalid_session_404(verified_client):
    response = verified_client.post(
        reverse('gym_nl_confirm', args=[9999]),
        {'parsed_json': PARSED_JSON},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_nl_confirm_complete_session_404(verified_client):
    session = WorkoutSession.objects.create(
        name='Done', status='complete', completed_at=timezone.now()
    )
    response = verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    assert response.status_code == 404
