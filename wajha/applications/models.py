from django.db import models
from django.conf import settings
from django.utils import timezone
from grants.models import GrantOpportunity


class Application(models.Model):
    STATUS_CHOICES = [
        ('saved', 'Saved'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    grant = models.ForeignKey(
        GrantOpportunity,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='saved')
    letter_drafted = models.BooleanField(default=False)
    motivation_letter_text = models.TextField(blank=True, default='')
    note = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = ('student', 'grant')

    def days_left(self):
        return self.grant.days_until_deadline()

    def __str__(self):
        return f"{self.student} - {self.grant} ({self.status})"