# Repeat Last Workout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "↺ Quick Repeat" buttons to the Start Workout screen that let the user repeat their last Push/Pull/Legs session with AI progressive overload suggestions pre-filled as editable inputs.

**Architecture:** A new pure-Python `workouts/repeat.py` module handles category detection and preview data assembly. Two new views (`repeat_preview` GET, `repeat_start` POST) serve the flow. The existing `log_home` view is updated to pass repeat button data. All DB writes in `repeat_start` use `transaction.atomic()`.

**Tech Stack:** Django 4.2, Python `collections.Counter`, existing `recommend()` from `workouts/coach.py`, pytest-django.

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `workouts/repeat.py` | Create | `session_category()`, `get_last_sessions_by_category()`, `get_repeat_preview()` |
| `workouts/views.py` | Modify | Update `log_home` + `start_session`, add `repeat_preview` + `repeat_start` |
| `core/urls.py` | Modify | Add `gym_repeat_preview` and `gym_repeat_start` URL patterns |
| `static/css/app.css` | Modify | Append repeat-specific styles |
| `templates/workouts/log_home.html` | Modify | Add Quick Repeat section |
| `templates/workouts/repeat_preview.html` | Create | Preview screen with editable set inputs |
| `tests/test_repeat_logic.py` | Create | 3 unit tests for `session_category()` |
| `tests/test_repeat_views.py` | Create | 7 HTTP tests for repeat views and log_home |

---

## Task 1: `workouts/repeat.py` + Unit Tests

**Files:**
- Create: `workouts/repeat.py`
- Create: `tests/test_repeat_logic.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_repeat_logic.py`:

```python
import pytest
from workouts.repeat import session_category


class FakeExercise:
    def __init__(self, category):
        self.category = category


class FakeWE:
    def __init__(self, category):
        self.exercise = FakeExercise(category)


def test_session_category_push():
    wes = [FakeWE('push'), FakeWE('push'), FakeWE('push'), FakeWE('pull')]
    assert session_category(wes) == 'push'


def test_session_category_tie():
    wes = [FakeWE('push'), FakeWE('push'), FakeWE('pull'), FakeWE('pull')]
    result = session_category(wes)
    assert result in ('push', 'pull')  # deterministic but either is valid


def test_session_category_empty():
    assert session_category([]) is None
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_repeat_logic.py -v
```

Expected: `ImportError: cannot import name 'session_category'`

- [ ] **Step 3: Create `workouts/repeat.py`**

```python
from collections import Counter

from .coach import recommend
from .models import WorkoutExercise

VALID_CATEGORIES = {'push', 'pull', 'legs', 'upper_arms', 'conditioning_abs'}


def session_category(workout_exercises) -> str | None:
    """
    Returns the most common exercise category across workout_exercises,
    or None if the list is empty.
    workout_exercises: iterable of objects with .exercise.category
    """
    cats = [we.exercise.category for we in workout_exercises]
    if not cats:
        return None
    return Counter(cats).most_common(1)[0][0]


def get_last_sessions_by_category() -> dict:
    """
    Returns {category_key: WorkoutSession} for each category that has at
    least one completed session. Only includes keys in VALID_CATEGORIES.
    """
    from .models import WorkoutSession
    completed = (WorkoutSession.objects
                 .filter(status='complete')
                 .order_by('-completed_at')
                 .prefetch_related('workout_exercises__exercise'))
    last_by_cat = {}
    for session in completed:
        wes = list(session.workout_exercises.all())
        cat = session_category(wes)
        if cat and cat in VALID_CATEGORIES and cat not in last_by_cat:
            last_by_cat[cat] = session
        if len(last_by_cat) == len(VALID_CATEGORIES):
            break
    return last_by_cat


def get_repeat_preview(category: str) -> dict | None:
    """
    Returns None if category is invalid or no completed session exists for it.
    Otherwise returns:
    {
      'session': WorkoutSession,
      'exercises': [
        {
          'exercise': Exercise,
          'rec': recommend() dict,
          'sets_count': int,
          'sets': [{'n': int, 'weight': float, 'reps': int}, ...]
        },
        ...
      ]
    }
    """
    if category not in VALID_CATEGORIES:
        return None
    last_by_cat = get_last_sessions_by_category()
    template_session = last_by_cat.get(category)
    if template_session is None:
        return None

    exercises_data = []
    wes = (template_session.workout_exercises
           .select_related('exercise')
           .prefetch_related('sets')
           .order_by('order'))
    for we in wes:
        last_we = (WorkoutExercise.objects
                   .filter(exercise=we.exercise, session__status='complete')
                   .order_by('-session__completed_at')
                   .first())
        last_sets = list(last_we.sets.all()) if last_we else []
        rec = recommend(we.exercise, last_sets)
        sets_count = rec['last_sets_count'] if rec['last_sets_count'] > 0 else we.exercise.default_sets
        exercises_data.append({
            'exercise': we.exercise,
            'rec': rec,
            'sets_count': sets_count,
            'sets': [
                {'n': i, 'weight': rec['target_weight'], 'reps': rec['target_reps_min']}
                for i in range(1, sets_count + 1)
            ],
        })

    return {'session': template_session, 'exercises': exercises_data}
```

