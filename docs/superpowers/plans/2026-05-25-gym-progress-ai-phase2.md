# Gym Progress AI — Phase 2 Workout Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add workout logging — name a session, add exercises, log sets (weight + reps), finish, view history as rich cards, with the dashboard hero updating to show the last session.

**Architecture:** Three new models (WorkoutSession, WorkoutExercise, WorkoutSet) in `workouts/models.py`. Nine new views in `workouts/views.py` using PRG (Post/Redirect/Get). All URL patterns added to `core/urls.py` in Task 4. PinMiddleware already protects everything under `/<secret>/`.

**Tech Stack:** Django 4.2, PostgreSQL, pytest-django, custom dark CSS (no new packages)

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `workouts/models.py` | Modify | Add WorkoutSession, WorkoutExercise, WorkoutSet |
| `workouts/admin.py` | Modify | Register new models |
| `workouts/views.py` | Modify | Replace entire file — add 9 new views |
| `core/urls.py` | Modify | Add all 9 new URL patterns |
| `core/views.py` | Modify | Pass last_session context to dashboard |
| `static/css/app.css` | Modify | Append log UI, history card, session detail styles |
| `templates/workouts/log_home.html` | Create | Start workout form |
| `templates/workouts/active_session.html` | Create | Main logging screen |
| `templates/workouts/history.html` | Create | Rich card history |
| `templates/workouts/session_detail.html` | Create | Session detail |
| `templates/core/dashboard.html` | Modify | Show last session in hero, FAB links to log |
| `templates/base.html` | Modify | Wire Log nav link to gym_log_home |
| `tests/test_workout_session_models.py` | Create | Model tests |
| `tests/test_log_views.py` | Create | Log flow view tests |
| `tests/test_history_views.py` | Create | History/detail view tests |

---

## Task 1: WorkoutSession, WorkoutExercise, WorkoutSet Models

**Files:**
- Modify: `workouts/models.py`
- Create: `tests/test_workout_session_models.py`

- [ ] **Step 1: Write failing model tests**

Write `tests/test_workout_session_models.py`:

```python
import pytest
from workouts.models import Exercise, WorkoutSession, WorkoutExercise, WorkoutSet


def make_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_session(**kwargs):
    defaults = {'name': 'Monday Push'}
    defaults.update(kwargs)
    return WorkoutSession.objects.create(**defaults)


@pytest.mark.django_db
def test_session_str():
    s = make_session()
    assert 'Monday Push' in str(s)


@pytest.mark.django_db
def test_session_defaults():
    s = make_session()
    assert s.status == 'active'
    assert s.completed_at is None


@pytest.mark.django_db
def test_session_ordering():
    s1 = make_session(name='First')
    s2 = make_session(name='Second')
    sessions = list(WorkoutSession.objects.all())
    assert sessions[0] == s2  # newest first


@pytest.mark.django_db
def test_workout_exercise_str():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    assert 'Bench Press' in str(we)
    assert 'Monday Push' in str(we)


@pytest.mark.django_db
def test_workout_set_str():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    ws = WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    assert '60' in str(ws)
    assert '10' in str(ws)


@pytest.mark.django_db
def test_cascade_delete_session_removes_exercises_and_sets():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    s.delete()
    assert WorkoutExercise.objects.count() == 0
    assert WorkoutSet.objects.count() == 0


@pytest.mark.django_db
def test_cascade_delete_workout_exercise_removes_sets():
    s = make_session()
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=s, exercise=ex, order=1)
    WorkoutSet.objects.create(workout_exercise=we, set_number=1, weight_kg=60, reps=10)
    we.delete()
    assert WorkoutSet.objects.count() == 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_workout_session_models.py -v
```

Expected: `ImportError` — models don't exist yet.

- [ ] **Step 3: Append three models to `workouts/models.py`**

Add after the `ExerciseAlias` class (end of file):

