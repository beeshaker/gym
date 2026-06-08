import json
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Exercise, Program, ProgramDay, ProgramExercise, WorkoutExercise, WorkoutSession, WorkoutSet
from .nl_parser import NLParseError, parse
from .coach import CoachError, get_ollama_tips, recommend
from .repeat import get_last_sessions_by_category, get_repeat_preview


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


def _log_home_context():
    last_by_cat = get_last_sessions_by_category()
    repeat_options = [
        {
            'category': cat,
            'label': dict(Exercise.CATEGORY_CHOICES)[cat],
            'last_date': session.completed_at,
            'exercise_count': len(session.workout_exercises.all()),
        }
        for cat, session in last_by_cat.items()
    ]
    programs = list(Program.objects.filter(is_active=True).prefetch_related('days'))
    return {'repeat_options': repeat_options, 'programs': programs}


def _create_session_from_form(request):
    """
    Reads name + exercise_id list + weight_{ex_id}_{n}/reps_{ex_id}_{n} from POST.
    Creates WorkoutSession + WorkoutExercise + WorkoutSet in transaction.atomic().
    Returns the new WorkoutSession.
    Raises ValueError if name is empty.
    """
    name = request.POST.get('name', '').strip()
    if not name:
        raise ValueError('name required')
    exercise_ids = request.POST.getlist('exercise_id')
    with transaction.atomic():
        session = WorkoutSession.objects.create(name=name)
        for order, ex_id in enumerate(exercise_ids, start=1):
            try:
                exercise = Exercise.objects.get(id=ex_id, is_active=True)
            except Exercise.DoesNotExist:
                continue
            try:
                rest_val = int(request.POST.get(f'rest_{ex_id}', ''))
                if rest_val <= 0:
                    rest_val = None
            except (ValueError, TypeError):
                rest_val = None
            we = WorkoutExercise.objects.create(
                session=session, exercise=exercise, order=order,
                planned_rest_seconds=rest_val,
            )
            n = 1
            while True:
                weight_key = f'weight_{ex_id}_{n}'
                reps_key = f'reps_{ex_id}_{n}'
                if weight_key not in request.POST:
                    break
                try:
                    weight = float(request.POST[weight_key])
                    reps = int(request.POST[reps_key])
                    if weight < 0 or reps < 1:
                        n += 1
                        continue
                except (ValueError, TypeError, KeyError):
                    n += 1
                    continue
                WorkoutSet.objects.create(
                    workout_exercise=we, set_number=n,
                    weight_kg=weight, reps=reps,
                )
                n += 1
    return session


def exercises(request):
    exercise_list = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'workouts/exercises.html', {'exercises': exercise_list})


def log_home(request):
    active = WorkoutSession.objects.filter(status='active').first()
    if active:
        return redirect('gym_active_session', session_id=active.id)
    return render(request, 'workouts/log_home.html', _log_home_context())


@require_http_methods(['POST'])
def start_session(request):
    name = request.POST.get('name', '').strip()
    if not name:
        ctx = _log_home_context()
        ctx['error'] = 'Please enter a session name.'
        return render(request, 'workouts/log_home.html', ctx)
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
    url = reverse('gym_active_session', kwargs={'session_id': session.id})
    return HttpResponseRedirect(f'{url}?timer={we_id}')


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


@require_http_methods(['GET'])
def repeat_preview(request, category):
    preview = get_repeat_preview(category)
    if preview is None:
        raise Http404
    today = timezone.localdate()
    label = dict(Exercise.CATEGORY_CHOICES).get(category, category.title())
    session_name = f"{today.strftime('%A')} {label}"
    return render(request, 'workouts/repeat_preview.html', {
        'category': category,
        'session_name': session_name,
        'exercises': preview['exercises'],
    })


@require_http_methods(['POST'])
def repeat_start(request, category):
    try:
        session = _create_session_from_form(request)
    except ValueError:
        return redirect('gym_log_home')
    return redirect('gym_active_session', session_id=session.id)


@require_http_methods(['GET'])
def program_day_list(request, program_id):
    program = get_object_or_404(Program, id=program_id, is_active=True)
    days = program.days.all()
    return render(request, 'workouts/program_days.html', {
        'program': program,
        'days': days,
    })


@require_http_methods(['GET'])
def program_preview(request, day_id):
    day = get_object_or_404(ProgramDay, id=day_id, program__is_active=True)
    today = timezone.localdate()
    session_name = f"{today.strftime('%A')} {day.name}"
    program_exercises = (day.exercises
                         .select_related('exercise')
                         .order_by('order'))
    exercise_ids = [pe.exercise_id for pe in program_exercises]
    last_wes = (WorkoutExercise.objects
                .filter(exercise_id__in=exercise_ids, session__status='complete')
                .prefetch_related('sets')
                .order_by('exercise_id', '-session__completed_at')
                .distinct('exercise_id'))
    last_we_by_exercise = {lw.exercise_id: lw for lw in last_wes}
    exercises_data = []
    for pe in program_exercises:
        last_we = last_we_by_exercise.get(pe.exercise_id)
        last_sets = list(last_we.sets.all()) if last_we else []
        eff = SimpleNamespace(
            default_min_reps=pe.effective_min_reps(),
            default_max_reps=pe.effective_max_reps(),
            default_increment=pe.exercise.default_increment,
        )
        rec = recommend(eff, last_sets)
        sets_count = rec['last_sets_count'] if rec['last_sets_count'] > 0 else pe.effective_sets()
        exercises_data.append({
            'exercise': pe.exercise,
            'rec': rec,
            'sets_count': sets_count,
            'sets': [
                {'n': i, 'weight': rec['target_weight'], 'reps': rec['target_reps_min']}
                for i in range(1, sets_count + 1)
            ],
        })
    return render(request, 'workouts/program_preview.html', {
        'day': day,
        'session_name': session_name,
        'exercises': exercises_data,
    })


@require_http_methods(['GET'])
def program_swap_options(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    alternatives = (Exercise.objects
                    .filter(muscle_group=exercise.muscle_group, is_active=True)
                    .exclude(id=exercise_id)
                    .order_by('equipment', 'name'))
    return JsonResponse({'alternatives': [
        {
            'id': e.id,
            'name': e.name,
            'equipment': e.get_equipment_display(),
            'movement_type': e.get_movement_type_display(),
        }
        for e in alternatives
    ]})


@require_http_methods(['POST'])
def program_start(request):
    try:
        session = _create_session_from_form(request)
    except ValueError:
        return redirect('gym_log_home')
    return redirect('gym_active_session', session_id=session.id)
