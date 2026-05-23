# Gym Progress AI — Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PIN-protected Django web app with a dark hero-layout dashboard shell, exercise library, and Django admin — running locally at http://localhost:8000.

**Architecture:** Two Django apps: `core` (PIN middleware, dashboard shell) and `workouts` (Exercise/ExerciseAlias models, admin, seed data). PIN middleware protects all routes under a configurable secret URL prefix read from `.env`. Custom hand-written dark CSS, no frontend framework.

**Tech Stack:** Django 4.2+, PostgreSQL, psycopg[binary], python-dotenv, whitenoise, pytest, pytest-django

---

## File Map

| File | Purpose |
|---|---|
| `requirements.txt` | Python dependencies |
| `.env` | Local environment config (never committed) |
| `.gitignore` | Exclude .env, __pycache__, staticfiles, etc. |
| `pytest.ini` | pytest-django config |
| `conftest.py` | Shared test fixtures |
| `gym_progress_ai/settings.py` | Django settings, reads from .env |
| `gym_progress_ai/urls.py` | Root URL routing (dynamic secret prefix) |
| `core/middleware.py` | PIN session verification middleware |
| `core/forms.py` | PinForm (hidden field, JS-filled) |
| `core/views.py` | index (redirect), pin, dashboard views |
| `core/urls.py` | core URL patterns |
| `core/management/commands/set_pin.py` | Hashes a PIN and prints it for .env |
| `workouts/models.py` | Exercise, ExerciseAlias models |
| `workouts/admin.py` | ExerciseAdmin with inline alias editor |
| `workouts/views.py` | exercises list view |
| `workouts/urls.py` | workouts URL patterns |
| `workouts/fixtures/exercises.json` | 35 exercises + aliases seed data |
| `templates/base.html` | Base dark layout with bottom nav |
| `templates/core/pin.html` | Number-pad PIN screen |
| `templates/core/dashboard.html` | Hero card dashboard shell |
| `templates/workouts/exercises.html` | Exercise library list |
| `static/css/app.css` | Full dark theme CSS |
| `tests/test_exercise_models.py` | Exercise + alias model tests |
| `tests/test_pin_middleware.py` | Middleware redirect/pass-through tests |
| `tests/test_pin_view.py` | PIN form correct/wrong PIN tests |
| `tests/test_dashboard_view.py` | Dashboard + exercises page load tests |

---

## Task 1: Project Scaffold and PostgreSQL Setup

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `pytest.ini`

- [ ] **Step 1: Create the PostgreSQL database and user**

```bash
cd /home/abhishek/abhi/gym
sudo -u postgres psql -c "CREATE DATABASE gym_progress_ai;"
sudo -u postgres psql -c "CREATE USER gym_user WITH PASSWORD 'gympass123';"
sudo -u postgres psql -c "ALTER ROLE gym_user SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE gym_user SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE gym_user SET timezone TO 'Africa/Nairobi';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE gym_progress_ai TO gym_user;"
sudo -u postgres psql -d gym_progress_ai -c "GRANT ALL ON SCHEMA public TO gym_user;"
```

Expected: `GRANT` lines with no errors.

- [ ] **Step 2: Create and activate a virtual environment**

```bash
cd /home/abhishek/abhi/gym
python3 -m venv venv
source venv/bin/activate
```

- [ ] **Step 3: Write requirements.txt**

```
Django>=4.2,<5.0
psycopg[binary]>=3.1
python-dotenv>=1.0
whitenoise>=6.6
pytest>=7.4
pytest-django>=4.7
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 5: Scaffold the Django project**

```bash
django-admin startproject gym_progress_ai .
python manage.py startapp core
python manage.py startapp workouts
```

Expected: `manage.py`, `gym_progress_ai/`, `core/`, `workouts/` directories created.

- [ ] **Step 6: Write .gitignore**

```
.env
__pycache__/
*.pyc
*.pyo
venv/
staticfiles/
*.sqlite3
.DS_Store
.superpowers/
```

- [ ] **Step 7: Write pytest.ini**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = gym_progress_ai.settings
pythonpath = .
python_files = tests/test_*.py
```

- [ ] **Step 8: Create test package and conftest**

```bash
mkdir -p tests
touch tests/__init__.py
```

Write `conftest.py` at the project root:

```python
import pytest
from django.utils import timezone


@pytest.fixture
def verified_client(client):
    session = client.session
    session['gym_pin_verified'] = True
    session['gym_pin_verified_at'] = timezone.now().isoformat()
    session.save()
    return client
```

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .gitignore pytest.ini conftest.py tests/
git commit -m "feat: project scaffold, dependencies, pytest config"
```

---

## Task 2: Settings and Environment

**Files:**
- Create: `.env`
- Modify: `gym_progress_ai/settings.py`

- [ ] **Step 1: Create .env**

```env
DJANGO_SECRET_KEY=dev-secret-key-change-in-production-abc123xyz
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

DATABASE_NAME=gym_progress_ai
DATABASE_USER=gym_user
DATABASE_PASSWORD=gympass123
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432

GYM_SECRET_PATH=gym-2026-private
GYM_PIN_HASH=
GYM_SESSION_TIMEOUT_HOURS=24
```

`GYM_PIN_HASH` is left blank until Task 13 generates it.

- [ ] **Step 2: Replace gym_progress_ai/settings.py entirely**

```python
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'core',
    'workouts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.PinMiddleware',
]

