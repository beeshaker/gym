from django.contrib import admin
from .models import Exercise, ExerciseAlias


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
