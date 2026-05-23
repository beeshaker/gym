from django.urls import path
from . import views
from workouts import views as workout_views

urlpatterns = [
    path('', views.index, name='gym_index'),
    path('pin/', views.pin, name='gym_pin'),
    path('dashboard/', views.dashboard, name='gym_dashboard'),
    path('exercises/', workout_views.exercises, name='gym_exercises'),
]
