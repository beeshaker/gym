# Program Preview Chat + Rest Timer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a free-form Ollama AI chat panel (floating bubble) to the program preview screen, and an auto-starting rest timer overlay on the active session screen with rest duration set per-exercise on the preview.

**Architecture:** `WorkoutExercise` gets a nullable `planned_rest_seconds` field saved from preview form POST. `add_set` redirects to `active_session?timer=<we_id>` to trigger the countdown. A new `POST /programs/<day_id>/chat/` endpoint powers the chat panel using Ollama's `/api/chat` with full conversation history sent client-side each request.

**Tech Stack:** Django 4.2, PostgreSQL, pytest-django, vanilla JS, Ollama (`qwen2.5:1.5b`).

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `workouts/models.py` | Modify | Add `planned_rest_seconds` to `WorkoutExercise` |
| `workouts/migrations/` | Create | Migration for new field |
| `workouts/coach.py` | Modify | Add `OLLAMA_CHAT_URL` + `get_program_chat_reply` |
| `workouts/views.py` | Modify | Update import; update `_create_session_from_form`; update `add_set`; add `program_chat` view |
| `core/urls.py` | Modify | Add `gym_program_chat` URL |
| `static/css/app.css` | Modify | Append rest presets + chat panel + timer overlay styles |
| `templates/workouts/program_preview.html` | Modify | Add `data-movement-type`; rest preset row per exercise; floating chat button + overlay + JS |
| `templates/workouts/active_session.html` | Modify | Add data attrs to `.we-card`; add timer overlay HTML + auto-start JS |
| `tests/test_rest_timer.py` | Create | 4 tests for model field + form behaviour + redirect |
| `tests/test_program_chat.py` | Create | 5 tests for chat endpoint |

---

## Task 1: `WorkoutExercise.planned_rest_seconds` Model Field

**Files:**
- Modify: `workouts/models.py`
- Create: migration (auto-generated)
- Create: `tests/test_rest_timer.py`

- [ ] **Step 1: Create `tests/test_rest_timer.py` with failing tests**

```python
import pytest
from django.urls import reverse

from workouts.models import (
    Exercise, Program, ProgramDay, ProgramExercise,
    WorkoutExercise, WorkoutSession,
)


def make_exercise(name='Bench Press', muscle_group='Chest',
                  category='push', equipment='barbell', movement_type='compound'):
    return Exercise.objects.create(
        name=name, muscle_group=muscle_group, category=category,
        equipment=equipment, movement_type=movement_type,
    )


@pytest.mark.django_db
def test_program_start_saves_planned_rest_seconds(verified_client):
    ex = make_exercise()
    verified_client.post(reverse('gym_program_start'), {
        'name': 'Monday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60',
        f'reps_{ex.id}_1': '10',
        f'rest_{ex.id}': '90',
    })
    we = WorkoutExercise.objects.get(session__name='Monday Push')
    assert we.planned_rest_seconds == 90


@pytest.mark.django_db
def test_program_start_without_rest_field_saves_none(verified_client):
    ex = make_exercise()
    verified_client.post(reverse('gym_program_start'), {
        'name': 'Tuesday Push',
        'exercise_id': [str(ex.id)],
        f'weight_{ex.id}_1': '60',
        f'reps_{ex.id}_1': '10',
    })
    we = WorkoutExercise.objects.get(session__name='Tuesday Push')
    assert we.planned_rest_seconds is None


@pytest.mark.django_db
def test_add_set_redirect_includes_timer_param(verified_client):
    session = WorkoutSession.objects.create(name='Test', status='active')
    ex = make_exercise()
    we = WorkoutExercise.objects.create(session=session, exercise=ex, order=1)
    response = verified_client.post(
        reverse('gym_add_set', args=[session.id, we.id]),
        {'weight_kg': '60', 'reps': '10'},
    )
    assert response.status_code == 302
    assert f'timer={we.id}' in response['Location']


@pytest.mark.django_db
def test_add_exercise_quick_log_planned_rest_is_null(verified_client):
    session = WorkoutSession.objects.create(name='Quick', status='active')
    ex = make_exercise()
    verified_client.post(
        reverse('gym_add_exercise', args=[session.id]),
        {'exercise_id': str(ex.id)},
    )
    we = WorkoutExercise.objects.get(session=session)
    assert we.planned_rest_seconds is None
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_rest_timer.py -v
```

