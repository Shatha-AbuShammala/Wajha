"""
Base scraper class.
All scholarship scrapers must inherit from BaseScraper and implement `scrape()`.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseScraper:
    """
    Abstract base for all scrapers.

    Subclasses must define:
        - source_name (str)     : Name of the scholarship site
        - source_url  (str)     : Root URL being scraped

    And implement:
        - scrape() -> list[dict]: Returns a list of parsed grant dicts
    """

    source_name: str = ''
    source_url:  str = ''

    def __init__(self):
        if not self.source_name or not self.source_url:
            raise NotImplementedError("Subclasses must set source_name and source_url")

    def scrape(self) -> list[dict]:
        """Override this in each scraper. Return a list of grant dicts."""
        raise NotImplementedError("Subclasses must implement scrape()")

    def run(self):
        """
        Called by the management command / Celery task.
        Fetches data, saves to ScrapedGrant, updates GrantSource stats.
        """
        from scrapers.models import GrantSource, ScrapedGrant

        # Get or create the GrantSource record
        source, _ = GrantSource.objects.get_or_create(
            url=self.source_url,
            defaults={'name': self.source_name, 'is_active': True}
        )

        if not source.is_active:
            logger.info(f"[{self.source_name}] Source is disabled. Skipping.")
            return

        logger.info(f"[{self.source_name}] Starting scrape...")
        saved = 0

        try:
            grants = self.scrape()

            for grant in grants:
                title = grant.get('title', '').strip()
                grant_url = grant.get('url', '').strip()
                if not title:
                    continue

                # Use source + URL as a stable deduplication key.
                # If the same listing appears on the next run, we skip it
                # instead of creating a duplicate in the review queue.
                raw_html = grant.pop('raw_html', '')
                obj, created = ScrapedGrant.objects.get_or_create(
                    source=source,
                    parsed_data__url=grant_url if grant_url else None,
                    defaults={
                        'raw_title': title,
                        'raw_html_snippet': raw_html,
                        'parsed_data': grant,
                        'status': 'pending',
                    }
                )
                if created:
                    saved += 1
                else:
                    logger.debug(f"[{self.source_name}] Skipped duplicate: {title[:60]}")

            # Update source health
            source.last_scraped_at = timezone.now()
            source.failure_count   = 0
            source.save(update_fields=['last_scraped_at', 'failure_count'])

            logger.info(f"[{self.source_name}] Done — {saved} grants saved.")

        except Exception as exc:
            source.failure_count += 1
            source.save(update_fields=['failure_count'])
            logger.error(f"[{self.source_name}] Scrape failed: {exc}", exc_info=True)
            raise
