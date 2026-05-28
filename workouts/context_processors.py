def active_session(request):
    from workouts.models import WorkoutSession
    session = WorkoutSession.objects.filter(status='active').first()
    return {'active_session': session}
