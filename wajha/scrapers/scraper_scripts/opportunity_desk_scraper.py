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
DEADLINE_RE = re.compile(r'[Dd]eadline[:\s]+([A-Za-z][\w\s,]+\d{4}|Unspecified)', re.IGNORECASE)


class OpportunityDeskScraper(BaseScraper):
    """
    Scrapes scholarship/fellowship listings from:
    https://opportunitydesk.org/category/fellowships-and-scholarships/
    """
    source_name = 'Opportunity Desk'
    source_url  = 'https://opportunitydesk.org/category/fellowships-and-scholarships/'

    def scrape(self) -> list[dict]:
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
                deadline = 'Unspecified'
                match = DEADLINE_RE.search(excerpt)
                if match:
                    deadline = match.group(1).strip()

                # ── Published date ────────────────────────────────────────────
                date_tag = article.select_one('time')
                published = date_tag.get('datetime', '') if date_tag else ''

                # ── Category ─────────────────────────────────────────────────
                cat_tag = article.select_one('.cat-links a') or article.select_one('.entry-meta a')
                category = cat_tag.get_text(strip=True) if cat_tag else 'Scholarship'

                grants.append({
                    'title':        title,
                    'url':          url,
                    'description':  excerpt,
                    'deadline':     deadline,
                    'organization': self.source_name,
                    'category':     category,
                    'published_at': published,
                    'raw_html':     str(article),
                })

            except Exception as e:
                logger.warning(f"[{self.source_name}] Skipped one article due to: {e}")
                continue

        logger.info(f"[{self.source_name}] Parsed {len(grants)} grants from listing page.")
        return grants
