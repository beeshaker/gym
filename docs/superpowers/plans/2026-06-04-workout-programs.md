# Workout Programs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a library of 5 pre-defined workout programs (PPL, 5x5, Upper/Lower, Full Body, Bro Split) to the Log screen, with a day-picker, progressive overload preview, and per-exercise equipment swap.

**Architecture:** Three new Django models (`Program`, `ProgramDay`, `ProgramExercise`) seeded via fixture. New views share `_create_session_from_form()` with the existing `repeat_start` view. The swap button fetches alternatives via a JSON endpoint and renames form inputs client-side. All writes use `transaction.atomic()`.

**Tech Stack:** Django 4.2, PostgreSQL, pytest-django, vanilla JS (no framework).

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `workouts/models.py` | Modify | Add `Program`, `ProgramDay`, `ProgramExercise` models |
| `workouts/migrations/` | Create | Migration for new models |
| `workouts/fixtures/programs.json` | Create | Seed data for all 5 programs |
| `workouts/views.py` | Modify | `_create_session_from_form`, `_log_home_context` update, 4 new views, refactor `repeat_start` |
| `core/urls.py` | Modify | 4 new URL patterns |
| `static/css/app.css` | Modify | Append program + swap styles |
| `templates/workouts/log_home.html` | Modify | Add Programs section |
| `templates/workouts/program_days.html` | Create | Program day picker |
| `templates/workouts/program_preview.html` | Create | Preview with swap JS |
| `tests/test_program_fixtures.py` | Create | 2 fixture sanity tests (no DB) |
| `tests/test_program_views.py` | Create | 9 HTTP tests |

---

## Task 1: Models + Migration

**Files:**
- Modify: `workouts/models.py`
- Create: migration (auto-generated)

- [ ] **Step 1: Add three models to `workouts/models.py`**

Read the file first. Append after the `WorkoutSet` class:

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
    name    = models.CharField(max_length=50)
    order   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.program.name} — {self.name}'


class ProgramExercise(models.Model):
    program_day       = models.ForeignKey(ProgramDay, on_delete=models.CASCADE, related_name='exercises')
    exercise          = models.ForeignKey('Exercise', on_delete=models.PROTECT, related_name='program_exercises')
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

    def __str__(self):
        return f'{self.program_day} — {self.exercise.name}'
```

- [ ] **Step 2: Generate migration**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && python manage.py makemigrations workouts
```

Expected: `Migrations for 'workouts': workouts/migrations/000X_program_programday_programexercise.py`

- [ ] **Step 3: Apply migration**

```bash
python manage.py migrate
```

Expected: `Applying workouts.000X_program_programday_programexercise... OK`

- [ ] **Step 4: Verify Django check passes**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Run full suite — no regressions**

```bash
pytest tests/ -q
```

Expected: 86 tests pass.

- [ ] **Step 6: Commit**

```bash
git add workouts/models.py workouts/migrations/
git commit -m "feat: Program, ProgramDay, ProgramExercise models"
```

---

## Task 2: Programs Fixture + Fixture Tests

**Files:**
- Create: `workouts/fixtures/programs.json`
- Create: `tests/test_program_fixtures.py`

- [ ] **Step 1: Write failing fixture tests**

Create `tests/test_program_fixtures.py`:

```python
import json
import os

FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'workouts', 'fixtures'
)


def _load(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


def test_all_programs_have_days():
    data = _load('programs.json')
    program_pks = {e['pk'] for e in data if e['model'] == 'workouts.program'}
    day_program_pks = {
        e['fields']['program']
        for e in data
        if e['model'] == 'workouts.programday'
    }
    for pk in program_pks:
        assert pk in day_program_pks, f'Program pk={pk} has no days'


def test_all_program_exercises_reference_valid_exercises():
    programs = _load('programs.json')
    exercises = _load('exercises.json')
    valid_pks = {e['pk'] for e in exercises if e['model'] == 'workouts.exercise'}
    for entry in programs:
        if entry['model'] == 'workouts.programexercise':
            ex_pk = entry['fields']['exercise']
            assert ex_pk in valid_pks, (
                f"ProgramExercise pk={entry['pk']} references missing exercise pk={ex_pk}"
            )
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_program_fixtures.py -v
```