ROOT_URLCONF = 'gym_progress_ai.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gym_progress_ai.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DATABASE_NAME'],
        'USER': os.environ['DATABASE_USER'],
        'PASSWORD': os.environ['DATABASE_PASSWORD'],
        'HOST': os.getenv('DATABASE_HOST', '127.0.0.1'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Gym app
GYM_SECRET_PATH = os.environ['GYM_SECRET_PATH']
GYM_PIN_HASH = os.getenv('GYM_PIN_HASH', '')
GYM_SESSION_TIMEOUT_HOURS = int(os.getenv('GYM_SESSION_TIMEOUT_HOURS', '24'))
```

- [ ] **Step 3: Verify settings load**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add gym_progress_ai/settings.py
git commit -m "feat: configure settings from .env"
```

---

## Task 3: Exercise Models and Migration

**Files:**
- Modify: `workouts/models.py`
- Create: `tests/test_exercise_models.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_exercise_models.py`:

```python
import pytest
from django.db import IntegrityError
from workouts.models import Exercise, ExerciseAlias


def make_exercise(**kwargs):
    defaults = dict(
        name='Bench Press',
        muscle_group='Chest',
        category='push',
        equipment='barbell',
        movement_type='compound',
        default_min_reps=8,
        default_max_reps=12,
        default_sets=3,
        default_increment=2.5,
    )
    defaults.update(kwargs)
    return Exercise.objects.create(**defaults)


@pytest.mark.django_db
def test_exercise_str():
    ex = make_exercise()
    assert str(ex) == 'Bench Press'


@pytest.mark.django_db
def test_exercise_defaults():
    ex = make_exercise()
    assert ex.is_active is True
    assert ex.default_sets == 3


@pytest.mark.django_db
def test_exercise_name_unique():
    make_exercise()
    with pytest.raises(IntegrityError):
        make_exercise()


@pytest.mark.django_db
def test_alias_str():
    ex = make_exercise()
    alias = ExerciseAlias.objects.create(exercise=ex, alias='bench')
    assert str(alias) == 'bench → Bench Press'


@pytest.mark.django_db
def test_alias_unique_together():
    ex = make_exercise()
    ExerciseAlias.objects.create(exercise=ex, alias='bench')
    with pytest.raises(IntegrityError):
        ExerciseAlias.objects.create(exercise=ex, alias='bench')


@pytest.mark.django_db
def test_alias_cascade_delete():
    ex = make_exercise()
    ExerciseAlias.objects.create(exercise=ex, alias='bench')
    ex.delete()
    assert ExerciseAlias.objects.count() == 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_exercise_models.py -v
```

Expected: `ImportError` or `django.core.exceptions.ImproperlyConfigured` — models don't exist yet.

- [ ] **Step 3: Write workouts/models.py**

```python
from django.db import models


class Exercise(models.Model):
    CATEGORY_CHOICES = [
        ('push', 'Push'),
        ('pull', 'Pull'),
        ('legs', 'Legs'),
        ('upper_arms', 'Upper/Arms'),
        ('conditioning_abs', 'Conditioning/Abs'),
    ]
    EQUIPMENT_CHOICES = [
        ('barbell', 'Barbell'),
        ('dumbbell', 'Dumbbell'),
        ('machine', 'Machine'),
        ('cable', 'Cable'),
        ('bodyweight', 'Bodyweight'),
    ]
    MOVEMENT_CHOICES = [
        ('compound', 'Compound'),
        ('isolation', 'Isolation'),
        ('cardio', 'Cardio'),
        ('core', 'Core'),
    ]

    name = models.CharField(max_length=100, unique=True)
    muscle_group = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    equipment = models.CharField(max_length=20, choices=EQUIPMENT_CHOICES)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    default_min_reps = models.PositiveIntegerField(default=8)
    default_max_reps = models.PositiveIntegerField(default=12)
    default_sets = models.PositiveIntegerField(default=3)
    default_increment = models.DecimalField(max_digits=4, decimal_places=1, default=2.5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ExerciseAlias(models.Model):
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name='aliases'
    )
    alias = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('exercise', 'alias')]
        verbose_name_plural = 'exercise aliases'

    def __str__(self):
        return f'{self.alias} → {self.exercise.name}'
```

- [ ] **Step 4: Register app config**

Write `workouts/apps.py`:

```python
from django.apps import AppConfig


class WorkoutsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workouts'
```

Write `core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
```

- [ ] **Step 5: Create and apply migrations**

```bash
python manage.py makemigrations workouts
python manage.py migrate
```

Expected: Migration created and applied. `OK` on all lines.

- [ ] **Step 6: Run tests — expect pass**

```bash
pytest tests/test_exercise_models.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add workouts/models.py workouts/apps.py core/apps.py workouts/migrations/ tests/test_exercise_models.py
git commit -m "feat: Exercise and ExerciseAlias models with tests"
```

---

## Task 4: Django Admin

**Files:**
- Modify: `workouts/admin.py`

- [ ] **Step 1: Write workouts/admin.py**

```python
from django.contrib import admin
from .models import Exercise, ExerciseAlias


class ExerciseAliasInline(admin.TabularInline):
    model = ExerciseAlias
    extra = 1
    fields = ('alias',)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'equipment', 'movement_type', 'is_active')
    list_filter = ('category', 'equipment', 'movement_type', 'is_active')
    search_fields = ('name', 'muscle_group')
    inlines = [ExerciseAliasInline]
    ordering = ('category', 'name')
```

- [ ] **Step 2: Create a Django superuser**

```bash
python manage.py createsuperuser
```

Enter a username, email (optional), and password when prompted.

- [ ] **Step 3: Verify admin loads**

```bash
python manage.py runserver
```

Open http://localhost:8000/admin/ and log in. Confirm "Exercises" appears in the sidebar with the inline alias editor.

Stop the server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add workouts/admin.py
git commit -m "feat: Django admin for Exercise with inline alias editor"
```

---

## Task 5: URL Routing and Stub Views

**Files:**
- Modify: `gym_progress_ai/urls.py`
- Create: `core/urls.py`
- Create: `workouts/urls.py`
- Create: `core/views.py` (stub)
- Create: `workouts/views.py` (stub)

- [ ] **Step 1: Write core/views.py with stub views**

```python
from django.http import HttpResponse
from django.shortcuts import redirect, render


def index(request):
    return redirect('gym_dashboard')


def pin(request):
    return HttpResponse('pin stub')


def dashboard(request):
    return HttpResponse('dashboard stub')
```

- [ ] **Step 2: Write workouts/views.py with stub view**

```python
from django.http import HttpResponse


def exercises(request):
    return HttpResponse('exercises stub')
```

- [ ] **Step 3: Write core/urls.py**

```python
from django.urls import path
from . import views
from workouts import views as workout_views

urlpatterns = [
    path('', views.index, name='gym_index'),
    path('pin/', views.pin, name='gym_pin'),
    path('dashboard/', views.dashboard, name='gym_dashboard'),
    path('exercises/', workout_views.exercises, name='gym_exercises'),
]
```

- [ ] **Step 4: Write workouts/urls.py**

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.exercises, name='gym_exercises'),
]
```

- [ ] **Step 5: Write gym_progress_ai/urls.py**

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path(f'{settings.GYM_SECRET_PATH}/', include('core.urls')),
]
```

- [ ] **Step 6: Write core/middleware.py (stub — required for settings check)**

```python
class PinMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
```

- [ ] **Step 7: Verify check passes**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 8: Verify routes exist**

```bash
python manage.py shell -c "from django.urls import reverse; print(reverse('gym_pin')); print(reverse('gym_dashboard')); print(reverse('gym_exercises'))"
```

Expected:
```
/gym-2026-private/pin/
/gym-2026-private/dashboard/
/gym-2026-private/exercises/
```

- [ ] **Step 9: Commit**

```bash
git add gym_progress_ai/urls.py core/urls.py core/views.py core/middleware.py workouts/urls.py workouts/views.py
git commit -m "feat: URL routing and stub views"
```

---

## Task 6: PIN Middleware

**Files:**
- Modify: `core/middleware.py`
- Create: `tests/test_pin_middleware.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_pin_middleware.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_pin_middleware.py -v
```

Expected: `test_unverified_request_redirects_to_pin` FAILS (returns 200, not 302). Others may vary.

- [ ] **Step 3: Replace core/middleware.py with full implementation**

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_pin_middleware.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add core/middleware.py tests/test_pin_middleware.py
git commit -m "feat: PIN middleware with session timeout, tests passing"
```

