"""
Scraper for Opportunity Desk (opportunitydesk.org)
A popular scholarship & fellowship listing site.
"""
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging
import re

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    )
}

# Regex to pull a deadline string like "Deadline: August 12, 2026" from text
DEADLINE_RE = re.compile(r'[Dd]eadline[:\s]+(.+)', re.IGNORECASE)
DATE_RE = re.compile(
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\s+\d{1,2},?\s+\d{4}',
    re.IGNORECASE
)

# ── Degree-type detection ─────────────────────────────────────────────────────
# Searched against the lowercased title + excerpt text.
# Order matters: more-specific terms first.
DEGREE_TEXT_RULES = [
    # PhD / Postdoctoral
    ('phd',              'PhD'),
    ('ph.d',             'PhD'),
    ('post-doctoral',    'PhD'),
    ('postdoctoral',     'PhD'),
    ('post doctoral',    'PhD'),
    ('doctoral',         'PhD'),
    ('doctorate',        'PhD'),
    # Master
    ('master',           'Master'),
    ('postgraduate',     'Master'),
    ('post-graduate',    'Master'),
    ('post graduate',    'Master'),
    ('msc',              'Master'),
    ('mba',              'Master'),
    ('mphil',            'Master'),
    # Bachelor
    ('bachelor',         'Bachelor'),
    ('undergraduate',    'Bachelor'),
    ('bsc',              'Bachelor'),
    ('b.sc',             'Bachelor'),
    # Diploma
    ('diploma',          'Diploma'),
    ('certificate',      'Diploma'),
]

# ── Region / Country mapping ──────────────────────────────────────────────────
# OpportunityDesk uses the SmartMag WordPress theme. The category link inside
# <span class="meta-item post-cat"> often contains a region name
# (e.g. "Africa", "America", "Europe") rather than a specific country.
# We capture that as the country value.


def _extract_degree_types(text: str) -> list:
    """
    Returns a deduplicated list of degree labels inferred from free text
    (title + excerpt combined).

    Example: "PhD Position in Human Geography" → ['PhD']
             "Undergraduate and Postgraduate Studies" → ['Bachelor', 'Master']
    """
    lower = text.lower()
    found, seen = [], set()
    for fragment, label in DEGREE_TEXT_RULES:
        if fragment in lower and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _extract_country(article) -> str:
    """
    Returns the region/country string from the SmartMag post-cat meta span.
    Falls back to the legacy .cat-links selector and then to ''.

    Examples: 'Africa', 'America', 'Europe', 'Asia'
    """
    # SmartMag theme (current)
    post_cat = article.select_one('span.meta-item.post-cat a')
    if post_cat:
        return post_cat.get_text(strip=True)

    # Older / alternative theme layout
    cat_tag = (
        article.select_one('.cat-links a') or
        article.select_one('.entry-meta a')
    )
    if cat_tag:
        return cat_tag.get_text(strip=True)

    return ''


class OpportunityDeskScraper(BaseScraper):
    """
    Scrapes scholarship/fellowship listings from:
    https://opportunitydesk.org/category/fellowships-and-scholarships/
    """
    source_name = 'Opportunity Desk'
    source_url  = 'https://opportunitydesk.org/category/fellowships-and-scholarships/'

    def scrape(self) -> list:
        grants = []

        try:
            response = requests.get(self.source_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {self.source_url}: {e}")
            raise

        soup = BeautifulSoup(response.text, 'html.parser')

        # Each post card on the listing page — the site uses <article> tags
        articles = soup.select('article')

        if not articles:
            logger.warning(f"[{self.source_name}] No articles found — page structure may have changed.")
            return grants

        for article in articles:
            try:
                # ── Title & URL ───────────────────────────────────────────────
                title_tag = (
                    article.select_one('h2 a') or
                    article.select_one('h3 a') or
                    article.select_one('.entry-title a')
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                url   = title_tag.get('href', '')

                # ── Excerpt / description ─────────────────────────────────────
                excerpt_tag = (
                    article.select_one('.entry-summary p') or
                    article.select_one('.entry-content p') or
                    article.select_one('p')
                )
                excerpt = excerpt_tag.get_text(strip=True) if excerpt_tag else ''

                # ── Deadline (extracted from excerpt text) ────────────────────
                deadline = ''
                match = DEADLINE_RE.search(excerpt)
                if match:
                    raw_deadline_text = match.group(1).strip()
                    date_match = DATE_RE.search(raw_deadline_text)
                    if date_match:
                        try:
                            from dateutil.parser import parse
                            deadline = parse(date_match.group(0)).strftime('%Y-%m-%d')
                        except Exception:
                            pass

                # ── Published date ────────────────────────────────────────────
                date_tag = article.select_one('time')
                published = date_tag.get('datetime', '') if date_tag else ''

                # ── Country / Region ──────────────────────────────────────────
                country = _extract_country(article)

                # ── Category (existing field) ─────────────────────────────────
                cat_tag = article.select_one('.cat-links a') or article.select_one('.entry-meta a')
                category = cat_tag.get_text(strip=True) if cat_tag else 'Scholarship'

                # ── Degree types — inferred from title + excerpt ───────────────
                combined_text = f"{title} {excerpt}"
                degree_types = _extract_degree_types(combined_text)

                grants.append({
                    'title':        title,
                    'url':          url,
                    'description':  excerpt,
                    'deadline':     deadline,
                    'organization': self.source_name,
                    'category':     category,
                    'country':      country,
                    'degree_types': degree_types,   # list e.g. ['Bachelor', 'Master']
                    'published_at': published,
                    'raw_html':     str(article),
                })

            except Exception as e:
                logger.warning(f"[{self.source_name}] Skipped one article due to: {e}")
                continue

        logger.info(f"[{self.source_name}] Parsed {len(grants)} grants from listing page.")
        return grants