Expected: `AttributeError: type object 'WorkoutExercise' has no attribute 'planned_rest_seconds'` (or migration error).

- [ ] **Step 3: Add `planned_rest_seconds` to `WorkoutExercise` in `workouts/models.py`**

Read the file first. Find the `WorkoutExercise` class (line 76) and add the field after `order`:

Change:
```python
class WorkoutExercise(models.Model):
    session  = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='workout_exercises')
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name='workout_exercises')
    order    = models.PositiveIntegerField(default=0)
```
To:
```python
class WorkoutExercise(models.Model):
    session               = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='workout_exercises')
    exercise              = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name='workout_exercises')
    order                 = models.PositiveIntegerField(default=0)
    planned_rest_seconds  = models.PositiveIntegerField(null=True, blank=True)
```

- [ ] **Step 4: Generate and apply migration**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && python manage.py makemigrations workouts && python manage.py migrate
```

Expected: `Migrations for 'workouts': workouts/migrations/0005_workoutexercise_planned_rest_seconds.py` then `Applying workouts.0005... OK`.

- [ ] **Step 5: Run tests — expect 2 pass, 2 fail**

```bash
pytest tests/test_rest_timer.py -v
```

Expected: `test_add_set_redirect_includes_timer_param` FAILS (redirect still bare URL), `test_program_start_saves_planned_rest_seconds` FAILS (`_create_session_from_form` doesn't read `rest_` yet). The two null-checks should PASS.

- [ ] **Step 6: Commit**

```bash
git add workouts/models.py workouts/migrations/0005_workoutexercise_planned_rest_seconds.py tests/test_rest_timer.py
git commit -m "feat: planned_rest_seconds on WorkoutExercise + failing rest timer tests"
```

---

## Task 2: Wire Rest Time into `_create_session_from_form` + `add_set` Redirect

**Files:**
- Modify: `workouts/views.py`

- [ ] **Step 1: Update `_create_session_from_form` to read `rest_<ex_id>` from POST**

Read `workouts/views.py`. Find `_create_session_from_form`. Change the `WorkoutExercise.objects.create` call from:

```python
            we = WorkoutExercise.objects.create(
                session=session, exercise=exercise, order=order
            )
```
To:
```python
            try:
                rest_val = int(request.POST.get(f'rest_{ex_id}', ''))
                if rest_val <= 0:
                    rest_val = None
            except (ValueError, TypeError):
                rest_val = None
            we = WorkoutExercise.objects.create(
                session=session, exercise=exercise, order=order,
                planned_rest_seconds=rest_val,
            )
```

- [ ] **Step 2: Update `add_set` to redirect with `?timer=<we_id>`**

Read `workouts/views.py`. Find `add_set`. Change the final redirect from:

```python
    WorkoutSet.objects.create(workout_exercise=we, set_number=set_number, weight_kg=weight_kg, reps=reps)
    return redirect('gym_active_session', session_id=session.id)
```
To:
```python
    WorkoutSet.objects.create(workout_exercise=we, set_number=set_number, weight_kg=weight_kg, reps=reps)
    from django.http import HttpResponseRedirect
    from django.urls import reverse as _reverse
    url = _reverse('gym_active_session', kwargs={'session_id': session.id})
    return HttpResponseRedirect(f'{url}?timer={we_id}')
```

- [ ] **Step 3: Run rest timer tests — all 4 pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_rest_timer.py -v
```

Expected: 4 tests pass.

- [ ] **Step 4: Run full suite — no regressions**

```bash
pytest tests/ -q
```

