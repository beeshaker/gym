from collections import Counter

from .coach import recommend

VALID_CATEGORIES = {'push', 'pull', 'legs', 'upper_arms', 'conditioning_abs'}


def session_category(workout_exercises) -> str | None:
    """
    Returns the most common exercise category across workout_exercises,
    or None if the list is empty.
    workout_exercises: iterable of objects with .exercise.category
    """
    cats = [we.exercise.category for we in workout_exercises]
    if not cats:
        return None
    return Counter(cats).most_common(1)[0][0]


def get_last_sessions_by_category() -> dict:
    """
    Returns {category_key: WorkoutSession} for each category that has at
    least one completed session. Only includes keys in VALID_CATEGORIES.
    """
    from .models import WorkoutSession
    completed = (WorkoutSession.objects
                 .filter(status='complete')
                 .order_by('-completed_at')
                 .prefetch_related('workout_exercises__exercise'))
    last_by_cat = {}
    for session in completed:
        wes = list(session.workout_exercises.all())
        cat = session_category(wes)
        if cat and cat in VALID_CATEGORIES and cat not in last_by_cat:
            last_by_cat[cat] = session
        if len(last_by_cat) == len(VALID_CATEGORIES):
            break
    return last_by_cat


def get_repeat_preview(category: str) -> dict | None:
    """
    Returns None if category is invalid or no completed session exists for it.
    Otherwise returns:
    {
      'session': WorkoutSession,
      'exercises': [
        {
          'exercise': Exercise,
          'rec': recommend() dict,
          'sets_count': int,
          'sets': [{'n': int, 'weight': float, 'reps': int}, ...]
        },
        ...
      ]
    }
    """
    if category not in VALID_CATEGORIES:
        return None
    last_by_cat = get_last_sessions_by_category()
    template_session = last_by_cat.get(category)
    if template_session is None:
        return None

    from .models import WorkoutExercise

    exercises_data = []
    wes = (template_session.workout_exercises
           .select_related('exercise')
           .prefetch_related('sets')
           .order_by('order'))

    # Batch query to find last completed workout exercise for each exercise
    exercise_ids = [we.exercise_id for we in wes]
    last_wes_qs = (WorkoutExercise.objects
                   .filter(exercise_id__in=exercise_ids, session__status='complete')
                   .select_related('exercise')
                   .prefetch_related('sets')
                   .order_by('exercise_id', '-session__completed_at')
                   .distinct('exercise_id'))
    last_we_by_exercise = {lw.exercise_id: lw for lw in last_wes_qs}

    for we in wes:
        last_we = last_we_by_exercise.get(we.exercise_id)
        last_sets = list(last_we.sets.all()) if last_we else []
        rec = recommend(we.exercise, last_sets)
        sets_count = rec['last_sets_count'] if rec['last_sets_count'] > 0 else we.exercise.default_sets
        exercises_data.append({
            'exercise': we.exercise,
            'rec': rec,
            'sets_count': sets_count,
            'sets': [
                {'n': i, 'weight': rec['target_weight'], 'reps': rec['target_reps_min']}
                for i in range(1, sets_count + 1)
            ],
        })

    return {'session': template_session, 'exercises': exercises_data}
