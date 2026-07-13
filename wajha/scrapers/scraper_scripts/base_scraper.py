"""
Base scraper class.
All scholarship scrapers must inherit from BaseScraper and implement `scrape()`.

Shared constants and helper functions used by all scrapers are also defined here
to avoid code duplication (DRY principle).
"""
import re
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Shared HTTP Headers ───────────────────────────────────────────────────────
# Fakes a real Chrome browser to avoid bot-detection blocks.
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    )
}

# ── Degree-type detection ─────────────────────────────────────────────────────
# Searched against the lowercased title + full content text.
# Order matters: more-specific terms first.
DEGREE_TEXT_RULES = [
    # PhD / Postdoctoral
    ('phd',           'PhD'),
    ('ph.d',          'PhD'),
    ('post-doctoral', 'PhD'),
    ('postdoctoral',  'PhD'),
    ('post doctoral', 'PhD'),
    ('doctoral',      'PhD'),
    ('doctorate',     'PhD'),
    # Master
    ('master',        'Master'),
    ('postgraduate',  'Master'),
    ('post-graduate', 'Master'),
    ('post graduate', 'Master'),
    ('msc',           'Master'),
    ('mba',           'Master'),
    ('mphil',         'Master'),
    # Bachelor
    ('bachelor',      'Bachelor'),
    ('undergraduate', 'Bachelor'),
    ('bsc',           'Bachelor'),
    ('b.sc',          'Bachelor'),
    # Diploma
    ('diploma',       'Diploma'),
    ('certificate',   'Diploma'),
]

# ── Host Country detection ────────────────────────────────────────────────────
# Each entry is (regex_pattern, canonical_country_name).
# \b = word boundary to avoid partial matches (e.g. "usa" ≠ "usage").
COUNTRY_KEYWORDS = [
    (r'\bireland\b|\birish\b',                                          'Ireland'),
    (r'\busa\b|\bu\.s\b|\bamerica\b|\bunited states\b|\bamerican\b',    'United States'),
    (r'\buk\b|\bu\.k\b|\bbritish\b|\bengland\b|\bscotland\b|\bunited kingdom\b', 'United Kingdom'),
    (r'\bgermany\b|\bgerman\b|\bdaad\b|\bdeutsch\b',                    'Germany'),
    (r'\bzurich\b|\bswitzerland\b|\bswiss\b',                           'Switzerland'),
    (r'\bcanada\b|\bcanadian\b',                                        'Canada'),
    (r'\baustralia\b|\baustralian\b',                                   'Australia'),
    (r'\bnetherlands\b|\bdutch\b|\bholland\b',                         'Netherlands'),
    (r'\bsweden\b|\bswedish\b',                                         'Sweden'),
    (r'\bnorway\b|\bnorwegian\b',                                       'Norway'),
    (r'\bfrance\b|\bfrench\b',                                          'France'),
    (r'\bchina\b|\bchinese\b',                                          'China'),
    (r'\bjapan\b|\bjapanese\b',                                         'Japan'),
    (r'\bsingapore\b',                                                  'Singapore'),
    (r'\bmalaysia\b|\bmalaysian\b',                                     'Malaysia'),
    (r'\bitaly\b|\bitalian\b',                                          'Italy'),
    (r'\bspain\b|\bspanish\b',                                          'Spain'),
    (r'\bbelgium\b|\bbelgian\b',                                        'Belgium'),
    (r'\baustria\b|\baustrian\b',                                       'Austria'),
    (r'\bdenmark\b|\bdanish\b',                                         'Denmark'),
    (r'\bfinland\b|\bfinnish\b',                                        'Finland'),
    (r'\bnew zealand\b',                                                'New Zealand'),
    (r'\bturkey\b|\bturkish\b',                                         'Turkey'),
    (r'\bpoland\b|\bpolish\b',                                          'Poland'),
    (r'\bhungary\b|\bhungarian\b',                                      'Hungary'),
    (r'\bportugal\b|\bportuguese\b',                                    'Portugal'),
    (r'\bgreece\b|\bgreek\b',                                           'Greece'),
]

