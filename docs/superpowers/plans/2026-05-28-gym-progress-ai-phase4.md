# Gym Progress AI — Phase 4 Coach Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a progressive overload coach that shows inline weight/rep recommendations on each exercise card and a dedicated Coach tab, with on-demand Ollama tips.

**Architecture:** A pure Python `workouts/coach.py` module (mirrors `nl_parser.py`) holds `recommend()` (rule-based progression) and `get_ollama_tips()` (Ollama call). Two new views (`coach_view`, `coach_tips`) serve the Coach tab and tips endpoint. A context processor makes the active session available in `base.html` so the Coach nav item links correctly.

**Tech Stack:** Django 4.2, Python `difflib`/`requests` (already installed), Ollama at `http://localhost:11434` with `qwen` model.

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `workouts/coach.py` | Create | `recommend()` + `get_ollama_tips()` + `CoachError` |
| `workouts/context_processors.py` | Create | Inject `active_session` into every template |
| `workouts/templatetags/__init__.py` | Create | Make templatetags a package |
| `workouts/templatetags/workout_extras.py` | Create | `get_item` filter for dict lookup in templates |
| `workouts/views.py` | Modify | Add `_get_recommendations()` helper + `coach_view` + `coach_tips`; update `active_session` |
| `core/urls.py` | Modify | Add `gym_coach` and `gym_coach_tips` URL patterns |
| `gym_progress_ai/settings.py` | Modify | Register context processor |
| `static/css/app.css` | Modify | Append coach UI styles |
| `templates/base.html` | Modify | Wire Coach nav item to `gym_coach` |
| `templates/workouts/active_session.html` | Modify | Add inline coach tip to each exercise card |
| `templates/workouts/coach.html` | Create | Coach tab template |
| `tests/test_coach.py` | Create | 6 unit tests for `recommend()` |
| `tests/test_coach_views.py` | Create | 5 HTTP tests for coach views |

---

## Task 1: Coach Module + Unit Tests

**Files:**
- Create: `workouts/coach.py`
- Create: `tests/test_coach.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_coach.py`:

```python
import pytest
from workouts.coach import recommend, get_ollama_tips, CoachError


class FakeExercise:
    def __init__(self):
        self.default_min_reps = 8
        self.default_max_reps = 12
        self.default_sets = 3
        self.default_increment = 2.5


class FakeSet:
    def __init__(self, weight_kg, reps):
        self.weight_kg = weight_kg
        self.reps = reps


EX = FakeExercise()


def test_recommend_no_history():
    rec = recommend(EX, [])
    assert rec['action'] == 'start'
    assert rec['last_weight'] is None
    assert rec['last_reps'] is None
    assert rec['last_sets_count'] == 0
    assert rec['target_weight'] == 0.0
    assert rec['target_reps_min'] == 8
    assert rec['target_reps_max'] == 12


def test_recommend_all_max_reps():
    sets = [FakeSet(60.0, 12), FakeSet(60.0, 12), FakeSet(60.0, 12)]
    rec = recommend(EX, sets)
    assert rec['action'] == 'increase'
    assert rec['target_weight'] == 62.5
    assert rec['last_weight'] == 60.0


def test_recommend_hold():
    sets = [FakeSet(60.0, 10), FakeSet(60.0, 10), FakeSet(60.0, 9)]
    rec = recommend(EX, sets)
    assert rec['action'] == 'hold'
    assert rec['target_weight'] == 60.0
    assert rec['last_reps'] == 9


def test_recommend_deload():
    sets = [FakeSet(60.0, 10), FakeSet(60.0, 7), FakeSet(60.0, 6)]
    rec = recommend(EX, sets)
    assert rec['action'] == 'deload'
    assert rec['target_weight'] == 57.5


def test_recommend_last_weight_is_max():
    sets = [FakeSet(60.0, 10), FakeSet(60.0, 10), FakeSet(62.5, 8)]
    rec = recommend(EX, sets)
    assert rec['last_weight'] == 62.5


def test_recommend_last_reps_is_min():
    sets = [FakeSet(60.0, 12), FakeSet(60.0, 10), FakeSet(60.0, 8)]
    rec = recommend(EX, sets)
    assert rec['last_reps'] == 8
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_coach.py -v
```

