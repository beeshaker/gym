from django.db import models


class Exercise(models.Model):
    CATEGORY_CHOICES = [
        ('push', 'Push'),
        ('pull', 'Pull'),
        ('legs', 'Legs'),
        ('upper_arms', 'Upper/Arms'),
        ('conditioning_abs', 'Conditioning/Abs'),
    ]
    EQUIPMENT_CHOICES = [
        ('barbell', 'Barbell'),
        ('dumbbell', 'Dumbbell'),
        ('machine', 'Machine'),
        ('cable', 'Cable'),
        ('bodyweight', 'Bodyweight'),
    ]
    MOVEMENT_CHOICES = [
        ('compound', 'Compound'),
        ('isolation', 'Isolation'),
        ('cardio', 'Cardio'),
        ('core', 'Core'),
    ]

    name = models.CharField(max_length=100, unique=True)
    muscle_group = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    equipment = models.CharField(max_length=20, choices=EQUIPMENT_CHOICES)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    default_min_reps = models.PositiveIntegerField(default=8)
    default_max_reps = models.PositiveIntegerField(default=12)
    default_sets = models.PositiveIntegerField(default=3)
    default_increment = models.DecimalField(max_digits=4, decimal_places=1, default=2.5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ExerciseAlias(models.Model):
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name='aliases'
    )
    alias = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('exercise', 'alias')]
        verbose_name_plural = 'exercise aliases'

    def __str__(self):
        return f'{self.alias} → {self.exercise.name}'
