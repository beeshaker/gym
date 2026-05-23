# Gym Progress AI — Phase 2 Workout Logging Design

**Date:** 2026-05-23
**Phase:** 2 of 6 — Workout Logging
**Status:** Approved

---

## Overview

Phase 2 adds the ability to log gym sessions. A user names a session, adds exercises from the library, logs sets (weight + reps) for each exercise, and finishes the session. Completed sessions appear on a history page as rich cards. The dashboard hero card updates to reflect the last session.

No AI, no PR detection, no progressive overload — those come in later phases.

---

## 1. Data Models

Three new models added to `workouts/models.py`.

### WorkoutSession

```python
class WorkoutSession(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('complete', 'Complete')]

    name         = CharField(max_length=100)           # e.g. "Monday Push"
    status       = CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    started_at   = DateTimeField(auto_now_add=True)
    completed_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.name} ({self.started_at:%Y-%m-%d})'
```

### WorkoutExercise

```python
class WorkoutExercise(models.Model):
    session  = ForeignKey(WorkoutSession, on_delete=CASCADE, related_name='workout_exercises')
    exercise = ForeignKey(Exercise, on_delete=PROTECT, related_name='workout_exercises')
    order    = PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.session.name} — {self.exercise.name}'
```

### WorkoutSet

```python
class WorkoutSet(models.Model):
    workout_exercise = ForeignKey(WorkoutExercise, on_delete=CASCADE, related_name='sets')
    set_number       = PositiveIntegerField()
    weight_kg        = DecimalField(max_digits=5, decimal_places=1)
    reps             = PositiveIntegerField()
    created_at       = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['set_number']

    def __str__(self):
        return f'Set {self.set_number}: {self.weight_kg}kg × {self.reps}'
```

---

## 2. Routes

All routes live under `/<secret>/`, added to `core/urls.py`.

| URL | Name | View | Method |
|---|---|---|---|
| `log/` | `gym_log_home` | `log_home` | GET |
| `log/start/` | `gym_log_start` | `start_session` | POST |
| `log/<int:session_id>/` | `gym_active_session` | `active_session` | GET |
| `log/<int:session_id>/add-exercise/` | `gym_add_exercise` | `add_exercise` | POST |
| `log/<int:session_id>/exercise/<int:we_id>/add-set/` | `gym_add_set` | `add_set` | POST |
| `log/<int:session_id>/exercise/<int:we_id>/delete-set/<int:set_id>/` | `gym_delete_set` | `delete_set` | POST |
| `log/<int:session_id>/finish/` | `gym_finish_session` | `finish_session` | POST |
| `history/` | `gym_history` | `history` | GET |
| `history/<int:session_id>/` | `gym_session_detail` | `session_detail` | GET |

All log views use the PRG (Post/Redirect/Get) pattern — no form re-submission on browser refresh. The only client-side JavaScript used is: (1) filtering the exercise picker list as the user types, and (2) toggling the exercise picker card open/closed. All data mutations are plain form POSTs.

---

## 3. Views

All new views live in `workouts/views.py`.

### `log_home(request)`
- If an active session exists → redirect to `gym_active_session` for that session
- Else → render `workouts/log_home.html` with a blank session name form

### `start_session(request)` — POST only
- Validates session name (non-empty, max 100 chars)
- Creates `WorkoutSession(name=name, status='active')`
- Redirects to `gym_active_session`

### `active_session(request, session_id)`
- Gets `WorkoutSession` — 404 if not found or status is `complete`
- Fetches all `WorkoutExercise` objects with their sets prefetched
- Fetches all active `Exercise` objects for the exercise picker
- Renders `workouts/active_session.html`

### `add_exercise(request, session_id)` — POST only
- Gets active `WorkoutSession` — 404 if not found or complete
- Gets `Exercise` by posted `exercise_id`
- Creates `WorkoutExercise(session=session, exercise=exercise, order=session.workout_exercises.count() + 1)`
- Redirects to `gym_active_session`

### `add_set(request, session_id, we_id)` — POST only
- Gets active `WorkoutSession` and `WorkoutExercise`
- Validates `weight_kg` (positive decimal) and `reps` (positive integer)
- Creates `WorkoutSet(workout_exercise=we, set_number=we.sets.count() + 1, weight_kg=w, reps=r)`
- Redirects to `gym_active_session`

