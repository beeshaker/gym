from django.urls import path

from . import views
from workouts import views as workout_views

urlpatterns = [
    path('', views.index, name='gym_index'),
    path('pin/', views.pin, name='gym_pin'),
    path('dashboard/', views.dashboard, name='gym_dashboard'),
    path('exercises/', workout_views.exercises, name='gym_exercises'),
    # Workout logging
    path('log/', workout_views.log_home, name='gym_log_home'),
    path('log/start/', workout_views.start_session, name='gym_log_start'),
    path('log/<int:session_id>/', workout_views.active_session, name='gym_active_session'),
    path('log/<int:session_id>/add-exercise/', workout_views.add_exercise, name='gym_add_exercise'),
    path('log/<int:session_id>/exercise/<int:we_id>/add-set/', workout_views.add_set, name='gym_add_set'),
    path('log/<int:session_id>/exercise/<int:we_id>/delete-set/<int:set_id>/', workout_views.delete_set, name='gym_delete_set'),
    path('log/<int:session_id>/finish/', workout_views.finish_session, name='gym_finish_session'),
    path('log/<int:session_id>/cancel/', workout_views.cancel_session, name='gym_cancel_session'),
    path('log/<int:session_id>/nl-parse/', workout_views.nl_parse, name='gym_nl_parse'),
    path('log/<int:session_id>/nl-confirm/', workout_views.nl_confirm, name='gym_nl_confirm'),
    path('log/<int:session_id>/coach/', workout_views.coach_view, name='gym_coach'),
    path('log/<int:session_id>/coach-tips/', workout_views.coach_tips, name='gym_coach_tips'),
    path('log/repeat/<str:category>/', workout_views.repeat_preview, name='gym_repeat_preview'),
    path('log/repeat/<str:category>/start/', workout_views.repeat_start, name='gym_repeat_start'),
    # Programs
    path('programs/start/', workout_views.program_start, name='gym_program_start'),
    path('programs/<int:program_id>/', workout_views.program_day_list, name='gym_program_days'),
    path('programs/<int:day_id>/preview/', workout_views.program_preview, name='gym_program_preview'),
    path('programs/swap/<int:exercise_id>/', workout_views.program_swap_options, name='gym_program_swap'),
    path('programs/<int:day_id>/chat/', workout_views.program_chat, name='gym_program_chat'),
    # History
    path('history/', workout_views.history, name='gym_history'),
    path('history/<int:session_id>/', workout_views.session_detail, name='gym_session_detail'),
    path('history/<int:session_id>/delete/', workout_views.delete_session, name='gym_delete_session'),
]