---

## Task 7: PIN Form and View

**Files:**
- Create: `core/forms.py`
- Modify: `core/views.py`
- Create: `tests/test_pin_view.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_pin_view.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_pin_view.py -v
```

Expected: `test_pin_get_renders_form` fails with `TemplateDoesNotExist` — no template yet.

- [ ] **Step 3: Write core/forms.py**

```python
from django import forms


class PinForm(forms.Form):
    pin = forms.CharField(
        max_length=20,
        widget=forms.HiddenInput(),
        required=False,
    )
```

- [ ] **Step 4: Create templates directory structure**

```bash
mkdir -p templates/core templates/workouts
mkdir -p static/css
```

- [ ] **Step 5: Write templates/core/pin.html (minimal — full styling in Task 10)**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Enter PIN — Gym AI</title>
</head>
<body>
<h1>Enter PIN</h1>
{% if error %}<p>{{ error }}</p>{% endif %}
<form method="post" id="pin-form">
  {% csrf_token %}
  <input type="hidden" name="pin" id="pin-input" value="">
  <div>
    <button type="button" onclick="pinPress('1')">1</button>
    <button type="button" onclick="pinPress('2')">2</button>
    <button type="button" onclick="pinPress('3')">3</button>
    <button type="button" onclick="pinPress('4')">4</button>
    <button type="button" onclick="pinPress('5')">5</button>
    <button type="button" onclick="pinPress('6')">6</button>
    <button type="button" onclick="pinPress('7')">7</button>
    <button type="button" onclick="pinPress('8')">8</button>
    <button type="button" onclick="pinPress('9')">9</button>
    <button type="button" onclick="pinPress('0')">0</button>
    <button type="button" onclick="pinDelete()">⌫</button>
  </div>
</form>
<script>
let currentPin = '';
function pinPress(d) {
  if (currentPin.length >= 4) return;
  currentPin += d;
  document.getElementById('pin-input').value = currentPin;
  if (currentPin.length === 4) document.getElementById('pin-form').submit();
}
function pinDelete() {
  currentPin = currentPin.slice(0, -1);
  document.getElementById('pin-input').value = currentPin;
}
</script>
</body>
</html>
```

- [ ] **Step 6: Replace core/views.py with full PIN view**

```python
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
    return HttpResponse('dashboard stub')
