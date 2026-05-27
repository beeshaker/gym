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


# ── active_session ────────────────────────────────────────────────

@pytest.mark.django_db
def test_active_session_shows_session_name(verified_client):
    session = make_session()
    response = verified_client.get(reverse('gym_active_session', args=[session.id]))
    assert response.status_code == 200
    assert b'Monday Push' in response.content


@pytest.mark.django_db
def test_active_session_redirects_if_complete(verified_client):
    session = make_session(status='complete')
    response = verified_client.get(reverse('gym_active_session', args=[session.id]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_active_session_404_if_not_found(verified_client):
    response = verified_client.get(reverse('gym_active_session', args=[9999]))
    assert response.status_code == 404


# ── add_exercise ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_add_exercise_creates_workout_exercise(verified_client):
    session = make_session()
    ex = make_exercise()
    response = verified_client.post(
        reverse('gym_add_exercise', args=[session.id]),
        {'exercise_id': ex.id},
    )
    assert response.status_code == 302
    assert WorkoutExercise.objects.filter(session=session, exercise=ex).exists()


@pytest.mark.django_db
def test_add_exercise_sets_order(verified_client):
    session = make_session()
    ex1 = make_exercise()
    ex2 = Exercise.objects.create(
        name='Squat', muscle_group='Legs', category='legs',
        equipment='barbell', movement_type='compound',
    )
    verified_client.post(reverse('gym_add_exercise', args=[session.id]), {'exercise_id': ex1.id})
    verified_client.post(reverse('gym_add_exercise', args=[session.id]), {'exercise_id': ex2.id})
    orders = list(WorkoutExercise.objects.filter(session=session).values_list('order', flat=True))
    assert orders == [1, 2]


# ── add_set ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_add_set_creates_set(verified_client):
    session = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=session, exercise=ex, order=1)
    response = verified_client.post(
        reverse('gym_add_set', args=[session.id, we.id]),
        {'weight_kg': '60', 'reps': '10'},
    )
    assert response.status_code == 302
    assert WorkoutSet.objects.filter(workout_exercise=we, weight_kg=60, reps=10).exists()


@pytest.mark.django_db
def test_add_set_increments_set_number(verified_client):
    session = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=session, exercise=ex, order=1)
    verified_client.post(reverse('gym_add_set', args=[session.id, we.id]), {'weight_kg': '60', 'reps': '10'})
    verified_client.post(reverse('gym_add_set', args=[session.id, we.id]), {'weight_kg': '60', 'reps': '9'})
    set_numbers = list(WorkoutSet.objects.filter(workout_exercise=we).values_list('set_number', flat=True))
    assert set_numbers == [1, 2]


# ── delete_set ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_delete_set_removes_set(verified_client):
    session = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=session, exercise=ex, order=1)
    ws = WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    response = verified_client.post(reverse('gym_delete_set', args=[session.id, we.id, ws.id]))
    assert response.status_code == 302
    assert not WorkoutSet.objects.filter(id=ws.id).exists()


# ── finish_session ────────────────────────────────────────────────

@pytest.mark.django_db
def test_finish_session_marks_complete(verified_client):
    session = make_session()
    response = verified_client.post(reverse('gym_finish_session', args=[session.id]))
    session.refresh_from_db()
    assert session.status == 'complete'
    assert session.completed_at is not None
    assert response.status_code == 302


@pytest.mark.django_db
def test_finish_session_redirects_to_history(verified_client):
    session = make_session()
    response = verified_client.post(reverse('gym_finish_session', args=[session.id]))
    assert reverse('gym_history') in response['Location']
