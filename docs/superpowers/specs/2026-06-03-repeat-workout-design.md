# Repeat Last Workout — Design Spec

**Date:** 2026-06-03
**Phase:** 5 of 6 — Quick Repeat Workout
**Status:** Approved

---

## Overview

Adds a "↺ Quick Repeat" section to the Start Workout screen. For each workout category (Push, Pull, Legs, etc.) that has at least one completed session, a repeat button is shown with the last session date and exercise count. Tapping one opens a preview screen with all exercises from that session pre-filled with AI progressive overload suggestions (from `recommend()`). The user edits weights/reps as needed, taps "Start Session", and lands directly on the active session screen with sets already logged.

No new models needed — uses existing `WorkoutSession`, `WorkoutExercise`, `WorkoutSet`, and `Exercise`.

---

## 1. Category Detection

A session's category is determined by the majority exercise category across its `WorkoutExercise` rows.

```python
def session_category(session):
    """
    Returns the most common exercise category in the session,
    or None if the session has no exercises.
    """
    from collections import Counter
    cats = [we.exercise.category for we in session.workout_exercises.select_related('exercise')]
    if not cats:
        return None
    return Counter(cats).most_common(1)[0][0]
```

Tie-breaking: `Counter.most_common` is stable for equal counts — first insertion order wins (consistent with exercise order in the session).

### `get_last_sessions_by_category()`

```python
def get_last_sessions_by_category():
    """
    Returns a dict: {category_key: session} for each category that has
    at least one completed session. Only includes valid CATEGORY_CHOICES keys.
    """
```

Implementation: fetch all completed sessions ordered by `completed_at` descending, iterate once, record the first (most recent) session per category key. Valid category keys: `push`, `pull`, `legs`, `upper_arms`, `conditioning_abs`.

---

## 2. Data Flow

```
log_home (GET)
  → get_last_sessions_by_category()
  → pass repeat_options = [
      {'category': 'push', 'label': 'Push', 'last_date': ..., 'exercise_count': 3},
      ...
    ]
  → render log_home.html with repeat_options

repeat_preview (GET, /log/repeat/<category>/)
  → get_last_sessions_by_category()[category]  → 404 if none
  → for each WorkoutExercise in that session:
      rec = recommend(exercise, last_sets_from_previous_session)
      sets_count = rec['last_sets_count'] or exercise.default_sets
  → session_name = f"{today.strftime('%A')} {Exercise.CATEGORY_CHOICES label}"
  → render repeat_preview.html with exercises, recommendations, session_name

repeat_start (POST, /log/repeat/<category>/start/)
  → parse form: name, per-exercise/set weight + reps
  → transaction.atomic():
      session = WorkoutSession.objects.create(name=name)
      for each exercise_id in order:
          we = WorkoutExercise.objects.create(session, exercise, order)
          for each set row:
              WorkoutSet.objects.create(we, set_number, weight_kg, reps)
  → redirect to gym_active_session
```

---

## 3. Helper Module — `workouts/repeat.py`

New file. Pure Python, no HTTP. Contains:

```python
from collections import Counter
from .coach import recommend
from .models import WorkoutExercise

VALID_CATEGORIES = {'push', 'pull', 'legs', 'upper_arms', 'conditioning_abs'}

def session_category(session) -> str | None:
    """Most common exercise category in session, or None if empty."""

def get_last_sessions_by_category() -> dict:
    """
    Returns {category_key: WorkoutSession} for each category with at
    least one completed session. Only valid VALID_CATEGORIES keys.
    """

def get_repeat_preview(category: str) -> dict | None:
    """
    Returns None if no completed session exists for category.
    Otherwise returns:
    {
      'session': WorkoutSession,
      'exercises': [
        {
          'exercise': Exercise,
          'rec': recommend() dict,
          'sets_count': int,
        },
        ...
      ]
    }
    """
```

`get_repeat_preview` calls `recommend()` for each exercise, using sets from the last completed session for that exercise (same lookup as `_get_recommendations` in views.py — find last completed `WorkoutExercise` for this exercise excluding the template session).

---

## 4. Views — `workouts/views.py`

### Updated `log_home`

```python
from .repeat import get_last_sessions_by_category

def log_home(request):
    active = WorkoutSession.objects.filter(status='active').first()
    if active:
        return redirect('gym_active_session', session_id=active.id)
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
    return render(request, 'workouts/log_home.html', {
        'repeat_options': repeat_options,
        'error': None,
    })
```

### New `repeat_preview(request, category)` — GET

```python
@require_http_methods(['GET'])
def repeat_preview(request, category):
    from .repeat import get_repeat_preview
    from django.utils import timezone
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
```

### New `repeat_start(request, category)` — POST