```python


class WorkoutSession(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('complete', 'Complete')]

    name         = models.CharField(max_length=100)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    started_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.name} ({self.started_at:%Y-%m-%d})'


class WorkoutExercise(models.Model):
    session  = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='workout_exercises')
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name='workout_exercises')
    order    = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.session.name} — {self.exercise.name}'


class WorkoutSet(models.Model):
    workout_exercise = models.ForeignKey(WorkoutExercise, on_delete=models.CASCADE, related_name='sets')
    set_number       = models.PositiveIntegerField()
    weight_kg        = models.DecimalField(max_digits=5, decimal_places=1)
    reps             = models.PositiveIntegerField()
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['set_number']

    def __str__(self):
        return f'Set {self.set_number}: {self.weight_kg}kg × {self.reps}'
```

- [ ] **Step 4: Create and apply migrations**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && python manage.py makemigrations workouts && python manage.py migrate
```

Expected: Migration created and applied, `OK` on all lines.

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_workout_session_models.py -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 28 tests pass.

- [ ] **Step 7: Commit**

```bash
git add workouts/models.py workouts/migrations/ tests/test_workout_session_models.py
git commit -m "feat: WorkoutSession, WorkoutExercise, WorkoutSet models"
```

---

## Task 2: Admin Registration

**Files:**
- Modify: `workouts/admin.py`

- [ ] **Step 1: Replace `workouts/admin.py`**

```python
from django.contrib import admin

from .models import Exercise, ExerciseAlias, WorkoutExercise, WorkoutSession, WorkoutSet


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


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0
    fields = ('exercise', 'order')
    readonly_fields = ('order',)


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'started_at', 'completed_at')
    list_filter = ('status',)
    readonly_fields = ('started_at', 'completed_at')
    inlines = [WorkoutExerciseInline]
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 28 tests pass.

- [ ] **Step 3: Commit**

```bash
git add workouts/admin.py
git commit -m "feat: register workout session models in admin"
```

---

## Task 3: CSS for Log UI

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 1: Append to `static/css/app.css`**

