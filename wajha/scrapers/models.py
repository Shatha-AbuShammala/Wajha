import datetime
import re

from django.db import models
from django.conf import settings
from django.utils import timezone


# ---------------------------------------------------------------------------
# Module-level constant shared by ScrapedGrant.attach_related()
# ---------------------------------------------------------------------------

DEGREE_MAP = {
    'bachelor': 'bachelor',
    'master':   'master',
    'phd':      'phd',
    'diploma':  'diploma',
}


class GrantSource(models.Model):
    """
    Represents a scholarship website that the scraper targets.
    Each source can be enabled/disabled and tracks scraping health.
    """

    class Frequency(models.TextChoices):
        DAILY   = 'daily',   'Daily'
        WEEKLY  = 'weekly',  'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    name            = models.CharField(max_length=300)
    url             = models.CharField(max_length=500)
    frequency       = models.CharField(
                          max_length=10,
                          choices=Frequency.choices,
                          default=Frequency.WEEKLY,
                      )
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

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    # Fallback constants used during approval
    DEFAULT_SOURCE_URL = 'https://opportunitydesk.org/'
    DEFAULT_ORG_NAME   = 'Opportunity Desk'

    source           = models.ForeignKey(
                           GrantSource,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='scraped_grants'
                       )
    raw_title        = models.TextField()
    raw_html_snippet = models.TextField(blank=True)
    parsed_data      = models.JSONField(
                           default=dict, blank=True,
                           help_text="Structured data extracted by the scraper (title, deadline, url, etc.)"
                       )
    status           = models.CharField(
                           max_length=10,
                           choices=Status.choices,
                           default=Status.PENDING,
                       )
    scraped_at       = models.DateTimeField(auto_now_add=True, db_column='scraped_at')
    reviewed_by      = models.ForeignKey(
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

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def source_url(self):
        """Return the scraped grant's source URL from parsed_data."""
        return self.parsed_data.get('url', '')

    @property
    def deadline(self):
        """Return the raw deadline string from parsed_data, or 'N/A'."""
        return self.parsed_data.get('deadline', 'N/A')

    # ------------------------------------------------------------------ #
    # Business-logic helpers (fat model)                                   #
    # ------------------------------------------------------------------ #

    def get_source_url(self):
        """Resolve the best available URL for this grant, with fallbacks."""
        url = self.parsed_data.get('url', '')
        if not url and self.source:
            url = self.source.url
        if not url:
            url = self.DEFAULT_SOURCE_URL
        return url

    def get_organization(self):
        """Resolve the organization name, with fallbacks."""
        org = self.parsed_data.get('organization', '')
        if not org and self.source:
            org = self.source.name
        if not org:
            org = self.DEFAULT_ORG_NAME
        return org

    def get_eligibility(self):
        """Return eligibility text, falling back to a generic guidance message."""
        eligibility = self.parsed_data.get('eligibility_text', '').strip()
        if not eligibility:
            eligibility = 'Please refer to the source website link for detailed eligibility criteria.'
        return eligibility

    def guess_funding_type(self):
        """Infer funding type from the grant title and description text."""
        desc = self.parsed_data.get('description', '') or self.raw_title
        search_text = (self.raw_title + ' ' + desc).lower()
        if 'partial' in search_text:
            return 'partial'
        if 'tuition' in search_text:
            return 'tuition_only'
        if 'stipend' in search_text:
            return 'stipend_only'
        if 'travel' in search_text:
            return 'travel_grant'
        return 'fully_funded'

    def is_duplicate(self):
        """Return True if a GrantOpportunity with the same source URL already exists."""
        from grants.models import GrantOpportunity  # local import to avoid circular dependency
        return GrantOpportunity.objects.filter(source_url=self.get_source_url()).exists()

    def attach_related(self, grant):
        """
        Persist countries, degree levels, and fields of study onto a GrantOpportunity.
        Called after the grant record is created during approval.
        """
        from grants.models import GrantCountry, GrantDegreeLevel, GrantFieldOfStudy

        # Countries (supports both list and single-value formats)
        countries = self.parsed_data.get('countries', [])
        if not countries:
            single = self.parsed_data.get('country', '').strip()
            if single:
                countries = [single]
        for country_name in countries:
            country_name = country_name.strip()
            if country_name:
                GrantCountry.objects.get_or_create(grant=grant, country_name=country_name)

        # Degree levels
        for label in self.parsed_data.get('degree_types', []):
            key = DEGREE_MAP.get(label.lower())
            if key:
                GrantDegreeLevel.objects.get_or_create(grant=grant, degree=key)

        # Fields of study
        for field_name in self.parsed_data.get('fields_of_study', []):
            field_name = field_name.strip()
            if field_name:
                GrantFieldOfStudy.objects.get_or_create(grant=grant, field_name=field_name)

    def approve_to_grant(self, added_by, grant_status='published'):
        """
        Create a GrantOpportunity from this scraped entry and mark it as approved.

        Returns:
            (grant, True)  - grant was created successfully.
            (None,  False) - a duplicate URL already exists; status still set to approved.
        """
        from grants.models import GrantOpportunity

        url = self.get_source_url()

        if self.is_duplicate():
            # Duplicate — mark approved without creating a new record
            ScrapedGrant.objects.filter(pk=self.pk).update(status=self.Status.APPROVED)
            return None, False

        deadline_date = self.parse_deadline_date(self.parsed_data.get('deadline', ''))
        if not deadline_date:
            deadline_date = timezone.now().date() + datetime.timedelta(days=30)

        grant = GrantOpportunity.objects.create(
            title=self.raw_title,
            organization=self.get_organization(),
            description=self.parsed_data.get('description', '') or self.raw_title,
            eligibility_text=self.get_eligibility(),
            eligibility_summary='No AI summary generated yet.',
            funding_type=self.guess_funding_type(),
            deadline=deadline_date,
            source_url=url,
            status=grant_status,
            added_by_id=added_by.pk,
        )

        self.attach_related(grant)
        ScrapedGrant.objects.filter(pk=self.pk).update(status=self.Status.APPROVED)
        return grant, True

    def reject(self):
        """
        Mark this grant as rejected.
        If it was previously approved, deletes any live GrantOpportunity created from it.
        """
        if self.status == self.Status.APPROVED:
            from grants.models import GrantOpportunity
            url = self.get_source_url()
            if url:
                GrantOpportunity.objects.filter(source_url=url).delete()

        ScrapedGrant.objects.filter(pk=self.pk).update(status=self.Status.REJECTED)

    # ------------------------------------------------------------------ #
    # Static utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_deadline_date(deadline_str):
        """
        Parse a loose deadline string into a `datetime.date` object.

        Handles ISO format (YYYY-MM-DD) and natural-language formats such as
        "March 15, 2025" or "15 Jan 2026". Returns `None` when the string
        is empty, unrecognised, or explicitly marked as unspecified.
        """
        if not deadline_str:
            return None
        deadline_str = deadline_str.strip()
        if deadline_str.lower() in {'unspecified', 'n/a', 'none', '—', ''}:
            return None

        # ISO format: YYYY-MM-DD
        iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', deadline_str)
        if iso_match:
            try:
                return datetime.date(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3))
                )
            except ValueError:
                pass

        months = {
            'january': 1, 'february': 2, 'march': 3,    'april': 4,
            'may': 5,     'june': 6,     'july': 7,      'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        }

        normalized = re.sub(r'[^\w\s]', ' ', deadline_str.lower())
        parts = normalized.split()
        year = month = day = None

        for part in parts:
            if part.isdigit() and len(part) == 4 and part.startswith('20'):
                year = int(part)
                break
        for part in parts:
            if part in months:
                month = months[part]
                break
        for part in parts:
            if part.isdigit() and len(part) <= 2:
                val = int(part)
                if 1 <= val <= 31:
                    day = val

        if year and month:
            try:
                return datetime.date(year, month, day or 1)
            except ValueError:
                pass
        return None