Expected: `FileNotFoundError` — `programs.json` doesn't exist yet.

- [ ] **Step 3: Generate `workouts/fixtures/programs.json`**

Create a one-off generator script at `/tmp/gen_programs.py`:

```python
import json

fixture = []

# ── Programs ─────────────────────────────────────────────────────────────────
programs = [
    (1, 'Bro Split', '5-day muscle-group split: Chest / Back / Shoulders / Arms / Legs'),
    (2, 'Full Body 3-Day', '3 full-body sessions per week, balanced compound movements'),
    (3, 'PPL — Push Pull Legs', 'Classic 3-day push/pull/legs split'),
    (4, '5x5 Stronglift', 'Two alternating sessions, 5 sets of 5 reps, barbell focus'),
    (5, 'Upper / Lower', '4-day upper/lower split with A/B variation'),
]
for pk, name, desc in programs:
    fixture.append({
        'model': 'workouts.program', 'pk': pk,
        'fields': {'name': name, 'description': desc, 'is_active': True}
    })

# ── ProgramDays ───────────────────────────────────────────────────────────────
days = [
    # Bro Split (program 1)
    (1,  1, 'Chest',     1),
    (2,  1, 'Back',      2),
    (3,  1, 'Shoulders', 3),
    (4,  1, 'Arms',      4),
    (5,  1, 'Legs',      5),
    # Full Body 3-Day (program 2)
    (6,  2, 'Day A', 1),
    (7,  2, 'Day B', 2),
    (8,  2, 'Day C', 3),
    # PPL (program 3)
    (9,  3, 'Push', 1),
    (10, 3, 'Pull', 2),
    (11, 3, 'Legs', 3),
    # 5x5 (program 4)
    (12, 4, 'Workout A', 1),
    (13, 4, 'Workout B', 2),
    # Upper/Lower (program 5)
    (14, 5, 'Upper A', 1),
    (15, 5, 'Lower A', 2),
    (16, 5, 'Upper B', 3),
    (17, 5, 'Lower B', 4),
]
for pk, prog, name, order in days:
    fixture.append({
        'model': 'workouts.programday', 'pk': pk,
        'fields': {'program': prog, 'name': name, 'order': order}
    })

# ── ProgramExercises ──────────────────────────────────────────────────────────
# (pk, day_pk, exercise_pk, order, sets_override, min_reps_override, max_reps_override)
pe_data = [
    # Bro Split — Chest (day 1)
    (1,  1,  1, 1, None, None, None),   # Bench Press
    (2,  1,  2, 2, None, None, None),   # Incline DB Press
    (3,  1,  4, 3, None, None, None),   # Machine Chest Press
    (4,  1,  5, 4, None, None, None),   # Cable Fly
    # Bro Split — Back (day 2)
    (5,  2,  9, 1, None, None, None),   # Lat Pulldown
    (6,  2, 11, 2, None, None, None),   # Seated Cable Row
    (7,  2, 13, 3, None, None, None),   # Dumbbell Row
    (8,  2, 12, 4, None, None, None),   # Chest-supported Row
    (9,  2, 14, 5, None, None, None),   # Face Pull
    # Bro Split — Shoulders (day 3)
    (10, 3,  3, 1, None, None, None),   # Dumbbell Shoulder Press
    (11, 3,  6, 2, None, None, None),   # Lateral Raise
    (12, 3, 26, 3, None, None, None),   # Rear Delt Fly
    (13, 3, 14, 4, None, None, None),   # Face Pull
    # Bro Split — Arms (day 4)
    (14, 4,  7, 1, None, None, None),   # Tricep Pushdown
    (15, 4, 27, 2, None, None, None),   # Rope Pushdown
    (16, 4, 28, 3, None, None, None),   # Skull Crusher
    (17, 4, 15, 4, None, None, None),   # Barbell Curl
    (18, 4, 16, 5, None, None, None),   # Dumbbell Curl
    (19, 4, 17, 6, None, None, None),   # Hammer Curl
    # Bro Split — Legs (day 5)
    (20, 5, 18, 1, None, None, None),   # Squat
    (21, 5, 19, 2, None, None, None),   # Leg Press
    (22, 5, 20, 3, None, None, None),   # Romanian Deadlift
    (23, 5, 21, 4, None, None, None),   # Leg Curl
    (24, 5, 22, 5, None, None, None),   # Leg Extension
    (25, 5, 24, 6, None, None, None),   # Calf Raise
    # Full Body Day A (day 6)
    (26, 6, 18, 1, None, None, None),   # Squat
    (27, 6,  1, 2, None, None, None),   # Bench Press
    (28, 6,  9, 3, None, None, None),   # Lat Pulldown
    (29, 6,  3, 4, None, None, None),   # Dumbbell Shoulder Press
    (30, 6, 20, 5, None, None, None),   # Romanian Deadlift
    # Full Body Day B (day 7)
    (31, 7, 19, 1, None, None, None),   # Leg Press
    (32, 7,  2, 2, None, None, None),   # Incline DB Press
    (33, 7, 11, 3, None, None, None),   # Seated Cable Row
    (34, 7,  6, 4, None, None, None),   # Lateral Raise
    (35, 7, 21, 5, None, None, None),   # Leg Curl
    # Full Body Day C (day 8)
    (36, 8, 18, 1, None, None, None),   # Squat
    (37, 8, 13, 2, None, None, None),   # Dumbbell Row
    (38, 8,  4, 3, None, None, None),   # Machine Chest Press
    (39, 8, 14, 4, None, None, None),   # Face Pull
    (40, 8, 23, 5, None, None, None),   # Walking Lunge
    # PPL Push (day 9)
    (41, 9,  1, 1, None, None, None),   # Bench Press
    (42, 9,  2, 2, None, None, None),   # Incline DB Press
    (43, 9,  3, 3, None, None, None),   # Dumbbell Shoulder Press
    (44, 9,  6, 4, None, None, None),   # Lateral Raise
    (45, 9,  7, 5, None, None, None),   # Tricep Pushdown
    # PPL Pull (day 10)
    (46, 10,  9, 1, None, None, None),  # Lat Pulldown
    (47, 10, 11, 2, None, None, None),  # Seated Cable Row
    (48, 10, 13, 3, None, None, None),  # Dumbbell Row
    (49, 10, 14, 4, None, None, None),  # Face Pull
    (50, 10, 15, 5, None, None, None),  # Barbell Curl
    # PPL Legs (day 11)
    (51, 11, 18, 1, None, None, None),  # Squat
    (52, 11, 19, 2, None, None, None),  # Leg Press
    (53, 11, 20, 3, None, None, None),  # Romanian Deadlift
    (54, 11, 21, 4, None, None, None),  # Leg Curl
    (55, 11, 24, 5, None, None, None),  # Calf Raise
    # 5x5 Workout A (day 12) — 5 sets × 5 reps
    (56, 12, 18, 1, 5, 5, 5),           # Squat
    (57, 12,  1, 2, 5, 5, 5),           # Bench Press
    (58, 12, 13, 3, 5, 5, 5),           # Dumbbell Row
    # 5x5 Workout B (day 13)
    (59, 13, 18, 1, 5, 5, 5),           # Squat
    (60, 13,  3, 2, 5, 5, 5),           # Dumbbell Shoulder Press
    (61, 13, 20, 3, 5, 5, 5),           # Romanian Deadlift
    # Upper/Lower Upper A (day 14)
    (62, 14,  1, 1, None, None, None),  # Bench Press
    (63, 14, 13, 2, None, None, None),  # Dumbbell Row
    (64, 14,  3, 3, None, None, None),  # Dumbbell Shoulder Press
    (65, 14,  9, 4, None, None, None),  # Lat Pulldown
    (66, 14,  7, 5, None, None, None),  # Tricep Pushdown
    (67, 14, 15, 6, None, None, None),  # Barbell Curl
    # Upper/Lower Lower A (day 15)
    (68, 15, 18, 1, None, None, None),  # Squat
    (69, 15, 20, 2, None, None, None),  # Romanian Deadlift
    (70, 15, 19, 3, None, None, None),  # Leg Press
    (71, 15, 21, 4, None, None, None),  # Leg Curl
    (72, 15, 24, 5, None, None, None),  # Calf Raise
    # Upper/Lower Upper B (day 16)
    (73, 16,  4, 1, None, None, None),  # Machine Chest Press
    (74, 16, 12, 2, None, None, None),  # Chest-supported Row
    (75, 16,  6, 3, None, None, None),  # Lateral Raise
    (76, 16, 11, 4, None, None, None),  # Seated Cable Row
    (77, 16, 28, 5, None, None, None),  # Skull Crusher
    (78, 16, 16, 6, None, None, None),  # Dumbbell Curl
    # Upper/Lower Lower B (day 17)
    (79, 17, 20, 1, None, None, None),  # Romanian Deadlift
    (80, 17, 23, 2, None, None, None),  # Walking Lunge
    (81, 17, 22, 3, None, None, None),  # Leg Extension
    (82, 17, 21, 4, None, None, None),  # Leg Curl
    (83, 17, 24, 5, None, None, None),  # Calf Raise
]
for pk, day_pk, ex_pk, order, sets_ov, min_ov, max_ov in pe_data:
    fixture.append({
        'model': 'workouts.programexercise', 'pk': pk,
        'fields': {
            'program_day': day_pk, 'exercise': ex_pk, 'order': order,
            'sets_override': sets_ov, 'min_reps_override': min_ov,
            'max_reps_override': max_ov,
        }
    })

with open('workouts/fixtures/programs.json', 'w') as f:
    json.dump(fixture, f, indent=2)

print(f'Written {len(fixture)} fixture entries')
```