```css
/* ── Log home ───────────────────────────────────────────────────── */
.log-home {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: calc(100dvh - var(--nav-height) - 60px);
  padding: 0 4px;
}

/* ── Active session ─────────────────────────────────────────────── */
.session-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
}

.we-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 14px 16px;
  margin-bottom: 12px;
}

.we-name { font-size: 15px; font-weight: 700; margin-bottom: 2px; }
.we-meta { font-size: 11px; color: var(--text-sec); margin-bottom: 12px; }

/* ── Set table ──────────────────────────────────────────────────── */
.set-table-header {
  display: grid;
  grid-template-columns: 28px 1fr 14px 1fr 36px 36px;
  gap: 6px;
  font-size: 9px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 0 2px;
  margin-bottom: 6px;
}

.set-row {
  display: grid;
  grid-template-columns: 28px 1fr 14px 1fr 36px 36px;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}

.set-num { font-size: 11px; color: var(--text-muted); text-align: center; }

.set-val {
  background: var(--card2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 4px;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.set-input {
  background: var(--card2);
  border: 1px solid var(--accent);
  border-radius: 8px;
  padding: 8px 4px;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  width: 100%;
  outline: none;
  -moz-appearance: textfield;
}

.set-input::-webkit-outer-spin-button,
.set-input::-webkit-inner-spin-button { -webkit-appearance: none; }

.set-x { font-size: 11px; color: var(--text-muted); text-align: center; }

.set-check {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--bg);
  font-size: 14px; font-weight: 700;
  border: none;
  display: flex; align-items: center; justify-content: center;
}

.set-delete {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: transparent;
  color: var(--text-muted);
  font-size: 18px;
  border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  line-height: 1;
}

/* ── Exercise picker ────────────────────────────────────────────── */
.picker-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.6);
  z-index: 200;
  align-items: flex-end;
}

.picker-overlay.open { display: flex; }

.picker-sheet {
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
  background: var(--card);
  border-radius: 20px 20px 0 0;
  padding: 20px 16px 32px;
  max-height: 70dvh;
  display: flex;
  flex-direction: column;
}

.picker-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.picker-search {
  flex: 1;
  background: var(--card2);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  padding: 10px 14px;
  color: var(--text);
  font-size: 14px;
  outline: none;
}

.picker-search:focus { border-color: var(--accent); }

.picker-close {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: var(--card2);
  border: 1px solid var(--border);
  color: var(--text-sec);
  font-size: 20px;
  display: flex; align-items: center; justify-content: center;
}

.picker-list { overflow-y: auto; flex: 1; }

.picker-item {
  display: block;
  width: 100%;
  background: none;
  border: none;
  border-bottom: 1px solid var(--border);
  padding: 12px 4px;
  text-align: left;
  cursor: pointer;
}

.picker-item:last-child { border-bottom: none; }
.picker-item-name { display: block; font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 2px; }
.picker-item-meta { font-size: 11px; color: var(--text-sec); }

/* ── History cards ──────────────────────────────────────────────── */
.history-card {
  display: block;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 14px 16px;
  margin-bottom: 12px;
  text-decoration: none;
  color: inherit;
}

.hc-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
.hc-name { font-size: 15px; font-weight: 700; }
.hc-date { font-size: 11px; color: var(--text-muted); }
.hc-meta { font-size: 11px; color: var(--text-sec); margin-bottom: 10px; }

.hc-exercises {
  border-top: 1px solid var(--border);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hc-ex { font-size: 12px; color: var(--text-sec); }
.hc-ex-weight { color: var(--text); font-weight: 600; }
.hc-more { font-size: 11px; color: var(--text-muted); }

/* ── Session detail ─────────────────────────────────────────────── */
.detail-hero { margin-bottom: 20px; }
.detail-name { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
.detail-meta { font-size: 12px; color: var(--text-sec); }

.detail-set-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}

.detail-set-row:last-child { border-bottom: none; }
.detail-set-num { color: var(--text-muted); width: 44px; }
.detail-set-val { color: var(--text); font-weight: 600; }
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 28 tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "feat: CSS for log UI, history cards, session detail"
```

---

## Task 4: URL Patterns + log_home + start_session

**Files:**
- Modify: `workouts/views.py` (full replacement)
- Modify: `core/urls.py`
- Create: `templates/workouts/log_home.html`
- Create: `tests/test_log_views.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_log_views.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_log_views.py -v
```

Expected: `NoReverseMatch` — URLs not defined yet.

- [ ] **Step 3: Replace `workouts/views.py` entirely**