```

- [ ] **Step 7: Run tests — expect pass**

```bash
pytest tests/test_pin_view.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add core/forms.py core/views.py templates/core/pin.html tests/test_pin_view.py
git commit -m "feat: PIN form and view, all pin tests passing"
```

---

## Task 8: Dashboard and Exercises Views

**Files:**
- Modify: `core/views.py`
- Modify: `workouts/views.py`
- Create: `tests/test_dashboard_view.py`
- Create: `templates/core/dashboard.html` (minimal — styled in Task 11)
- Create: `templates/workouts/exercises.html` (minimal — styled in Task 12)

- [ ] **Step 1: Write failing tests**

Write `tests/test_dashboard_view.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_dashboard_view.py -v
```

Expected: `test_dashboard_loads_when_verified` fails — dashboard stub returns 200 but `b'GYM AI'` not in content.

- [ ] **Step 3: Write minimal templates/core/dashboard.html**

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Dashboard — Gym AI</title></head>
<body>
<header>GYM AI</header>
<main>
  <div class="hero-card">
    <p>Today's Workout</p>
    <h1>No workout yet</h1>
    <p>Log your first workout to get started</p>
  </div>
  <section>
    <h2>Overload Suggestions</h2>
    <p>No data yet — log workouts to see suggestions</p>
  </section>
  <section>
    <h2>Recent PRs</h2>
    <p>No personal records yet</p>
  </section>
</main>
</body>
</html>
```

- [ ] **Step 4: Write minimal templates/workouts/exercises.html**

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Exercises — Gym AI</title></head>
<body>
<header>GYM AI</header>
<main>
  <h1>Exercise Library</h1>
  <p>{{ exercises|length }} exercises</p>
  {% for exercise in exercises %}
  <div>
    <strong>{{ exercise.name }}</strong>
    <span>{{ exercise.muscle_group }} · {{ exercise.get_equipment_display }}</span>
    <span>{{ exercise.default_sets }} × {{ exercise.default_min_reps }}–{{ exercise.default_max_reps }}</span>
  </div>
  {% empty %}
  <p>No exercises loaded yet.</p>
  {% endfor %}
</main>
</body>
</html>
```

- [ ] **Step 5: Update core/views.py dashboard view**

Replace the `dashboard` function stub:

```python
def dashboard(request):
    return render(request, 'core/dashboard.html')
```

(Keep `index` and `pin` functions unchanged.)

- [ ] **Step 6: Write full workouts/views.py**

```python
from django.shortcuts import render
from .models import Exercise


def exercises(request):
    exercise_list = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'workouts/exercises.html', {'exercises': exercise_list})
```

- [ ] **Step 7: Run tests — expect all pass**

```bash
pytest tests/ -v
```

Expected: All tests pass (18 total across 4 test files).

- [ ] **Step 8: Commit**

```bash
git add core/views.py workouts/views.py templates/core/dashboard.html templates/workouts/exercises.html tests/test_dashboard_view.py
git commit -m "feat: dashboard and exercises views, all tests passing"
```

---

## Task 9: Dark Theme CSS

**Files:**
- Create: `static/css/app.css`

- [ ] **Step 1: Write static/css/app.css**

```css
/* ── Variables ─────────────────────────────────────────────────── */
:root {
  --bg:          #070A0F;
  --card:        #111827;
  --card2:       #1F2937;
  --border:      #374151;
  --text:        #F9FAFB;
  --text-sec:    #9CA3AF;
  --text-muted:  #6B7280;
  --accent:      #22C55E;
  --accent-dim:  rgba(34,197,94,.15);
  --danger:      #EF4444;
  --warning:     #F59E0B;
  --radius-card: 14px;
  --radius-btn:  10px;
  --nav-height:  58px;
}

/* ── Reset ─────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
}

a { color: inherit; text-decoration: none; }
button { cursor: pointer; font-family: inherit; }

/* ── App wrapper ────────────────────────────────────────────────── */
.app-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
  max-width: 480px;
  margin: 0 auto;
  position: relative;
}

/* ── Header ─────────────────────────────────────────────────────── */
.app-header {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  padding: 14px 20px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.app-logo {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 1.5px;
  color: var(--accent);
}

.header-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

/* ── Main content ───────────────────────────────────────────────── */
.app-main {
  flex: 1;
  padding: 16px 16px calc(var(--nav-height) + 16px);
  overflow-y: auto;
}

/* ── Bottom navigation ──────────────────────────────────────────── */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  height: var(--nav-height);
  background: var(--card);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 0;
  font-size: 10px;
  color: var(--text-muted);
  transition: color .15s;
}

.nav-item.active,
.nav-item:hover { color: var(--accent); }

.nav-icon {
  font-size: 18px;
  line-height: 1;
}

/* ── Cards ──────────────────────────────────────────────────────── */
.gym-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 14px 16px;
  margin-bottom: 12px;
}

.section-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 16px 0 8px;
}

.empty-state {
  font-size: 13px;
  color: var(--text-sec);
  text-align: center;
  padding: 8px 0;
}

/* ── Hero card (dashboard) ──────────────────────────────────────── */
.hero-card {
  background: #0D1117;
  border: 1px solid var(--accent-dim);
  border-radius: var(--radius-card);
  padding: 20px 18px;
  margin-bottom: 16px;
  position: relative;
}

.hero-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.hero-day {
  font-size: 28px;
  font-weight: 800;
  color: var(--accent);
  line-height: 1;
  margin-bottom: 6px;
}

.hero-sub {
  font-size: 12px;
  color: var(--text-sec);
}

.hero-badge {
  position: absolute;
  top: 16px;
  right: 16px;
  background: var(--accent-dim);
  color: var(--accent);
  font-size: 10px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
}

/* ── Floating action button ─────────────────────────────────────── */
.fab {
  position: fixed;
  bottom: calc(var(--nav-height) + 16px);
  right: max(16px, calc(50vw - 224px));
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--bg);
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(34,197,94,.4);
  z-index: 100;
}

/* ── Buttons ────────────────────────────────────────────────────── */
.btn {
  display: block;
  width: 100%;
  padding: 13px;
  border-radius: var(--radius-btn);
  font-size: 15px;
  font-weight: 700;
  border: none;
  text-align: center;
}

