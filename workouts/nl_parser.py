import difflib
import json
import re

import requests


class NLParseError(Exception):
    pass


OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'qwen2.5:7b'
OLLAMA_TIMEOUT = 30


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
            if 'reps' in s:
                s['reps'] = int(s['reps'])
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
