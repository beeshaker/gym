from django.urls import path
from . import views

urlpatterns = [
    path('', views.exercises, name='gym_exercises'),
]
