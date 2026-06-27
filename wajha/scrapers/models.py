from django.db import models
from django.conf import settings


class GrantSource(models.Model):
    """
    Represents a scholarship website that the scraper targets.
    Each source can be enabled/disabled and tracks scraping health.
    """
    FREQUENCY_CHOICES = [
        ('daily',   'Daily'),
        ('weekly',  'Weekly'),
        ('monthly', 'Monthly'),
    ]

    name            = models.CharField(max_length=300)
    url             = models.CharField(max_length=500)
    frequency       = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    selector_map    = models.JSONField(
                          default=dict, blank=True,
                          help_text="CSS/XPath selectors used by the scraper for this source"
                      )
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    failure_count   = models.IntegerField(default=0)

    class Meta:
        db_table = 'grantsource'
        verbose_name = 'Grant Source'
        verbose_name_plural = 'Grant Sources'

    def __str__(self):
        return f"{self.name} ({self.url})"


class ScrapedGrant(models.Model):
    """
    Staging table for raw scraped data.
    Admins review entries here before publishing them to the main grants table.
    """
    STATUS_CHOICES = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    source          = models.ForeignKey(
                          GrantSource,
                          on_delete=models.SET_NULL,
                          null=True, blank=True,
                          related_name='scraped_grants'
                      )
    raw_title       = models.TextField()
    raw_html_snippet= models.TextField(blank=True)
    parsed_data     = models.JSONField(
                          default=dict, blank=True,
                          help_text="Structured data extracted by the scraper (title, deadline, url, etc.)"
                      )
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    scraped_at      = models.DateTimeField(auto_now_add=True, db_column='scraped_at')
    reviewed_by     = models.ForeignKey(
                          settings.AUTH_USER_MODEL,
                          on_delete=models.SET_NULL,
                          null=True, blank=True,
                          db_column='reviewed_by',
                          related_name='reviewed_scraped_grants'
                      )

    class Meta:
        db_table = 'scrapedgrant'
        verbose_name = 'Scraped Grant'
        verbose_name_plural = 'Scraped Grants'
        ordering = ['-scraped_at']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.raw_title[:60]}"

    @property
    def source_url(self):
        return self.parsed_data.get('url', '')

    @property
    def deadline(self):
        return self.parsed_data.get('deadline', 'N/A')
