from django.db import models
from django.conf import settings
from django.utils import timezone


# GRANT OPPORTUNITY
class GrantOpportunity(models.Model):

    FUNDING_TYPE_CHOICES = [
        ('fully_funded', 'Fully Funded'),
        ('partial', 'Partial'),
        ('tuition_only', 'Tuition Only'),
        ('stipend_only', 'Stipend Only'),
        ('travel_grant', 'Travel Grant'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    # --- Basic Info ---
    title = models.CharField(max_length=300)
    organization = models.CharField(max_length=200)
    description = models.TextField()

    # --- Eligibility ---
    eligibility_text = models.TextField()
    eligibility_summary = models.TextField(
        blank=True,
        help_text="AI-generated plain-language summary of eligibility."
    )

    # --- Funding ---
    funding_type = models.CharField(
        max_length=50,
        choices=FUNDING_TYPE_CHOICES
    )

    # --- Dates ---
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Source ---
    source_url = models.URLField(max_length=500)

    # --- Status ---
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # --- Added By ---
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='added_grants'
    )

    class Meta:
        ordering = ['deadline']
        verbose_name = 'Grant Opportunity'
        verbose_name_plural = 'Grant Opportunities'

    def __str__(self):
        return f"{self.title} — {self.organization}"

    def days_until_deadline(self):
        """Returns number of days until deadline."""
        return (self.deadline - timezone.now().date()).days

    def is_urgent(self):
        """Returns True if deadline is within 30 days."""
        return 0 <= self.days_until_deadline() <= 30

    def is_expired(self):
        """Returns True if deadline has passed."""
        return self.days_until_deadline() < 0


# =============================================================================
# TAG TABLES
# =============================================================================

class GrantFieldOfStudy(models.Model):
    """
    One grant can have multiple fields of study.
    Example: Computer Science, Engineering
    """

    grant = models.ForeignKey(
        GrantOpportunity,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    field_name = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Field of Study'
        verbose_name_plural = 'Fields of Study'
        unique_together = ('grant', 'field_name')

    def __str__(self):
        return f"{self.grant.title} — {self.field_name}"


class GrantDegreeLevel(models.Model):
    """
    One grant can support multiple degree levels.
    """

    DEGREE_CHOICES = [
        ('bachelor', 'Bachelor'),
        ('master', 'Master'),
        ('phd', 'PhD'),
        ('diploma', 'Diploma'),
    ]

    grant = models.ForeignKey(
        GrantOpportunity,
        on_delete=models.CASCADE,
        related_name='degree_levels'
    )
    degree = models.CharField(
        max_length=20,
        choices=DEGREE_CHOICES
    )

    class Meta:
        verbose_name = 'Degree Level'
        verbose_name_plural = 'Degree Levels'
        unique_together = ('grant', 'degree')

    def __str__(self):
        return f"{self.grant.title} — {self.get_degree_display()}"


class GrantCountry(models.Model):
    """
    One grant can be available for multiple countries.
    Example: Germany, Palestine, Jordan
    """

    grant = models.ForeignKey(
        GrantOpportunity,
        on_delete=models.CASCADE,
        related_name='countries'
    )
    country_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Grant Country'
        verbose_name_plural = 'Grant Countries'
        unique_together = ('grant', 'country_name')

    def __str__(self):
        return f"{self.grant.title} — {self.country_name}"