Expected: `ImportError` — `workouts/coach.py` doesn't exist yet.

- [ ] **Step 3: Create `workouts/coach.py`**

```python
import json
import re

import requests


class CoachError(Exception):
    pass


OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'qwen'
OLLAMA_TIMEOUT = 15


def recommend(exercise, last_sets) -> dict:
    """
    exercise: any object with default_min_reps, default_max_reps, default_increment
    last_sets: list/queryset of sets from the last session, each with .weight_kg and .reps
    Returns progression recommendation dict.
    """
    sets = list(last_sets)
    if not sets:
        return {
            'action': 'start',
            'last_weight': None,
            'last_reps': None,
            'last_sets_count': 0,
            'target_weight': 0.0,
            'target_reps_min': exercise.default_min_reps,
            'target_reps_max': exercise.default_max_reps,
        }

    last_weight = float(max(s.weight_kg for s in sets))
    last_reps = min(s.reps for s in sets)

    if all(s.reps >= exercise.default_max_reps for s in sets):
        action = 'increase'
        target_weight = last_weight + float(exercise.default_increment)
    elif any(s.reps < exercise.default_min_reps for s in sets):
        action = 'deload'
        target_weight = max(0.0, last_weight - float(exercise.default_increment))
    else:
        action = 'hold'
        target_weight = last_weight

    return {
        'action': action,
        'last_weight': last_weight,
        'last_reps': last_reps,
        'last_sets_count': len(sets),
        'target_weight': target_weight,
        'target_reps_min': exercise.default_min_reps,
        'target_reps_max': exercise.default_max_reps,
    }


def get_ollama_tips(exercises_with_recs: list) -> dict:
    """
    exercises_with_recs: list of dicts, each with:
      'name', 'action', 'last_weight', 'last_reps', 'last_sets_count',
      'target_weight', 'target_reps_min', 'target_reps_max'
    Returns: {"Exercise Name": "one-sentence tip", ...}
    Raises CoachError on any Ollama failure.
    """
    lines = []
    for ex in exercises_with_recs:
        if ex['action'] == 'start':
            history = 'no history yet'
        else:
            history = (f"last session: {ex['last_weight']} kg × {ex['last_reps']} reps"
                       f" ({ex['last_sets_count']} sets)")
        target = (f"target: {ex['target_weight']} kg × "
                  f"{ex['target_reps_min']}–{ex['target_reps_max']} reps"
                  f" ({ex['action']})")
        lines.append(f"- {ex['name']}: {history}, {target}")

    prompt = (
        'You are a strength training coach. Give one short motivating tip (one sentence) '
        'for each exercise below based on their history and today\'s target.\n\n'
        'Exercises:\n' + '\n'.join(lines) + '\n\n'
        'Return ONLY valid JSON: {"tips": {"Exercise Name": "one sentence tip", ...}}'
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={'model': OLLAMA_MODEL, 'prompt': prompt, 'stream': False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise CoachError('Ollama timed out')
    except requests.exceptions.RequestException as e:
        raise CoachError(f'Ollama request failed: {e}')

    raw = resp.json().get('response', '')
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        raise CoachError('Ollama returned no JSON')
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        raise CoachError('Ollama returned invalid JSON')
    if 'tips' not in data:
        raise CoachError('Ollama response missing tips key')
    return data['tips']
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_coach.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```

Expected: 71 tests pass (65 existing + 6 new).

- [ ] **Step 6: Commit**

```bash
git add workouts/coach.py tests/test_coach.py
git commit -m "feat: coach module — recommend() and get_ollama_tips()"
```

---

## Task 2: Context Processor + Templatetag + Settings

