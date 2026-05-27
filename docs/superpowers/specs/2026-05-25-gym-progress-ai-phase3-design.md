# Gym Progress AI — Phase 3 Natural Language Logging Design

**Date:** 2026-05-25
**Phase:** 3 of 6 — Natural Language Log Parsing
**Status:** Approved

---

## Overview

Phase 3 adds a natural language text box to the active session screen. The user types a conversational description of an exercise (e.g. "did bench press, 3 sets of 10 at 60kg") or a full session dump (e.g. "bench 60kg 3x10, incline db 24kg 3x12"), and the app parses it into structured WorkoutExercise + WorkoutSet records. Parsing uses a rule-based fast path with Ollama/Qwen as a fallback. A preview card shows the parsed result before any records are committed.

No AI coach, no overload suggestions — those are Phase 5 and 6.

---

## 1. Data Flow

```
User types text → POST /log/<id>/nl-parse/
  → Rule-based parser attempts extraction
  → If confidence low → Ollama (Qwen at localhost:11434)
  → Return parsed JSON to the page (fetch, no navigation)
  → Preview card replaces text box inline
  → User taps "Add ✓" → POST /log/<id>/nl-confirm/
  → WorkoutExercise + WorkoutSet records created
  → Redirect to gym_active_session
```

The parse step is a JSON endpoint. The confirm step is a standard form POST. No new models needed — Phase 2 models cover everything.

---

## 2. UI

The NL text box sits at the top of the active session screen, always visible, above the exercise list.

### Input state

```
[ Quick add                                    ]  [ → ]
  e.g. "did bench press, 3 sets of 10 at 60kg"
```

- `<textarea>` with placeholder text
- Arrow button submits via `fetch()` to `gym_nl_parse`
- Spinner shown while parsing

### Preview state (replaces text box after successful parse)

```
┌─ ✓ Parsed — confirm to add ──────────────────┐
│ Bench Press                                    │
│ Set 1 · 60 kg × 10 reps                       │
│ Set 2 · 60 kg × 9 reps                        │
│ Set 3 · 60 kg × 8 reps                        │
│                                                │
│  [ Add ✓ ]          [ Discard ]               │
└────────────────────────────────────────────────┘
```

- Green-tinted card with "✓ Parsed" label
- Lists each exercise and its sets
- "Add ✓" submits hidden JSON to `gym_nl_confirm` (standard form POST)
- "Discard" clears the preview and restores the text box

### Error state

If parsing fails (unknown exercise, Ollama timeout, invalid JSON):

```
Could not parse — try rephrasing or use the exercise picker
```

Inline error below the text box. Text box retains user's input.

---

## 3. Parser — `workouts/nl_parser.py`

Single public function:

```python
def parse(text: str, exercises: QuerySet) -> dict:
    """
    Returns:
      {"exercises": [{"name": str, "sets": [{"weight_kg": float, "reps": int}]}],
       "source": "rules" | "ollama"}
    or raises NLParseError on failure.
    """
```

`exercises` is the active `Exercise` queryset passed in by the view (avoids DB calls inside the parser, easier to test).

### Stage 1 — Rule-based

Patterns matched (in order):

1. **Set notation**: `3x10`, `3×10`, `3 sets of 10`, `3 sets 10 reps`, `3 × 10`
2. **Weight**: `60kg`, `60 kg`, `60`, `135lbs` → converted to kg (`lbs × 0.453592`, rounded to 1dp)
3. **Exercise name**: remaining tokens fuzzy-matched against `exercises` using `difflib.get_close_matches(n=1, cutoff=0.6)`

Confidence: **high** if exercise match score ≥ 0.6 AND at least one set with weight extracted. Returns `source='rules'`.

Confidence: **low** (fall through to Stage 2) if:
- No exercise name match above cutoff, or
- No set pattern found

### Stage 2 — Ollama fallback

POST to `http://localhost:11434/api/generate`:

```json
{
  "model": "qwen",
  "prompt": "Extract workout data as JSON. Return ONLY valid JSON, no explanation.\n\nAvailable exercises: [Bench Press, Incline DB Press, ...]\n\nText: \"did bench, 3 sets 10 at 60kg\"\n\nReturn format: {\"exercises\": [{\"name\": \"<exact exercise name from list>\", \"sets\": [{\"weight_kg\": 60.0, \"reps\": 10}]}]}",
  "stream": false
}
```

- Exercise list is truncated to names only (no metadata) to keep prompt short
- `stream: false` so response is a single JSON object
- Timeout: 10 seconds
- On timeout, invalid JSON, or missing keys → raises `NLParseError`

Returns `source='ollama'`.

### Weight unit conversion

`135lbs` → `61.2kg` (multiply by 0.453592, round to 1 decimal place). Applies in both rule-based and post-Ollama normalisation step.

### NLParseError

```python
class NLParseError(Exception):
    pass
```

Raised when neither stage can produce a valid result. Caught in the view, returns `{"error": "Could not parse — try rephrasing or use the exercise picker"}`.

---

## 4. Routes

Added to `core/urls.py` under `/<secret>/`:

| URL | Name | View | Method |
|---|---|---|---|
| `log/<int:session_id>/nl-parse/` | `gym_nl_parse` | `nl_parse` | POST |
| `log/<int:session_id>/nl-confirm/` | `gym_nl_confirm` | `nl_confirm` | POST |

---

## 5. Views

### `nl_parse(request, session_id)` — POST, returns JSON

