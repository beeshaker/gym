# Gym Progress AI — Phase 3 Natural Language Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a natural language text box to the active session screen so users can type "did bench press, 3 sets of 10 at 60kg" (or a full session dump) and have it parsed into WorkoutExercise + WorkoutSet records via a preview-then-confirm flow.

**Architecture:** Hybrid parser in `workouts/nl_parser.py` — rule-based fast path (regex + fuzzy matching) with Ollama/Qwen fallback. The `nl_parse` view returns JSON; the `nl_confirm` view creates DB records. No new models needed — Phase 2 models handle everything.

**Tech Stack:** Django 4.2, `requests` (new dependency), `difflib` (stdlib), Ollama running locally at `http://localhost:11434` with the `qwen` model.

---

## File Map

| File | Change | Purpose |
|---|---|---|
| `requirements.txt` | Modify | Add `requests>=2.31` |
| `workouts/nl_parser.py` | Create | Hybrid parser — rules + Ollama |
| `workouts/views.py` | Modify | Add `nl_parse`, `nl_confirm` views + imports |
| `core/urls.py` | Modify | Add 2 new URL patterns |
| `static/css/app.css` | Modify | Append NL UI styles |
| `templates/workouts/active_session.html` | Modify | Add text box, preview card, fetch JS |
| `tests/test_nl_parser.py` | Create | Unit tests for parser (Ollama mocked) |
| `tests/test_nl_views.py` | Create | HTTP tests for nl_parse + nl_confirm |

---

## Task 1: Parser Module + Parser Tests

**Files:**
- Create: `workouts/nl_parser.py`
- Create: `tests/test_nl_parser.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add `requests` to requirements and install it**

Append to `requirements.txt`:
```
requests>=2.31
```

Then install:
```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pip install requests>=2.31
```

Expected: `Successfully installed requests-...`

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_nl_parser.py`:

```python
import pytest
from unittest.mock import patch, Mock
import requests as req_lib

from workouts.nl_parser import parse, NLParseError


class FakeExercise:
    def __init__(self, name):
        self.name = name


EXERCISES = [
    FakeExercise('Bench Press'),
    FakeExercise('Incline DB Press'),
    FakeExercise('Tricep Pushdown'),
    FakeExercise('Squat'),
    FakeExercise('Deadlift'),
]


def test_rules_parse_simple():
    result = parse('bench press 3x10 60kg', EXERCISES)
    assert result['source'] == 'rules'
    assert result['exercises'][0]['name'] == 'Bench Press'
    assert len(result['exercises'][0]['sets']) == 3
    assert result['exercises'][0]['sets'][0] == {'weight_kg': 60.0, 'reps': 10}


def test_rules_parse_conversational():
    result = parse('did bench press, 3 sets of 10 at 60kg', EXERCISES)
    assert result['source'] == 'rules'
    assert result['exercises'][0]['name'] == 'Bench Press'
    assert len(result['exercises'][0]['sets']) == 3
    assert result['exercises'][0]['sets'][0]['weight_kg'] == 60.0
    assert result['exercises'][0]['sets'][0]['reps'] == 10


def test_rules_parse_multi_exercise():
    result = parse('bench 60kg 3x10, squat 100kg 4x8', EXERCISES)
    assert result['source'] == 'rules'
    assert len(result['exercises']) == 2
    names = [e['name'] for e in result['exercises']]
    assert 'Bench Press' in names
    assert 'Squat' in names


def test_weight_lbs_conversion():
    result = parse('bench press 3x10 135lbs', EXERCISES)
    assert result['exercises'][0]['sets'][0]['weight_kg'] == 61.2


@patch('workouts.nl_parser.requests.post')
def test_rules_no_match_triggers_ollama(mock_post):
    mock_response = Mock()
    mock_response.json.return_value = {
        'response': '{"exercises": [{"name": "Bench Press", "sets": [{"weight_kg": 60.0, "reps": 10}]}]}'
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    result = parse('xyzzy exercise 3x10 60kg', EXERCISES)
    assert mock_post.called
    assert result['source'] == 'ollama'


@patch('workouts.nl_parser.requests.post')
def test_parse_error_on_ollama_timeout(mock_post):
    mock_post.side_effect = req_lib.exceptions.Timeout()
    with pytest.raises(NLParseError):
        parse('xyzzy exercise 3x10 60kg', EXERCISES)


@patch('workouts.nl_parser.requests.post')
def test_parse_error_on_invalid_json(mock_post):
    mock_response = Mock()
    mock_response.json.return_value = {'response': 'this is not json at all'}
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response
    with pytest.raises(NLParseError):
        parse('xyzzy exercise 3x10 60kg', EXERCISES)
```

