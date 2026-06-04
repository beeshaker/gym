# Workout Programs — Design Spec

**Date:** 2026-06-04
**Phase:** 6 of 6 — Workout Programs + Equipment Swap
**Status:** Approved

---

## Overview

Adds a curated library of workout programs (PPL, 5x5, Upper/Lower, Full Body, Bro Split) to the Log screen. Tapping a program shows its days; tapping a day opens a preview screen with progressive overload suggestions pre-filled. Each exercise has a "⇄ Swap" button that fetches alternatives with the same muscle group via JSON. Confirming creates the session with sets already logged.

No Ollama involved. Custom program creation and LLama-generated programs are deferred to a later phase.

---

## 1. New Models

Added to `workouts/models.py`:

```python
class Program(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProgramDay(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='days')
    name    = models.CharField(max_length=50)   # "Push", "Pull A", "Workout A"
    order   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.program.name} — {self.name}'


class ProgramExercise(models.Model):
    program_day       = models.ForeignKey(ProgramDay, on_delete=models.CASCADE, related_name='exercises')
    exercise          = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name='program_exercises')
    order             = models.PositiveIntegerField(default=0)
    sets_override     = models.PositiveIntegerField(null=True, blank=True)
    min_reps_override = models.PositiveIntegerField(null=True, blank=True)
    max_reps_override = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def effective_sets(self):
        return self.sets_override or self.exercise.default_sets

    def effective_min_reps(self):
        return self.min_reps_override or self.exercise.default_min_reps

    def effective_max_reps(self):
        return self.max_reps_override or self.exercise.default_max_reps
```

One migration required.

---

## 2. Fixtures — `workouts/fixtures/programs.json`

New fixture file. Seeded alongside `exercises.json`. All exercise PKs reference the existing exercises fixture.

### Programs + days (exercise PKs from existing fixture):

**PPL — Push Pull Legs** (3 days)
- Push: Bench Press (1), Incline DB Press (2), Dumbbell Shoulder Press (3), Lateral Raise (6), Tricep Pushdown (7)
- Pull: Lat Pulldown (9), Seated Cable Row (11), Dumbbell Row (13), Face Pull (14), Barbell Curl (15)
- Legs: Squat (18), Leg Press (19), Romanian Deadlift (20), Leg Curl (21), Calf Raise (24)

**5x5 Stronglift** (2 days, sets_override=5, min/max_reps_override=5)
- Workout A: Squat (18), Bench Press (1), Dumbbell Row (13)
- Workout B: Squat (18), Dumbbell Shoulder Press (3), Romanian Deadlift (20)

**Upper / Lower** (4 days)
- Upper A: Bench Press (1), Dumbbell Row (13), Dumbbell Shoulder Press (3), Lat Pulldown (9), Tricep Pushdown (7), Barbell Curl (15)
- Lower A: Squat (18), Romanian Deadlift (20), Leg Press (19), Leg Curl (21), Calf Raise (24)
- Upper B: Machine Chest Press (4), Chest-supported Row (12), Lateral Raise (6), Seated Cable Row (11), Skull Crusher (28), Dumbbell Curl (16)
- Lower B: Romanian Deadlift (20), Walking Lunge (23), Leg Extension (22), Leg Curl (21), Calf Raise (24)

**Full Body 3-Day** (3 days)
- Day A: Squat (18), Bench Press (1), Lat Pulldown (9), Dumbbell Shoulder Press (3), Romanian Deadlift (20)
- Day B: Leg Press (19), Incline DB Press (2), Seated Cable Row (11), Lateral Raise (6), Leg Curl (21)
- Day C: Squat (18), Dumbbell Row (13), Machine Chest Press (4), Face Pull (14), Walking Lunge (23)

