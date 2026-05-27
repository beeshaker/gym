import pytest
from django.urls import reverse
from django.utils import timezone
from workouts.models import Exercise, WorkoutSession, WorkoutExercise, WorkoutSet


def make_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_complete_session(name='Monday Push'):
    return WorkoutSession.objects.create(
        name=name, status='complete', completed_at=timezone.now(),
    )


@pytest.mark.django_db
def test_history_shows_completed_sessions(verified_client):
    make_complete_session('Push Day')
    make_complete_session('Pull Day')
    response = verified_client.get(reverse('gym_history'))
    assert response.status_code == 200
    assert b'Push Day' in response.content
    assert b'Pull Day' in response.content


@pytest.mark.django_db
def test_history_empty_state(verified_client):
    response = verified_client.get(reverse('gym_history'))
    assert response.status_code == 200
    assert b'No workouts' in response.content


@pytest.mark.django_db
def test_history_does_not_show_active_sessions(verified_client):
    WorkoutSession.objects.create(name='Active', status='active')
    response = verified_client.get(reverse('gym_history'))
    assert b'Active' not in response.content


@pytest.mark.django_db
def test_session_detail_shows_session_name(verified_client):
    session = make_complete_session('Leg Day')
    response = verified_client.get(reverse('gym_session_detail', args=[session.id]))
    assert response.status_code == 200
    assert b'Leg Day' in response.content


@pytest.mark.django_db
def test_session_detail_shows_sets(verified_client):
    session = make_complete_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=session, exercise=ex, order=1)
    WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    response = verified_client.get(reverse('gym_session_detail', args=[session.id]))
    assert b'60' in response.content
    assert b'10' in response.content