Run it:

```bash
cd /home/abhishek/abhi/gym && python /tmp/gen_programs.py
```

Expected: `Written 105 fixture entries`

- [ ] **Step 4: Run fixture tests — expect pass**

```bash
pytest tests/test_program_fixtures.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Load fixture into DB and verify**

```bash
source venv/bin/activate && python manage.py loaddata workouts/fixtures/programs.json
python manage.py shell -c "
from workouts.models import Program, ProgramDay, ProgramExercise
print('Programs:', Program.objects.count())
print('Days:', ProgramDay.objects.count())
print('Exercises:', ProgramExercise.objects.count())
"
```

Expected:
```
Programs: 5
Days: 17
Exercises: 83
```

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -q
```

Expected: 88 tests pass (86 + 2 fixture tests).

- [ ] **Step 7: Commit**

```bash
git add workouts/fixtures/programs.json tests/test_program_fixtures.py
git commit -m "feat: programs fixture (PPL, 5x5, Upper/Lower, Full Body, Bro Split) and fixture tests"
```

---

## Task 3: Shared Helper + Views + URLs + View Tests

**Files:**
- Modify: `workouts/views.py`
- Modify: `core/urls.py`
- Create: `tests/test_program_views.py`

- [ ] **Step 1: Write failing view tests**