.btn-primary { background: var(--accent); color: var(--bg); }
.btn-secondary { background: var(--card2); color: var(--text); border: 1px solid var(--border); }
.btn-danger { background: transparent; color: var(--danger); border: 1px solid var(--danger); }

/* ── Form inputs ────────────────────────────────────────────────── */
.form-input {
  width: 100%;
  background: var(--card2);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  padding: 12px 14px;
  color: var(--text);
  font-size: 15px;
  outline: none;
  transition: border-color .15s;
}

.form-input:focus { border-color: var(--accent); }

/* ── PIN screen ─────────────────────────────────────────────────── */
.pin-screen {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  background: var(--bg);
}

.pin-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--card2);
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin-bottom: 20px;
}

.pin-title {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 6px;
}

.pin-sub {
  font-size: 13px;
  color: var(--text-sec);
  margin-bottom: 28px;
}

.pin-error {
  color: var(--danger);
  font-size: 13px;
  margin-bottom: 16px;
}

.pin-dots {
  display: flex;
  gap: 14px;
  margin-bottom: 32px;
}

.pin-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--border);
  background: transparent;
  transition: background .1s, border-color .1s;
}

.pin-dot.filled {
  background: var(--accent);
  border-color: var(--accent);
}

.pin-pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 280px;
}

.pin-key {
  height: 60px;
  background: var(--card2);
  border: 1px solid var(--border);
  border-radius: 12px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background .1s;
}

.pin-key:active { background: var(--border); }
.pin-key--del { font-size: 16px; color: var(--text-sec); }
.pin-key--empty { background: transparent; border: none; pointer-events: none; }

/* ── Page header ────────────────────────────────────────────────── */
.page-header { margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 700; }
.page-sub { font-size: 12px; color: var(--text-sec); margin-top: 2px; }

/* ── Exercise list ──────────────────────────────────────────────── */
.exercise-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 8px;
}

.exercise-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 2px;
}

.exercise-meta {
  font-size: 11px;
  color: var(--text-sec);
}