**Bro Split** (5 days)
- Chest: Bench Press (1), Incline DB Press (2), Machine Chest Press (4), Cable Fly (5)
- Back: Lat Pulldown (9), Seated Cable Row (11), Dumbbell Row (13), Chest-supported Row (12), Face Pull (14)
- Shoulders: Dumbbell Shoulder Press (3), Lateral Raise (6), Rear Delt Fly (26), Face Pull (14)
- Arms: Tricep Pushdown (7), Rope Pushdown (27), Skull Crusher (28), Barbell Curl (15), Dumbbell Curl (16), Hammer Curl (17)
- Legs: Squat (18), Leg Press (19), Romanian Deadlift (20), Leg Curl (21), Leg Extension (22), Calf Raise (24)

---

## 3. Data Flow

```
log_home (GET)
  → _log_home_context() now also fetches:
      programs = Program.objects.filter(is_active=True).prefetch_related('days')
  → render log_home.html with repeat_options + programs

program_day_list(request, program_id) — GET
  → get_object_or_404(Program, id=program_id, is_active=True)
  → render workouts/program_days.html with program + days

program_preview(request, day_id) — GET
  → get_object_or_404(ProgramDay, id=day_id)
  → for each ProgramExercise in day:
      last_we = last completed WorkoutExercise for this exercise
      last_sets = last_we.sets.all() if last_we else []
      rec = recommend(exercise, last_sets)  — uses effective_min/max_reps
      sets_count = rec['last_sets_count'] or pe.effective_sets()
  → session_name = f"{today.strftime('%A')} {day.name}"
  → render workouts/program_preview.html with day, session_name, exercises_data

program_swap_options(request, exercise_id) — GET, returns JSON
  → exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
  → alternatives = Exercise.objects.filter(
        muscle_group=exercise.muscle_group,
        is_active=True
    ).exclude(id=exercise_id).order_by('equipment', 'name')
  → return JsonResponse({'alternatives': [
        {'id': e.id, 'name': e.name, 'equipment': e.get_equipment_display(),
         'movement_type': e.get_movement_type_display()}
        for e in alternatives
    ]})

program_start(request) — POST
  → reads: name, exercise_id list, weight_{ex_id}_{n}, reps_{ex_id}_{n}
  → transaction.atomic():
      session = WorkoutSession.objects.create(name=name)
      for order, ex_id in enumerate(exercise_ids, start=1):
          exercise = Exercise.objects.get(id=ex_id, is_active=True)
          we = WorkoutExercise.objects.create(session, exercise, order)
          n = 1; while weight_{ex_id}_{n} in POST: create WorkoutSet; n++
  → redirect to gym_active_session
```

Note: `program_start` uses the same form-parsing pattern as `repeat_start`. A shared helper `_create_session_from_form(request, name)` in `views.py` can handle both to avoid duplication.

---

## 4. Routes

Added to `core/urls.py` under `/<secret>/`:

| URL | Name | View | Method |
|---|---|---|---|
| `programs/<int:program_id>/` | `gym_program_days` | `program_day_list` | GET |
| `programs/<int:day_id>/preview/` | `gym_program_preview` | `program_preview` | GET |
| `programs/start/` | `gym_program_start` | `program_start` | POST |
| `programs/swap/<int:exercise_id>/` | `gym_program_swap` | `program_swap_options` | GET |

---

## 5. Views — `workouts/views.py`

### Updated `_log_home_context()`

```python
def _log_home_context():
    from .models import Program
    last_by_cat = get_last_sessions_by_category()
    repeat_options = [...]  # unchanged
    programs = list(Program.objects.filter(is_active=True).prefetch_related('days'))
    return {'repeat_options': repeat_options, 'programs': programs}
```

### Shared helper `_create_session_from_form(request)`

```python
def _create_session_from_form(request):
    """
    Reads name + exercise_id list + weight_{ex_id}_{n}/reps_{ex_id}_{n} from POST.
    Creates WorkoutSession + WorkoutExercise + WorkoutSet in transaction.atomic().
    Returns the new WorkoutSession.
    Raises ValueError if name is empty.
    """
```

Both `repeat_start` and `program_start` call this helper. `repeat_start` is refactored to use it.

### New `program_day_list(request, program_id)` — GET

