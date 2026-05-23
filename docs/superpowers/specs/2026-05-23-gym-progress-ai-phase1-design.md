# Gym Progress AI — Phase 1 Foundation Design

**Date:** 2026-05-23  
**Phase:** 1 of 6 — Foundation  
**Status:** Approved

---

## Overview

Phase 1 delivers a working Django application with PIN-protected access, a dark hero-layout dashboard shell, an exercise library with seed data, and Django admin. No AI, no workout logging, no charts — those come in later phases. The goal is a deployable foundation that looks and feels like the finished app.

**Build environment:** Local machine (Python 3.10+, PostgreSQL, Ollama already installed). Deploy to DigitalOcean VPS in a later phase.

---

## 1. Architecture

### Project Structure

```
gym_progress_ai/           ← Django project root (at /home/abhishek/abhi/gym/)
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
├── gym_progress_ai/       ← project config package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                  ← PIN middleware, dashboard shell
│   ├── __init__.py
│   ├── middleware.py
│   ├── views.py
│   ├── urls.py
│   └── forms.py
├── workouts/              ← Exercise models, admin, seed data
│   ├── __init__.py
│   ├── models.py
│   ├── admin.py
│   ├── urls.py
│   └── fixtures/
│       └── exercises.json
├── templates/
│   ├── base.html
│   ├── core/
│   │   ├── pin.html
│   │   └── dashboard.html
│   └── workouts/
│       └── exercises.html
└── static/
    └── css/
        └── app.css
```

**Phase 1 apps (lean start):**
- `core` — PIN middleware, session verification, dashboard shell view
- `workouts` — Exercise and ExerciseAlias models, admin configuration, seed fixture

**Deferred to later phases:** `ai_coach` (Phase 6), `progress` (Phase 4)

### Python Packages (Phase 1)

```
Django
psycopg[binary]
python-dotenv
whitenoise
bcrypt
```

---

## 2. Environment Configuration

`.env` file at project root:

```env
DJANGO_SECRET_KEY=replace_with_secure_key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

DATABASE_NAME=gym_progress_ai
DATABASE_USER=gym_user
DATABASE_PASSWORD=replace_with_secure_password
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432

GYM_SECRET_PATH=gym-2026-private
GYM_PIN_HASH=replace_with_bcrypt_hashed_pin
GYM_SESSION_TIMEOUT_HOURS=24
```

The PIN hash is generated with bcrypt before first run. The secret path controls all URL prefixes.

---

## 3. Access Control

### URL Structure

All user-facing routes are nested under the secret path:

| URL | View | Purpose |
|---|---|---|
| `/<secret>/` | redirect | → PIN if unverified, → dashboard if verified |
| `/<secret>/pin/` | `core.views.pin` | PIN entry with number-pad form |
| `/<secret>/dashboard/` | `core.views.dashboard` | Hero dashboard shell |
| `/<secret>/exercises/` | `workouts.views.exercises` | Read-only exercise library |
| `/admin/` | Django admin | Manage exercises, aliases, seed data |

### PIN Flow

1. `PinMiddleware` intercepts all requests under `/<secret>/`
2. Checks `request.session["gym_pin_verified"] == True`
3. Also checks `gym_pin_verified_at` against `GYM_SESSION_TIMEOUT_HOURS`
4. If not verified or expired → redirect to `/<secret>/pin/`
5. User enters PIN via number-pad form
6. Django hashes submitted PIN with bcrypt and compares to `GYM_PIN_HASH`
7. If correct → set session vars, redirect to dashboard
8. If incorrect → re-render PIN screen with error message (no lockout for MVP)

```python
# Session variables set on success
request.session["gym_pin_verified"] = True
request.session["gym_pin_verified_at"] = timezone.now().isoformat()
```

Django admin (`/admin/`) is excluded from the PIN middleware — it uses Django's own superuser auth.

---

## 4. Data Models

### Exercise

```python
class Exercise(models.Model):
    CATEGORY_CHOICES = [
        ("push", "Push"),
        ("pull", "Pull"),
        ("legs", "Legs"),
        ("upper_arms", "Upper/Arms"),
        ("conditioning_abs", "Conditioning/Abs"),
    ]
    EQUIPMENT_CHOICES = [
        ("barbell", "Barbell"), ("dumbbell", "Dumbbell"),
        ("machine", "Machine"), ("cable", "Cable"), ("bodyweight", "Bodyweight"),
    ]
    MOVEMENT_CHOICES = [
        ("compound", "Compound"), ("isolation", "Isolation"),
        ("cardio", "Cardio"), ("core", "Core"),
    ]

    name              = CharField(max_length=100, unique=True)
    muscle_group      = CharField(max_length=50)
    category          = CharField(max_length=20, choices=CATEGORY_CHOICES)
    equipment         = CharField(max_length=20, choices=EQUIPMENT_CHOICES)
    movement_type     = CharField(max_length=20, choices=MOVEMENT_CHOICES)
    default_min_reps  = PositiveIntegerField(default=8)
    default_max_reps  = PositiveIntegerField(default=12)
    default_sets      = PositiveIntegerField(default=3)
    default_increment = DecimalField(max_digits=4, decimal_places=1, default=2.5)
    is_active         = BooleanField(default=True)
    created_at        = DateTimeField(auto_now_add=True)
    updated_at        = DateTimeField(auto_now=True)
```

### ExerciseAlias

```python
class ExerciseAlias(models.Model):
    exercise   = ForeignKey(Exercise, on_delete=CASCADE, related_name="aliases")
    alias      = CharField(max_length=100)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("exercise", "alias")]
```