.exercise-sets {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
  white-space: nowrap;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/css/app.css
git commit -m "feat: full dark theme CSS"
```

---

## Task 10: Base Template

**Files:**
- Create: `templates/base.html`

- [ ] **Step 1: Write templates/base.html**

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="theme-color" content="#070A0F">
  <title>{% block title %}Gym AI{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
</head>
<body>
<div class="app-wrapper">

  {% block header %}
  <header class="app-header">
    <span class="app-logo">GYM AI</span>
    <span class="header-dot"></span>
  </header>
  {% endblock %}

  <main class="app-main">
    {% block content %}{% endblock %}
  </main>

  {% block bottom_nav %}
  <nav class="bottom-nav">
    <a href="{% url 'gym_dashboard' %}"
       class="nav-item {% if request.resolver_match.url_name == 'gym_dashboard' %}active{% endif %}">
      <span class="nav-icon">⊞</span>
      <span>Home</span>
    </a>
    <a href="#" class="nav-item">
      <span class="nav-icon">✎</span>
      <span>Log</span>
    </a>
    <a href="#" class="nav-item">
      <span class="nav-icon">◎</span>
      <span>Coach</span>
    </a>
    <a href="#" class="nav-item">
      <span class="nav-icon">↗</span>
      <span>Progress</span>
    </a>
    <a href="{% url 'gym_exercises' %}"
       class="nav-item {% if request.resolver_match.url_name == 'gym_exercises' %}active{% endif %}">
      <span class="nav-icon">☰</span>
      <span>Exercises</span>
    </a>
  </nav>
  {% endblock %}

</div>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Verify tests still pass**

```bash
pytest tests/ -v
```

Expected: All tests still pass.

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat: base dark template with bottom nav"
```

---

## Task 11: Styled PIN Template

**Files:**
- Replace: `templates/core/pin.html`

- [ ] **Step 1: Replace templates/core/pin.html with full styled version**

```html
{% extends 'base.html' %}
{% load static %}

{% block title %}Enter PIN — Gym AI{% endblock %}

{% block header %}{% endblock %}
{% block bottom_nav %}{% endblock %}

{% block content %}
<div class="pin-screen">

  <div class="pin-icon">🔒</div>
  <h1 class="pin-title">Enter PIN</h1>
  <p class="pin-sub">Your personal gym tracker</p>

  {% if error %}
  <p class="pin-error">{{ error }}</p>
  {% endif %}

  <div class="pin-dots">
    <span class="pin-dot" id="dot-0"></span>
    <span class="pin-dot" id="dot-1"></span>
    <span class="pin-dot" id="dot-2"></span>
    <span class="pin-dot" id="dot-3"></span>
  </div>

  <form method="post" id="pin-form">
    {% csrf_token %}
    <input type="hidden" name="pin" id="pin-input" value="">
    <div class="pin-pad">
      <button type="button" class="pin-key" onclick="pinPress('1')">1</button>
      <button type="button" class="pin-key" onclick="pinPress('2')">2</button>
      <button type="button" class="pin-key" onclick="pinPress('3')">3</button>
      <button type="button" class="pin-key" onclick="pinPress('4')">4</button>
      <button type="button" class="pin-key" onclick="pinPress('5')">5</button>
      <button type="button" class="pin-key" onclick="pinPress('6')">6</button>
      <button type="button" class="pin-key" onclick="pinPress('7')">7</button>
      <button type="button" class="pin-key" onclick="pinPress('8')">8</button>
      <button type="button" class="pin-key" onclick="pinPress('9')">9</button>
      <span class="pin-key pin-key--empty"></span>
      <button type="button" class="pin-key" onclick="pinPress('0')">0</button>
      <button type="button" class="pin-key pin-key--del" onclick="pinDelete()">⌫</button>
    </div>
  </form>

</div>
{% endblock %}

{% block scripts %}
<script>
const MAX = 4;
let pin = '';

function updateDots() {
  for (let i = 0; i < MAX; i++) {
    document.getElementById('dot-' + i).classList.toggle('filled', i < pin.length);
  }
}

function pinPress(d) {
  if (pin.length >= MAX) return;
  pin += d;
  document.getElementById('pin-input').value = pin;
  updateDots();
  if (pin.length === MAX) document.getElementById('pin-form').submit();
}

function pinDelete() {
  pin = pin.slice(0, -1);
  document.getElementById('pin-input').value = pin;
  updateDots();
}
</script>
{% endblock %}
```

- [ ] **Step 2: Run tests to confirm nothing broke**

```bash
pytest tests/test_pin_view.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add templates/core/pin.html
git commit -m "feat: styled PIN screen with number pad and dots"
```

---

## Task 12: Styled Dashboard and Exercises Templates

**Files:**
- Replace: `templates/core/dashboard.html`
- Replace: `templates/workouts/exercises.html`

- [ ] **Step 1: Replace templates/core/dashboard.html**

```html
{% extends 'base.html' %}
{% block title %}Dashboard — Gym AI{% endblock %}

{% block content %}
<div class="hero-card">
  <div class="hero-label">Today's Workout</div>
  <div class="hero-day">No workout yet</div>
  <p class="hero-sub">Log your first workout to get started</p>
  <span class="hero-badge">Start here</span>
</div>

<div class="section-label">Overload Suggestions</div>
<div class="gym-card">
  <p class="empty-state">No data yet — log workouts to see suggestions</p>
</div>

<div class="section-label">Recent PRs</div>
<div class="gym-card">
  <p class="empty-state">No personal records yet</p>
</div>

<button class="fab" aria-label="Log workout">+</button>
{% endblock %}
```

- [ ] **Step 2: Replace templates/workouts/exercises.html**

```html
{% extends 'base.html' %}
{% block title %}Exercises — Gym AI{% endblock %}

{% block content %}
<div class="page-header">
  <h1 class="page-title">Exercise Library</h1>
  <p class="page-sub">{{ exercises|length }} exercises</p>
</div>

{% regroup exercises by get_category_display as category_groups %}
{% for group in category_groups %}
<div class="section-label">{{ group.grouper }}</div>
{% for exercise in group.list %}
<div class="exercise-row">
  <div>
    <span class="exercise-name">{{ exercise.name }}</span>
    <span class="exercise-meta">{{ exercise.muscle_group }} · {{ exercise.get_equipment_display }}</span>
  </div>
  <span class="exercise-sets">
    {{ exercise.default_sets }} × {{ exercise.default_min_reps }}–{{ exercise.default_max_reps }}
  </span>
</div>
{% endfor %}
{% empty %}
<p class="empty-state">No exercises loaded yet. Run: python manage.py loaddata exercises</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 4: Manual smoke test**

```bash
python manage.py runserver
```

Open http://localhost:8000/gym-2026-private/ in a mobile-sized browser window. Confirm:
- Redirects to PIN screen
- PIN screen shows number pad with 4 dots
- Colors: black background, green accent
- Bottom nav is absent on PIN screen

Stop the server with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add templates/core/dashboard.html templates/workouts/exercises.html
git commit -m "feat: styled dashboard and exercises templates"
```

---

## Task 13: set_pin Management Command

**Files:**
- Create: `core/management/__init__.py`
- Create: `core/management/commands/__init__.py`
- Create: `core/management/commands/set_pin.py`

- [ ] **Step 1: Create management command package**

```bash
mkdir -p core/management/commands
touch core/management/__init__.py
touch core/management/commands/__init__.py
```

- [ ] **Step 2: Write core/management/commands/set_pin.py**

```python
import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Hash a PIN for use in GYM_PIN_HASH env variable'

    def handle(self, *args, **options):
        pin = getpass.getpass('Enter PIN (input hidden): ')
        if not pin.strip():
            self.stderr.write(self.style.ERROR('PIN cannot be empty.'))
            return
        confirm = getpass.getpass('Confirm PIN: ')
        if pin != confirm:
            self.stderr.write(self.style.ERROR('PINs do not match.'))
            return
        pin_hash = make_password(pin)
        self.stdout.write('\nAdd this to your .env file:')
        self.stdout.write(self.style.SUCCESS(f'GYM_PIN_HASH={pin_hash}'))
        self.stdout.write('\nThen restart the server.')
```

- [ ] **Step 3: Generate your PIN hash**

```bash
python manage.py set_pin
```

Enter and confirm your desired PIN when prompted. Copy the output line starting with `GYM_PIN_HASH=` into your `.env` file.

- [ ] **Step 4: Verify PIN works**

```bash
python manage.py runserver
```

Open http://localhost:8000/gym-2026-private/, enter your PIN on the number pad. You should be redirected to the dashboard after 4 digits.

Stop the server with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add core/management/
git commit -m "feat: set_pin management command"
```

---

## Task 14: Exercise Seed Fixture

**Files:**
- Create: `workouts/fixtures/exercises.json`

- [ ] **Step 1: Create fixtures directory**

```bash
mkdir -p workouts/fixtures
```

- [ ] **Step 2: Write workouts/fixtures/exercises.json**

```json
[
  {"model":"workouts.exercise","pk":1,"fields":{"name":"Bench Press","muscle_group":"Chest","category":"push","equipment":"barbell","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":2,"fields":{"name":"Incline Dumbbell Press","muscle_group":"Chest","category":"push","equipment":"dumbbell","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":3,"fields":{"name":"Dumbbell Shoulder Press","muscle_group":"Shoulders","category":"push","equipment":"dumbbell","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":4,"fields":{"name":"Machine Chest Press","muscle_group":"Chest","category":"push","equipment":"machine","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":5,"fields":{"name":"Cable Fly","muscle_group":"Chest","category":"push","equipment":"cable","movement_type":"isolation","default_min_reps":10,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":6,"fields":{"name":"Lateral Raise","muscle_group":"Shoulders","category":"push","equipment":"dumbbell","movement_type":"isolation","default_min_reps":12,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":7,"fields":{"name":"Tricep Pushdown","muscle_group":"Triceps","category":"push","equipment":"cable","movement_type":"isolation","default_min_reps":10,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":8,"fields":{"name":"Overhead Tricep Extension","muscle_group":"Triceps","category":"push","equipment":"cable","movement_type":"isolation","default_min_reps":10,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":9,"fields":{"name":"Lat Pulldown","muscle_group":"Back","category":"pull","equipment":"cable","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":10,"fields":{"name":"Pull-up","muscle_group":"Back","category":"pull","equipment":"bodyweight","movement_type":"compound","default_min_reps":5,"default_max_reps":12,"default_sets":3,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":11,"fields":{"name":"Seated Cable Row","muscle_group":"Back","category":"pull","equipment":"cable","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":12,"fields":{"name":"Chest-supported Row","muscle_group":"Back","category":"pull","equipment":"machine","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":13,"fields":{"name":"Dumbbell Row","muscle_group":"Back","category":"pull","equipment":"dumbbell","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":14,"fields":{"name":"Face Pull","muscle_group":"Rear Delts","category":"pull","equipment":"cable","movement_type":"isolation","default_min_reps":12,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":15,"fields":{"name":"Barbell Curl","muscle_group":"Biceps","category":"pull","equipment":"barbell","movement_type":"isolation","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":16,"fields":{"name":"Dumbbell Curl","muscle_group":"Biceps","category":"pull","equipment":"dumbbell","movement_type":"isolation","default_min_reps":10,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":17,"fields":{"name":"Hammer Curl","muscle_group":"Biceps","category":"pull","equipment":"dumbbell","movement_type":"isolation","default_min_reps":10,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":18,"fields":{"name":"Squat","muscle_group":"Quads","category":"legs","equipment":"barbell","movement_type":"compound","default_min_reps":6,"default_max_reps":10,"default_sets":3,"default_increment":"5.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":19,"fields":{"name":"Leg Press","muscle_group":"Quads","category":"legs","equipment":"machine","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"5.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":20,"fields":{"name":"Romanian Deadlift","muscle_group":"Hamstrings","category":"legs","equipment":"barbell","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"5.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":21,"fields":{"name":"Leg Curl","muscle_group":"Hamstrings","category":"legs","equipment":"machine","movement_type":"isolation","default_min_reps":10,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":22,"fields":{"name":"Leg Extension","muscle_group":"Quads","category":"legs","equipment":"machine","movement_type":"isolation","default_min_reps":10,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":23,"fields":{"name":"Walking Lunge","muscle_group":"Legs","category":"legs","equipment":"dumbbell","movement_type":"compound","default_min_reps":10,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":24,"fields":{"name":"Calf Raise","muscle_group":"Calves","category":"legs","equipment":"machine","movement_type":"isolation","default_min_reps":12,"default_max_reps":20,"default_sets":3,"default_increment":"5.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":25,"fields":{"name":"Machine Row","muscle_group":"Back","category":"upper_arms","equipment":"machine","movement_type":"compound","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":26,"fields":{"name":"Rear Delt Fly","muscle_group":"Rear Delts","category":"upper_arms","equipment":"machine","movement_type":"isolation","default_min_reps":12,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":27,"fields":{"name":"Rope Pushdown","muscle_group":"Triceps","category":"upper_arms","equipment":"cable","movement_type":"isolation","default_min_reps":12,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":28,"fields":{"name":"Skull Crusher","muscle_group":"Triceps","category":"upper_arms","equipment":"barbell","movement_type":"isolation","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":29,"fields":{"name":"Treadmill Incline Walk","muscle_group":"Conditioning","category":"conditioning_abs","equipment":"machine","movement_type":"cardio","default_min_reps":20,"default_max_reps":40,"default_sets":1,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":30,"fields":{"name":"Bike","muscle_group":"Conditioning","category":"conditioning_abs","equipment":"machine","movement_type":"cardio","default_min_reps":20,"default_max_reps":40,"default_sets":1,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":31,"fields":{"name":"Rowing Machine","muscle_group":"Conditioning","category":"conditioning_abs","equipment":"machine","movement_type":"cardio","default_min_reps":20,"default_max_reps":30,"default_sets":1,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":32,"fields":{"name":"Cable Crunch","muscle_group":"Abs","category":"conditioning_abs","equipment":"cable","movement_type":"core","default_min_reps":12,"default_max_reps":15,"default_sets":3,"default_increment":"2.5","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":33,"fields":{"name":"Hanging Knee Raise","muscle_group":"Abs","category":"conditioning_abs","equipment":"bodyweight","movement_type":"core","default_min_reps":10,"default_max_reps":15,"default_sets":3,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":34,"fields":{"name":"Plank","muscle_group":"Core","category":"conditioning_abs","equipment":"bodyweight","movement_type":"core","default_min_reps":30,"default_max_reps":60,"default_sets":3,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercise","pk":35,"fields":{"name":"Ab Wheel","muscle_group":"Core","category":"conditioning_abs","equipment":"bodyweight","movement_type":"core","default_min_reps":8,"default_max_reps":12,"default_sets":3,"default_increment":"0.0","is_active":true,"created_at":"2026-05-23T00:00:00Z","updated_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":1,"fields":{"exercise":1,"alias":"bench","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":2,"fields":{"exercise":1,"alias":"flat bench","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":3,"fields":{"exercise":1,"alias":"bb bench","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":4,"fields":{"exercise":2,"alias":"incline db","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":5,"fields":{"exercise":2,"alias":"incline press","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":6,"fields":{"exercise":3,"alias":"shoulder press","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":7,"fields":{"exercise":3,"alias":"db shoulder press","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":8,"fields":{"exercise":6,"alias":"lateral raise","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":9,"fields":{"exercise":6,"alias":"lat raise","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":10,"fields":{"exercise":7,"alias":"pushdown","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":11,"fields":{"exercise":7,"alias":"tricep pushdown","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":12,"fields":{"exercise":9,"alias":"lat pulldown","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":13,"fields":{"exercise":9,"alias":"lat pull","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":14,"fields":{"exercise":9,"alias":"pulldown","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":15,"fields":{"exercise":11,"alias":"cable row","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":16,"fields":{"exercise":11,"alias":"seated row","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":17,"fields":{"exercise":13,"alias":"db row","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":18,"fields":{"exercise":14,"alias":"face pull","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":19,"fields":{"exercise":15,"alias":"bb curl","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":20,"fields":{"exercise":15,"alias":"barbell curl","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":21,"fields":{"exercise":16,"alias":"db curl","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":22,"fields":{"exercise":17,"alias":"hammer","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":23,"fields":{"exercise":18,"alias":"squat","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":24,"fields":{"exercise":18,"alias":"bb squat","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":25,"fields":{"exercise":19,"alias":"leg press","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":26,"fields":{"exercise":20,"alias":"rdl","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":27,"fields":{"exercise":20,"alias":"romanian deadlift","created_at":"2026-05-23T00:00:00Z"}},
  {"model":"workouts.exercisealias","pk":28,"fields":{"exercise":32,"alias":"cable crunch","created_at":"2026-05-23T00:00:00Z"}}
]
```

- [ ] **Step 3: Load the fixture**

```bash
python manage.py loaddata exercises
```

Expected:
```
Installed 63 object(s) from 1 fixture(s)
```

- [ ] **Step 4: Verify in admin and exercises page**

```bash
python manage.py runserver
```

- Open http://localhost:8000/admin/workouts/exercise/ — confirm 35 exercises appear, grouped by category
- Open http://localhost:8000/gym-2026-private/exercises/ (after PIN) — confirm exercises list renders with categories

Stop the server.

- [ ] **Step 5: Commit**

```bash
git add workouts/fixtures/exercises.json
git commit -m "feat: exercise seed fixture with 35 exercises and 28 aliases"
```

---

## Task 15: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_exercise_models.py::test_exercise_str PASSED
tests/test_exercise_models.py::test_exercise_defaults PASSED
tests/test_exercise_models.py::test_exercise_name_unique PASSED
tests/test_exercise_models.py::test_alias_str PASSED
tests/test_exercise_models.py::test_alias_unique_together PASSED
tests/test_exercise_models.py::test_alias_cascade_delete PASSED
tests/test_pin_middleware.py::test_unverified_request_redirects_to_pin PASSED
tests/test_pin_middleware.py::test_pin_url_accessible_without_session PASSED
tests/test_pin_middleware.py::test_exercises_url_redirects_without_session PASSED
tests/test_pin_middleware.py::test_verified_session_passes_through PASSED
tests/test_pin_middleware.py::test_expired_session_redirects PASSED
tests/test_pin_middleware.py::test_admin_not_protected_by_pin PASSED
tests/test_pin_view.py::test_pin_get_renders_form PASSED
tests/test_pin_view.py::test_correct_pin_sets_session_and_redirects PASSED
tests/test_pin_view.py::test_wrong_pin_shows_error PASSED
tests/test_pin_view.py::test_empty_pin_shows_error PASSED
tests/test_dashboard_view.py::test_dashboard_requires_pin PASSED
tests/test_dashboard_view.py::test_dashboard_loads_when_verified PASSED
tests/test_dashboard_view.py::test_exercises_requires_pin PASSED
tests/test_dashboard_view.py::test_exercises_loads_when_verified PASSED
tests/test_dashboard_view.py::test_exercises_shows_active_exercises PASSED

21 passed in X.XXs
```

- [ ] **Step 2: Manual acceptance criteria check**

```bash
python manage.py runserver
```

Verify each acceptance criterion from the spec:

| Criterion | How to verify |
|---|---|
| App opens on secret URL | Visit http://localhost:8000/gym-2026-private/ |
| PIN screen blocks access | Confirm redirect to /pin/ without session |
| Wrong PIN shows error | Enter wrong digits — should show "Incorrect PIN" |
| Correct PIN opens dashboard | Enter correct PIN — hero card renders |
| Dashboard renders on mobile viewport | Resize browser to 375px wide — layout intact |
| Exercise library accessible | Visit /exercises/ after PIN — 35 exercises listed |
| Admin manages exercises | Visit /admin/workouts/exercise/ — inline alias editor works |
| Session expires after timeout | Set GYM_SESSION_TIMEOUT_HOURS=0 in .env, reload — redirected to PIN |

- [ ] **Step 3: Final commit**

```bash
git add -A
git status  # verify nothing sensitive is staged
git commit -m "feat: Phase 1 Foundation complete — PIN auth, dashboard, exercise library"
```

---

*Phase 2 plan: WorkoutSession, WorkoutExercise, WorkoutSet models — manual log form, workout history, session detail page.*