# ── Field of Study detection ──────────────────────────────────────────────────
# Matched against lowercased title + full content text.
FIELD_OF_STUDY_RULES = [
    (r'\bcomputer science\b|\bsoftware engineering\b|\bcomputing\b|\binformation technology\b|\bdata science\b', 'Computer Science'),
    (r'\bengineering\b',                                                                                          'Engineering'),
    (r'\bmedicine\b|\bmedical\b|\bhealth sciences?\b|\bpublic health\b|\bnursing\b|\bpharmacy\b',                 'Medicine & Health'),
    (r'\bbusiness\b|\bmanagement\b|\bmba\b|\bfinance\b|\beconomics\b|\bcommerce\b',                              'Business & Economics'),
    (r'\blaw\b|\blegal\b|\bjurisprudence\b',                                                                      'Law'),
    (r'\barts?\b|\bhumanities\b|\bliterature\b|\bphilosophy\b|\bhistory\b|\blinguistics?\b',                     'Arts & Humanities'),
    (r'\bsocial sciences?\b|\bsociology\b|\bpolitical science\b|\bpsychology\b|\banthropology\b',                'Social Sciences'),
    (r'\beducation\b|\bteaching\b|\bpedagogy\b',                                                                  'Education'),
    (r'\benvironment\b|\benvironmental\b|\bclimate\b|\bsustainability\b|\bnatural resources?\b',                  'Environment & Sustainability'),
    (r'\bagriculture\b|\bagricultural\b|\bfood science\b|\bfood security\b',                                     'Agriculture'),
    (r'\barchitecture\b|\burban planning\b|\bcivil engineering\b',                                                'Architecture & Urban Planning'),
    (r'\bscience\b|\bstem\b|\bphysics\b|\bchemistry\b|\bbiology\b|\bmathematics?\b|\bmath\b',                   'Science & STEM'),
    (r'\bjournalism\b|\bmedia\b|\bcommunication\b',                                                               'Journalism & Media'),
    (r'\binternational relations?\b|\bglobal studies\b|\binternational development\b',                            'International Relations'),
    (r'\bpublic policy\b|\bgovernance\b|\bpublic administration\b',                                              'Public Policy'),
]

# ── Eligibility keywords ──────────────────────────────────────────────────────
ELIGIBILITY_KEYWORDS = [
    'eligible', 'eligibility', 'open to', 'requirements',
    'criteria', 'must be', 'applicants must', 'who can apply',
    'qualification', 'nationals of', 'citizens of',
]


# ── Shared helper functions ───────────────────────────────────────────────────

def _extract_degree_types_from_text(text: str) -> list:
    """
    Returns a deduplicated list of degree labels inferred from free text
    (title + full content combined).
    """
    lower = text.lower()
    found, seen = [], set()
    for fragment, label in DEGREE_TEXT_RULES:
        if fragment in lower and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _extract_fields_of_study(text: str) -> list:
    """
    Returns a deduplicated list of field-of-study labels inferred from free text.
    """
    lower = text.lower()
    found, seen = [], set()
    for pattern, label in FIELD_OF_STUDY_RULES:
        if re.search(pattern, lower) and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _extract_host_countries(title: str, text: str,
                             priority_country: str = '',
                             fallback_region: str = '') -> list:
    """
    Builds a deduplicated, ordered list of host countries.

    Priority order:
      1. priority_country  — e.g. extracted from a CSS class (highest confidence)
      2. Title keyword scan
      3. Full-text keyword scan
      4. fallback_region   — e.g. a WordPress category label (lowest confidence)
    """
    found, seen = [], set()

    # 1. Highest-confidence source (e.g. CSS region class on youthop)
    if priority_country and priority_country not in seen:
        found.append(priority_country)
        seen.add(priority_country)

    # 2. Title matches
    title_lower = title.lower()
    for pattern, country in COUNTRY_KEYWORDS:
        if re.search(pattern, title_lower) and country not in seen:
            found.append(country)
            seen.add(country)

    # 3. Full-content matches
    text_lower = text.lower()
    for pattern, country in COUNTRY_KEYWORDS:
        if re.search(pattern, text_lower) and country not in seen:
            found.append(country)
            seen.add(country)

    # 4. Fallback to WordPress region category if nothing found
    if not found and fallback_region:
        found.append(fallback_region)

    return found


def _extract_eligibility_text(paragraphs: list) -> str:
    """
    Scans a list of paragraph strings and returns up to 5 consecutive paragraphs
    starting from the first one that contains an eligibility keyword.
    Returns '' if no eligibility paragraph is found.
    """
    eligibility_paras = []
    capture = False
    for para in paragraphs:
        lower = para.lower()
        if any(kw in lower for kw in ELIGIBILITY_KEYWORDS):
            capture = True
        if capture:
            eligibility_paras.append(para)
            if len(eligibility_paras) >= 5:
                break
    return '\n\n'.join(eligibility_paras)


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
                title     = grant.get('title', '').strip()
                grant_url = grant.get('url', '').strip()
                if not title:
                    continue

                # Use source + URL as a stable deduplication key.
                # If the same listing appears on the next run, we skip it
                # instead of creating a duplicate in the review queue.
                raw_html = grant.pop('raw_html', '')

                # Check if this URL was already scraped from this source.
                # Using filter().first() prevents MultipleObjectsReturned errors
                # if duplicates exist.
                existing = None
                if grant_url:
                    existing = ScrapedGrant.objects.filter(
                        source=source,
                        parsed_data__url=grant_url
                    ).first()

                if existing:
                    created = False
                else:
                    ScrapedGrant.objects.create(
                        source=source,
                        raw_title=title,
                        raw_html_snippet=raw_html,
                        parsed_data=grant,
                        status='pending',
                    )
                    created = True

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