```python
from django.db.models import Max, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Exercise, WorkoutExercise, WorkoutSession, WorkoutSet


def exercises(request):
    exercise_list = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'workouts/exercises.html', {'exercises': exercise_list})


def log_home(request):
    active = WorkoutSession.objects.filter(status='active').first()
    if active:
        return redirect('gym_active_session', session_id=active.id)
    return render(request, 'workouts/log_home.html')


@require_http_methods(['POST'])
def start_session(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'workouts/log_home.html', {'error': 'Please enter a session name.'})
    session = WorkoutSession.objects.create(name=name)
    return redirect('gym_active_session', session_id=session.id)


def active_session(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    if session.status == 'complete':
        return redirect('gym_session_detail', session_id=session.id)
    workout_exercises = session.workout_exercises.select_related('exercise').prefetch_related('sets')
    all_exercises = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'workouts/active_session.html', {
        'session': session,
        'workout_exercises': workout_exercises,
        'all_exercises': all_exercises,
    })


@require_http_methods(['POST'])
def add_exercise(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    exercise = get_object_or_404(Exercise, id=request.POST.get('exercise_id'))
    order = session.workout_exercises.count() + 1
    WorkoutExercise.objects.create(session=session, exercise=exercise, order=order)
    return redirect('gym_active_session', session_id=session.id)


@require_http_methods(['POST'])
def add_set(request, session_id, we_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    we = get_object_or_404(WorkoutExercise, id=we_id, session=session)
    try:
        weight_kg = float(request.POST.get('weight_kg', ''))
        reps = int(request.POST.get('reps', ''))
        if weight_kg < 0 or reps < 1:
            raise ValueError
    except (ValueError, TypeError):
        return redirect('gym_active_session', session_id=session.id)
    set_number = we.sets.count() + 1
    WorkoutSet.objects.create(workout_exercise=we, set_number=set_number, weight_kg=weight_kg, reps=reps)
    return redirect('gym_active_session', session_id=session.id)


@require_http_methods(['POST'])
def delete_set(request, session_id, we_id, set_id):
    ws = get_object_or_404(
        WorkoutSet, id=set_id,
        workout_exercise__id=we_id,
        workout_exercise__session__id=session_id,
    )
    ws.delete()
    return redirect('gym_active_session', session_id=session_id)


@require_http_methods(['POST'])
def finish_session(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    session.status = 'complete'
    session.completed_at = timezone.now()
    session.save()
    return redirect('gym_history')


def history(request):
    exercises_qs = WorkoutExercise.objects.select_related('exercise').annotate(
        max_weight=Max('sets__weight_kg')
    ).order_by('order')
    sessions = WorkoutSession.objects.filter(status='complete').prefetch_related(
        Prefetch('workout_exercises', queryset=exercises_qs)
    )
    return render(request, 'workouts/history.html', {'sessions': sessions})


def session_detail(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    workout_exercises = session.workout_exercises.select_related('exercise').prefetch_related('sets')
    return render(request, 'workouts/session_detail.html', {
        'session': session,
        'workout_exercises': workout_exercises,
    })
```

- [ ] **Step 4: Replace `core/urls.py`**

```python
from django.urls import path

from . import views
from workouts import views as workout_views

urlpatterns = [
    path('', views.index, name='gym_index'),
    path('pin/', views.pin, name='gym_pin'),
    path('dashboard/', views.dashboard, name='gym_dashboard'),
    path('exercises/', workout_views.exercises, name='gym_exercises'),
    # Workout logging
    path('log/', workout_views.log_home, name='gym_log_home'),
    path('log/start/', workout_views.start_session, name='gym_log_start'),
    path('log/<int:session_id>/', workout_views.active_session, name='gym_active_session'),
    path('log/<int:session_id>/add-exercise/', workout_views.add_exercise, name='gym_add_exercise'),
    path('log/<int:session_id>/exercise/<int:we_id>/add-set/', workout_views.add_set, name='gym_add_set'),
    path('log/<int:session_id>/exercise/<int:we_id>/delete-set/<int:set_id>/', workout_views.delete_set, name='gym_delete_set'),
    path('log/<int:session_id>/finish/', workout_views.finish_session, name='gym_finish_session'),
    # History
    path('history/', workout_views.history, name='gym_history'),
    path('history/<int:session_id>/', workout_views.session_detail, name='gym_session_detail'),
]
```

- [ ] **Step 5: Create `templates/workouts/log_home.html`**

```html
{% extends 'base.html' %}
{% block title %}Start Workout — Gym AI{% endblock %}

{% block content %}
<div class="log-home">
  <div class="page-header">
    <h1 class="page-title">Start Workout</h1>
    <p class="page-sub">Name this session, then add exercises</p>
  </div>

  {% if error %}<p class="pin-error">{{ error }}</p>{% endif %}

  <form method="post" action="{% url 'gym_log_start' %}">
    {% csrf_token %}
    <input type="text" name="name" class="form-input" placeholder="e.g. Monday Push"
           autofocus maxlength="100" style="margin-bottom:12px">
    <button type="submit" class="btn btn-primary">Start Workout</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Run log_home + start_session tests**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_log_views.py -v
```