### Seed Data

`workouts/fixtures/exercises.json` contains ~35 exercises across all 5 categories with their default aliases. Loaded via `python manage.py loaddata exercises`.

**Categories covered:**
- **Push:** Bench Press, Incline DB Press, DB Shoulder Press, Machine Chest Press, Cable Fly, Lateral Raise, Tricep Pushdown, Overhead Tricep Extension
- **Pull:** Lat Pulldown, Pull-up, Seated Cable Row, Chest-supported Row, Dumbbell Row, Face Pull, Barbell Curl, Dumbbell Curl, Hammer Curl
- **Legs:** Squat, Leg Press, Romanian Deadlift, Leg Curl, Leg Extension, Walking Lunge, Calf Raise
- **Upper/Arms:** Incline DB Press, Machine Row, Lateral Raise, Rear Delt Fly, Barbell Curl, Rope Pushdown, Hammer Curl, Skull Crusher
- **Conditioning/Abs:** Treadmill Incline Walk, Bike, Rowing Machine, Cable Crunch, Hanging Knee Raise, Plank, Ab Wheel

### Admin Configuration

- `ExerciseAdmin` — list display: name, category, equipment, movement_type, is_active; search by name; filter by category, equipment, is_active; inline alias editor
- `ExerciseAliasAdmin` — inline only (shown within Exercise admin)

---

## 5. Dark UI Theme

### Color Palette

| Token | Hex | Usage |
|---|---|---|
| Background | `#070A0F` | Page background |
| Card | `#111827` | Primary cards, nav bar |
| Card secondary | `#1F2937` | Input fields, secondary cards |
| Border | `#374151` | Card borders, dividers |
| Text primary | `#F9FAFB` | Headings, body |
| Text secondary | `#9CA3AF` | Labels, subtitles |
| Text muted | `#6B7280` | Micro labels |
| Accent | `#22C55E` | CTA buttons, hero text, FAB, active nav |
| Danger | `#EF4444` | Delete, errors |
| Warning / PR | `#F59E0B` | Personal records, warnings |

### Key Components (app.css)

- **Cards:** `border-radius: 12-14px`, `border: 1px solid #374151`, dark backgrounds
- **PIN keypad:** 3×4 grid, large tap targets (min 52px), `#1F2937` keys
- **Primary button:** `background: #22C55E`, `color: #070A0F`, `border-radius: 10px`, bold
- **Secondary button:** `background: #1F2937`, `border: 1px solid #374151`
- **FAB:** `52px` circle, `#22C55E`, fixed bottom-right, `box-shadow: 0 4px 16px #22C55E55`
- **Bottom nav:** 5 items, `#111827` background, `#22C55E` active state
- **Inputs:** `background: #1F2937`, `border: 1px solid #374151`, focus → `border-color: #22C55E`

### PIN Screen Layout

Number-pad style (not a text input): 4 dots showing entry progress, 3×4 grid of digit keys, backspace key. No keyboard shown — mobile-native feel.

### Dashboard Layout (Layout C — Hero + FAB)

```
┌─────────────────────────────┐
│ GYM AI              [● online]│  ← header
├─────────────────────────────┤
│                             │
│  Today's Workout        [badge]
│  Pull Day                   │  ← hero card (#0D1117, green border)
│  Push done 2 days ago       │
│                             │
│  OVERLOAD SUGGESTIONS       │
│  ┌─────────────────────┐    │
│  │ Bench Press  Stay 60kg│  │  ← overload card
│  │ Lat Pulldown  ↑57.5kg│  │
│  └─────────────────────┘    │
│                        [FAB+]│  ← floating action button
│                             │
├─────────────────────────────┤
│ ⊞Home  ✎Log  ◎Coach  ↗Prog  ☰│  ← bottom nav
└─────────────────────────────┘
```

Dashboard in Phase 1 shows "No workout logged yet" state for hero card and "No data yet" for overload card. These become live in Phase 2+.

---

## 6. Phase 1 Acceptance Criteria

1. `python manage.py runserver` starts without errors
2. Visiting `http://localhost:8000/<secret>/` redirects to PIN screen if session is empty
3. Wrong PIN shows error, does not redirect
4. Correct PIN redirects to dashboard with hero card layout
5. Dashboard renders correctly on a 375px mobile viewport
6. `http://localhost:8000/<secret>/exercises/` shows the exercise library
7. All ~35 exercises visible and manageable in Django admin
8. Session expires correctly after `GYM_SESSION_TIMEOUT_HOURS`

---

## 7. What Phase 1 Does NOT Include

- Workout logging (Phase 2)
- Natural language parsing (Phase 3)
- PR detection (Phase 4)
- Progressive overload engine (Phase 5)
- AI coach / Ollama integration (Phase 6)
- Deployment to VPS (after Phase 1 is working locally)

---

## 8. Build Sequence (Phase 1)

1. Create PostgreSQL database and user
2. Scaffold Django project with `core` and `workouts` apps
3. Configure settings, `.env`, database connection
4. Implement `PinMiddleware` and PIN view
5. Write `Exercise` and `ExerciseAlias` models + migrations
6. Configure Django admin with inline aliases
7. Write `app.css` with full dark theme
8. Build `base.html`, `pin.html`, `dashboard.html`, `exercises.html`
9. Create `exercises.json` fixture with all ~35 seed exercises + aliases
10. Load fixture and verify admin
11. Verify all acceptance criteria

---

*Next phase: Phase 2 — Workout Logging (WorkoutSession, WorkoutExercise, WorkoutSet models, manual log form, history page, session detail)*
