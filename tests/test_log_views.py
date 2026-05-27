import pytest
from django.urls import reverse
from workouts.models import Exercise, WorkoutSession, WorkoutExercise, WorkoutSet


def make_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_session(**kwargs):
    defaults = {'name': 'Monday Push', 'status': 'active'}
    defaults.update(kwargs)
    return WorkoutSession.objects.create(**defaults)


@pytest.mark.django_db
def test_log_home_shows_start_form(verified_client):
    response = verified_client.get(reverse('gym_log_home'))
    assert response.status_code == 200
    assert b'Start' in response.content


@pytest.mark.django_db
def test_log_home_redirects_to_active_session(verified_client):
    session = make_session()
    response = verified_client.get(reverse('gym_log_home'))
    assert response.status_code == 302
    assert str(session.id) in response['Location']


@pytest.mark.django_db
def test_start_session_creates_session_and_redirects(verified_client):
    response = verified_client.post(reverse('gym_log_start'), {'name': 'Push Day'})
    assert WorkoutSession.objects.filter(name='Push Day').exists()
    session = WorkoutSession.objects.get(name='Push Day')
    assert response.status_code == 302
    assert str(session.id) in response['Location']


@pytest.mark.django_db
def test_start_session_empty_name_rerenders_form(verified_client):
    response = verified_client.post(reverse('gym_log_start'), {'name': '   '})
    assert response.status_code == 200
    assert WorkoutSession.objects.count() == 0