- Gets active `WorkoutSession` — 404 if not found or complete
- Reads `text` from `request.POST`
- Fetches `Exercise.objects.filter(is_active=True)` and passes to parser
- On success: `JsonResponse({"exercises": [...], "source": "rules"|"ollama"})`
- On `NLParseError`: `JsonResponse({"error": "..."}, status=422)`

### `nl_confirm(request, session_id)` — POST, redirects

- Gets active `WorkoutSession` — 404 if not found or complete
- Reads `parsed_json` hidden field from POST body (JSON string)
- For each exercise in parsed data:
  - `get_or_create`-style: checks if `WorkoutExercise` already exists for this session+exercise; if not, creates it with `order=session.workout_exercises.count() + 1`
  - Creates `WorkoutSet` records with incrementing `set_number`
- Redirects to `gym_active_session`
- If `parsed_json` is missing or invalid: redirects to `gym_active_session` (silent fail — nothing to confirm)

---

## 6. Template Changes — `active_session.html`

Add at the top of `{% block content %}`, before the exercise list:

```html
<div class="nl-quick-add" id="nl-quick-add">
  <div class="nl-box-label">Quick add</div>
  <div class="nl-row">
    <textarea id="nl-text" class="nl-textarea" rows="2"
              placeholder="e.g. bench press, 3 sets of 10 at 60kg"></textarea>
    <button type="button" class="nl-btn" id="nl-submit">→</button>
  </div>
  <div id="nl-error" class="nl-error" style="display:none"></div>
</div>

<div id="nl-preview" style="display:none">
  <!-- populated by JS after successful parse -->
  <form method="post" action="{% url 'gym_nl_confirm' session.id %}">
    {% csrf_token %}
    <input type="hidden" name="parsed_json" id="nl-parsed-json">
    <div class="preview-card">
      <div class="preview-label">✓ Parsed — confirm to add</div>
      <div id="preview-body"></div>
      <div class="btn-row">
        <button type="submit" class="btn-confirm">Add ✓</button>
        <button type="button" class="btn-discard" onclick="discardPreview()">Discard</button>
      </div>
    </div>
  </form>
</div>
```

JS in `{% block scripts %}`:

- `nl-submit` click → `fetch` POST to `gym_nl_parse` with CSRF token
- On success: hide `nl-quick-add`, populate `preview-body` with exercises/sets, set `nl-parsed-json` value, show `nl-preview`
- On error: show `nl-error` with the error message
- `discardPreview()`: hide `nl-preview`, clear `nl-text`, show `nl-quick-add`

---

## 7. CSS additions — `static/css/app.css`

New classes:

```css
.nl-quick-add  — container, margin-bottom: 16px
.nl-box-label  — small uppercase label, accent colour, letter-spacing: 1px
.nl-row        — flex row, gap: 8px
.nl-textarea   — full-width input, 2 rows, same style as .set-input but taller
.nl-btn        — submit arrow button, accent colour
.nl-error      — small red error text below textarea
.preview-card  — green-tinted card (.background: #0D1F0D, border: accent)
.preview-label — small uppercase label, accent colour
.preview-ex    — exercise name, bold
.preview-set   — set line, muted colour with bold weight/reps
.btn-confirm   — green confirm button
.btn-discard   — ghost discard button
```

---

## 8. Tests

### `tests/test_nl_parser.py` — unit tests, no HTTP, Ollama mocked

- `test_rules_parse_simple` — `"bench press 3x10 60kg"` → `{name: "Bench Press", sets: [{weight_kg: 60.0, reps: 10}]}`
- `test_rules_parse_conversational` — `"did bench press, 3 sets of 10 at 60kg"` → correct
- `test_rules_parse_multi_exercise` — `"bench 60kg 3x10, incline db 24kg 3x12"` → two exercises
- `test_rules_no_match_triggers_ollama` — unknown exercise name → Ollama called (mock asserted)
- `test_weight_lbs_conversion` — `"135lbs"` → `weight_kg=61.2`
- `test_parse_error_on_ollama_timeout` — Ollama times out → `NLParseError` raised
- `test_parse_error_on_invalid_json` — Ollama returns garbage → `NLParseError` raised

### `tests/test_nl_views.py` — HTTP tests using `verified_client`, Ollama mocked

- `test_nl_parse_returns_json` — POST valid text → 200 + JSON with exercises
- `test_nl_parse_invalid_session_404` — unknown session_id → 404
- `test_nl_parse_complete_session_404` — complete session → 404
- `test_nl_parse_unparseable_returns_422` — gibberish input → 422 + error JSON
- `test_nl_confirm_creates_workout_exercise` — POST parsed JSON → WorkoutExercise created
- `test_nl_confirm_creates_sets` — POST parsed JSON → WorkoutSet records created with correct set_numbers
- `test_nl_confirm_redirects` — → 302 to `gym_active_session`

---

## 9. What Phase 3 Does NOT Include

- Editing a parsed set before confirming (accept or discard only)
- Parsing session names from NL input
- Logging weight in lbs throughout the app (conversion is parse-time only)
- Any AI coach behaviour (Phase 6)
- Progressive overload suggestions (Phase 5)

---

## 10. Acceptance Criteria

1. Text box appears at top of active session screen
2. `"did bench press, 3 sets of 10 at 60kg"` → preview shows Bench Press with 3 sets
3. `"bench 60kg 3x10, incline db 24kg 3x12"` → preview shows two exercises
4. Confirming preview creates correct WorkoutExercise + WorkoutSet records
5. Discarding preview restores the text box with no records created
6. Unknown exercise name falls back to Ollama (Qwen)
7. Ollama timeout shows inline error, does not crash
8. `135lbs` parsed as `61.2kg`
9. All tests pass (Ollama mocked in tests)