Create `tests/test_program_views.py`:

```python
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from workouts.models import Exercise, Program, ProgramDay, ProgramExercise, WorkoutSession


def make_exercise(name='Bench Press', muscle_group='Chest', category='push', equipment='barbell'):
    return Exercise.objects.create(
        name=name, muscle_group=muscle_group, category=category,
        equipment=equipment, movement_type='compound',
    )


def make_program_with_day(exercise):
    prog = Program.objects.create(name='Test Program', description='For tests', is_active=True)
    day = ProgramDay.objects.create(program=prog, name='Push', order=1)
    ProgramExercise.objects.create(program_day=day, exercise=exercise, order=1)
    return prog, day


@pytest.mark.django_db
def test_program_day_list_returns_200(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_days', args=[prog.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_program_day_list_shows_day_names(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_days', args=[prog.id]))
    assert b'Push' in response.content


@pytest.mark.django_db
def test_program_preview_returns_200(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_preview', args=[day.id]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_program_preview_contains_exercise_name(verified_client):
    ex = make_exercise()
    prog, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_preview', args=[day.id]))
    assert b'Bench Press' in response.content


@pytest.mark.django_db
def test_program_swap_options_returns_json(verified_client):
    ex = make_exercise(name='Bench Press', equipment='barbell')
    make_exercise(name='DB Press', equipment='dumbbell')  # same muscle group
    response = verified_client.get(reverse('gym_program_swap', args=[ex.id]))
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'alternatives' in data
    assert isinstance(data['alternatives'], list)


@pytest.mark.django_db
def test_program_swap_excludes_original_exercise(verified_client):
    ex = make_exercise(name='Bench Press')
    response = verified_client.get(reverse('gym_program_swap', args=[ex.id]))
    data = json.loads(response.content)
    ids = [a['id'] for a in data['alternatives']]
    assert ex.id not in ids


@pytest.mark.django_db
def test_program_start_creates_session(verified_client):
    ex = make_exercise()
    response = verified_client.post(reverse('gym_program_start'), {
        'name': 'Wednesday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60',
        f'reps_{ex.id}_1': '10',
    })
    assert response.status_code == 302
    assert WorkoutSession.objects.filter(name='Wednesday Push', status='active').exists()


@pytest.mark.django_db
def test_program_start_creates_sets(verified_client):
    ex = make_exercise()
    verified_client.post(reverse('gym_program_start'), {
        'name': 'Wednesday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60', f'reps_{ex.id}_1': '10',
        f'weight_{ex.id}_2': '60', f'reps_{ex.id}_2': '10',
        f'weight_{ex.id}_3': '60', f'reps_{ex.id}_3': '10',
    })
    session = WorkoutSession.objects.get(name='Wednesday Push')
    we = session.workout_exercises.first()
    assert we.sets.count() == 3


@pytest.mark.django_db
def test_log_home_shows_programs(verified_client):
    ex = make_exercise()
    make_program_with_day(ex)
    response = verified_client.get(reverse('gym_log_home'))
    assert b'Programs' in response.content
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_program_views.py -v
```