Expected: 101 tests pass (97 existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add workouts/views.py
git commit -m "feat: save planned_rest_seconds from form, add_set redirects with ?timer=<we_id>"
```

---

## Task 3: AI Chat — `get_program_chat_reply` + View + URL + Tests

**Files:**
- Create: `tests/test_program_chat.py`
- Modify: `workouts/coach.py`
- Modify: `workouts/views.py`
- Modify: `core/urls.py`

- [ ] **Step 1: Create `tests/test_program_chat.py` with failing tests**

```python
import json
import pytest
from unittest.mock import patch
from django.urls import reverse

from workouts.models import Exercise, Program, ProgramDay, ProgramExercise
from workouts.coach import CoachError


def make_exercise(name='Bench Press', muscle_group='Chest',
                  category='push', equipment='barbell'):
    return Exercise.objects.create(
        name=name, muscle_group=muscle_group, category=category,
        equipment=equipment, movement_type='compound',
    )


def make_program_with_day(exercise):
    prog = Program.objects.create(name='Test Program', description='', is_active=True)
    day = ProgramDay.objects.create(program=prog, name='Push', order=1)
    ProgramExercise.objects.create(program_day=day, exercise=exercise, order=1)
    return prog, day


@pytest.mark.django_db
def test_program_chat_valid_message_returns_reply(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    with patch('workouts.views.get_program_chat_reply', return_value='Rest 90 seconds.'):
        response = verified_client.post(
            reverse('gym_program_chat', args=[day.id]),
            data=json.dumps({'message': 'How long should I rest?', 'history': []}),
            content_type='application/json',
        )
    assert response.status_code == 200
    assert json.loads(response.content)['reply'] == 'Rest 90 seconds.'


@pytest.mark.django_db
def test_program_chat_missing_message_returns_400(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    response = verified_client.post(
        reverse('gym_program_chat', args=[day.id]),
        data=json.dumps({'history': []}),
        content_type='application/json',
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_program_chat_inactive_program_returns_404(verified_client):
    ex = make_exercise()
    prog = Program.objects.create(name='Inactive', description='', is_active=False)
    day = ProgramDay.objects.create(program=prog, name='Day 1', order=1)
    ProgramExercise.objects.create(program_day=day, exercise=ex, order=1)
    response = verified_client.post(
        reverse('gym_program_chat', args=[day.id]),
        data=json.dumps({'message': 'hello'}),
        content_type='application/json',
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_program_chat_coach_error_returns_422(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    with patch('workouts.views.get_program_chat_reply', side_effect=CoachError('timeout')):
        response = verified_client.post(
            reverse('gym_program_chat', args=[day.id]),
            data=json.dumps({'message': 'hello'}),
            content_type='application/json',
        )
    assert response.status_code == 422
    assert 'error' in json.loads(response.content)


@pytest.mark.django_db
def test_program_chat_get_returns_405(verified_client):
    ex = make_exercise()
    _, day = make_program_with_day(ex)
    response = verified_client.get(reverse('gym_program_chat', args=[day.id]))
    assert response.status_code == 405
```

- [ ] **Step 2: Run tests — expect NoReverseMatch failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_program_chat.py -v
```

Expected: `NoReverseMatch` for `gym_program_chat`.

- [ ] **Step 3: Add `OLLAMA_CHAT_URL` and `get_program_chat_reply` to `workouts/coach.py`**

Read `workouts/coach.py`. Add `OLLAMA_CHAT_URL` constant after the existing `OLLAMA_TIMEOUT` line:

```python
OLLAMA_CHAT_URL = 'http://localhost:11434/api/chat'
```

Then append the new function at the end of `coach.py`:

```python
def get_program_chat_reply(program_name, day_name, context_lines, history, question):
    """
    program_name: str
    day_name: str
    context_lines: list of str, one per exercise
    history: list of {role, content} dicts from prior turns
    question: str — the user's latest message
    Returns: reply string
    Raises CoachError on any Ollama failure.
    """
    system_content = (
        f'You are a strength training coach. '
        f'The user is about to start {program_name} — {day_name}. '
        f"Today’s exercises:\n" + '\n'.join(context_lines) + '\n\n'
        'Answer questions about rest periods, exercise swaps, and progressive overload. '
        'Be concise and practical. Use plain text, no markdown.'
    )
    messages = [{'role': 'system', 'content': system_content}]
    for turn in history:
        if turn.get('role') in ('user', 'assistant') and turn.get('content'):
            messages.append({'role': turn['role'], 'content': str(turn['content'])})
    messages.append({'role': 'user', 'content': question})

    try:
        resp = requests.post(
            OLLAMA_CHAT_URL,
            json={'model': OLLAMA_MODEL, 'messages': messages, 'stream': False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise CoachError('Ollama timed out')
    except requests.exceptions.RequestException as e:
        raise CoachError(f'Ollama request failed: {e}')

    try:
        data = resp.json()
        reply = data['message']['content']
    except (KeyError, ValueError, TypeError):
        raise CoachError('Ollama returned invalid response')

    if not reply:
        raise CoachError('Ollama returned empty reply')
    return reply
```

- [ ] **Step 4: Update the import in `workouts/views.py`**

Read `workouts/views.py`. Change the coach import line from:

```python
from .coach import CoachError, get_ollama_tips, recommend
```
To:
```python
from .coach import CoachError, get_ollama_tips, get_program_chat_reply, recommend
```

- [ ] **Step 5: Add `program_chat` view at the end of `workouts/views.py`**

Append after the last view function:

```python
@require_http_methods(['POST'])
def program_chat(request, day_id):
    day = get_object_or_404(
        ProgramDay.objects.select_related('program'),
        id=day_id,
        program__is_active=True,
    )
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid JSON'}, status=400)
    message = body.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'message required'}, status=400)
    history = body.get('history', [])

    program_exercises = day.exercises.select_related('exercise').order_by('order')
    context_lines = [
        f'- {pe.exercise.name} ({pe.exercise.get_movement_type_display()}, '
        f'{pe.exercise.get_equipment_display()})'
        for pe in program_exercises
    ]

    try:
        reply = get_program_chat_reply(
            day.program.name, day.name, context_lines, history, message
        )
    except CoachError as e:
        return JsonResponse(
            {'error': str(e) or 'Coach unavailable — try again'},
            status=422,
        )
    return JsonResponse({'reply': reply})
```

- [ ] **Step 6: Add URL to `core/urls.py`**

Read `core/urls.py`. After the `gym_program_swap` line, add:

```python
    path('programs/<int:day_id>/chat/', workout_views.program_chat, name='gym_program_chat'),
```

- [ ] **Step 7: Run chat tests — all 5 pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_program_chat.py -v
```

Expected: 5 tests pass.

- [ ] **Step 8: Run full suite**

```bash
pytest tests/ -q
```

Expected: 106 tests pass (101 + 5).

- [ ] **Step 9: Commit**

```bash
git add workouts/coach.py workouts/views.py core/urls.py tests/test_program_chat.py
git commit -m "feat: program preview AI chat endpoint with Ollama conversation support"
```

---

## Task 4: CSS — Rest Presets + Chat Panel + Timer Overlay

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 1: Append styles to `static/css/app.css`**

Read the end of the file to confirm the last line, then append:

```css
/* ── Rest presets (program preview) ─────────────────────────────── */
.rest-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.rest-row-label {
  font-size: 10px;
  color: var(--text-sec);
  flex-shrink: 0;
}

.rest-preset-btn {
  font-size: 10px;
  color: var(--text-sec);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 3px 9px;
  background: transparent;
  cursor: pointer;
}

.rest-preset-btn.active {
  color: var(--accent);
  border-color: rgba(34,197,94,0.5);
  background: rgba(34,197,94,0.08);
}

/* ── Coach chat bubble + overlay ─────────────────────────────────── */
.coach-bubble {
  position: fixed;
  bottom: 72px;
  right: 16px;
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 24px;
  padding: 10px 16px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  z-index: 200;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}

.coach-overlay {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 62%;
  background: var(--bg-soft, #0f1a2e);
  border-top: 1px solid var(--border);
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
  z-index: 300;
  transform: translateY(100%);
  transition: transform 0.25s ease;
}

.coach-overlay.open {
  transform: translateY(0);
}

.coach-overlay-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.coach-overlay-close {
  background: transparent;
  border: none;
  color: var(--text-sec);
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
}

.coach-chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.coach-msg-user,
.coach-msg-ai {
  max-width: 85%;
  font-size: 12px;
  line-height: 1.5;
  padding: 7px 11px;
  border-radius: 10px;
}

.coach-msg-user {
  align-self: flex-end;
  background: var(--accent);
  color: #000;
  border-bottom-right-radius: 3px;
}

.coach-msg-ai {
  align-self: flex-start;
  background: var(--card);
  border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
}

.coach-msg-ai.error { color: #EF4444; }

.coach-chat-input-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.coach-chat-input {
  flex: 1;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 12px;
  padding: 8px 10px;
}

.coach-send-btn {
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  flex-shrink: 0;
}

.coach-send-btn:disabled { opacity: 0.5; cursor: default; }

/* ── Rest timer overlay ───────────────────────────────────────────── */
.timer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(7,17,31,0.96);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 400;
}

.timer-exercise-name {
  font-size: 12px;
  color: var(--text-sec);
  margin-bottom: 8px;
  text-align: center;
  padding: 0 20px;
}

.timer-countdown {
  font-size: 72px;
  font-weight: 800;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
  line-height: 1;
  margin-bottom: 28px;
}

.timer-presets {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  justify-content: center;
}

.timer-preset-btn {
  font-size: 11px;
  color: var(--text-sec);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 12px;
  background: var(--card);
  cursor: pointer;
}

.timer-skip-btn {
  font-size: 12px;
  color: var(--text-sec);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 24px;
  cursor: pointer;
}
```

- [ ] **Step 2: Run full suite — no regressions**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -q
```

Expected: 106 tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "feat: CSS for rest presets, coach chat panel, and timer overlay"
```

---

## Task 5: Program Preview Template — Rest Presets + Chat Overlay

**Files:**
- Modify: `templates/workouts/program_preview.html`

- [ ] **Step 1: Add `data-movement-type` to each exercise card and rest preset row**

Read `templates/workouts/program_preview.html`. Make the following changes:

**A)** Change the opening `.we-card` div from:

```html
  <div class="we-card" data-exercise-id="{{ item.exercise.id }}">
```
To:
```html
  <div class="we-card" data-exercise-id="{{ item.exercise.id }}" data-movement-type="{{ item.exercise.movement_type }}">
```

**B)** Add the rest preset row + hidden input inside each `.we-card`, immediately before the closing `</div>` of the swap panel (i.e. after `<div class="swap-panel" style="display:none">...</div>`). Insert between the swap panel and the closing `</div>` of `.we-card`:

```html
    <div class="rest-row">
      <span class="rest-row-label">Rest:</span>
      <button type="button" class="rest-preset-btn" data-seconds="60">60s</button>
      <button type="button" class="rest-preset-btn" data-seconds="90">90s</button>
      <button type="button" class="rest-preset-btn" data-seconds="120">2min</button>
      <button type="button" class="rest-preset-btn" data-seconds="180">3min</button>
    </div>
    <input type="hidden" name="rest_{{ item.exercise.id }}" class="rest-hidden" value="">
```

- [ ] **Step 2: Add floating coach button and chat overlay after the closing `</form>` tag**

After `</form>` and before `{% endblock %}`, add:

```html
<button type="button" class="coach-bubble" id="coach-bubble-btn">✦ Ask Coach</button>

<div class="coach-overlay" id="coach-overlay">
  <div class="coach-overlay-header">
    <span>Coach — {{ day.name }}</span>
    <button type="button" class="coach-overlay-close" id="coach-overlay-close">✕</button>
  </div>
  <div class="coach-chat-history" id="coach-chat-history"></div>
  <div class="coach-chat-input-row">
    <input type="text" class="coach-chat-input" id="coach-chat-input"
           placeholder="Ask about rest, swaps, overload…">
    <button type="button" class="coach-send-btn" id="coach-send-btn">Send</button>
  </div>
</div>
```

- [ ] **Step 3: Add JS to `{% block scripts %}` in `program_preview.html`**

The `{% block scripts %}` already contains the swap panel JS. Add the following **after** the closing `</script>` of the existing swap block (i.e. as additional JS in the same block, or in a new `<script>` tag):

```html
<script>
// ── Rest presets ─────────────────────────────────────────────────
const REST_DEFAULTS = { compound: 180, isolation: 90, cardio: 60 };

document.querySelectorAll('.we-card').forEach(function (card) {
  const mt = card.getAttribute('data-movement-type');
  const def = REST_DEFAULTS[mt] || 90;
  const btn = card.querySelector('.rest-preset-btn[data-seconds="' + def + '"]');
  if (btn) {
    btn.classList.add('active');
    card.querySelector('.rest-hidden').value = def;
  }
});

document.querySelectorAll('.rest-preset-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    const card = btn.closest('.we-card');
    card.querySelectorAll('.rest-preset-btn').forEach(function (b) {
      b.classList.remove('active');
    });
    btn.classList.add('active');
    card.querySelector('.rest-hidden').value = btn.getAttribute('data-seconds');
  });
});

// ── Coach chat overlay ───────────────────────────────────────────
const CHAT_URL = "{% url 'gym_program_chat' day.id %}";
const CSRF_TOKEN = '{{ csrf_token }}';
let chatHistory = [];

document.getElementById('coach-bubble-btn').addEventListener('click', function () {
  document.getElementById('coach-overlay').classList.add('open');
  document.getElementById('coach-chat-input').focus();
});

document.getElementById('coach-overlay-close').addEventListener('click', function () {
  document.getElementById('coach-overlay').classList.remove('open');
  chatHistory = [];
  document.getElementById('coach-chat-history').innerHTML = '';
});

function appendMsg(text, role) {
  const div = document.createElement('div');
  div.className = role === 'user' ? 'coach-msg-user' : 'coach-msg-ai';
  div.textContent = text;
  const history = document.getElementById('coach-chat-history');
  history.appendChild(div);
  history.scrollTop = history.scrollHeight;
  return div;
}

document.getElementById('coach-send-btn').addEventListener('click', sendChat);
document.getElementById('coach-chat-input').addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function sendChat() {
  const input = document.getElementById('coach-chat-input');
  const sendBtn = document.getElementById('coach-send-btn');
  const message = input.value.trim();
  if (!message) return;

  appendMsg(message, 'user');
  chatHistory.push({ role: 'user', content: message });
  input.value = '';
  sendBtn.textContent = '…';
  sendBtn.disabled = true;

  fetch(CHAT_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
    body: JSON.stringify({ message: message, history: chatHistory.slice(0, -1) }),
  })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      sendBtn.textContent = 'Send';
      sendBtn.disabled = false;
      if (!res.ok) {
        const el = appendMsg(res.data.error || 'Coach unavailable — try again', 'ai');
        el.classList.add('error');
        return;
      }
      const reply = res.data.reply || '';
      appendMsg(reply, 'ai');
      chatHistory.push({ role: 'assistant', content: reply });
    })
    .catch(function () {
      sendBtn.textContent = 'Send';
      sendBtn.disabled = false;
      const el = appendMsg('Request failed — check your connection', 'ai');
      el.classList.add('error');
    });
}
</script>
```

- [ ] **Step 4: Run full suite — no regressions**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -q
```

Expected: 106 tests pass.

- [ ] **Step 5: Commit**

```bash
git add templates/workouts/program_preview.html
git commit -m "feat: rest presets and AI chat overlay on program preview"
```

---

## Task 6: Active Session Template — Data Attrs + Timer Overlay

**Files:**
- Modify: `templates/workouts/active_session.html`

- [ ] **Step 1: Add data attributes to each `.we-card`**

Read `templates/workouts/active_session.html`. Change the opening `.we-card` div from:

```html
<div class="we-card">
```
To:
```html
<div class="we-card" data-we-id="{{ we.id }}" data-rest="{{ we.planned_rest_seconds|default:'' }}" data-movement-type="{{ we.exercise.movement_type }}" data-exercise-name="{{ we.exercise.name }}">
```

- [ ] **Step 2: Add the timer overlay HTML**

After the closing `</div>` of the exercise picker overlay (`</div>` that closes `picker-overlay`) and before `{% endblock %}`, add:

```html
<!-- Rest timer overlay -->
<div class="timer-overlay" id="timer-overlay" style="display:none">
  <div class="timer-exercise-name" id="timer-exercise-name"></div>
  <div class="timer-countdown" id="timer-countdown">0:00</div>
  <div class="timer-presets">
    <button type="button" class="timer-preset-btn" data-seconds="60">1 min</button>
    <button type="button" class="timer-preset-btn" data-seconds="90">90 s</button>
    <button type="button" class="timer-preset-btn" data-seconds="120">2 min</button>
    <button type="button" class="timer-preset-btn" data-seconds="180">3 min</button>
  </div>
  <button type="button" class="timer-skip-btn" id="timer-skip">Skip</button>
</div>
```

- [ ] **Step 3: Add timer JS to `{% block scripts %}`**

The active session `{% block scripts %}` already has picker + NL JS. Append inside the same block (as a new `<script>` tag after the existing one):

```html
<script>
// ── Rest timer ──────────────────────────────────────────────────
const REST_DEFAULTS_ACTIVE = { compound: 180, isolation: 90, cardio: 60 };
let timerInterval = null;
let timerRemaining = 0;

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m + ':' + (sec < 10 ? '0' : '') + sec;
}

function updateDisplay() {
  document.getElementById('timer-countdown').textContent = fmtTime(timerRemaining);
}

function startTimer(exerciseName, seconds) {
  clearInterval(timerInterval);
  timerRemaining = seconds;
  document.getElementById('timer-exercise-name').textContent =
    'Resting after ' + exerciseName;
  updateDisplay();
  document.getElementById('timer-overlay').style.display = 'flex';

  timerInterval = setInterval(function () {
    timerRemaining -= 1;
    updateDisplay();
    if (timerRemaining <= 0) {
      clearInterval(timerInterval);
      document.getElementById('timer-overlay').style.display = 'none';
      if (navigator.vibrate) { navigator.vibrate([200, 100, 200]); }
    }
  }, 1000);
}

function stopTimer() {
  clearInterval(timerInterval);
  document.getElementById('timer-overlay').style.display = 'none';
}

document.getElementById('timer-skip').addEventListener('click', stopTimer);

document.querySelectorAll('.timer-preset-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    const name = document.getElementById('timer-exercise-name').textContent
      .replace('Resting after ', '');
    startTimer(name, parseInt(btn.getAttribute('data-seconds'), 10));
  });
});

// Auto-start from ?timer=<we_id>
(function () {
  const params = new URLSearchParams(window.location.search);
  const weId = params.get('timer');
  if (!weId) return;
  const card = document.querySelector('.we-card[data-we-id="' + weId + '"]');
  if (!card) return;
  const restAttr = card.getAttribute('data-rest');
  let seconds = restAttr ? parseInt(restAttr, 10) : 0;
  if (!seconds || isNaN(seconds)) {
    const mt = card.getAttribute('data-movement-type');
    seconds = REST_DEFAULTS_ACTIVE[mt] || 90;
  }
  startTimer(card.getAttribute('data-exercise-name'), seconds);
})();
</script>
```

- [ ] **Step 4: Run full suite — no regressions**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -q
```

Expected: 106 tests pass.

- [ ] **Step 5: Commit**

```bash
git add templates/workouts/active_session.html
git commit -m "feat: auto-start rest timer overlay on active session after set logged"
```

---

## Final Verification

- [ ] Start the server: `source venv/bin/activate && python manage.py runserver 8001`
- [ ] Open a program day preview (e.g. PPL → Push)
- [ ] Verify rest preset buttons appear on each exercise card with compound exercises defaulting to 3min
- [ ] Tap a different preset — confirm it highlights and the hidden input value changes
- [ ] Tap "✦ Ask Coach" — overlay slides up
- [ ] Type "How long should I rest between sets of bench press?" — AI replies
- [ ] Type a follow-up ("What if I'm training for strength?") — AI uses conversation context
- [ ] Close overlay — history clears, form intact
- [ ] Hit "▶ Start Session" — redirects to active session
- [ ] Log a set on any exercise — timer overlay auto-appears with correct duration
- [ ] Tap a preset mid-countdown — timer resets to that duration
- [ ] Wait for timer to reach 0 — overlay dismisses + vibrates (on mobile)
- [ ] Tap Skip — overlay dismisses immediately
- [ ] Verify all 106 tests pass: `pytest tests/ -v`
