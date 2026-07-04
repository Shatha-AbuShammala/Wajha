"""
Scraper for Youth Opportunities (youthop.com)
The largest opportunity discovery platform for youth worldwide.
Targets the /scholarships listing page.
"""
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging
import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    )
}


def _parse_iso_datetime(iso_str: str) -> str:
    """
    Parses an ISO 8601 datetime string (e.g. '2026-09-09T18:59:00+00:00')
    and returns a date-only string 'YYYY-MM-DD', or '' on failure.
    """
    if not iso_str:
        return ''
    try:
        iso_str = iso_str.strip()
        if 'T' in iso_str:
            date_part = iso_str.split('T')[0]
            return datetime.date.fromisoformat(date_part).isoformat()
    except (ValueError, AttributeError):
        pass
    return ''


# ── Degree-type detection ─────────────────────────────────────────────────────
# Maps CSS class/tag fragments → canonical degree label.
# Checked against the article's full class attribute string (which includes
# both category-* and tag-* tokens added by WordPress).
# Order matters: check more-specific tokens first.
DEGREE_CLASS_RULES = [
    ('phd',           'PhD'),
    ('post-doctoral',  'PhD'),
    ('postdoctoral',   'PhD'),
    ('doctoral',       'PhD'),
    ('doctorate',      'PhD'),
    ('master',         'Master'),
    ('post-graduate',  'Master'),
    ('postgraduate',   'Master'),
    ('bachelor',       'Bachelor'),
    ('undergraduate',  'Bachelor'),
    ('diploma',        'Diploma'),
]


def _extract_degree_types(article_classes: list) -> list:
    """
    Returns a deduplicated list of degree labels detected from the article's
    CSS class tokens (WordPress adds both category-* and tag-* classes).

    Example input : ['category-post-graduate', 'tag-phd-studentship', ...]
    Example output: ['Master', 'PhD']
    """
    class_str = ' '.join(article_classes).lower()
    found, seen = [], set()
    for fragment, label in DEGREE_CLASS_RULES:
        if fragment in class_str and label not in seen:
            found.append(label)
            seen.add(label)
    return found  # empty list = unknown / general scholarship


def _extract_country(article_classes: list) -> str:
    """
    Returns the host country from a `regions-{country}` CSS class.
    e.g. 'regions-malaysia'      → 'Malaysia'
         'regions-united-states' → 'United States'
    Returns '' if no region class is found.
    """
    for cls in article_classes:
        if cls.startswith('regions-'):
            return cls[len('regions-'):].replace('-', ' ').title()
    return ''


class YouthOpScraper(BaseScraper):
    """
    Scrapes scholarship listings from:
    https://www.youthop.com/scholarships
    """
    source_name = 'Youth Opportunities'
    source_url  = 'https://www.youthop.com/scholarships'

    def scrape(self) -> list[dict]:
        grants = []

        try:
            response = requests.get(self.source_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {self.source_url}: {e}")
            raise

        soup = BeautifulSoup(response.text, 'html.parser')

        # Each scholarship card uses <article class="post-item ...">
        articles = soup.select('article.post-item')

        if not articles:
            logger.warning(f"[{self.source_name}] No articles found — page layout may have changed.")
            return grants

        for article in articles:
            try:
                # ── CSS class list (source of country + degree data) ──────────
                article_classes = article.get('class', [])

                # ── Title & URL ───────────────────────────────────────────────
                # The page structure is: <a href="..."><h3 class="post-title">...</h3></a>
                # The <a> WRAPS the <h3>, so we find the h3 first then get its parent <a>.
                h3_tag = article.select_one('h3.post-title') or article.select_one('h2.post-title')
                if not h3_tag:
                    continue

                title = h3_tag.get_text(strip=True)
                if not title:
                    continue

                # Walk up to the parent anchor that holds the href
                link_tag = h3_tag.find_parent('a')
                if not link_tag:
                    continue

                href = link_tag.get('href', '').strip()
                if not href:
                    continue

                # Strip the ?ref=browse_page tracking param for a clean URL
                url = href.split('?')[0] if '?' in href else href

                # ── Country ───────────────────────────────────────────────────
                country = _extract_country(article_classes)

                # ── Degree types (can be multiple) ────────────────────────────
                degree_types = _extract_degree_types(article_classes)

                # ── Funding type / Category ───────────────────────────────────
                funding_tag = article.select_one('.post-meta-funding')
                category = funding_tag.get_text(strip=True) if funding_tag else 'Scholarship'

                # ── Location / Organization ───────────────────────────────────
                # Organization = the source portal that listed this scholarship.
                # The country is already captured separately in the 'country' field.
                organization = self.source_name

                # ── Deadline ──────────────────────────────────────────────────
                # The site stores the deadline as an ISO datetime in the
                # itemprop="startDate" content attribute.
                deadline_tag = article.select_one('span[itemprop="startDate"]')
                deadline = ''
                if deadline_tag:
                    iso_content = deadline_tag.get('content', '')
                    deadline = _parse_iso_datetime(iso_content)

                if not deadline:
                    # Some listings display "On Going" — skip them as there is
                    # no concrete deadline to show in the review queue.
                    logger.debug(f"[{self.source_name}] Skipped (no deadline): {title[:80]}")
                    continue

                # ── Description ───────────────────────────────────────────────
                excerpt_tag = article.select_one('.entry-summary')
                excerpt = excerpt_tag.get_text(strip=True) if excerpt_tag else ''
                if not excerpt:
                    excerpt = f"View full details and application requirements for this opportunity: {title}."

                grants.append({
                    'title':        title,
                    'url':          url,
                    'description':  excerpt,
                    'deadline':     deadline,
                    'organization': organization,
                    'category':     category,
                    'country':      country,
                    'degree_types': degree_types,
                    'published_at': '',
                    'raw_html':     str(article),
                })

            except Exception as e:
                logger.warning(f"[{self.source_name}] Skipped one article due to: {e}")
                continue

        logger.info(f"[{self.source_name}] Parsed {len(grants)} grants from listing page.")
        return grants