```python
@require_http_methods(['GET'])
def program_day_list(request, program_id):
    program = get_object_or_404(Program, id=program_id, is_active=True)
    days = program.days.all()
    return render(request, 'workouts/program_days.html', {
        'program': program,
        'days': days,
    })
```

### New `program_preview(request, day_id)` — GET

```python
@require_http_methods(['GET'])
def program_preview(request, day_id):
    day = get_object_or_404(ProgramDay, id=day_id)
    today = timezone.localdate()
    session_name = f"{today.strftime('%A')} {day.name}"
    program_exercises = (day.exercises
                         .select_related('exercise')
                         .prefetch_related('exercise__workout_exercises__sets')
                         .order_by('order'))
    exercise_ids = [pe.exercise_id for pe in program_exercises]
    last_wes = (WorkoutExercise.objects
                .filter(exercise_id__in=exercise_ids, session__status='complete')
                .select_related('exercise')
                .prefetch_related('sets')
                .order_by('exercise_id', '-session__completed_at')
                .distinct('exercise_id'))
    last_we_by_exercise = {lw.exercise_id: lw for lw in last_wes}
    exercises_data = []
    for pe in program_exercises:
        last_we = last_we_by_exercise.get(pe.exercise_id)
        last_sets = list(last_we.sets.all()) if last_we else []
        # Build a fake exercise object with effective reps for recommend()
        class EffectiveExercise:
            default_min_reps = pe.effective_min_reps()
            default_max_reps = pe.effective_max_reps()
            default_sets = pe.effective_sets()
            default_increment = pe.exercise.default_increment
        rec = recommend(EffectiveExercise(), last_sets)
        sets_count = rec['last_sets_count'] if rec['last_sets_count'] > 0 else pe.effective_sets()
        exercises_data.append({
            'exercise': pe.exercise,
            'rec': rec,
            'sets_count': sets_count,
            'sets': [
                {'n': i, 'weight': rec['target_weight'], 'reps': rec['target_reps_min']}
                for i in range(1, sets_count + 1)
            ],
        })
    return render(request, 'workouts/program_preview.html', {
        'day': day,
        'session_name': session_name,
        'exercises': exercises_data,
    })
```

### New `program_swap_options(request, exercise_id)` — GET

```python
@require_http_methods(['GET'])
def program_swap_options(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    alternatives = (Exercise.objects
                    .filter(muscle_group=exercise.muscle_group, is_active=True)
                    .exclude(id=exercise_id)
                    .order_by('equipment', 'name'))
    return JsonResponse({'alternatives': [
        {
            'id': e.id,
            'name': e.name,
            'equipment': e.get_equipment_display(),
            'movement_type': e.get_movement_type_display(),
        }
        for e in alternatives
    ]})
```

### New `program_start(request)` — POST

```python
@require_http_methods(['POST'])
def program_start(request):
    try:
        session = _create_session_from_form(request)
    except ValueError:
        return redirect('gym_log_home')
    return redirect('gym_active_session', session_id=session.id)
```

---

## 6. Shared Helper Refactor — `_create_session_from_form`

Extract the session-creation logic from `repeat_start` into a shared helper:

```python
def _create_session_from_form(request):
    name = request.POST.get('name', '').strip()
    if not name:
        raise ValueError('name required')
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
                except (ValueError, TypeError, KeyError):
                    n += 1
                    continue
                WorkoutSet.objects.create(
                    workout_exercise=we, set_number=n,
                    weight_kg=weight, reps=reps,
                )
                n += 1
    return session
```

`repeat_start` becomes:

```python
@require_http_methods(['POST'])
def repeat_start(request, category):
    try:
        session = _create_session_from_form(request)
    except ValueError:
        return redirect('gym_log_home')
    return redirect('gym_active_session', session_id=session.id)
```

---

## 7. Templates

### `templates/workouts/log_home.html`

Add below the Quick Repeat section:

