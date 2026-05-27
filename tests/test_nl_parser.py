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
