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


class WorkoutSession(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('complete', 'Complete')]

    name         = models.CharField(max_length=100)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    started_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.name} ({self.started_at:%Y-%m-%d})'


class WorkoutExercise(models.Model):
    session  = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='workout_exercises')
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name='workout_exercises')
    order    = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.session.name} — {self.exercise.name}'


class WorkoutSet(models.Model):
    workout_exercise = models.ForeignKey(WorkoutExercise, on_delete=models.CASCADE, related_name='sets')
    set_number       = models.PositiveIntegerField()
    weight_kg        = models.DecimalField(max_digits=5, decimal_places=1)
    reps             = models.PositiveIntegerField()
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['set_number']

    def __str__(self):
        return f'Set {self.set_number}: {self.weight_kg}kg × {self.reps}'