Expected: `NoReverseMatch` for `gym_program_days`.

- [ ] **Step 3: Add URL patterns to `core/urls.py`**

Read `core/urls.py` first. After the `gym_repeat_start` line, add:

```python
    path('programs/<int:program_id>/', workout_views.program_day_list, name='gym_program_days'),
    path('programs/<int:day_id>/preview/', workout_views.program_preview, name='gym_program_preview'),
    path('programs/start/', workout_views.program_start, name='gym_program_start'),
    path('programs/swap/<int:exercise_id>/', workout_views.program_swap_options, name='gym_program_swap'),
```

- [ ] **Step 4: Update `workouts/views.py`**

Read `workouts/views.py` first. Make these changes:

**A) Add `Program` and `ProgramDay` to the models import line:**

Change:
```python
from .models import Exercise, WorkoutExercise, WorkoutSession, WorkoutSet
```
To:
```python
from .models import Exercise, Program, ProgramDay, ProgramExercise, WorkoutExercise, WorkoutSession, WorkoutSet
```

**B) Add `_create_session_from_form` helper** after `_log_home_context()` and before `def exercises`:

```python
def _create_session_from_form(request):
    """
    Reads name + exercise_id list + weight_{ex_id}_{n}/reps_{ex_id}_{n} from POST.
    Creates WorkoutSession + WorkoutExercise + WorkoutSet in transaction.atomic().
    Returns the new WorkoutSession.
    Raises ValueError if name is empty.
    """
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

**C) Update `_log_home_context()` to add programs:**

Replace the existing `_log_home_context` function with:

```python
def _log_home_context():
    last_by_cat = get_last_sessions_by_category()
    repeat_options = [
        {
            'category': cat,
            'label': dict(Exercise.CATEGORY_CHOICES)[cat],
            'last_date': session.completed_at,
            'exercise_count': len(session.workout_exercises.all()),
        }
        for cat, session in last_by_cat.items()
    ]
    programs = list(Program.objects.filter(is_active=True).prefetch_related('days'))
    return {'repeat_options': repeat_options, 'programs': programs}