**Files:**
- Create: `workouts/context_processors.py`
- Create: `workouts/templatetags/__init__.py`
- Create: `workouts/templatetags/workout_extras.py`
- Modify: `gym_progress_ai/settings.py`

- [ ] **Step 1: Create `workouts/context_processors.py`**

```python
def active_session(request):
    from workouts.models import WorkoutSession
    session = WorkoutSession.objects.filter(status='active').first()
    return {'active_session': session}
```

- [ ] **Step 2: Create `workouts/templatetags/__init__.py`**

Create an empty file at `workouts/templatetags/__init__.py` (makes the directory a Python package):

```python
```

- [ ] **Step 3: Create `workouts/templatetags/workout_extras.py`**

```python
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
```

- [ ] **Step 4: Register context processor in `gym_progress_ai/settings.py`**

Find the `context_processors` list (currently at line ~45). It looks like:

```python
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
```

Add the new processor at the end:

```python
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'workouts.context_processors.active_session',
            ],
```

- [ ] **Step 5: Verify Django starts cleanly**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 71 tests pass (no regressions).

- [ ] **Step 7: Commit**

```bash
git add workouts/context_processors.py workouts/templatetags/__init__.py workouts/templatetags/workout_extras.py gym_progress_ai/settings.py
git commit -m "feat: active_session context processor and get_item templatetag"
```

---

## Task 3: Views + URL Patterns + View Tests

**Files:**
- Modify: `workouts/views.py`
- Modify: `core/urls.py`
- Create: `tests/test_coach_views.py`

- [ ] **Step 1: Write failing view tests**

Create `tests/test_coach_views.py`:

```python
import json
import pytest
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone

from workouts.models import Exercise, WorkoutSession, WorkoutExercise, WorkoutSet


def make_exercise():
    return Exercise.objects.create(
        name='Bench Press', muscle_group='Chest', category='push',
        equipment='barbell', movement_type='compound',
    )


def make_active_session():
    return WorkoutSession.objects.create(name='Test Session', status='active')


def add_exercise_to_session(session, exercise):
    return WorkoutExercise.objects.create(session=session, exercise=exercise, order=1)


@pytest.mark.django_db
def test_coach_view_returns_200(verified_client):
    session = make_active_session()
    response = verified_client.get(reverse('gym_coach', args=[session.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_coach_view_404_on_complete_session(verified_client):
    session = WorkoutSession.objects.create(
        name='Done', status='complete', completed_at=timezone.now()
    )
    response = verified_client.get(reverse('gym_coach', args=[session.id]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_coach_view_contains_exercise_name(verified_client):
    exercise = make_exercise()
    session = make_active_session()
    add_exercise_to_session(session, exercise)
    response = verified_client.get(reverse('gym_coach', args=[session.id]))
    assert b'Bench Press' in response.content


@pytest.mark.django_db
@patch('workouts.views.get_ollama_tips')
def test_coach_tips_returns_json(mock_tips, verified_client):
    exercise = make_exercise()
    session = make_active_session()
    add_exercise_to_session(session, exercise)
    mock_tips.return_value = {'Bench Press': 'Great lift today!'}
    response = verified_client.post(reverse('gym_coach_tips', args=[session.id]))
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'tips' in data


@pytest.mark.django_db
@patch('workouts.views.get_ollama_tips')
def test_coach_tips_422_on_ollama_failure(mock_tips, verified_client):
    from workouts.coach import CoachError
    session = make_active_session()
    mock_tips.side_effect = CoachError('Ollama timed out')
    response = verified_client.post(reverse('gym_coach_tips', args=[session.id]))
    assert response.status_code == 422
    assert b'error' in response.content
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_coach_views.py -v
```

Expected: `NoReverseMatch` — URLs not defined yet.

- [ ] **Step 3: Update `workouts/views.py`**

Add two imports at the top of `workouts/views.py` (after the existing `.nl_parser` import line):

```python
from .coach import CoachError, get_ollama_tips, recommend
```

Add a private helper function after the imports and before the first view function (`def exercises`):

