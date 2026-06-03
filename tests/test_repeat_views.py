import pytest
from django.urls import reverse
from django.utils import timezone

from workouts.models import Exercise, WorkoutExercise, WorkoutSession, WorkoutSet


def make_push_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_completed_push_session(exercise):
    session = WorkoutSession.objects.create(
        name='Monday Push', status='complete', completed_at=timezone.now()
    )
    we = WorkoutExercise.objects.create(session=session, exercise=exercise, order=1)
    WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60.0, reps=10)
    WorkoutSet.objects.create(workout_exercise=we, set_number=2, weight_kg=60.0, reps=10)
    WorkoutSet.objects.create(workout_exercise=we, set_number=3, weight_kg=60.0, reps=10)
    return session


@pytest.mark.django_db
def test_repeat_preview_returns_200(verified_client):
    exercise = make_push_exercise()
    make_completed_push_session(exercise)
    response = verified_client.get(reverse('gym_repeat_preview', args=['push']))
    assert response.status_code == 200


@pytest.mark.django_db
def test_repeat_preview_404_no_history(verified_client):
    response = verified_client.get(reverse('gym_repeat_preview', args=['push']))
    assert response.status_code == 404


@pytest.mark.django_db
def test_repeat_preview_contains_exercise_name(verified_client):
    exercise = make_push_exercise()
    make_completed_push_session(exercise)
    response = verified_client.get(reverse('gym_repeat_preview', args=['push']))
    assert b'Bench Press' in response.content


@pytest.mark.django_db
def test_repeat_start_creates_session(verified_client):
    exercise = make_push_exercise()
    make_completed_push_session(exercise)
    response = verified_client.post(reverse('gym_repeat_start', args=['push']), {
        'name': 'Tuesday Push',
        'exercise_id': [str(exercise.id)],
        f'weight_{exercise.id}_1': '62.5',
        f'reps_{exercise.id}_1': '8',
    })
    assert response.status_code == 302
    assert WorkoutSession.objects.filter(name='Tuesday Push', status='active').exists()


@pytest.mark.django_db
def test_repeat_start_creates_sets(verified_client):
    exercise = make_push_exercise()
    make_completed_push_session(exercise)
    verified_client.post(reverse('gym_repeat_start', args=['push']), {
        'name': 'Tuesday Push',
        'exercise_id': [str(exercise.id)],
        f'weight_{exercise.id}_1': '62.5',
        f'reps_{exercise.id}_1': '8',
        f'weight_{exercise.id}_2': '62.5',
        f'reps_{exercise.id}_2': '8',
        f'weight_{exercise.id}_3': '62.5',
        f'reps_{exercise.id}_3': '8',
    })
    session = WorkoutSession.objects.get(name='Tuesday Push')
    we = session.workout_exercises.first()
    assert we.sets.count() == 3


@pytest.mark.django_db
def test_log_home_shows_repeat_buttons(verified_client):
    exercise = make_push_exercise()
    make_completed_push_session(exercise)
    response = verified_client.get(reverse('gym_log_home'))
    assert b'Quick Repeat' in response.content


@pytest.mark.django_db
def test_log_home_no_repeat_buttons_empty(verified_client):
    response = verified_client.get(reverse('gym_log_home'))
    assert b'Quick Repeat' not in response.content
