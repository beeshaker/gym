from django.shortcuts import render
from .models import Exercise


def exercises(request):
    exercise_list = Exercise.objects.filter(is_active=True).order_by('category', 'name')
    return render(request, 'workouts/exercises.html', {'exercises': exercise_list})