```python
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
            set_keys = [k for k in request.POST if k.startswith(f'weight_{ex_id}_')]
            for i, _ in enumerate(set_keys, start=1):
                try:
                    weight = float(request.POST.get(f'weight_{ex_id}_{i}', 0))
                    reps = int(request.POST.get(f'reps_{ex_id}_{i}', 0))
                    if weight < 0 or reps < 1:
                        continue
                except (ValueError, TypeError):
                    continue
                WorkoutSet.objects.create(
                    workout_exercise=we,
                    set_number=i,
                    weight_kg=weight,
                    reps=reps,
                )
    return redirect('gym_active_session', session_id=session.id)
```

---

## 5. Routes

Added to `core/urls.py` under `/<secret>/`:

| URL | Name | View | Method |
|---|---|---|---|
| `log/repeat/<str:category>/` | `gym_repeat_preview` | `repeat_preview` | GET |
| `log/repeat/<str:category>/start/` | `gym_repeat_start` | `repeat_start` | POST |

---

## 6. Templates

### `templates/workouts/log_home.html`

Add below the existing Start Workout form, only if `repeat_options` is non-empty:

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

### `templates/workouts/repeat_preview.html` — new

Extends `base.html`. Shows:
- Session name heading (`session_name`)
- "Adjust weights & reps, then start" subtitle
- `<form method="post" action="{% url 'gym_repeat_start' category %}">` with CSRF
- Hidden `<input name="name" value="{{ session_name }}">` 
- One `.we-card` per exercise containing:
  - Exercise name + coach badge (action)
  - Hidden `<input name="exercise_id" value="{{ item.exercise.id }}">`
  - N set rows (N = `item.sets_count`), each with:
    - `<input name="weight_<ex_id>_<n>" value="{{ item.rec.target_weight }}">`
    - `<input name="reps_<ex_id>_<n>" value="{{ item.rec.target_reps_min }}">`
- "▶ Start Session" submit button

---

## 7. CSS additions — `static/css/app.css`

```
.repeat-section    — margin-top 16px
.repeat-divider    — small uppercase label, grey, centered, margin 8px 0
.repeat-btn        — flex row, background var(--card), border var(--border),
                     border-radius var(--radius-card), padding 10px 14px,
                     text-decoration none, color var(--text), margin-bottom 8px
.repeat-icon       — font-size 16px, color var(--accent)
.repeat-label      — font-size 13px, font-weight 700
.repeat-meta       — font-size 11px, color var(--text-sec)
.preview-set-row   — flex row, gap 6px, align-items center, margin-bottom 6px
.preview-input     — background var(--card2), border 1px solid var(--border),
                     border-radius 4px, padding 4px 8px, font-size 12px,
                     color var(--text), width 60px, text-align center
```

---

## 8. Tests

### `tests/test_repeat_logic.py` — unit tests, no DB

```python
class FakeExercise:
    def __init__(self, category):
        self.category = category

class FakeWE:
    def __init__(self, category):
        self.exercise = FakeExercise(category)
```

- `test_session_category_push` — 3 push + 1 pull WEs → `'push'`
- `test_session_category_tie` — 2 push + 2 pull → deterministic result
- `test_session_category_empty` — no WEs → `None`

### `tests/test_repeat_views.py` — HTTP tests

- `test_repeat_preview_returns_200` — completed push session exists → 200
- `test_repeat_preview_404_no_history` — no completed push sessions → 404
- `test_repeat_preview_contains_exercise_name` — exercise name in response HTML
- `test_repeat_start_creates_session` — POST valid data → WorkoutSession created, redirect to active session
- `test_repeat_start_creates_sets` — POST 3 sets per exercise → correct WorkoutSet records in DB
- `test_log_home_shows_repeat_buttons` — completed sessions exist → repeat buttons in HTML
- `test_log_home_no_repeat_buttons_empty` — no history → no repeat section in HTML

**Expected total: 86 tests (76 existing + 3 unit + 7 view)**

---

## 9. What This Does NOT Include

- Editing the exercise list on the preview screen (adding/removing exercises — Phase 6)
- Repeat for sessions that don't have a clear majority category (empty sessions, or sessions where no single category has more exercises than others — these simply don't generate a button)

Note: all 5 categories (`push`, `pull`, `legs`, `upper_arms`, `conditioning_abs`) are supported equally — buttons appear for whichever ones have completed session history.

---

## 10. Acceptance Criteria

1. Log screen shows "↺ Quick Repeat" section only when at least one category has completed sessions
2. Each button shows correct category label, last date, and exercise count
3. Preview screen shows correct session name (`{Today} {Category}`)
4. Each exercise card shows the coach badge and pre-filled target weight/reps from `recommend()`
5. Sets count matches last session's set count (or `default_sets` if no history)
6. "Start Session" creates WorkoutSession + WorkoutExercise + WorkoutSet records
7. Redirects to active session with sets already logged
8. All 86 tests pass