### `delete_set(request, session_id, we_id, set_id)` — POST only
- Gets the `WorkoutSet` — 404 if not found
- Deletes it
- Redirects to `gym_active_session`

### `finish_session(request, session_id)` — POST only
- Gets active `WorkoutSession`
- Sets `status='complete'` and `completed_at=timezone.now()`
- Saves
- Redirects to `gym_history`

### `history(request)`
- Fetches all `WorkoutSession` objects with `status='complete'`, ordered by `-started_at`
- For each session, prefetches `workout_exercises` → `exercise` + `sets`
- Renders `workouts/history.html`

### `session_detail(request, session_id)`
- Gets `WorkoutSession` by id
- Prefetches all exercises and sets
- Renders `workouts/session_detail.html`

---

## 4. Templates

All templates extend `base.html`.

### `workouts/log_home.html`

Single card centred on screen. Text input for session name, primary "Start Workout" button. If there's an active session in context, the view redirects before this renders.

### `workouts/active_session.html`

- **Header area:** session name + "Finish Workout" button (danger style, confirms before submitting)
- **Per exercise:** one `.gym-card` showing exercise name, set table (Set # | kg | × | Reps | ✓), "+ Add set" link, small delete (×) per set row
- **Exercise picker:** a search input + scrollable list of all exercises, shown as a slide-up card when "+ Add Exercise" is tapped. Selecting an exercise POSTs to `add_exercise`. Filter is client-side JS on the pre-rendered list (no AJAX needed).
- **Finish Workout:** form POSTing to `gym_finish_session`, placed at bottom

### `workouts/history.html`

Rich cards (Layout B chosen during brainstorm):
- Session name + date (right-aligned)
- Exercise count + set count subtitle
- Up to 3 exercises listed with their heaviest set: `Bench Press · 60kg`
- `+N more` if over 3 exercises
- Card is a link to `gym_session_detail`

Empty state: "No workouts logged yet — tap + to start"

### `workouts/session_detail.html`

- Hero: session name (large), date + duration (started_at → completed_at)
- One section per exercise: exercise name as section label, set table showing all sets (set # | weight | reps)

### `core/dashboard.html` (updated)

The view passes `last_session` context (most recent complete `WorkoutSession` or `None`).

- If `last_session` is None → current Phase 1 empty state ("No workout yet")
- If `last_session` exists → hero shows last session name + how many days ago

---

## 5. Admin

```python
# workouts/admin.py additions
class WorkoutSetInline(admin.TabularInline):
    model = WorkoutSet
    extra = 0
    fields = ('set_number', 'weight_kg', 'reps')

class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0
    fields = ('exercise', 'order')

@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'started_at', 'completed_at')
    list_filter = ('status',)
    inlines = [WorkoutExerciseInline]
```

---

## 6. Dashboard View Update

`core/views.py` `dashboard` view fetches:
```python
last_session = WorkoutSession.objects.filter(status='complete').first()
```
Passes it to the template as context.

---

## 7. Navigation

- FAB on dashboard → `gym_log_home`
- Bottom nav "Log" item → `gym_log_home`
- Bottom nav "History" (the ☰ icon, currently "Exercises") stays as Exercises for now — History gets its own nav slot in a later phase
- History is accessible from the dashboard or via direct URL

---

## 8. Tests

**`tests/test_workout_models.py`** — WorkoutSession, WorkoutExercise, WorkoutSet str, defaults, cascade deletes, ordering

**`tests/test_log_views.py`** — start session, add exercise, add set, delete set, finish session, redirect behaviour, 404 on complete session

**`tests/test_history_views.py`** — history renders completed sessions, empty state, session detail renders all sets

All tests use the existing `verified_client` fixture from `conftest.py`.

---

## 9. What Phase 2 Does NOT Include

- PR detection (Phase 4)
- Progressive overload suggestions (Phase 5)
- AI coach (Phase 6)
- Natural language log parsing (Phase 3)
- Edit session name after creation
- Reorder exercises within a session

---

## 10. Acceptance Criteria

1. Tapping FAB on dashboard reaches the Start Workout screen
2. Naming and starting a session creates a `WorkoutSession` with `status='active'`
3. Exercises can be added from the exercise library via the picker
4. Sets can be added (weight + reps) and deleted for each exercise
5. Finishing a session sets `status='complete'` and `completed_at`
6. History page shows completed sessions as rich cards
7. Session detail shows all exercises and sets
8. Dashboard hero card shows the last completed session name
9. All tests pass