- [ ] **Step 3: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_nl_parser.py -v
```

Expected: `ImportError` — `workouts/nl_parser.py` doesn't exist yet.

- [ ] **Step 4: Create `workouts/nl_parser.py`**

```python
import difflib
import json
import re

import requests


class NLParseError(Exception):
    pass


OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'qwen'
OLLAMA_TIMEOUT = 10


def _lbs_to_kg(lbs: float) -> float:
    return round(lbs * 0.453592, 1)


def _parse_sets_reps(text: str):
    m = re.search(r'(\d+)\s*[x×]\s*(\d+)', text, re.IGNORECASE)
    if m:
        count, reps = int(m.group(1)), int(m.group(2))
        return [{'reps': reps} for _ in range(count)]
    m = re.search(r'(\d+)\s+sets?\s+(?:of\s+)?(\d+)(?:\s+reps?)?', text, re.IGNORECASE)
    if m:
        count, reps = int(m.group(1)), int(m.group(2))
        return [{'reps': reps} for _ in range(count)]
    return None


def _extract_weight(text: str):
    m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|lbs?)', text, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return _lbs_to_kg(val) if m.group(2).lower().startswith('lb') else val
    m = re.search(r'\bat\s+(\d+(?:\.\d+)?)\b', text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _fuzzy_match(fragment: str, exercises) -> str | None:
    low = fragment.lower()
    low_map = {e.name.lower(): e.name for e in exercises}
    matches = difflib.get_close_matches(low, list(low_map), n=1, cutoff=0.6)
    return low_map[matches[0]] if matches else None


def _clean_name(text: str) -> str:
    t = re.sub(r'\d+\s*[x×]\s*\d+', '', text, flags=re.IGNORECASE)
    t = re.sub(r'\d+\s+sets?\s+(?:of\s+)?\d+(?:\s+reps?)?', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\d+(?:\.\d+)?\s*(?:kg|lbs?)', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bat\s+\d+(?:\.\d+)?\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(did|do|was|performed?|completed?)\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[,;]', ' ', t)
    return ' '.join(t.split())


def _parse_single(text: str, exercises):
    sets = _parse_sets_reps(text)
    if sets is None:
        return None
    weight = _extract_weight(text)
    fragment = _clean_name(text)
    if not fragment:
        return None
    name = _fuzzy_match(fragment, exercises)
    if name is None:
        return None
    weight_kg = weight or 0.0
    return {'name': name, 'sets': [{'weight_kg': weight_kg, 'reps': s['reps']} for s in sets]}


def _parse_rules(text: str, exercises):
    segments = [s.strip() for s in re.split(r'[,;]', text) if s.strip()]
    if len(segments) > 1:
        results = []
        for seg in segments:
            r = _parse_single(seg, exercises)
            if r is None:
                break
            results.append(r)
        else:
            if results:
                return {'exercises': results, 'source': 'rules'}
    single = _parse_single(text, exercises)
    if single:
        return {'exercises': [single], 'source': 'rules'}
    return None


def _call_ollama(text: str, exercises) -> dict:
    names = ', '.join(e.name for e in exercises)
    prompt = (
        'Extract workout data as JSON. Return ONLY valid JSON, no explanation.\n\n'
        f'Available exercises: {names}\n\n'
        f'Text: "{text}"\n\n'
        'Return format: {"exercises": [{"name": "<exact exercise name from list>", '
        '"sets": [{"weight_kg": 60.0, "reps": 10}]}]}'
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={'model': OLLAMA_MODEL, 'prompt': prompt, 'stream': False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise NLParseError('Ollama timed out')
    except requests.exceptions.RequestException as e:
        raise NLParseError(f'Ollama request failed: {e}')
    raw = resp.json().get('response', '')
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        raise NLParseError('Ollama returned no JSON')
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        raise NLParseError('Ollama returned invalid JSON')
    if 'exercises' not in data:
        raise NLParseError('Ollama response missing exercises key')
    for ex in data['exercises']:
        for s in ex.get('sets', []):
            if 'weight_kg' in s:
                s['weight_kg'] = float(s['weight_kg'])
    data['source'] = 'ollama'
    return data


def parse(text: str, exercises) -> dict:
    """
    Parse natural language workout text into structured data.

    Returns {"exercises": [{"name": str, "sets": [{"weight_kg": float, "reps": int}]}],
             "source": "rules" | "ollama"}.
    Raises NLParseError if neither stage can parse the text.
    """
    result = _parse_rules(text, exercises)
    if result is not None:
        return result
    return _call_ollama(text, exercises)
```

- [ ] **Step 5: Run parser tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_nl_parser.py -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 56 tests pass (49 existing + 7 new).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt workouts/nl_parser.py tests/test_nl_parser.py
git commit -m "feat: NL parser — rule-based with Ollama/Qwen fallback"
```

---

## Task 2: Views + URL Patterns + View Tests

**Files:**
- Modify: `workouts/views.py`
- Modify: `core/urls.py`
- Create: `tests/test_nl_views.py`

- [ ] **Step 1: Write failing view tests**

Create `tests/test_nl_views.py`:

```python
import json
import pytest
from unittest.mock import patch, Mock
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


PARSED_JSON = json.dumps({
    'exercises': [
        {'name': 'Bench Press', 'sets': [
            {'weight_kg': 60.0, 'reps': 10},
            {'weight_kg': 60.0, 'reps': 9},
        ]}
    ],
    'source': 'rules',
})


@pytest.mark.django_db
@patch('workouts.views.parse')
def test_nl_parse_returns_json(mock_parse, verified_client):
    make_exercise()
    session = make_active_session()
    mock_parse.return_value = {
        'exercises': [{'name': 'Bench Press', 'sets': [{'weight_kg': 60.0, 'reps': 10}]}],
        'source': 'rules',
    }
    response = verified_client.post(
        reverse('gym_nl_parse', args=[session.id]),
        {'text': 'bench press 3x10 60kg'},
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'exercises' in data


@pytest.mark.django_db
def test_nl_parse_invalid_session_404(verified_client):
    response = verified_client.post(
        reverse('gym_nl_parse', args=[9999]), {'text': 'bench 3x10 60kg'}
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_nl_parse_complete_session_404(verified_client):
    session = WorkoutSession.objects.create(
        name='Done', status='complete', completed_at=timezone.now()
    )
    response = verified_client.post(
        reverse('gym_nl_parse', args=[session.id]), {'text': 'bench 3x10 60kg'}
    )
    assert response.status_code == 404


@pytest.mark.django_db
@patch('workouts.views.parse')
def test_nl_parse_unparseable_returns_422(mock_parse, verified_client):
    from workouts.nl_parser import NLParseError
    session = make_active_session()
    mock_parse.side_effect = NLParseError('Could not parse')
    response = verified_client.post(
        reverse('gym_nl_parse', args=[session.id]), {'text': 'asdfghjkl'}
    )
    assert response.status_code == 422
    assert b'error' in response.content


@pytest.mark.django_db
def test_nl_confirm_creates_workout_exercise(verified_client):
    make_exercise()
    session = make_active_session()
    verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    assert WorkoutExercise.objects.filter(session=session).exists()


@pytest.mark.django_db
def test_nl_confirm_creates_sets(verified_client):
    make_exercise()
    session = make_active_session()
    verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    we = WorkoutExercise.objects.get(session=session)
    set_numbers = list(WorkoutSet.objects.filter(workout_exercise=we).values_list('set_number', flat=True))
    assert set_numbers == [1, 2]


@pytest.mark.django_db
def test_nl_confirm_redirects(verified_client):
    make_exercise()
    session = make_active_session()
    response = verified_client.post(
        reverse('gym_nl_confirm', args=[session.id]),
        {'parsed_json': PARSED_JSON},
    )
    assert response.status_code == 302
    assert str(session.id) in response['Location']
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_nl_views.py -v
```

Expected: `NoReverseMatch` — URLs not defined yet.

- [ ] **Step 3: Update `workouts/views.py` imports and add two new views**

Replace the import block at the top of `workouts/views.py` (keep all existing imports, add three new ones):

```python
import json

from django.db.models import Max, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Exercise, WorkoutExercise, WorkoutSession, WorkoutSet
from .nl_parser import NLParseError, parse
```

Then append these two views at the end of `workouts/views.py`:

```python
@require_http_methods(['POST'])
def nl_parse(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'No text provided'}, status=422)
    exercises = Exercise.objects.filter(is_active=True)
    try:
        result = parse(text, exercises)
        return JsonResponse(result)
    except NLParseError as e:
        return JsonResponse(
            {'error': str(e) or 'Could not parse — try rephrasing or use the exercise picker'},
            status=422,
        )


@require_http_methods(['POST'])
def nl_confirm(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    raw = request.POST.get('parsed_json', '')
    try:
        data = json.loads(raw)
        exercises_data = data['exercises']
    except (json.JSONDecodeError, KeyError, TypeError):
        return redirect('gym_active_session', session_id=session.id)
    for ex_data in exercises_data:
        exercise = Exercise.objects.filter(name__iexact=ex_data['name'], is_active=True).first()
        if exercise is None:
            continue
        we, _ = WorkoutExercise.objects.get_or_create(
            session=session,
            exercise=exercise,
            defaults={'order': session.workout_exercises.count() + 1},
        )
        set_number_start = we.sets.count() + 1
        for i, set_data in enumerate(ex_data.get('sets', [])):
            WorkoutSet.objects.create(
                workout_exercise=we,
                set_number=set_number_start + i,
                weight_kg=set_data.get('weight_kg', 0),
                reps=set_data.get('reps', 1),
            )
    return redirect('gym_active_session', session_id=session.id)
```

- [ ] **Step 4: Add URL patterns to `core/urls.py`**

Read `core/urls.py` first (to see current content), then add these two lines after the `gym_finish_session` line:

```python
    path('log/<int:session_id>/nl-parse/', workout_views.nl_parse, name='gym_nl_parse'),
    path('log/<int:session_id>/nl-confirm/', workout_views.nl_confirm, name='gym_nl_confirm'),
```

The updated logging section of `core/urls.py` should look like:

```python
    # Workout logging
    path('log/', workout_views.log_home, name='gym_log_home'),
    path('log/start/', workout_views.start_session, name='gym_log_start'),
    path('log/<int:session_id>/', workout_views.active_session, name='gym_active_session'),
    path('log/<int:session_id>/add-exercise/', workout_views.add_exercise, name='gym_add_exercise'),
    path('log/<int:session_id>/exercise/<int:we_id>/add-set/', workout_views.add_set, name='gym_add_set'),
    path('log/<int:session_id>/exercise/<int:we_id>/delete-set/<int:set_id>/', workout_views.delete_set, name='gym_delete_set'),
    path('log/<int:session_id>/finish/', workout_views.finish_session, name='gym_finish_session'),
    path('log/<int:session_id>/nl-parse/', workout_views.nl_parse, name='gym_nl_parse'),
    path('log/<int:session_id>/nl-confirm/', workout_views.nl_confirm, name='gym_nl_confirm'),
```

- [ ] **Step 5: Run view tests — expect pass**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/test_nl_views.py -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```

Expected: 63 tests pass.

- [ ] **Step 7: Commit**

```bash
git add workouts/views.py core/urls.py tests/test_nl_views.py
git commit -m "feat: nl_parse and nl_confirm views"
```

---

## Task 3: CSS for NL UI

**Files:**
- Modify: `static/css/app.css`

- [ ] **Step 1: Append to `static/css/app.css`**

Read the file first to confirm the end, then append exactly:

```css
/* ── Natural language quick-add ─────────────────────────────────── */
.nl-quick-add {
  margin-bottom: 16px;
}

.nl-box-label {
  font-size: 9px;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  margin-bottom: 4px;
}

.nl-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.nl-textarea {
  flex: 1;
  background: var(--card2);
  border: 1px solid var(--accent);
  border-radius: var(--radius-btn);
  padding: 10px 12px;
  color: var(--text);
  font-size: 13px;
  resize: none;
  outline: none;
  line-height: 1.4;
  font-family: inherit;
}

.nl-textarea::placeholder { color: var(--text-muted); }
.nl-textarea:focus { border-color: var(--accent); }

.nl-btn {
  width: 42px;
  height: 42px;
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: var(--radius-btn);
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
}

.nl-error {
  font-size: 11px;
  color: #EF4444;
  margin-top: 6px;
}

/* ── NL preview card ─────────────────────────────────────────────── */
.preview-card {
  background: #0D1F0D;
  border: 1px solid var(--accent);
  border-radius: var(--radius-card);
  padding: 14px 16px;
  margin-bottom: 16px;
}

.preview-label {
  font-size: 9px;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  margin-bottom: 8px;
}

.preview-ex {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 4px;
  margin-top: 10px;
  color: var(--text);
}

.preview-ex:first-of-type { margin-top: 0; }

.preview-set {
  font-size: 12px;
  color: var(--text-sec);
  padding: 2px 0;
}

.preview-set strong {
  color: var(--text);
  font-weight: 600;
}

.btn-confirm {
  flex: 1;
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: var(--radius-btn);
  padding: 10px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.btn-discard {
  flex: 1;
  background: transparent;
  color: var(--text-sec);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  padding: 10px;
  font-size: 13px;
  cursor: pointer;
}
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 63 tests pass.

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "feat: CSS for NL quick-add and preview card"
```

---

## Task 4: Template Update

**Files:**
- Modify: `templates/workouts/active_session.html`

- [ ] **Step 1: Add NL text box + preview card to `templates/workouts/active_session.html`**

Replace the entire file with this content:

```html
{% extends 'base.html' %}
{% block title %}{{ session.name }} — Gym AI{% endblock %}

{% block content %}
<div class="session-title">{{ session.name }}</div>

<!-- Natural language quick-add -->
<div class="nl-quick-add" id="nl-quick-add">
  <div class="nl-box-label">Quick add</div>
  <div class="nl-row">
    <textarea id="nl-text" class="nl-textarea" rows="2"
              placeholder="e.g. bench press, 3 sets of 10 at 60kg"></textarea>
    <button type="button" class="nl-btn" id="nl-submit">→</button>
  </div>
  <div id="nl-error" class="nl-error" style="display:none"></div>
</div>

<!-- Preview card (hidden until parse succeeds) -->
<div id="nl-preview" style="display:none">
  <form method="post" action="{% url 'gym_nl_confirm' session.id %}">
    {% csrf_token %}
    <input type="hidden" name="parsed_json" id="nl-parsed-json">
    <div class="preview-card">
      <div class="preview-label">✓ Parsed — confirm to add</div>
      <div id="preview-body"></div>
      <div class="btn-row" style="display:flex;gap:8px;margin-top:12px">
        <button type="submit" class="btn-confirm">Add ✓</button>
        <button type="button" class="btn-discard" onclick="discardPreview()">Discard</button>
      </div>
    </div>
  </form>
</div>

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
const NL_PARSE_URL = '{% url "gym_nl_parse" session.id %}';
const CSRF_TOKEN = '{{ csrf_token }}';

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

document.getElementById('nl-submit').addEventListener('click', function () {
  const text = document.getElementById('nl-text').value.trim();
  if (!text) return;
  const btn = this;
  btn.textContent = '…';
  btn.disabled = true;
  document.getElementById('nl-error').style.display = 'none';

  const body = new FormData();
  body.append('text', text);
  body.append('csrfmiddlewaretoken', CSRF_TOKEN);

  fetch(NL_PARSE_URL, { method: 'POST', body: body })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      btn.textContent = '→';
      btn.disabled = false;
      if (!res.ok) {
        const el = document.getElementById('nl-error');
        el.textContent = res.data.error || 'Could not parse — try rephrasing';
        el.style.display = 'block';
        return;
      }
      renderPreview(res.data);
      document.getElementById('nl-parsed-json').value = JSON.stringify(res.data);
      document.getElementById('nl-quick-add').style.display = 'none';
      document.getElementById('nl-preview').style.display = 'block';
    })
    .catch(function () {
      btn.textContent = '→';
      btn.disabled = false;
      const el = document.getElementById('nl-error');
      el.textContent = 'Request failed — check your connection';
      el.style.display = 'block';
    });
});

function renderPreview(data) {
  const body = document.getElementById('preview-body');
  body.innerHTML = '';
  (data.exercises || []).forEach(function (ex) {
    const nameEl = document.createElement('div');
    nameEl.className = 'preview-ex';
    nameEl.textContent = ex.name;
    body.appendChild(nameEl);
    (ex.sets || []).forEach(function (s, i) {
      const setEl = document.createElement('div');
      setEl.className = 'preview-set';
      setEl.innerHTML = 'Set ' + (i + 1) + ' · <strong>' + s.weight_kg + ' kg × ' + s.reps + ' reps</strong>';
      body.appendChild(setEl);
    });
  });
}

function discardPreview() {
  document.getElementById('nl-preview').style.display = 'none';
  document.getElementById('nl-text').value = '';
  document.getElementById('nl-quick-add').style.display = 'block';
}
</script>
{% endblock %}
```

- [ ] **Step 2: Run full suite**

```bash
cd /home/abhishek/abhi/gym && source venv/bin/activate && pytest tests/ -v
```

Expected: 63 tests pass.

- [ ] **Step 3: Commit**

```bash
git add templates/workouts/active_session.html
git commit -m "feat: NL quick-add text box and preview card on active session"
```

---

## Final Verification

- [ ] Start the dev server: `source venv/bin/activate && python manage.py runserver`
- [ ] Open `http://localhost:8000/gym-2026-private/`, enter PIN `1234`
- [ ] Start a new session → active session screen
- [ ] Type `bench press, 3 sets of 10 at 60kg` → tap → preview card shows "Bench Press · Set 1 · 60.0 kg × 10 reps" (×3)
- [ ] Tap "Add ✓" → Bench Press card appears with 3 sets
- [ ] Start another session, type `squat 100kg 3x8, deadlift 120kg 1x5` → tap → preview shows two exercises
- [ ] Tap "Add ✓" → both exercises appear
- [ ] Type `xyzzy 3x10 60kg` → Ollama called → either parses (if Qwen running) or shows inline error (if not)
- [ ] Type gibberish → inline error shown, text retained
- [ ] Tap "Discard" → preview hides, text box restores
- [ ] Confirm all 63 tests pass: `pytest tests/ -v`
