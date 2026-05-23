import pytest
from django.contrib.auth.hashers import make_password
from django.urls import reverse


@pytest.mark.django_db
def test_pin_get_renders_form(client):
    response = client.get(reverse('gym_pin'))
    assert response.status_code == 200
    assert b'Enter PIN' in response.content


@pytest.mark.django_db
def test_correct_pin_sets_session_and_redirects(client, settings):
    settings.GYM_PIN_HASH = make_password('1234')
    response = client.post(reverse('gym_pin'), {'pin': '1234'})
    assert response.status_code == 302
    assert reverse('gym_dashboard') in response['Location']
    assert client.session.get('gym_pin_verified') is True
    assert client.session.get('gym_pin_verified_at') is not None


@pytest.mark.django_db
def test_wrong_pin_shows_error(client, settings):
    settings.GYM_PIN_HASH = make_password('1234')
    response = client.post(reverse('gym_pin'), {'pin': '9999'})
    assert response.status_code == 200
    assert b'Incorrect' in response.content
    assert not client.session.get('gym_pin_verified')


@pytest.mark.django_db
def test_empty_pin_shows_error(client, settings):
    settings.GYM_PIN_HASH = make_password('1234')
    response = client.post(reverse('gym_pin'), {'pin': ''})
    assert response.status_code == 200
    assert not client.session.get('gym_pin_verified')
