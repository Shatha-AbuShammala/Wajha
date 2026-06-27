"""
Scraper for Grab Scholarship (grabscholarship.com)
A popular Arabic portal for international scholarships.
"""
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    )
}


class GrabScholarshipScraper(BaseScraper):
    """
    Scrapes scholarship listings from:
    https://grabscholarship.com/scholarships/
    """
    source_name = 'Grab Scholarship'
    source_url  = 'https://grabscholarship.com/scholarships/'

    def scrape(self) -> list[dict]:
        grants = []

        try:
            response = requests.get(self.source_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {self.source_url}: {e}")
            raise

        soup = BeautifulSoup(response.text, 'html.parser')

        # Each post card uses <article> tags under the Elementor grid layout
        articles = soup.select('article.elementor-post')

        if not articles:
            logger.warning(f"[{self.source_name}] No articles found — page layout may have changed.")
            return grants

        for article in articles:
            try:
                # ── Title & URL ───────────────────────────────────────────────
                title_tag = article.select_one('h3.elementor-post__title a') or article.select_one('h2.elementor-post__title a') or article.select_one('a')
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                url   = title_tag.get('href', '')

                # ── Category / Degree Badge ───────────────────────────────────
                badge_tag = article.select_one('.elementor-post__badge')
                category = badge_tag.get_text(strip=True) if badge_tag else 'Scholarship'

                # ── Description Excerpt ───────────────────────────────────────
                # Elementor listing template has an excerpt block but it's typically blank.
                # Use a friendly Arabic placeholder to satisfy non-null constraints.
                excerpt_tag = article.select_one('.elementor-post__excerpt')
                excerpt = excerpt_tag.get_text(strip=True) if excerpt_tag else ''
                if not excerpt:
                    excerpt = f"شاهد التفاصيل الكاملة وشروط التقديم لهذه الفرصة: ({title}) مباشرة عبر رابط المصدر الرسمي."

                # ── Published date ────────────────────────────────────────────
                date_tag = article.select_one('.elementor-post-date')
                published = date_tag.get_text(strip=True) if date_tag else ''

                grants.append({
                    'title':        title,
                    'url':          url,
                    'description':  excerpt,
                    'deadline':     'Unspecified',  # Deadlines are not list-level metadata on this site
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
