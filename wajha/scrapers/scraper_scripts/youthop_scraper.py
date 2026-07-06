"""
Scraper for Youth Opportunities (youthop.com)
The largest opportunity discovery platform for youth worldwide.
Targets the /scholarships listing page.
"""
import re
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

DEGREE_TEXT_RULES = [
    ('phd',           'PhD'),
    ('ph.d',          'PhD'),
    ('post-doctoral', 'PhD'),
    ('postdoctoral',  'PhD'),
    ('doctoral',      'PhD'),
    ('doctorate',     'PhD'),
    ('master',        'Master'),
    ('postgraduate',  'Master'),
    ('post-graduate', 'Master'),
    ('msc',           'Master'),
    ('mba',           'Master'),
    ('bachelor',      'Bachelor'),
    ('undergraduate', 'Bachelor'),
    ('bsc',           'Bachelor'),
    ('diploma',       'Diploma'),
    ('certificate',   'Diploma'),
]

# ── Field of Study detection ──────────────────────────────────────────────────
FIELD_OF_STUDY_RULES = [
    (r'\bcomputer science\b|\bsoftware engineering\b|\bcomputing\b|\binformation technology\b|\bdata science\b', 'Computer Science'),
    (r'\bengineering\b', 'Engineering'),
    (r'\bmedicine\b|\bmedical\b|\bhealth sciences?\b|\bpublic health\b|\bnursing\b|\bpharmacy\b', 'Medicine & Health'),
    (r'\bbusiness\b|\bmanagement\b|\bmba\b|\bfinance\b|\beconomics\b|\bcommerce\b', 'Business & Economics'),
    (r'\blaw\b|\blegal\b|\bjurisprudence\b', 'Law'),
    (r'\barts?\b|\bhumanities\b|\bliterature\b|\bphilosophy\b|\bhistory\b|\blinguistics?\b', 'Arts & Humanities'),
    (r'\bsocial sciences?\b|\bsociology\b|\bpolitical science\b|\bpsychology\b|\banthropology\b', 'Social Sciences'),
    (r'\beducation\b|\bteaching\b|\bpedagogy\b', 'Education'),
    (r'\benvironment\b|\benvironmental\b|\bclimate\b|\bsustainability\b|\bnatural resources?\b', 'Environment & Sustainability'),
    (r'\bagriculture\b|\bagricultural\b|\bfood science\b|\bfood security\b', 'Agriculture'),
    (r'\barchitecture\b|\burban planning\b|\bcivil engineering\b', 'Architecture & Urban Planning'),
    (r'\bscience\b|\bstem\b|\bphysics\b|\bchemistry\b|\bbiology\b|\bmathematics?\b|\bmath\b', 'Science & STEM'),
    (r'\bjournalism\b|\bmedia\b|\bcommunication\b', 'Journalism & Media'),
    (r'\binternational relations?\b|\bglobal studies\b|\binternational development\b', 'International Relations'),
    (r'\bpublic policy\b|\bgovernance\b|\bpublic administration\b', 'Public Policy'),
]

# ── Host Country detection ────────────────────────────────────────────────────
COUNTRY_KEYWORDS = [
    (r'\bireland\b|\birish\b', 'Ireland'),
    (r'\busa\b|\bu\.s\b|\bamerica\b|\bunited states\b|\bamerican\b', 'United States'),
    (r'\buk\b|\bu\.k\b|\bbritish\b|\bengland\b|\bscotland\b|\bunited kingdom\b', 'United Kingdom'),
    (r'\bgermany\b|\bgerman\b|\bdaad\b|\bdeutsch\b', 'Germany'),
    (r'\bzurich\b|\bswitzerland\b|\bswiss\b', 'Switzerland'),
    (r'\bcanada\b|\bcanadian\b', 'Canada'),
    (r'\baustralia\b|\baustralian\b', 'Australia'),
    (r'\bnetherlands\b|\bdutch\b|\bholland\b', 'Netherlands'),
    (r'\bsweden\b|\bswedish\b', 'Sweden'),
    (r'\bnorway\b|\bnorwegian\b', 'Norway'),
    (r'\bfrance\b|\bfrench\b', 'France'),
    (r'\bchina\b|\bchinese\b', 'China'),
    (r'\bjapan\b|\bjapanese\b', 'Japan'),
    (r'\bsingapore\b', 'Singapore'),
    (r'\bmalaysia\b|\bmalaysian\b', 'Malaysia'),
    (r'\bitaly\b|\bitalian\b', 'Italy'),
    (r'\bspain\b|\bspanish\b', 'Spain'),
    (r'\bbelgium\b|\bbelgian\b', 'Belgium'),
    (r'\baustria\b|\baustrian\b', 'Austria'),
    (r'\bdenmark\b|\bdanish\b', 'Denmark'),
    (r'\bfinland\b|\bfinnish\b', 'Finland'),
    (r'\bnew zealand\b', 'New Zealand'),
    (r'\bturkey\b|\bturkish\b', 'Turkey'),
    (r'\bpoland\b|\bpolish\b', 'Poland'),
    (r'\bhungary\b|\bhungarian\b', 'Hungary'),
    (r'\bportugal\b|\bportuguese\b', 'Portugal'),
    (r'\bgreece\b|\bgreek\b', 'Greece'),
]

