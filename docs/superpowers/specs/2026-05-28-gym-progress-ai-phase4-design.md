# Gym Progress AI — Phase 4 Coach Recommendations Design

**Date:** 2026-05-28
**Phase:** 4 of 6 — Progressive Overload Coach
**Status:** Approved

---

## Overview

Phase 4 adds a progressive overload coach to the active session screen. For each exercise in the current session, the app looks up the last time that exercise was performed, applies a rule-based progression algorithm, and shows an inline recommendation ("Last: 60 kg × 10 · Target: 62.5 kg × 8–12"). A dedicated Coach tab shows the full plan for the session. An on-demand "Get tips" button calls Ollama/Qwen to add a one-sentence coaching tip per exercise.

No new models needed — the existing Exercise, WorkoutExercise, WorkoutSet, and WorkoutSession models provide all required data.

---

## 1. Data Flow

```
active_session view
  → for each WorkoutExercise in session:
      last_we = last completed session containing this exercise (excluding current)
      last_sets = last_we.sets.all() if last_we else []
      rec = recommend(exercise, last_sets)
      recommendations[exercise.id] = rec
  → render active_session.html with recommendations dict

coach_view(request, session_id)
  → same recommendation lookup
  → render coach.html with session, workout_exercises, recommendations

coach_tips(request, session_id)  [POST, JSON]
  → build exercises_with_recs list from session exercises + recommendations
  → call get_ollama_tips(exercises_with_recs)
  → return JsonResponse({"tips": {"Bench Press": "tip...", ...}})
  → on CoachError: JsonResponse({"error": "..."}, status=422)
```

---

## 2. Progression Rule

Implemented in `recommend(exercise, last_sets)`:

| Condition | Action | Target weight | Target reps |
|---|---|---|---|
| `last_sets` is empty | `start` | `exercise.default_sets` × `exercise.default_min_reps` kg (see note) | `default_min_reps – default_max_reps` |
| All sets hit `≥ default_max_reps` | `increase` | `last_weight + default_increment` | `default_min_reps – default_max_reps` |
| Any set below `default_min_reps` | `deload` | `last_weight − default_increment` | `default_min_reps – default_max_reps` |
| Otherwise | `hold` | `last_weight` | aim for `default_max_reps` |

**Note on `start` case:** When no history exists, `target_weight` is 0.0 (no suggestion — user picks their starting weight). Target reps are from `exercise.default_min_reps – exercise.default_max_reps`.

- `last_weight` = max weight across all sets of the last session (the working weight)
- `last_reps` = min reps across all sets of the last session (most conservative signal)
- `last_sets_count` = number of sets in the last session

---

## 3. Coach Module — `workouts/coach.py`

```python
class CoachError(Exception):
    pass

def recommend(exercise, last_sets) -> dict:
    """
    Returns:
      {
        "action": "start" | "increase" | "hold" | "deload",
        "last_weight": float | None,
        "last_reps": int | None,
        "last_sets_count": int,
        "target_weight": float,
        "target_reps_min": int,
        "target_reps_max": int,
      }
    """

def get_ollama_tips(exercises_with_recs: list[dict]) -> dict:
    """
    exercises_with_recs: list of dicts with keys:
      "name", "action", "last_weight", "last_reps", "target_weight",
      "target_reps_min", "target_reps_max"
    Returns: {"Exercise Name": "one-sentence tip", ...}
    Raises: CoachError on Ollama failure.
    """
```

`get_ollama_tips` sends one POST to `http://localhost:11434/api/generate`:
- Model: `qwen`, `stream: false`, timeout: 15s (longer than NL parser — more exercises)
- Prompt lists all exercises with their last performance and target, asks for one sentence each
- Returns JSON `{"tips": {"Bench Press": "...", "Squat": "..."}}`
- On timeout → `CoachError('Ollama timed out')`
- On invalid JSON / missing keys → `CoachError('Ollama returned invalid response')`

---

## 4. Routes

Added to `core/urls.py` under `/<secret>/`:

