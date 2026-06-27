from celery import shared_task
from scrapers.scraper_scripts import ALL_SCRAPERS
import logging

logger = logging.getLogger(__name__)


@shared_task(name="scrapers.tasks.run_all_scrapers_task")
def run_all_scrapers_task():
    """
    Celery task that runs all registered scrapers.
    """
    logger.info("Celery task: starting run_all_scrapers...")
    success = 0
    failed = 0

    for ScraperClass in ALL_SCRAPERS:
        scraper = ScraperClass()
        try:
            logger.info(f"Running scraper: {scraper.source_name}")
            scraper.run()
            success += 1
        except Exception as e:
            logger.error(f"Scraper {scraper.source_name} failed: {e}", exc_info=True)
            failed += 1

    return f"Completed: {success} succeeded, {failed} failed."
