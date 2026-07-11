# -*- coding: utf-8 -*-
"""
Django management command to run all registered scrapers.

Usage:
    python manage.py run_scrapers                  # Run all scrapers
    python manage.py run_scrapers --source "Opportunity Desk"  # Run one by name
"""
import sys
import io
from django.core.management.base import BaseCommand
from scrapers.scraper_scripts import ALL_SCRAPERS
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run all registered scholarship scrapers and save results to the review queue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default=None,
            help='Run only the scraper matching this source_name (optional).',
        )

    def handle(self, *args, **options):
        # Force stdout to UTF-8 so Unicode chars don't crash on Windows cp1252
        if hasattr(self.stdout, '_out'):
            self.stdout._out = io.TextIOWrapper(
                self.stdout._out.buffer, encoding='utf-8', errors='replace'
            )

        target = options.get('source')
        scrapers_to_run = ALL_SCRAPERS

        if target:
            scrapers_to_run = [
                s for s in ALL_SCRAPERS
                if s.source_name.lower() == target.lower()
            ]
            if not scrapers_to_run:
                self.stderr.write(
                    self.s5tyle.ERROR(f'No scraper found with source_name="{target}"')
                )
                return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nRunning {len(scrapers_to_run)} scraper(s)...\n'
        ))

        success = 0
        failed  = 0

        for ScraperClass in scrapers_to_run:
            scraper = ScraperClass()
            try:
                self.stdout.write(f'  -> {scraper.source_name}...', ending=' ')
                scraper.run()
                self.stdout.write(self.style.SUCCESS('Done'))
                success += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed: {e}'))
                failed += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Finished: {success} succeeded, {failed} failed.'))
