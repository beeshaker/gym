# Program Preview Chat + Rest Timer Design

**Date:** 2026-06-08
**Feature:** Free-form AI coach chat on the program preview screen + auto-starting rest timer on the active session screen

## Goal

1. Add a floating "Ask Coach" button to the program preview page that opens a free-form chat panel. The user can ask the Ollama AI about rest periods, exercise swaps, and progressive overload recommendations before starting the session.
2. Let the user set a planned rest duration per exercise on the preview screen (presets + AI-guided).
3. Auto-start a countdown timer overlay on the active session screen after every logged set, using the planned rest duration.

---

## Part 1: AI Coach Chat

### New endpoint

`POST /programs/<day_id>/chat/`

Request body:
- `message` — the user's free-form question (string, required)
- `history` — JSON array of `{role, content}` pairs for prior turns (optional, defaults to `[]`)

Response (JSON):
- `{"reply": "..."}` on success (200)
- `{"error": "..."}` on bad input (400), inactive program (404), or Ollama failure (422)

The view:
1. Loads `ProgramDay` (404 if program is inactive)
2. Builds context lines for each `ProgramExercise`: name, equipment, category, overload recommendation (action, last weight/reps, target weight/reps)
3. Calls `get_program_chat_reply(context_lines, history, message)` from `coach.py`
4. Returns JSON reply

History is stateless on the server — the client sends the full history array on every request.

### `coach.py` addition

New function `get_program_chat_reply(context_lines, history, question)`:
- System prompt: "You are a strength coach. The user is about to start {program} — {day}. Here are today's exercises + their progression status: ..."
- Formats `history` as alternating user/assistant turns for Ollama
- Calls Ollama (`qwen2.5:1.5b`) with full prompt + conversation
- Returns the reply string
- Raises `CoachError` on any Ollama failure (same pattern as `get_ollama_tips`)

### New URL

```python
path('programs/<int:day_id>/chat/', workout_views.program_chat, name='gym_program_chat'),
```

### Preview screen frontend

**Floating button:** Fixed "✦ Ask Coach" button pinned bottom-right, always visible while scrolling.

**Overlay panel** (slide-up, ~60% screen height):
- Header: "Coach — {day name}" + close (✕) button
- Scrollable `.coach-chat-history` area with `.coach-msg-user` and `.coach-msg-ai` bubbles
- Text input + Send button row at the bottom

**JS behaviour:**
- `history` array kept in memory; cleared on panel close
- On send: push user message, POST to chat endpoint with `message` + serialised `history`, push AI reply, render both
- Send button disabled + shows "…" while waiting
- Errors rendered inline as a red `.coach-msg-ai` bubble
- Form (exercise list, weights, reps, rest presets) untouched while panel is open

---

## Part 2: Rest Timer

### Data model

Add `planned_rest_seconds` (PositiveIntegerField, null=True, blank=True) to `WorkoutExercise`. Single nullable column — no backfill required.

Category defaults (used when field is null):
- `compound` → 180s
- `isolation` → 90s
- `cardio` → 60s
- anything else → 90s

### `_create_session_from_form` update

Reads `rest_<ex_id>` from POST for each exercise. Saves as `planned_rest_seconds` on the created `WorkoutExercise`. If the field is absent or invalid, saves `None` (falls back to category default at render time).

### `add_set` update

After creating the `WorkoutSet`, redirect to:
```
active_session?timer=<we_id>
```
instead of the bare URL. On error (invalid weight/reps), redirect without the query param as before.

### Preview screen — rest presets

Each exercise card on `program_preview.html` gets a rest row below the set inputs: four preset buttons — **60s / 90s / 2min / 3min**. Tapping one highlights it (active style) and updates a hidden input `rest_<ex_id>`. On page load JS pre-selects the category default (compound → 3min, otherwise → 90s).

The AI chat naturally covers rest questions — the system prompt includes exercise categories, so Ollama can give specific advice. The user reads the reply and taps the matching preset.

### Active session timer

`active_session` view: no change. Each exercise card in the template gains `data-rest="{{ we.planned_rest_seconds|default:'' }}"` and `data-category="{{ we.exercise.category }}"` attributes.

JS on page load:
1. Reads `?timer=<we_id>` from the URL
2. Finds the matching card, reads `data-rest` (or derives from `data-category` if blank)
3. Auto-starts fullscreen countdown overlay

**Timer overlay:**
- Exercise name: "Resting after {name}"
- Large MM:SS countdown
- Four preset buttons (60s / 90s / 2min / 3min) — tapping resets countdown to that value
- Skip button — dismisses overlay immediately
- On reaching 0: overlay auto-dismisses + `navigator.vibrate([200, 100, 200])` if available

If the page loads without `?timer=`, the overlay never appears.

---

## CSS additions (`static/css/app.css`)

Chat panel: `.coach-bubble`, `.coach-overlay`, `.coach-overlay-header`, `.coach-chat-history`, `.coach-msg-user`, `.coach-msg-ai`, `.coach-chat-input-row`

Rest presets + timer: `.rest-presets`, `.rest-preset-btn`, `.rest-preset-btn.active`, `.timer-overlay`, `.timer-countdown`, `.timer-exercise-name`, `.timer-actions`

All use existing dark-theme variables (`--card`, `--border`, `--accent`, `--text`, `--text-sec`).

---

## Files changed

| File | Change |
|---|---|
| `workouts/models.py` | Add `planned_rest_seconds` to `WorkoutExercise` |
| `workouts/migrations/` | Migration for new field |
| `workouts/coach.py` | Add `get_program_chat_reply` |
| `workouts/views.py` | Add `program_chat` view; update `_create_session_from_form`; update `add_set` redirect |
| `core/urls.py` | Add `gym_program_chat` URL |
| `static/css/app.css` | Append chat + timer styles |
| `templates/workouts/program_preview.html` | Add rest presets, floating chat button + overlay + JS |
| `templates/workouts/active_session.html` | Add `data-rest`/`data-category` attrs + timer overlay + JS |
| `tests/test_program_chat.py` | 5 HTTP tests (create) |
| `tests/test_rest_timer.py` | 4 model/redirect tests (create) |

---

## Tests

### `tests/test_program_chat.py` — 5 tests (mock `get_program_chat_reply`)

1. Valid POST → 200 + `{"reply": "..."}`
2. Missing `message` → 400
3. Inactive program day → 404
4. `CoachError` → 422 + `{"error": "..."}`
5. GET → 405

### `tests/test_rest_timer.py` — 4 tests

1. `program_start` with `rest_<ex_id>` in POST saves `planned_rest_seconds` on `WorkoutExercise`
2. `program_start` without rest field saves `None` (category default handled client-side)
3. `add_set` redirect URL includes `?timer=<we_id>`
4. `start_session` (quick log, no rest fields) creates `WorkoutExercise` with `planned_rest_seconds=None`

**Expected total: 97 + 5 + 4 = 106 tests.**
