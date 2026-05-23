import pytest
from django.utils import timezone


@pytest.fixture
def verified_client(client):
    session = client.session
    session['gym_pin_verified'] = True
    session['gym_pin_verified_at'] = timezone.now().isoformat()
    session.save()
    return client
