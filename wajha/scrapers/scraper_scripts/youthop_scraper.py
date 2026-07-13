"""
Scraper for Youth Opportunities (youthop.com)
The largest opportunity discovery platform for youth worldwide.
Targets the /scholarships listing page.
"""
import re
import requests
from bs4 import BeautifulSoup
from .base_scraper import (
    BaseScraper,
    HEADERS,
    _extract_degree_types_from_text,
    _extract_fields_of_study,
    _extract_host_countries,
    _extract_eligibility_text,
)
import logging
import datetime

logger = logging.getLogger(__name__)


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

                # ── Country (from CSS class) ───────────────────────────────────
                css_country = _extract_country(article_classes)

                # ── Degree types from CSS classes ─────────────────────────────
                degree_types_css = _extract_degree_types_from_text(' '.join(article_classes))

                # ── Funding type / Category ───────────────────────────────────
                funding_tag = article.select_one('.post-meta-funding')
                category    = funding_tag.get_text(strip=True) if funding_tag else 'Scholarship'

                # ── Organization ──────────────────────────────────────────────
                organization = self.source_name

                # ── Deadline ──────────────────────────────────────────────────
                deadline_tag = article.select_one('span[itemprop="startDate"]')
                deadline     = ''
                if deadline_tag:
                    iso_content = deadline_tag.get('content', '')
                    deadline    = _parse_iso_datetime(iso_content)

                if not deadline:
                    logger.debug(f"[{self.source_name}] Skipped (no deadline): {title[:80]}")
                    continue

                # ── Fetch Detail Page for full content ─────────────────────────
                full_text   = ''
                description = ''
                paragraphs  = []
                try:
                    detail_res  = requests.get(url, headers=HEADERS, timeout=10)
                    detail_res.raise_for_status()
                    detail_soup = BeautifulSoup(detail_res.text, 'html.parser')

                    # youthop uses .entry-content for the full article body
                    content_block = (
                        detail_soup.select_one('.entry-content') or
                        detail_soup.select_one('.post-content') or
                        detail_soup.select_one('article')
                    )
                    if content_block:
                        paragraphs  = [
                            p.get_text(strip=True)
                            for p in content_block.select('p')
                            if p.get_text(strip=True)
                        ]
                        full_text   = '\n\n'.join(paragraphs)
                        description = full_text
                except Exception as e:
                    logger.warning(f"[{self.source_name}] Could not fetch detail page for {title[:60]}: {e}")

                # Fallback to listing excerpt if detail fetch failed
                if not description:
                    excerpt_tag = article.select_one('.entry-summary')
                    description = excerpt_tag.get_text(strip=True) if excerpt_tag else ''
                    if not description:
                        description = f"View full details and application requirements for this opportunity: {title}."
                    full_text = description

                # ── Eligibility text (extracted from detail page) ─────────────
                eligibility_text = _extract_eligibility_text(paragraphs)

                # ── Countries (multi) — CSS class + keyword scan ──────────────
                countries = _extract_host_countries(
                    title, full_text, priority_country=css_country
                )

                # ── Degree types — merge CSS + text detection ─────────────────
                degree_types_text = _extract_degree_types_from_text(full_text)
                degree_types      = list(dict.fromkeys(degree_types_css + degree_types_text))

                # ── Fields of Study ───────────────────────────────────────────
                combined_text   = f"{title} {full_text}"
                fields_of_study = _extract_fields_of_study(combined_text)

                grants.append({
                    'title':            title,
                    'url':              url,
                    'description':      description,
                    'deadline':         deadline,
                    'organization':     organization,
                    'category':         category,
                    'country':          countries[0] if countries else css_country,  # backward compat
                    'countries':        countries,
                    'degree_types':     degree_types,
                    'fields_of_study':  fields_of_study,
                    'eligibility_text': eligibility_text,
                    'published_at':     '',
                    'raw_html':         str(article),
                })

            except Exception as e:
                logger.warning(f"[{self.source_name}] Skipped one article due to: {e}")
                continue

        logger.info(f"[{self.source_name}] Parsed {len(grants)} grants from listing page.")
        return grants