ELIGIBILITY_KEYWORDS = [
    'eligible', 'eligibility', 'open to', 'requirements',
    'criteria', 'must be', 'applicants must', 'who can apply',
    'qualification', 'nationals of', 'citizens of',
]


def _extract_degree_types_from_classes(article_classes: list) -> list:
    """
    Returns a deduplicated list of degree labels detected from the article's
    CSS class tokens (WordPress adds both category-* and tag-* classes).
    """
    class_str = ' '.join(article_classes).lower()
    found, seen = [], set()
    for fragment, label in DEGREE_CLASS_RULES:
        if fragment in class_str and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _extract_degree_types_from_text(text: str) -> list:
    """Augment degree detection using full article text."""
    lower = text.lower()
    found, seen = [], set()
    for fragment, label in DEGREE_TEXT_RULES:
        if fragment in lower and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _merge_degree_types(from_classes: list, from_text: list) -> list:
    """Merge two degree lists, preserving order and deduplicating."""
    seen = set()
    result = []
    for label in from_classes + from_text:
        if label not in seen:
            result.append(label)
            seen.add(label)
    return result


def _extract_fields_of_study(text: str) -> list:
    """Returns a deduplicated list of field-of-study labels from free text."""
    lower = text.lower()
    found, seen = [], set()
    for pattern, label in FIELD_OF_STUDY_RULES:
        if re.search(pattern, lower) and label not in seen:
            found.append(label)
            seen.add(label)
    return found


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


def _extract_host_countries(css_country: str, title: str, text: str) -> list:
    """
    Builds a deduplicated list of countries.
    Starts with the CSS-class region (highest confidence), then scans
    title and full content text for additional country mentions.
    """
    found, seen = [], set()

    # 1. CSS region class (most reliable for youthop)
    if css_country:
        found.append(css_country)
        seen.add(css_country)

    # 2. Title keyword scan
    title_lower = title.lower()
    for pattern, country in COUNTRY_KEYWORDS:
        if re.search(pattern, title_lower) and country not in seen:
            found.append(country)
            seen.add(country)

    # 3. Full text keyword scan
    text_lower = text.lower()
    for pattern, country in COUNTRY_KEYWORDS:
        if re.search(pattern, text_lower) and country not in seen:
            found.append(country)
            seen.add(country)

    return found


def _extract_eligibility_text(paragraphs: list) -> str:
    """
    Scans the list of paragraph strings from the detail page and returns
    a block of text containing eligibility-related content.
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
                degree_types_css = _extract_degree_types_from_classes(article_classes)

                # ── Funding type / Category ───────────────────────────────────
                funding_tag = article.select_one('.post-meta-funding')
                category = funding_tag.get_text(strip=True) if funding_tag else 'Scholarship'

                # ── Organization ──────────────────────────────────────────────
                organization = self.source_name

                # ── Deadline ──────────────────────────────────────────────────
                deadline_tag = article.select_one('span[itemprop="startDate"]')
                deadline = ''
                if deadline_tag:
                    iso_content = deadline_tag.get('content', '')
                    deadline = _parse_iso_datetime(iso_content)

                if not deadline:
                    logger.debug(f"[{self.source_name}] Skipped (no deadline): {title[:80]}")
                    continue

                # ── Fetch Detail Page for full content ─────────────────────────
                full_text = ''
                description = ''
                paragraphs = []
                try:
                    detail_res = requests.get(url, headers=HEADERS, timeout=10)
                    detail_res.raise_for_status()
                    detail_soup = BeautifulSoup(detail_res.text, 'html.parser')

                    # youthop uses .entry-content for the full article body
                    content_block = (
                        detail_soup.select_one('.entry-content') or
                        detail_soup.select_one('.post-content') or
                        detail_soup.select_one('article')
                    )
                    if content_block:
                        paragraphs = [
                            p.get_text(strip=True)
                            for p in content_block.select('p')
                            if p.get_text(strip=True)
                        ]
                        full_text = '\n\n'.join(paragraphs)
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
                countries = _extract_host_countries(css_country, title, full_text)

                # ── Degree types — merge CSS + text detection ─────────────────
                degree_types_text = _extract_degree_types_from_text(full_text)
                degree_types = _merge_degree_types(degree_types_css, degree_types_text)

                # ── Fields of Study ───────────────────────────────────────────
                combined_text = f"{title} {full_text}"
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
