"""
Scraper for Grab Scholarship (grabscholarship.com)
A popular Arabic portal for international scholarships.
"""
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import logging
import datetime
import re
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    )
}

ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

SCHOLARSHIP_CATEGORY_KEYWORDS = (
    'بكالوريوس',
    'ماجستير',
    'دكتوراه',
    'دكتوراة',
    'دكتور',
    'زمالة',
    'زمالات',
    'منحة',
    'منح',
    'bachelor',
    'master',
    'phd',
    'doctor',
    'scholarship',
    'fellowship',
)

MONTHS = {
    'يناير': 1, 'كانون الثاني': 1, 'فبراير': 2, 'شباط': 2,
    'مارس': 3, 'آذار': 3, 'ابريل': 4, 'أبريل': 4, 'نيسان': 4,
    'مايو': 5, 'أيار': 5, 'يونيو': 6, 'حزيران': 6,
    'يوليو': 7, 'تموز': 7, 'اغسطس': 8, 'أغسطس': 8, 'آب': 8,
    'سبتمبر': 9, 'ايلول': 9, 'أيلول': 9, 'اكتوبر': 10, 'أكتوبر': 10,
    'تشرين الأول': 10, 'نوفمبر': 11, 'تشرين الثاني': 11,
    'ديسمبر': 12, 'كانون الأول': 12,
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
    'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
    'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

DEADLINE_LABEL_RE = re.compile(
    r'(?:آخر|اخر)\s+موعد(?:\s+(?:للتقديم|التقديم))?\s*[:：]?\s*.{0,120}',
    re.IGNORECASE,
)
ISO_DATE_RE = re.compile(r'(20\d{2})-(\d{1,2})-(\d{1,2})')


def _normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').translate(ARABIC_DIGITS)).strip()


def _is_scholarship_category(category: str) -> bool:
    normalized = _normalize_text(category).lower()
    return any(keyword in normalized for keyword in SCHOLARSHIP_CATEGORY_KEYWORDS)


def _parse_deadline_to_iso(text: str) -> str:
    normalized = _normalize_text(text)

    iso_match = ISO_DATE_RE.search(normalized)
    if iso_match:
        try:
            year, month, day = map(int, iso_match.groups())
            return datetime.date(year, month, day).isoformat()
        except ValueError:
            return ''

    month_names = '|'.join(re.escape(name) for name in sorted(MONTHS, key=len, reverse=True))
    date_patterns = (
        rf'(\d{{1,2}})\s+({month_names})\s+(\d{{4}})',
        rf'({month_names})\s+(\d{{1,2}}),?\s+(\d{{4}})',
    )

    for pattern in date_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue

        if match.group(1).isdigit():
            day = int(match.group(1))
            month = MONTHS[match.group(2).lower()]
            year = int(match.group(3))
        else:
            month = MONTHS[match.group(1).lower()]
            day = int(match.group(2))
            year = int(match.group(3))

        try:
            return datetime.date(year, month, day).isoformat()
        except ValueError:
            return ''

    return ''


def _extract_deadline_from_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    page_text = _normalize_text(' '.join(soup.stripped_strings))

    for match in DEADLINE_LABEL_RE.finditer(page_text):
        deadline = _parse_deadline_to_iso(match.group(0))
        if deadline:
            return deadline

    return ''


class GrabScholarshipScraper(BaseScraper):
    """
    Scrapes scholarship listings from:
    https://grabscholarship.com/scholarships/
    """
    source_name = 'Grab Scholarship'
    source_url  = 'https://grabscholarship.com/scholarships/'

    def _fetch_deadline(self, url: str) -> str:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{self.source_name}] Failed to fetch detail page {url}: {e}")
            return ''

        return _extract_deadline_from_html(response.text)

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
                href = title_tag.get('href', '').strip()
                if not href:
                    continue
                url = urljoin(self.source_url, href)

                # ── Category / Degree Badge ───────────────────────────────────
                badge_tag = article.select_one('.elementor-post__badge')
                category = badge_tag.get_text(strip=True) if badge_tag else ''
                if not _is_scholarship_category(category):
                    logger.debug(f"[{self.source_name}] Skipped non-scholarship category: {category or 'missing'}")
                    continue

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

                deadline = self._fetch_deadline(url)
                if not deadline:
                    logger.warning(f"[{self.source_name}] Skipped article with no parseable deadline: {title[:80]}")
                    continue

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
