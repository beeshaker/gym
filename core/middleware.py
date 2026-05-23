from datetime import timedelta

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone


class PinMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        secret = settings.GYM_SECRET_PATH
        protected_prefix = f'/{secret}/'
        pin_path = f'/{secret}/pin/'

        if (
            request.path.startswith(protected_prefix)
            and request.path != pin_path
        ):
            if not self._is_verified(request):
                return redirect('gym_pin')

        return self.get_response(request)

    def _is_verified(self, request):
        if not request.session.get('gym_pin_verified'):
            return False
        verified_at_str = request.session.get('gym_pin_verified_at')
        if not verified_at_str:
            return False
        try:
            verified_at = timezone.datetime.fromisoformat(verified_at_str)
            if timezone.is_naive(verified_at):
                verified_at = timezone.make_aware(verified_at)
            timeout_hours = getattr(settings, 'GYM_SESSION_TIMEOUT_HOURS', 24)
            return timezone.now() < verified_at + timedelta(hours=timeout_hours)
        except (ValueError, TypeError):
            return False
