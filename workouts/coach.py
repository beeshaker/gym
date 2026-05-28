import json
import re

import requests


class CoachError(Exception):
    pass


OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'qwen'
OLLAMA_TIMEOUT = 15


def recommend(exercise, last_sets) -> dict:
    """
    exercise: any object with default_min_reps, default_max_reps, default_increment
    last_sets: list/queryset of sets from the last session, each with .weight_kg and .reps
    Returns progression recommendation dict.
    """
    sets = list(last_sets)
    if not sets:
        return {
            'action': 'start',
            'last_weight': None,
            'last_reps': None,
            'last_sets_count': 0,
            'target_weight': 0.0,
            'target_reps_min': exercise.default_min_reps,
            'target_reps_max': exercise.default_max_reps,
        }

    last_weight = float(max(s.weight_kg for s in sets))
    last_reps = min(s.reps for s in sets)

    if all(s.reps >= exercise.default_max_reps for s in sets):
        action = 'increase'
        target_weight = last_weight + float(exercise.default_increment)
    elif any(s.reps < exercise.default_min_reps for s in sets):
        action = 'deload'
        target_weight = max(0.0, last_weight - float(exercise.default_increment))
    else:
        action = 'hold'
        target_weight = last_weight

    return {
        'action': action,
        'last_weight': last_weight,
        'last_reps': last_reps,
        'last_sets_count': len(sets),
        'target_weight': target_weight,
        'target_reps_min': exercise.default_min_reps,
        'target_reps_max': exercise.default_max_reps,
    }


def get_ollama_tips(exercises_with_recs: list) -> dict:
    """
    exercises_with_recs: list of dicts, each with:
      'name', 'action', 'last_weight', 'last_reps', 'last_sets_count',
      'target_weight', 'target_reps_min', 'target_reps_max'
    Returns: {"Exercise Name": "one-sentence tip", ...}
    Raises CoachError on any Ollama failure.
    """
    lines = []
    for ex in exercises_with_recs:
        if ex['action'] == 'start':
            history = 'no history yet'
        else:
            history = (f"last session: {ex['last_weight']} kg × {ex['last_reps']} reps"
                       f" ({ex['last_sets_count']} sets)")
        target = (f"target: {ex['target_weight']} kg × "
                  f"{ex['target_reps_min']}–{ex['target_reps_max']} reps"
                  f" ({ex['action']})")
        lines.append(f"- {ex['name']}: {history}, {target}")

    prompt = (
        'You are a strength training coach. Give one short motivating tip (one sentence) '
        'for each exercise below based on their history and today\'s target.\n\n'
        'Exercises:\n' + '\n'.join(lines) + '\n\n'
        'Return ONLY valid JSON: {"tips": {"Exercise Name": "one sentence tip", ...}}'
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={'model': OLLAMA_MODEL, 'prompt': prompt, 'stream': False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise CoachError('Ollama timed out')
    except requests.exceptions.RequestException as e:
        raise CoachError(f'Ollama request failed: {e}')

    raw = resp.json().get('response', '')
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        raise CoachError('Ollama returned no JSON')
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        raise CoachError('Ollama returned invalid JSON')
    if 'tips' not in data:
        raise CoachError('Ollama response missing tips key')
    return data['tips']
