# Program Preview Chat Design

**Date:** 2026-06-08
**Feature:** Free-form AI coach chat on the program preview screen

## Goal

Add a floating "Ask Coach" button to the program preview page that opens a free-form chat panel. The user can ask the Ollama AI about rest periods, exercise swaps, and progressive overload recommendations before starting the session.

## Architecture

### New endpoint

`POST /programs/<day_id>/chat/`

Request body (form or JSON):
- `message` — the user's free-form question (string, required)
- `history` — JSON array of `{role, content}` pairs representing prior turns (optional, defaults to `[]`)

Response (JSON):
- `{"reply": "..."}` on success (200)
- `{"error": "..."}` on Ollama failure (422) or bad input (400)

The view:
1. Loads `ProgramDay` (404 if inactive program)
2. Builds context lines for each `ProgramExercise`: name, equipment, category, overload recommendation (action, last weight/reps, target weight/reps)
3. Calls `get_program_chat_reply(context_lines, history, message)` from `coach.py`
4. Returns JSON reply

### `coach.py` addition

New function `get_program_chat_reply(context_lines, history, question)`:
- Builds a system prompt: "You are a strength coach. The user is about to start {program} — {day}. Here are today's exercises: ..."
- Formats `history` as alternating user/assistant turns for Ollama
- Calls Ollama (`qwen2.5:1.5b`) with the full prompt + conversation
- Returns the reply string
- Raises `CoachError` on any Ollama failure (same pattern as `get_ollama_tips`)

History is stateless on the server — the client sends the full history array on every request.

### URL

Added to `core/urls.py` alongside the other program routes:
```python
path('programs/<int:day_id>/chat/', workout_views.program_chat, name='gym_program_chat'),
```

## Frontend (`program_preview.html`)

**Floating button:** Fixed "✦ Ask Coach" button pinned bottom-right, always visible while scrolling the exercise list.

**Overlay panel:** Slide-up panel covering ~60% of the screen height:
- Header: "Coach — {day name}" + close (✕) button
- Scrollable `.coach-chat-history` area with `.coach-msg-user` and `.coach-msg-ai` message bubbles
- Text input + Send button row at the bottom

**JS behaviour:**
- `history` array maintained in memory (cleared on panel close)
- On send: push user message to history and render, POST to chat endpoint with `message` + serialised `history`, push AI reply and render
- Send button disabled + shows "…" while waiting
- Errors rendered inline as a `.coach-msg-ai` bubble with red text
- No page reload; the form (exercise list, weights, reps) is untouched

## CSS additions (appended to `static/css/app.css`)

New classes: `.coach-bubble`, `.coach-overlay`, `.coach-overlay-header`, `.coach-chat-history`, `.coach-msg-user`, `.coach-msg-ai`, `.coach-chat-input-row`

Style follows the existing dark-theme variables (`--card`, `--border`, `--accent`, `--text`, `--text-sec`).

## Files changed

| File | Change |
|---|---|
| `workouts/coach.py` | Add `get_program_chat_reply` |
| `workouts/views.py` | Add `program_chat` view |
| `core/urls.py` | Add `gym_program_chat` URL |
| `static/css/app.css` | Append chat + bubble styles |
| `templates/workouts/program_preview.html` | Add floating button + overlay + JS |
| `tests/test_program_chat.py` | 5 HTTP tests (create) |

## Tests

`tests/test_program_chat.py` — 5 tests, all mocking `get_program_chat_reply`:

1. Valid POST → 200 + `{"reply": "..."}` 
2. Missing `message` → 400
3. Inactive program day → 404
4. `CoachError` from Ollama → 422 + `{"error": "..."}`
5. GET request → 405

Expected total: 97 existing + 5 new = **102 tests**.
