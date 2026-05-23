import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone


@pytest.mark.django_db
def test_unverified_request_redirects_to_pin(client):
    response = client.get(reverse('gym_dashboard'))
    assert response.status_code == 302
    assert reverse('gym_pin') in response['Location']


@pytest.mark.django_db
def test_pin_url_accessible_without_session(client):
    response = client.get(reverse('gym_pin'))
    assert response.status_code == 200


@pytest.mark.django_db
def test_exercises_url_redirects_without_session(client):
    response = client.get(reverse('gym_exercises'))
    assert response.status_code == 302
    assert reverse('gym_pin') in response['Location']


@pytest.mark.django_db
def test_verified_session_passes_through(client):
    session = client.session
    session['gym_pin_verified'] = True
    session['gym_pin_verified_at'] = timezone.now().isoformat()
    session.save()
    response = client.get(reverse('gym_dashboard'))
    assert response.status_code == 200


@pytest.mark.django_db
def test_expired_session_redirects(client, settings):
    settings.GYM_SESSION_TIMEOUT_HOURS = 1
    expired = timezone.now() - timedelta(hours=2)
    session = client.session
    session['gym_pin_verified'] = True
    session['gym_pin_verified_at'] = expired.isoformat()
    session.save()
    response = client.get(reverse('gym_dashboard'))
    assert response.status_code == 302
    assert reverse('gym_pin') in response['Location']


@pytest.mark.django_db
def test_admin_not_protected_by_pin(client):
    response = client.get('/admin/')
    # Admin redirects to admin login, not pin screen
    assert response.status_code == 302
    assert '/admin/' in response['Location']