```python
def _get_recommendations(session):
    recommendations = {}
    for we in session.workout_exercises.select_related('exercise').prefetch_related('sets'):
        last_we = (WorkoutExercise.objects
                   .filter(exercise=we.exercise, session__status='complete')
                   .exclude(session=session)
                   .order_by('-session__completed_at')
                   .first())
        last_sets = list(last_we.sets.all()) if last_we else []
        recommendations[we.exercise.id] = recommend(we.exercise, last_sets)
    return recommendations
```

Update the existing `active_session` view to pass recommendations:

```python
def active_session(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    if session.status == 'complete':
        return redirect('gym_session_detail', session_id=session.id)
    workout_exercises = session.workout_exercises.select_related('exercise').prefetch_related('sets')
    all_exercises = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    recommendations = _get_recommendations(session)
    return render(request, 'workouts/active_session.html', {
        'session': session,
        'workout_exercises': workout_exercises,
        'all_exercises': all_exercises,
        'recommendations': recommendations,
    })
```

Append two new views at the end of `workouts/views.py`:

```python
def coach_view(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    workout_exercises = session.workout_exercises.select_related('exercise').prefetch_related('sets')
    recommendations = _get_recommendations(session)
    return render(request, 'workouts/coach.html', {
        'session': session,
        'workout_exercises': workout_exercises,
        'recommendations': recommendations,
    })


@require_http_methods(['POST'])
def coach_tips(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    recommendations = _get_recommendations(session)
    exercises_with_recs = []
    for we in session.workout_exercises.select_related('exercise'):
        rec = recommendations.get(we.exercise.id, {})
        exercises_with_recs.append({'name': we.exercise.name, **rec})
    try:
        tips = get_ollama_tips(exercises_with_recs)
        return JsonResponse({'tips': tips})
    except CoachError as e:
        return JsonResponse(
            {'error': str(e) or 'Could not get tips — try again'},
            status=422,
        )
```

- [ ] **Step 4: Add URL patterns to `core/urls.py`**

Read `core/urls.py` first. After the `gym_nl_confirm` line add:

```python
    path('log/<int:session_id>/coach/', workout_views.coach_view, name='gym_coach'),
    path('log/<int:session_id>/coach-tips/', workout_views.coach_tips, name='gym_coach_tips'),
```

The history section should remain after these, unchanged.

- [ ] **Step 5: Run view tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_coach_views.py -v
```

Expected: 5 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 76 tests pass (71 existing + 5 new).

- [ ] **Step 7: Commit**

```bash
git add workouts/views.py core/urls.py tests/test_coach_views.py
git commit -m "feat: coach_view and coach_tips views"
```

---

## Task 4: CSS

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 1: Append to `static/css/app.css`**

Read the end of the file first to confirm current end, then append:

```css
/* ── Coach recommendations ───────────────────────────────────────── */
.coach-inline {
  font-size: 11px;
  color: var(--text-sec);
  margin: 5px 0 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  line-height: 1.5;
}

.coach-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  border-radius: 4px;
  padding: 2px 6px;
  flex-shrink: 0;
}