```

**D) Refactor `repeat_start` to use `_create_session_from_form`:**

Replace the existing `repeat_start` view body (keep the decorator and signature):

```python
@require_http_methods(['POST'])
def repeat_start(request, category):
    try:
        session = _create_session_from_form(request)
    except ValueError:
        return redirect('gym_log_home')
    return redirect('gym_active_session', session_id=session.id)
```

**E) Append four new views at the END of `workouts/views.py`:**

```python
@require_http_methods(['GET'])
def program_day_list(request, program_id):
    program = get_object_or_404(Program, id=program_id, is_active=True)
    days = program.days.all()
    return render(request, 'workouts/program_days.html', {
        'program': program,
        'days': days,
    })


@require_http_methods(['GET'])
def program_preview(request, day_id):
    from types import SimpleNamespace
    day = get_object_or_404(ProgramDay, id=day_id)
    today = timezone.localdate()
    session_name = f"{today.strftime('%A')} {day.name}"
    program_exercises = (day.exercises
                         .select_related('exercise')
                         .order_by('order'))
    exercise_ids = [pe.exercise_id for pe in program_exercises]
    last_wes = (WorkoutExercise.objects
                .filter(exercise_id__in=exercise_ids, session__status='complete')
                .prefetch_related('sets')
                .order_by('exercise_id', '-session__completed_at')
                .distinct('exercise_id'))
    last_we_by_exercise = {lw.exercise_id: lw for lw in last_wes}
    exercises_data = []
    for pe in program_exercises:
        last_we = last_we_by_exercise.get(pe.exercise_id)
        last_sets = list(last_we.sets.all()) if last_we else []
        eff = SimpleNamespace(
            default_min_reps=pe.effective_min_reps(),
            default_max_reps=pe.effective_max_reps(),
            default_increment=pe.exercise.default_increment,
        )
        rec = recommend(eff, last_sets)
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


@require_http_methods(['POST'])
def program_start(request):
    try:
        session = _create_session_from_form(request)
    except ValueError:
        return redirect('gym_log_home')
    return redirect('gym_active_session', session_id=session.id)
```

- [ ] **Step 5: Run view tests — expect pass**

```bash
pytest tests/test_program_views.py -v
```

Expected: 9 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -q
```

Expected: 97 tests pass (88 + 9).

- [ ] **Step 7: Commit**

```bash
git add workouts/views.py core/urls.py tests/test_program_views.py
git commit -m "feat: program views, swap endpoint, shared _create_session_from_form helper"
```

---

## Task 4: CSS

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 1: Append CSS to `static/css/app.css`**

Read the end of the file to confirm current last line, then append:

```css
/* ── Workout Programs ────────────────────────────────────────────── */
.program-section  { margin-top: 20px; }

.program-divider {
  font-size: 9px;
  color: var(--text-sec);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  text-align: center;
  margin: 8px 0 10px;
}

.program-btn {
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

.program-icon  { font-size: 16px; flex-shrink: 0; }
.program-name  { font-size: 13px; font-weight: 700; }
.program-meta  { font-size: 11px; color: var(--text-sec); margin-top: 1px; }

/* ── Swap panel ──────────────────────────────────────────────────── */
.swap-btn {
  font-size: 10px;
  color: var(--accent);
  border: 1px solid rgba(34,197,94,0.3);
  border-radius: 4px;
  padding: 2px 8px;
  background: transparent;
  cursor: pointer;
  flex-shrink: 0;
}

.swap-panel {
  background: var(--card2);
  border: 1px solid rgba(34,197,94,0.25);
  border-radius: 4px;
  padding: 8px;
  margin-top: 6px;
}

.swap-panel-label {
  font-size: 10px;
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 6px;
}

.swap-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 9px;
  margin-bottom: 4px;
}

.swap-option-name { font-size: 11px; font-weight: 600; }
.swap-option-meta { font-size: 10px; color: var(--text-sec); }

.swap-use-btn {
  font-size: 10px;
  color: var(--accent);
  border: 1px solid rgba(34,197,94,0.3);
  border-radius: 3px;
  padding: 2px 8px;
  background: transparent;
  cursor: pointer;
}
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -q
```