Expected: 4 tests pass.

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -v
```

Expected: 32 tests pass.

- [ ] **Step 8: Commit**

```bash
git add workouts/views.py core/urls.py templates/workouts/log_home.html tests/test_log_views.py
git commit -m "feat: log_home, start_session, all URL patterns"
```

---

## Task 5: active_session + add_exercise Views

**Files:**
- Modify: `tests/test_log_views.py`
- Create: `templates/workouts/active_session.html`

- [ ] **Step 1: Append failing tests to `tests/test_log_views.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_log_views.py -k "active_session or add_exercise" -v
```

Expected: FAIL — template `active_session.html` doesn't exist yet.

- [ ] **Step 3: Create `templates/workouts/active_session.html`**

```html
{% extends 'base.html' %}
{% block title %}{{ session.name }} — Gym AI{% endblock %}

{% block content %}
<div class="session-title">{{ session.name }}</div>

{% for we in workout_exercises %}
<div class="we-card">
  <div class="we-name">{{ we.exercise.name }}</div>
  <div class="we-meta">{{ we.exercise.get_category_display }} · {{ we.exercise.get_equipment_display }}</div>

  {% with sets=we.sets.all %}
  {% if sets %}
  <div class="set-table-header">
    <span>Set</span><span style="text-align:center">kg</span><span></span>
    <span style="text-align:center">Reps</span><span></span><span></span>
  </div>
  {% for set in sets %}
  <div class="set-row">
    <span class="set-num">{{ set.set_number }}</span>
    <span class="set-val">{{ set.weight_kg|floatformat:"-1" }}</span>
    <span class="set-x">×</span>
    <span class="set-val">{{ set.reps }}</span>
    <span></span>
    <form method="post" action="{% url 'gym_delete_set' session.id we.id set.id %}">
      {% csrf_token %}
      <button type="submit" class="set-delete" aria-label="Delete">×</button>
    </form>
  </div>
  {% endfor %}
  {% endif %}

  <form method="post" action="{% url 'gym_add_set' session.id we.id %}" class="set-row" style="margin-top:8px">
    {% csrf_token %}
    <span class="set-num">{{ sets|length|add:1 }}</span>
    <input type="number" name="weight_kg" class="set-input" step="0.5" min="0"
           placeholder="kg" required inputmode="decimal">
    <span class="set-x">×</span>
    <input type="number" name="reps" class="set-input" min="1"
           placeholder="reps" required inputmode="numeric">
    <button type="submit" class="set-check">✓</button>
    <span></span>
  </form>
  {% endwith %}
</div>
{% empty %}
<p class="empty-state" style="margin-bottom:16px">No exercises yet — add one below</p>
{% endfor %}

<button type="button" class="btn btn-secondary" style="margin-bottom:12px" onclick="openPicker()">
  + Add Exercise
</button>

<form method="post" action="{% url 'gym_finish_session' session.id %}">
  {% csrf_token %}
  <button type="submit" class="btn btn-danger">Finish Workout</button>
</form>

