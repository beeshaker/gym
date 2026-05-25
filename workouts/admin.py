from django.contrib import admin

from .models import Exercise, ExerciseAlias, WorkoutExercise, WorkoutSession, WorkoutSet


class ExerciseAliasInline(admin.TabularInline):
    model = ExerciseAlias
    extra = 1
    fields = ('alias',)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'equipment', 'movement_type', 'is_active')
    list_filter = ('category', 'equipment', 'movement_type', 'is_active')
    search_fields = ('name', 'muscle_group')
    inlines = [ExerciseAliasInline]
    ordering = ('category', 'name')


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0
    fields = ('exercise', 'order')
    readonly_fields = ('order',)


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'started_at', 'completed_at')
    list_filter = ('status',)
    readonly_fields = ('started_at', 'completed_at')
    inlines = [WorkoutExerciseInline]
