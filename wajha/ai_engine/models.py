from django.db import models

# Create your models here.

from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()

class AIMatch(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_matches')
    grant = models.ForeignKey('grants.GrantOpportunity', on_delete=models.CASCADE, related_name='student_matches')
    match_score = models.DecimalField(max_digits=5, decimal_places=2)
    explanation = models.TextField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'aimatch'
        ordering = ['-match_score'] 
        verbose_name = "AI Match"
        verbose_name_plural = "AI Matches"

    @property
    def fit_status(self):
        score = float(self.match_score)
        if score >= 85:
            return "strong fit"
        elif score >= 70:
            return "good fit"
        return "fair fit"

    def __str__(self):
        return f"{self.student.username} <-> {self.grant.title} ({self.match_score}%)"