<!-- Exercise picker -->
<div class="picker-overlay" id="picker-overlay">
  <div class="picker-sheet">
    <div class="picker-header">
      <input type="text" class="picker-search" id="picker-search" placeholder="Search exercises...">
      <button type="button" class="picker-close" onclick="closePicker()">×</button>
    </div>
    <div class="picker-list" id="picker-list">
      {% for ex in all_exercises %}
      <form method="post" action="{% url 'gym_add_exercise' session.id %}">
        {% csrf_token %}
        <input type="hidden" name="exercise_id" value="{{ ex.id }}">
        <button type="submit" class="picker-item">
          <span class="picker-item-name">{{ ex.name }}</span>
          <span class="picker-item-meta">{{ ex.get_category_display }} · {{ ex.get_equipment_display }}</span>
        </button>
      </form>
      {% endfor %}
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function openPicker() {
  document.getElementById('picker-overlay').classList.add('open');
  document.getElementById('picker-search').focus();
}
function closePicker() {
  document.getElementById('picker-overlay').classList.remove('open');
}
document.getElementById('picker-search').addEventListener('input', function () {
  const q = this.value.toLowerCase();
  document.querySelectorAll('#picker-list form').forEach(function (form) {
    const name = form.querySelector('.picker-item-name').textContent.toLowerCase();
    form.style.display = name.includes(q) ? '' : 'none';
  });
});
document.getElementById('picker-overlay').addEventListener('click', function (e) {
  if (e.target === this) closePicker();
});
</script>
{% endblock %}
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_log_views.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```

Expected: 37 tests pass.

- [ ] **Step 6: Commit**

```bash
git add templates/workouts/active_session.html tests/test_log_views.py
git commit -m "feat: active_session and add_exercise views"
```

---

## Task 6: add_set + delete_set Views

**Files:**
- Modify: `tests/test_log_views.py`

(Views already implemented in Task 4's `workouts/views.py` replacement.)

- [ ] **Step 1: Append failing tests to `tests/test_log_views.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_log_views.py -k "add_set or delete_set" -v
```

Expected: 3 tests pass (views already implemented in Task 4).

- [ ] **Step 3: Run full suite**

```bash
pytest tests/ -v
```

Expected: 40 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_log_views.py
git commit -m "test: add_set and delete_set view tests"
```

---

## Task 7: finish_session View

**Files:**
- Modify: `tests/test_log_views.py`

(View already implemented in Task 4.)

- [ ] **Step 1: Append failing tests to `tests/test_log_views.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_log_views.py -k "finish_session" -v
```

Expected: 2 tests pass.

- [ ] **Step 3: Run full suite**

```bash
pytest tests/ -v
```

Expected: 42 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_log_views.py
git commit -m "test: finish_session view tests"
```

---

## Task 8: history + session_detail Views

**Files:**
- Create: `templates/workouts/history.html`
- Create: `templates/workouts/session_detail.html`
- Create: `tests/test_history_views.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_history_views.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_history_views.py -v
```

Expected: FAIL — templates don't exist yet.

- [ ] **Step 3: Create `templates/workouts/history.html`**

```html
{% extends 'base.html' %}
{% block title %}History — Gym AI{% endblock %}

{% block content %}
<div class="page-header">
  <h1 class="page-title">History</h1>
</div>

{% for session in sessions %}
{% with exlist=session.workout_exercises.all %}
<a href="{% url 'gym_session_detail' session.id %}" class="history-card">
  <div class="hc-top">
    <div class="hc-name">{{ session.name }}</div>
    <div class="hc-date">{{ session.completed_at|timesince }} ago</div>
  </div>
  <div class="hc-meta">{{ exlist|length }} exercise{{ exlist|length|pluralize }}</div>
  {% if exlist %}
  <div class="hc-exercises">
    {% for we in exlist|slice:":3" %}
    <span class="hc-ex">
      {{ we.exercise.name }}{% if we.max_weight %} · <span class="hc-ex-weight">{{ we.max_weight|floatformat:"-1" }}kg</span>{% endif %}
    </span>
    {% endfor %}
    {% if exlist|length > 3 %}
    <span class="hc-more">+{{ exlist|length|add:"-3" }} more</span>
    {% endif %}
  </div>
  {% endif %}
</a>
{% endwith %}
{% empty %}
<p class="empty-state">No workouts logged yet — tap + to start</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: Create `templates/workouts/session_detail.html`**