```html
{% if programs %}
<div class="program-section">
  <div class="program-divider">📋 Programs</div>
  {% for prog in programs %}
  <a href="{% url 'gym_program_days' prog.id %}" class="program-btn">
    <span class="program-icon">📋</span>
    <div>
      <div class="program-name">{{ prog.name }}</div>
      <div class="program-meta">{{ prog.description }}</div>
    </div>
  </a>
  {% endfor %}
</div>
{% endif %}
```

### `templates/workouts/program_days.html` — new

Extends `base.html`. Shows program name + description, then one button per day. Each button links to `gym_program_preview`.

### `templates/workouts/program_preview.html` — new

Extends `base.html`. Same structure as `repeat_preview.html` with two additions per exercise card:

1. A `data-exercise-id` attribute on the `.we-card` div
2. A "⇄ Swap" button that triggers a JS fetch to `gym_program_swap`
3. A `.swap-panel` div (initially hidden) below the set rows

**Swap JS behaviour:**
- Tap "⇄ Swap": fetch `GET /programs/swap/{exercise_id}/` → render alternatives in `.swap-panel`, show panel
- Tap "Use" on an alternative:
  - Update the card's `data-exercise-id` attribute to the new exercise ID
  - Update the hidden `<input name="exercise_id">` value
  - Rename all `weight_{old_id}_{n}` and `reps_{old_id}_{n}` inputs to use new ID
  - Update `.we-name` text and `.we-meta` text
  - Hide the swap panel

---

## 8. CSS additions — `static/css/app.css`

```
.program-section   — same as .repeat-section (margin-top 20px)
.program-divider   — same as .repeat-divider
.program-btn       — same as .repeat-btn
.program-icon      — same as .repeat-icon
.program-name      — same as .repeat-label
.program-meta      — same as .repeat-meta
.swap-panel        — background var(--card2), border 1px solid var(--accent) at 30% opacity,
                     border-radius 4px, padding 8px, margin-top 6px
.swap-option       — flex row, justify-content space-between, padding 5px 8px,
                     background var(--card), border 1px solid var(--border), border-radius 4px, margin-bottom 4px
.swap-use-btn      — font-size 11px, color var(--accent), border 1px solid var(--accent) at 30%,
                     border-radius 3px, padding 2px 8px, background transparent, cursor pointer
```

---

## 9. Tests

### `tests/test_program_fixtures.py` — no DB (loads fixture data only)

```python
def test_all_programs_have_days():
    # load programs.json, verify each program has >= 1 day

def test_all_program_exercises_reference_valid_exercises():
    # load both fixtures, verify all exercise PKs in programs.json exist in exercises.json
```

### `tests/test_program_views.py` — HTTP tests

```python
def test_program_day_list_returns_200(verified_client)
def test_program_day_list_shows_day_names(verified_client)
def test_program_preview_returns_200(verified_client)
def test_program_preview_contains_exercise_name(verified_client)
def test_program_swap_options_returns_json(verified_client)
def test_program_swap_excludes_original_exercise(verified_client)
def test_program_start_creates_session(verified_client)
def test_program_start_creates_sets(verified_client)
def test_log_home_shows_programs(verified_client)
```

**Expected total: 95 tests (86 existing + 2 fixture + 9 view)**

---

## 10. What This Does NOT Include

- Custom program creation UI (Phase 7)
- Ollama-generated programs (Phase 7)
- Program progress tracking ("you're on week 3 of PPL")
- Rest day scheduling
- Program assignment (setting "I'm running PPL for 12 weeks")

---

## 11. Acceptance Criteria

1. Log screen shows Programs section with all 5 programs
2. Tapping a program shows its days
3. Tapping a day opens preview screen with AI-suggested weights pre-filled
4. Preview session name is `{Today} {DayName}` (e.g., "Wednesday Push")
5. 5x5 exercises show 5 sets × 5 reps (from overrides)
6. "⇄ Swap" fetches and displays alternatives with same muscle group
7. Selecting an alternative updates the card and renames the form inputs
8. "▶ Start Session" creates session + exercises + sets, redirects to active session
9. `repeat_start` still works after refactor to `_create_session_from_form`
10. All 95 tests pass