Expected: 97 tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "feat: CSS for program list and swap panel"
```

---

## Task 5: Templates

**Files:**
- Modify: `templates/workouts/log_home.html`
- Create: `templates/workouts/program_days.html`
- Create: `templates/workouts/program_preview.html`

- [ ] **Step 1: Update `templates/workouts/log_home.html`**

Read the file first. Add the Programs section at the end of `{% block content %}`, after the existing `{% if repeat_options %}` block and before `{% endblock %}`:

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

- [ ] **Step 2: Create `templates/workouts/program_days.html`**

```html
{% extends 'base.html' %}
{% block title %}{{ program.name }} — Gym AI{% endblock %}

{% block content %}
<div class="page-header">
  <h1 class="page-title">{{ program.name }}</h1>
  <p class="page-sub">{{ program.description }}</p>
</div>

{% for day in days %}
<a href="{% url 'gym_program_preview' day.id %}" class="program-btn" style="margin-bottom:10px">
  <div>
    <div class="program-name">{{ day.name }}</div>
  </div>
</a>
{% endfor %}
{% endblock %}
```

- [ ] **Step 3: Create `templates/workouts/program_preview.html`**

```html
{% extends 'base.html' %}
{% block title %}{{ session_name }} — Gym AI{% endblock %}

{% block content %}
<div class="page-header">
  <h1 class="page-title">{{ session_name }}</h1>
  <p class="page-sub">Adjust or swap exercises, then start</p>
</div>

<form method="post" action="{% url 'gym_program_start' %}">
  {% csrf_token %}
  <input type="hidden" name="name" value="{{ session_name }}">

  {% for item in exercises %}
  <div class="we-card" data-exercise-id="{{ item.exercise.id }}">
    <div class="we-name" style="display:flex;justify-content:space-between;align-items:center">
      <span class="we-name-text">
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
      </span>
      <button type="button" class="swap-btn" data-exercise-id="{{ item.exercise.id }}">⇄ Swap</button>
    </div>
    <div class="we-meta we-meta-text">{{ item.exercise.get_category_display }} · {{ item.exercise.get_equipment_display }}</div>
    <input type="hidden" name="exercise_id" value="{{ item.exercise.id }}">
    {% for s in item.sets %}
    <div class="preview-set-row">
      <span class="preview-set-label">Set {{ s.n }}</span>
      <input type="number" step="0.5" min="0"
             name="weight_{{ item.exercise.id }}_{{ s.n }}"
             value="{{ s.weight }}" class="preview-input">
      <span class="preview-sep">kg ×</span>
      <input type="number" min="1"
             name="reps_{{ item.exercise.id }}_{{ s.n }}"
             value="{{ s.reps }}" class="preview-input">
      <span class="preview-sep">reps</span>
    </div>
    {% endfor %}
    <div class="swap-panel" style="display:none">
      <div class="swap-panel-label">⇄ Alternatives — same muscles, different kit</div>
      <div class="swap-options-list"></div>
    </div>
  </div>
  {% endfor %}

  <button type="submit" class="btn btn-primary" style="margin-top:8px">▶ Start Session</button>
</form>
{% endblock %}

{% block scripts %}
<script>
// Embed a swap URL template: replaces the 0 placeholder with any exercise ID
const SWAP_URL_TPL = "{% url 'gym_program_swap' 0 %}";

function getSwapUrl(exerciseId) {
  return SWAP_URL_TPL.replace('/0/', '/' + exerciseId + '/');
}