```html
{% extends 'base.html' %}
{% block title %}{{ session.name }} — Gym AI{% endblock %}

{% block content %}
<div class="detail-hero">
  <div class="detail-name">{{ session.name }}</div>
  <div class="detail-meta">
    {{ session.started_at|date:"D j M Y" }}{% if session.completed_at %} · {{ session.started_at|timesince:session.completed_at }}{% endif %}
  </div>
</div>

{% for we in workout_exercises %}
<div class="section-label">{{ we.exercise.name }}</div>
<div class="gym-card">
  {% for set in we.sets.all %}
  <div class="detail-set-row">
    <span class="detail-set-num">Set {{ set.set_number }}</span>
    <span class="detail-set-val">{{ set.weight_kg|floatformat:"-1" }} kg × {{ set.reps }} reps</span>
  </div>
  {% empty %}
  <p class="empty-state">No sets logged</p>
  {% endfor %}
</div>
{% empty %}
<p class="empty-state">No exercises in this session</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Run tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_history_views.py -v
```

Expected: 5 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 47 tests pass.

- [ ] **Step 7: Commit**

```bash
git add templates/workouts/history.html templates/workouts/session_detail.html tests/test_history_views.py
git commit -m "feat: history and session_detail views"
```

---

## Task 9: Dashboard Update

**Files:**
- Modify: `core/views.py`
- Modify: `templates/core/dashboard.html`
- Modify: `tests/test_dashboard_view.py`

- [ ] **Step 1: Append failing tests to `tests/test_dashboard_view.py`**

Read the current file first, then append these two tests:

```python
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
```

- [ ] **Step 2: Run new tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_dashboard_view.py -k "last_session or no_session" -v
```

Expected: FAIL — dashboard doesn't pass `last_session` context yet.

- [ ] **Step 3: Update `core/views.py` dashboard function**

Replace the `dashboard` function:

```python
def dashboard(request):
    from workouts.models import WorkoutSession
    last_session = WorkoutSession.objects.filter(status='complete').first()
    return render(request, 'core/dashboard.html', {'last_session': last_session})
```

- [ ] **Step 4: Replace `templates/core/dashboard.html`**

```html
{% extends 'base.html' %}
{% block title %}Dashboard — Gym AI{% endblock %}

{% block content %}
<div class="hero-card">
  <div class="hero-label">Last Workout</div>
  {% if last_session %}
  <div class="hero-day">{{ last_session.name }}</div>
  <p class="hero-sub">{{ last_session.completed_at|timesince }} ago</p>
  {% else %}
  <div class="hero-day">No workout yet</div>
  <p class="hero-sub">Log your first workout to get started</p>
  <span class="hero-badge">Start here</span>
  {% endif %}
</div>

<div class="section-label">Overload Suggestions</div>
<div class="gym-card">
  <p class="empty-state">No data yet — log workouts to see suggestions</p>
</div>

<div class="section-label">Recent PRs</div>
<div class="gym-card">
  <p class="empty-state">No personal records yet</p>
</div>

<a href="{% url 'gym_log_home' %}" class="fab" aria-label="Log workout">+</a>
{% endblock %}
```

- [ ] **Step 5: Run dashboard tests**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_dashboard_view.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 49 tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/views.py templates/core/dashboard.html tests/test_dashboard_view.py
git commit -m "feat: dashboard shows last session, FAB links to log"
```

---

## Task 10: Navigation Links

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: Replace `templates/base.html`**

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
    <a href="{% url 'gym_log_home' %}"
       class="nav-item {% if request.resolver_match.url_name == 'gym_log_home' or request.resolver_match.url_name == 'gym_active_session' %}active{% endif %}">
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

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 49 tests pass.

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat: wire Log nav link to log_home"
```

---

## Final Verification

- [ ] Start the server: `source venv/bin/activate && python manage.py runserver`
- [ ] Dashboard FAB → Start Workout form
- [ ] Name session → active session view
- [ ] Add Exercise → picker opens, search filters, select adds exercise
- [ ] Log set (weight + reps ✓) → set appears in table
- [ ] Delete set → set disappears
- [ ] Finish Workout → history page with rich card
- [ ] History card → session detail with all sets
- [ ] Dashboard hero shows last session name
- [ ] Log nav item active on log pages