- [ ] **Step 4: Run unit tests — expect pass**

```bash
pytest tests/test_repeat_logic.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```

Expected: 79 tests pass (76 existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git add workouts/repeat.py tests/test_repeat_logic.py
git commit -m "feat: repeat module — session_category, get_last_sessions_by_category, get_repeat_preview"
```

---

## Task 2: Views + URLs + View Tests

**Files:**
- Modify: `workouts/views.py`
- Modify: `core/urls.py`
- Create: `tests/test_repeat_views.py`

- [ ] **Step 1: Write failing view tests**

Create `tests/test_repeat_views.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_repeat_views.py -v
```

Expected: `NoReverseMatch` for `gym_repeat_preview`.

- [ ] **Step 3: Add URL patterns to `core/urls.py`**

Read `core/urls.py`. After the `gym_coach_tips` line, add:

```python
    path('log/repeat/<str:category>/', workout_views.repeat_preview, name='gym_repeat_preview'),
    path('log/repeat/<str:category>/start/', workout_views.repeat_start, name='gym_repeat_start'),
```

- [ ] **Step 4: Update `workouts/views.py`**

Add import at top (after existing `.coach` import):

```python
from .repeat import get_last_sessions_by_category, get_repeat_preview
```

Add `Http404` to Django imports line:

```python
from django.http import Http404, JsonResponse
```

Add a private helper after the existing `_get_recommendations` function:

```python
def _log_home_context():
    last_by_cat = get_last_sessions_by_category()
    repeat_options = [
        {
            'category': cat,
            'label': dict(Exercise.CATEGORY_CHOICES)[cat],
            'last_date': session.completed_at,
            'exercise_count': session.workout_exercises.count(),
        }
        for cat, session in last_by_cat.items()
    ]
    return {'repeat_options': repeat_options}
```

Replace the existing `log_home` view:

```python
def log_home(request):
    active = WorkoutSession.objects.filter(status='active').first()
    if active:
        return redirect('gym_active_session', session_id=active.id)
    return render(request, 'workouts/log_home.html', _log_home_context())
```

Replace the existing `start_session` view:

```python
@require_http_methods(['POST'])
def start_session(request):
    name = request.POST.get('name', '').strip()
    if not name:
        ctx = _log_home_context()
        ctx['error'] = 'Please enter a session name.'
        return render(request, 'workouts/log_home.html', ctx)
    session = WorkoutSession.objects.create(name=name)
    return redirect('gym_active_session', session_id=session.id)
```

Append two new views at the END of `workouts/views.py`:

```python
@require_http_methods(['GET'])
def repeat_preview(request, category):
    preview = get_repeat_preview(category)
    if preview is None:
        raise Http404
    today = timezone.localdate()
    label = dict(Exercise.CATEGORY_CHOICES).get(category, category.title())
    session_name = f"{today.strftime('%A')} {label}"
    return render(request, 'workouts/repeat_preview.html', {
        'category': category,
        'session_name': session_name,
        'exercises': preview['exercises'],
    })


@require_http_methods(['POST'])
def repeat_start(request, category):
    name = request.POST.get('name', '').strip()
    if not name:
        return redirect('gym_log_home')
    exercise_ids = request.POST.getlist('exercise_id')
    with transaction.atomic():
        session = WorkoutSession.objects.create(name=name)
        for order, ex_id in enumerate(exercise_ids, start=1):
            try:
                exercise = Exercise.objects.get(id=ex_id, is_active=True)
            except Exercise.DoesNotExist:
                continue
            we = WorkoutExercise.objects.create(
                session=session, exercise=exercise, order=order
            )
            n = 1
            while True:
                weight_key = f'weight_{ex_id}_{n}'
                reps_key = f'reps_{ex_id}_{n}'
                if weight_key not in request.POST:
                    break
                try:
                    weight = float(request.POST[weight_key])
                    reps = int(request.POST[reps_key])
                    if weight < 0 or reps < 1:
                        n += 1
                        continue
                except (ValueError, TypeError):
                    n += 1
                    continue
                WorkoutSet.objects.create(
                    workout_exercise=we,
                    set_number=n,
                    weight_kg=weight,
                    reps=reps,
                )
                n += 1
    return redirect('gym_active_session', session_id=session.id)
```

- [ ] **Step 5: Run view tests — expect pass**

```bash
pytest tests/test_repeat_views.py -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 86 tests pass (79 existing + 7 new).

- [ ] **Step 7: Commit**

```bash
git add workouts/views.py core/urls.py tests/test_repeat_views.py
git commit -m "feat: repeat_preview and repeat_start views"
```

---

## Task 3: CSS

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 1: Append to `static/css/app.css`**

Read the end of the file to confirm current end, then append:

```css
/* ── Quick Repeat ────────────────────────────────────────────────── */
.repeat-section {
  margin-top: 20px;
}

.repeat-divider {
  font-size: 9px;
  color: var(--text-sec);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  text-align: center;
  margin: 8px 0 10px;
}

.repeat-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 10px 14px;
  text-decoration: none;
  color: var(--text);
  margin-bottom: 8px;
}

.repeat-icon {
  font-size: 18px;
  color: var(--accent);
  flex-shrink: 0;
}

.repeat-label {
  font-size: 13px;
  font-weight: 700;
}

.repeat-meta {
  font-size: 11px;
  color: var(--text-sec);
  margin-top: 1px;
}

/* ── Repeat preview ──────────────────────────────────────────────── */
.preview-set-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.preview-set-label {
  font-size: 10px;
  color: var(--text-sec);
  width: 36px;
  flex-shrink: 0;
}

.preview-input {
  background: var(--card2);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text);
  width: 60px;
  text-align: center;
}

.preview-sep {
  font-size: 11px;
  color: var(--text-sec);
}
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 86 tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "feat: CSS for quick repeat buttons and preview screen"
```

---

## Task 4: Templates

**Files:**
- Modify: `templates/workouts/log_home.html`
- Create: `templates/workouts/repeat_preview.html`

- [ ] **Step 1: Update `templates/workouts/log_home.html`**

Read the file first. Add the Quick Repeat section at the end of `{% block content %}`, before `{% endblock %}`:

```html
  {% if repeat_options %}
  <div class="repeat-section">
    <div class="repeat-divider">↺ Quick Repeat</div>
    {% for opt in repeat_options %}
    <a href="{% url 'gym_repeat_preview' opt.category %}" class="repeat-btn">
      <span class="repeat-icon">↺</span>
      <div>
        <div class="repeat-label">{{ opt.label }}</div>
        <div class="repeat-meta">Last: {{ opt.last_date|date:"D j M" }} · {{ opt.exercise_count }} exercise{{ opt.exercise_count|pluralize }}</div>
      </div>
    </a>
    {% endfor %}
  </div>
  {% endif %}
```

- [ ] **Step 2: Create `templates/workouts/repeat_preview.html`**

```html
{% extends 'base.html' %}
{% load workout_extras %}
{% block title %}{{ session_name }} — Gym AI{% endblock %}

{% block content %}
<div class="page-header">
  <h1 class="page-title">{{ session_name }}</h1>
  <p class="page-sub">Adjust weights &amp; reps, then start</p>
</div>

<form method="post" action="{% url 'gym_repeat_start' category %}">
  {% csrf_token %}
  <input type="hidden" name="name" value="{{ session_name }}">

  {% for item in exercises %}
  <div class="we-card">
    <div class="we-name">
      {{ item.exercise.name }}
      {% if item.rec.action == 'increase' %}
      <span class="coach-badge increase">▲ Increase</span>
      {% elif item.rec.action == 'hold' %}
      <span class="coach-badge hold">→ Hold</span>
      {% elif item.rec.action == 'deload' %}
      <span class="coach-badge deload">▽ Back off</span>
      {% else %}
      <span class="coach-badge start">First time</span>
      {% endif %}
    </div>
    <div class="we-meta">{{ item.exercise.get_category_display }} · {{ item.exercise.get_equipment_display }}</div>
    <input type="hidden" name="exercise_id" value="{{ item.exercise.id }}">
    {% for s in item.sets %}
    <div class="preview-set-row">
      <span class="preview-set-label">Set {{ s.n }}</span>
      <input type="number" step="0.5" min="0" name="weight_{{ item.exercise.id }}_{{ s.n }}"
             value="{{ s.weight }}" class="preview-input">
      <span class="preview-sep">kg ×</span>
      <input type="number" min="1" name="reps_{{ item.exercise.id }}_{{ s.n }}"
             value="{{ s.reps }}" class="preview-input">
      <span class="preview-sep">reps</span>
    </div>
    {% endfor %}
  </div>
  {% endfor %}

  <button type="submit" class="btn btn-primary" style="margin-top:8px">▶ Start Session</button>
</form>
{% endblock %}
```

- [ ] **Step 3: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 86 tests pass.

- [ ] **Step 4: Commit**

```bash
git add templates/workouts/log_home.html templates/workouts/repeat_preview.html
git commit -m "feat: quick repeat buttons on log home and repeat preview template"
```

---

## Final Verification

- [ ] Start the dev server: `source venv/bin/activate && python manage.py runserver`
- [ ] Open `http://localhost:8000/gym-2026-private/log/`
- [ ] If you have completed sessions: "↺ Quick Repeat" section appears with category buttons
- [ ] Tap a button → preview screen shows exercises with AI-suggested weights pre-filled
- [ ] Adjust a weight, tap "▶ Start Session" → redirects to active session with sets logged
- [ ] Verify all 86 tests pass: `pytest tests/ -v`