| URL | Name | View | Method |
|---|---|---|---|
| `log/<int:session_id>/coach/` | `gym_coach` | `coach_view` | GET |
| `log/<int:session_id>/coach-tips/` | `gym_coach_tips` | `coach_tips` | POST |

---

## 5. Views — `workouts/views.py`

### Updated `active_session`

Import `recommend` from `.coach` at top of file. After fetching `workout_exercises`, build a `recommendations` dict keyed by `exercise.id`:

```python
from .coach import CoachError, recommend, get_ollama_tips

def active_session(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    workout_exercises = session.workout_exercises.select_related('exercise').prefetch_related('sets')
    all_exercises = Exercise.objects.filter(is_active=True).order_by('category', 'name')

    recommendations = {}
    for we in workout_exercises:
        last_we = (WorkoutExercise.objects
                   .filter(exercise=we.exercise, session__status='complete')
                   .exclude(session=session)
                   .order_by('-session__completed_at')
                   .select_related('session')
                   .first())
        last_sets = list(last_we.sets.all()) if last_we else []
        recommendations[we.exercise.id] = recommend(we.exercise, last_sets)

    return render(request, 'workouts/active_session.html', {
        'session': session,
        'workout_exercises': workout_exercises,
        'all_exercises': all_exercises,
        'recommendations': recommendations,
    })
```

### New `coach_view(request, session_id)` — GET

- `get_object_or_404(WorkoutSession, id=session_id, status='active')`
- Same recommendation lookup as `active_session`
- Renders `workouts/coach.html` with `session`, `workout_exercises`, `recommendations`

### New `coach_tips(request, session_id)` — POST, returns JSON

- `@require_http_methods(['POST'])`
- `get_object_or_404(WorkoutSession, id=session_id, status='active')`
- Builds `exercises_with_recs` by combining `workout_exercises` with their recommendations
- Calls `get_ollama_tips(exercises_with_recs)`
- Returns `JsonResponse({"tips": {...}})` on success
- Returns `JsonResponse({"error": "..."}, status=422)` on `CoachError`

---

## 6. Context Processor — `workouts/context_processors.py`

New file. Adds `active_session` to every template context so `base.html` can link the Coach nav item dynamically:

```python
def active_session(request):
    from workouts.models import WorkoutSession
    session = WorkoutSession.objects.filter(status='active').first()
    return {'active_session': session}
```

Register in `settings.py` under `TEMPLATES[0]['OPTIONS']['context_processors']` by adding `'workouts.context_processors.active_session'` to the list.

---

## 7. Template Changes

### `base.html` — Coach nav item

Replace the `<a href="#">` Progress/Coach slot:

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

### `active_session.html` — inline coach tip

Add a `get_item` template filter call (see Section 8) inside each exercise card, between `.we-meta` and the set table:

```html
{% with rec=recommendations|get_item:we.exercise.id %}
{% if rec %}
<div class="coach-inline">
  {% if rec.action == 'start' %}
  <span class="coach-badge start">First time</span>
  Aim for {{ rec.target_reps_min }}–{{ rec.target_reps_max }} reps
  {% elif rec.action == 'increase' %}
  <span class="coach-badge increase">▲</span>
  Last: {{ rec.last_weight }} kg × {{ rec.last_reps }} &nbsp;·&nbsp;
  Try <strong>{{ rec.target_weight }} kg × {{ rec.target_reps_min }}–{{ rec.target_reps_max }}</strong>
  {% elif rec.action == 'hold' %}
  <span class="coach-badge hold">→</span>
  Last: {{ rec.last_weight }} kg × {{ rec.last_reps }} &nbsp;·&nbsp;
  Aim for <strong>{{ rec.target_weight }} kg × {{ rec.target_reps_max }} reps</strong>
  {% else %}
  <span class="coach-badge deload">▽</span>
  Last: {{ rec.last_weight }} kg × {{ rec.last_reps }} &nbsp;·&nbsp;
  Back off to <strong>{{ rec.target_weight }} kg</strong>
  {% endif %}
  <div class="coach-tip-text" id="coach-tip-{{ we.exercise.id }}" style="display:none"></div>
</div>
{% endif %}
{% endwith %}
```