document.querySelectorAll('.swap-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    const card = btn.closest('.we-card');
    const panel = card.querySelector('.swap-panel');
    const exerciseId = card.getAttribute('data-exercise-id');

    if (panel.style.display !== 'none') {
      panel.style.display = 'none';
      return;
    }

    fetch(getSwapUrl(exerciseId))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        const list = panel.querySelector('.swap-options-list');
        list.innerHTML = '';
        if (!data.alternatives || data.alternatives.length === 0) {
          list.innerHTML = '<p style="font-size:11px;color:var(--text-sec)">No alternatives found.</p>';
        } else {
          data.alternatives.forEach(function (alt) {
            const div = document.createElement('div');
            div.className = 'swap-option';
            div.innerHTML =
              '<div><div class="swap-option-name">' + alt.name + '</div>' +
              '<div class="swap-option-meta">' + alt.equipment + ' · ' + alt.movement_type + '</div></div>' +
              '<button type="button" class="swap-use-btn" data-id="' + alt.id + '" data-name="' + alt.name + '" data-eq="' + alt.equipment + '">Use</button>';
            list.appendChild(div);
          });
          list.querySelectorAll('.swap-use-btn').forEach(function (useBtn) {
            useBtn.addEventListener('click', function () {
              const newId = useBtn.getAttribute('data-id');
              const newName = useBtn.getAttribute('data-name');
              const newEq = useBtn.getAttribute('data-eq');
              const oldId = exerciseId;

              // Update card data attribute
              card.setAttribute('data-exercise-id', newId);

              // Update exercise_id hidden input
              card.querySelector('input[name="exercise_id"]').value = newId;

              // Rename weight/reps inputs
              card.querySelectorAll('input[name^="weight_' + oldId + '_"]').forEach(function (inp) {
                inp.name = inp.name.replace('weight_' + oldId + '_', 'weight_' + newId + '_');
              });
              card.querySelectorAll('input[name^="reps_' + oldId + '_"]').forEach(function (inp) {
                inp.name = inp.name.replace('reps_' + oldId + '_', 'reps_' + newId + '_');
              });

              // Update swap button's data attribute for future swaps
              btn.setAttribute('data-exercise-id', newId);

              // Update displayed name and meta
              const nameSpan = card.querySelector('.we-name-text');
              // Replace text node (first child) — keep the badge span
              const badge = nameSpan.querySelector('span');
              nameSpan.textContent = newName + ' ';
              if (badge) nameSpan.appendChild(badge);

              card.querySelector('.we-meta-text').textContent = newEq;

              panel.style.display = 'none';
            });
          });
        }
        panel.style.display = 'block';
      })
      .catch(function () {
        panel.querySelector('.swap-options-list').innerHTML =
          '<p style="font-size:11px;color:#EF4444">Failed to load alternatives.</p>';
        panel.style.display = 'block';
      });
  });
});
</script>
{% endblock %}
```

- [ ] **Step 4: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 97 tests pass.

- [ ] **Step 5: Commit**

```bash
git add templates/workouts/log_home.html templates/workouts/program_days.html templates/workouts/program_preview.html
git commit -m "feat: program list on log home, day picker, preview with swap"
```

---

## Final Verification

- [ ] Start the server: `source venv/bin/activate && python manage.py runserver`
- [ ] Open `http://localhost:8000/gym-2026-private/log/`
- [ ] Verify "📋 Programs" section shows all 5 programs
- [ ] Tap PPL → 3 days shown (Push / Pull / Legs)
- [ ] Tap Push → preview screen with Bench Press, Incline DB Press, etc. pre-filled
- [ ] Tap "⇄ Swap" on Bench Press → alternatives panel appears showing dumbbell/machine/cable Chest exercises
- [ ] Tap "Use" on an alternative → card updates, panel closes
- [ ] Tap "▶ Start Session" → redirects to active session with sets logged
- [ ] Check 5x5 Workout A: Squat shows 5 sets × 5 reps
- [ ] Verify all 97 tests pass: `pytest tests/ -v`
