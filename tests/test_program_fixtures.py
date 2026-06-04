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
