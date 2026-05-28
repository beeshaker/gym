import json

from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Exercise, WorkoutExercise, WorkoutSession, WorkoutSet
from .nl_parser import NLParseError, parse
from .coach import CoachError, get_ollama_tips, recommend


def _get_recommendations(session):
    recommendations = {}
    workout_exercises = list(
        session.workout_exercises.select_related('exercise').prefetch_related('sets')
    )
    for we in workout_exercises:
        last_we = (WorkoutExercise.objects
                   .filter(exercise=we.exercise, session__status='complete')
                   .exclude(session=session)
                   .order_by('-session__completed_at')
                   .first())
        last_sets = list(last_we.sets.all()) if last_we else []
        recommendations[we.exercise.id] = recommend(we.exercise, last_sets)
    return workout_exercises, recommendations


def exercises(request):
    exercise_list = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'workouts/exercises.html', {'exercises': exercise_list})


def log_home(request):
    active = WorkoutSession.objects.filter(status='active').first()
    if active:
        return redirect('gym_active_session', session_id=active.id)
    return render(request, 'workouts/log_home.html')


@require_http_methods(['POST'])
def start_session(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return render(request, 'workouts/log_home.html', {'error': 'Please enter a session name.'})
    session = WorkoutSession.objects.create(name=name)
    return redirect('gym_active_session', session_id=session.id)


def active_session(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    if session.status == 'complete':
        return redirect('gym_session_detail', session_id=session.id)
    all_exercises = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    workout_exercises, recommendations = _get_recommendations(session)
    return render(request, 'workouts/active_session.html', {
        'session': session,
        'workout_exercises': workout_exercises,
        'all_exercises': all_exercises,
        'recommendations': recommendations,
    })


@require_http_methods(['POST'])
def add_exercise(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    exercise = get_object_or_404(Exercise, id=request.POST.get('exercise_id'))
    order = session.workout_exercises.count() + 1
    WorkoutExercise.objects.create(session=session, exercise=exercise, order=order)
    return redirect('gym_active_session', session_id=session.id)


@require_http_methods(['POST'])
def add_set(request, session_id, we_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    we = get_object_or_404(WorkoutExercise, id=we_id, session=session)
    try:
        weight_kg = float(request.POST.get('weight_kg', ''))
        reps = int(request.POST.get('reps', ''))
        if weight_kg < 0 or reps < 1:
            raise ValueError
    except (ValueError, TypeError):
        return redirect('gym_active_session', session_id=session.id)
    set_number = we.sets.count() + 1
    WorkoutSet.objects.create(workout_exercise=we, set_number=set_number, weight_kg=weight_kg, reps=reps)
    return redirect('gym_active_session', session_id=session.id)


@require_http_methods(['POST'])
def delete_set(request, session_id, we_id, set_id):
    ws = get_object_or_404(
        WorkoutSet, id=set_id,
        workout_exercise__id=we_id,
        workout_exercise__session__id=session_id,
    )
    ws.delete()
    return redirect('gym_active_session', session_id=session_id)


@require_http_methods(['POST'])
def finish_session(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    session.status = 'complete'
    session.completed_at = timezone.now()
    session.save()
    return redirect('gym_history')


def history(request):
    exercises_qs = WorkoutExercise.objects.select_related('exercise').annotate(
        max_weight=Max('sets__weight_kg')
    ).order_by('order')
    sessions = WorkoutSession.objects.filter(status='complete').prefetch_related(
        Prefetch('workout_exercises', queryset=exercises_qs)
    )
    return render(request, 'workouts/history.html', {'sessions': sessions})


def session_detail(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    workout_exercises = session.workout_exercises.select_related('exercise').prefetch_related('sets')
    return render(request, 'workouts/session_detail.html', {
        'session': session,
        'workout_exercises': workout_exercises,
    })


@require_http_methods(['POST'])
def nl_parse(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'No text provided'}, status=422)
    active_exercises = Exercise.objects.filter(is_active=True)
    try:
        result = parse(text, active_exercises)
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
    with transaction.atomic():
        for ex_data in exercises_data:
            exercise_name = ex_data.get('name', '')
            if not exercise_name:
                continue
            exercise = Exercise.objects.filter(name__iexact=exercise_name, is_active=True).first()
            if exercise is None:
                continue
            we, _ = WorkoutExercise.objects.get_or_create(
                session=session,
                exercise=exercise,
                defaults={'order': session.workout_exercises.count() + 1},
            )
            set_number_start = we.sets.count() + 1
            for i, set_data in enumerate(ex_data.get('sets', [])):
                try:
                    weight_kg = float(set_data.get('weight_kg', 0))
                    reps = int(set_data.get('reps', 1))
                except (TypeError, ValueError):
                    continue
                if weight_kg < 0 or reps < 1:
                    continue
                WorkoutSet.objects.create(
                    workout_exercise=we,
                    set_number=set_number_start + i,
                    weight_kg=weight_kg,
                    reps=reps,
                )
    return redirect('gym_active_session', session_id=session.id)


@require_http_methods(['GET'])
def coach_view(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    workout_exercises, recommendations = _get_recommendations(session)
    return render(request, 'workouts/coach.html', {
        'session': session,
        'workout_exercises': workout_exercises,
        'recommendations': recommendations,
    })


@require_http_methods(['POST'])
def coach_tips(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, status='active')
    workout_exercises, recommendations = _get_recommendations(session)
    exercises_with_recs = []
    for we in workout_exercises:
        rec = recommendations.get(we.exercise.id, {})
        exercises_with_recs.append({'name': we.exercise.name, **rec})
    try:
        tips = get_ollama_tips(exercises_with_recs)
        return JsonResponse({'tips': tips})
    except CoachError as e:
        return JsonResponse(
            {'error': str(e) or 'Could not get tips — try again'},
            status=422,
        )