.coach-badge.increase { background: #14532D; color: #22C55E; }
.coach-badge.hold     { background: #1F2937; color: #9CA3AF; }
.coach-badge.deload   { background: #450A0A; color: #F87171; }
.coach-badge.start    { background: #0C1A2E; color: #38BDF8; }

.coach-tip-text {
  font-size: 11px;
  color: var(--accent);
  font-style: italic;
  margin-top: 4px;
  width: 100%;
}

/* ── Coach tab ───────────────────────────────────────────────────── */
.coach-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 14px 16px;
  margin-bottom: 12px;
}

.coach-card .we-name { font-size: 15px; font-weight: 700; margin-bottom: 2px; }
.coach-card .we-meta { font-size: 11px; color: var(--text-sec); margin-bottom: 6px; }

.coach-tips-btn {
  display: block;
  width: 100%;
  background: var(--card2);
  border: 1px solid var(--accent);
  border-radius: var(--radius-btn);
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
  padding: 10px;
  text-align: center;
  cursor: pointer;
  margin-bottom: 16px;
}

.coach-tips-error {
  font-size: 11px;
  color: #EF4444;
  margin-bottom: 12px;
}
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 76 tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "feat: CSS for coach inline tips and coach tab"
```

---

## Task 5: Templates

**Files:**
- Modify: `templates/base.html`
- Modify: `templates/workouts/active_session.html`
- Create: `templates/workouts/coach.html`

- [ ] **Step 1: Update Coach nav item in `templates/base.html`**

Find the current Progress/Coach nav item (currently `<a href="#" class="nav-item">`). Replace it with:

```html
    {% if active_session %}
    <a href="{% url 'gym_coach' active_session.id %}"
       class="nav-item {% if request.resolver_match.url_name == 'gym_coach' %}active{% endif %}">
      <span class="nav-icon">↗</span>
      <span>Coach</span>
    </a>
    {% else %}
    <a href="#" class="nav-item">
      <span class="nav-icon">↗</span>
      <span>Coach</span>
    </a>
    {% endif %}
```

- [ ] **Step 2: Add inline coach tip to `templates/workouts/active_session.html`**

At the top of the file, after `{% extends 'base.html' %}`, add:

```html
{% load workout_extras %}
```

Inside each `<div class="we-card">`, after the `<div class="we-meta">` line and before `{% with sets=we.sets.all %}`, add:

```html
  {% with rec=recommendations|get_item:we.exercise.id %}
  {% if rec %}
  <div class="coach-inline">
    {% if rec.action == 'start' %}
    <span class="coach-badge start">First time</span>
    Aim for {{ rec.target_reps_min }}–{{ rec.target_reps_max }} reps
    {% elif rec.action == 'increase' %}
    <span class="coach-badge increase">▲ Increase</span>
    Last: {{ rec.last_weight }} kg × {{ rec.last_reps }}
    &nbsp;·&nbsp; Try <strong>{{ rec.target_weight }} kg × {{ rec.target_reps_min }}–{{ rec.target_reps_max }}</strong>
    {% elif rec.action == 'hold' %}
    <span class="coach-badge hold">→ Hold</span>
    Last: {{ rec.last_weight }} kg × {{ rec.last_reps }}
    &nbsp;·&nbsp; Aim for <strong>{{ rec.target_weight }} kg × {{ rec.target_reps_max }} reps</strong>
    {% else %}
    <span class="coach-badge deload">▽ Back off</span>
    Last: {{ rec.last_weight }} kg × {{ rec.last_reps }}
    &nbsp;·&nbsp; Try <strong>{{ rec.target_weight }} kg</strong>
    {% endif %}
    <div class="coach-tip-text" id="coach-tip-{{ we.exercise.id }}" style="display:none"></div>
  </div>
  {% endif %}
  {% endwith %}
```

- [ ] **Step 3: Create `templates/workouts/coach.html`**

```html
{% extends 'base.html' %}
{% load workout_extras %}
{% block title %}Coach — {{ session.name }} — Gym AI{% endblock %}

{% block content %}
<div class="session-title">Coach — {{ session.name }}</div>

<button type="button" class="coach-tips-btn" id="coach-tips-btn">✦ Get Ollama tips</button>
<div id="coach-tips-error" class="coach-tips-error" style="display:none"></div>

{% for we in workout_exercises %}
{% with rec=recommendations|get_item:we.exercise.id %}
<div class="coach-card">
  <div class="we-name">{{ we.exercise.name }}</div>
  <div class="we-meta">{{ we.exercise.get_category_display }} · {{ we.exercise.get_equipment_display }}</div>

  {% if rec %}
  <div class="coach-inline">
    {% if rec.action == 'start' %}
    <span class="coach-badge start">First time</span>
    Aim for {{ rec.target_reps_min }}–{{ rec.target_reps_max }} reps
    {% elif rec.action == 'increase' %}
    <span class="coach-badge increase">▲ Increase</span>
    Last: {{ rec.last_weight }} kg × {{ rec.last_reps }}
    &nbsp;·&nbsp; Try <strong>{{ rec.target_weight }} kg × {{ rec.target_reps_min }}–{{ rec.target_reps_max }}</strong>
    {% elif rec.action == 'hold' %}
    <span class="coach-badge hold">→ Hold</span>
    Last: {{ rec.last_weight }} kg × {{ rec.last_reps }}
    &nbsp;·&nbsp; Aim for <strong>{{ rec.target_weight }} kg × {{ rec.target_reps_max }} reps</strong>
    {% else %}
    <span class="coach-badge deload">▽ Back off</span>
    Last: {{ rec.last_weight }} kg × {{ rec.last_reps }}
    &nbsp;·&nbsp; Try <strong>{{ rec.target_weight }} kg</strong>
    {% endif %}
    <div class="coach-tip-text" id="coach-tip-{{ we.exercise.id }}" style="display:none"></div>
  </div>
  {% endif %}
</div>
{% endwith %}
{% empty %}
<p class="empty-state">No exercises in this session yet. Add some from the Log tab.</p>
{% endfor %}
{% endblock %}

{% block scripts %}
<script>
const COACH_TIPS_URL = '{% url "gym_coach_tips" session.id %}';
const CSRF_TOKEN = '{{ csrf_token }}';

document.getElementById('coach-tips-btn').addEventListener('click', function () {
  const btn = this;
  btn.textContent = '…';
  btn.disabled = true;
  document.getElementById('coach-tips-error').style.display = 'none';

  const body = new FormData();
  body.append('csrfmiddlewaretoken', CSRF_TOKEN);

  fetch(COACH_TIPS_URL, { method: 'POST', body: body })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      btn.textContent = '✦ Get Ollama tips';
      btn.disabled = false;
      if (!res.ok) {
        const el = document.getElementById('coach-tips-error');
        el.textContent = res.data.error || 'Could not get tips — try again';
        el.style.display = 'block';
        return;
      }
      const tips = res.data.tips || {};
      Object.keys(tips).forEach(function (name) {
        document.querySelectorAll('.coach-card').forEach(function (card) {
          if (card.querySelector('.we-name') &&
              card.querySelector('.we-name').textContent.trim() === name) {
            const tipEl = card.querySelector('.coach-tip-text');
            if (tipEl) {
              tipEl.textContent = tips[name];
              tipEl.style.display = 'block';
            }
          }
        });
      });
    })
    .catch(function () {
      btn.textContent = '✦ Get Ollama tips';
      btn.disabled = false;
      const el = document.getElementById('coach-tips-error');
      el.textContent = 'Request failed — check your connection';
      el.style.display = 'block';
    });
});
</script>
{% endblock %}
```

- [ ] **Step 4: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 76 tests pass.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html templates/workouts/active_session.html templates/workouts/coach.html
git commit -m "feat: coach nav, inline tips on active session, coach tab template"
```

---

## Final Verification

- [ ] Start the server: `source venv/bin/activate && python manage.py runserver`
- [ ] Open `http://localhost:8000/gym-2026-private/`, enter PIN `1234`
- [ ] Start a new session, add Bench Press, add one set (60kg × 10 reps), finish
- [ ] Start a second session, add Bench Press → inline tip should show "Last: 60.0 kg × 10 · Aim for 60.0 kg × 12 reps" (hold, since 10 is between 8–12)
- [ ] Do 3 sets of Bench Press at 12 reps, finish session
- [ ] Start a third session, add Bench Press → inline tip should show "▲ Increase · Try 62.5 kg × 8–12"
- [ ] Tap Coach (↗) in bottom nav → Coach tab shows the same recommendation
- [ ] Tap "Get tips" → tips appear under each exercise (if Ollama/Qwen running) or error shown (if not)
- [ ] Confirm all 76 tests pass: `pytest tests/ -v`
