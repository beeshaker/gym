from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import PinForm


def index(request):
    return redirect('gym_dashboard')


@require_http_methods(['GET', 'POST'])
def pin(request):
    error = None
    if request.method == 'POST':
        form = PinForm(request.POST)
        if form.is_valid():
            submitted = form.cleaned_data['pin']
            stored_hash = settings.GYM_PIN_HASH
            if submitted and stored_hash and check_password(submitted, stored_hash):
                request.session['gym_pin_verified'] = True
                request.session['gym_pin_verified_at'] = timezone.now().isoformat()
                return redirect('gym_dashboard')
        error = 'Incorrect PIN. Try again.'
    else:
        form = PinForm()
    return render(request, 'core/pin.html', {'form': form, 'error': error})


def dashboard(request):
    from workouts.models import WorkoutSession
    last_session = WorkoutSession.objects.filter(status='complete').first()
    return render(request, 'core/dashboard.html', {'last_session': last_session})