### `templates/workouts/coach.html` — new template

Extends `base.html`. Shows:
- Session name heading
- "✦ Get tips" button (`id="coach-tips-btn"`)
- Error div (`id="coach-tips-error"`, hidden)
- One `.coach-card` per `WorkoutExercise` with:
  - Exercise name, category/equipment meta
  - Recommendation row (same badge + last/target text as inline)
  - `.coach-tip-text` div (hidden, populated by JS)
- JS in `{% block scripts %}`:
  - `coach-tips-btn` click → fetch POST to `gym_coach_tips` with CSRF
  - On success: for each tip, populate and show the matching `.coach-tip-text` div
  - On error: show `coach-tips-error` with the error message
  - Spinner on button during fetch

---

## 8. Template Tag — `workouts/templatetags/workout_extras.py`

New file (create `workouts/templatetags/__init__.py` too):

```python
from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
```

Load in templates with `{% load workout_extras %}`.

---

## 9. CSS additions — `static/css/app.css`

```
.coach-inline    — small row inside exercise card, margin: 6px 0, flex, align-items: center, gap: 6px
.coach-badge     — pill badge, font-size: 9px, border-radius, font-weight: 700
.coach-badge.increase  — green background / text
.coach-badge.hold      — grey background / text
.coach-badge.deload    — red background / text
.coach-badge.start     — blue/accent background / text
.coach-tip-text  — italic, font-size: 11px, color: accent, margin-top: 4px
.coach-card      — same as .we-card, used on coach.html
.coach-tips-btn  — secondary button style, full-width on coach.html
```

---

## 10. Tests

### `tests/test_coach.py` — unit tests, no DB, no Ollama

Uses `FakeExercise` (same pattern as `test_nl_parser.py`):

```python
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
```

Tests:
- `test_recommend_no_history` — empty list → `action='start'`, `target_weight=0.0`
- `test_recommend_all_max_reps` — 3 sets at 12 reps → `action='increase'`, weight += 2.5
- `test_recommend_hold` — 3 sets at 10 reps (between 8–12) → `action='hold'`, same weight
- `test_recommend_deload` — one set at 6 reps (below min) → `action='deload'`, weight -= 2.5
- `test_recommend_last_weight_is_max` — sets at 60/60/62.5 kg → `last_weight=62.5`
- `test_recommend_last_reps_is_min` — sets at 12/10/8 reps → `last_reps=8`

### `tests/test_coach_views.py` — HTTP tests, Ollama mocked

- `test_coach_view_returns_200` — GET active session → 200
- `test_coach_view_404_on_complete_session` — complete session → 404
- `test_coach_view_contains_exercise_name` — response HTML contains exercise name
- `test_coach_tips_returns_json` — POST (mocked Ollama) → 200 + `{"tips": {...}}`
- `test_coach_tips_422_on_ollama_failure` — CoachError raised → 422 + `{"error": "..."}`

**Expected total:** 76 tests (65 existing + 6 unit + 5 view)

---

## 11. What Phase 4 Does NOT Include

- Progress charts or graphs (Phase 5)
- Multi-session trend analysis ("you've been plateauing for 3 weeks")
- Deload week detection
- RPE-based recommendations
- Any recommendation for exercises not yet added to the current session

---

## 12. Acceptance Criteria

1. Each exercise card on the active session screen shows a coach inline tip (▲/→/▽/First time)
2. `action='increase'` when all sets hit `default_max_reps`
3. `action='hold'` when reps between min and max
4. `action='deload'` when any set below `default_min_reps`
5. `action='start'` when no history for that exercise
6. Coach nav item in bottom nav links to the Coach tab when a session is active; stays `#` when no session
7. Coach tab shows all exercises in the current session with recommendations
8. "Get tips" button on Coach tab triggers Ollama; tips appear under each exercise
9. Ollama timeout/failure shows an inline error message, does not crash
10. All 76 tests pass (Ollama mocked in tests)
