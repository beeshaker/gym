import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_requires_pin(client):
    response = client.get(reverse('gym_dashboard'))
    assert response.status_code == 302


@pytest.mark.django_db
def test_dashboard_loads_when_verified(verified_client):
    response = verified_client.get(reverse('gym_dashboard'))
    assert response.status_code == 200
    assert b'GYM AI' in response.content


@pytest.mark.django_db
def test_exercises_requires_pin(client):
    response = client.get(reverse('gym_exercises'))
    assert response.status_code == 302


@pytest.mark.django_db
def test_exercises_loads_when_verified(verified_client):
    response = verified_client.get(reverse('gym_exercises'))
    assert response.status_code == 200
    assert b'Exercise Library' in response.content


@pytest.mark.django_db
def test_exercises_shows_active_exercises(verified_client):
    from workouts.models import Exercise
    Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
        default_min_reps=8, default_max_reps=12,
        default_sets=3, default_increment=2.5,
    )
    Exercise.objects.create(
        name='Hidden Exercise', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
        default_min_reps=8, default_max_reps=12,
        default_sets=3, default_increment=2.5, is_active=False,
    )
    response = verified_client.get(reverse('gym_exercises'))
    assert b'Bench Press' in response.content
    assert b'Hidden Exercise' not in response.content


@pytest.mark.django_db
def test_dashboard_shows_last_session_name(verified_client):
    from django.utils import timezone
    from workouts.models import WorkoutSession
    WorkoutSession.objects.create(
        name='Tuesday Pull', status='complete', completed_at=timezone.now(),
    )
    response = verified_client.get(reverse('gym_dashboard'))
    assert b'Tuesday Pull' in response.content


@pytest.mark.django_db
def test_dashboard_no_session_shows_empty_state(verified_client):
    response = verified_client.get(reverse('gym_dashboard'))
    assert response.status_code == 200
    assert b'No workout' in response.content
