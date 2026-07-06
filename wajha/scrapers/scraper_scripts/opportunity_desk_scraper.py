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
# Searched against the lowercased title + full content text.
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

# ── Host Country detection ────────────────────────────────────────────────────
# Searched against lowercased title and full content text.
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

# ── Field of Study detection ──────────────────────────────────────────────────
# Matched against lowercased title + full content text.
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


def _extract_degree_types(text: str) -> list:
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
    Returns a deduplicated list of field-of-study labels inferred from free text
    (title + full content combined).
    """
    lower = text.lower()
    found, seen = [], set()
    for pattern, label in FIELD_OF_STUDY_RULES:
        if re.search(pattern, lower) and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _extract_fallback_region(article) -> str:
    """
    Returns the region/category string from the SmartMag post-cat meta span.
    Falls back to the legacy .cat-links selector and then to ''.
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


def _extract_host_countries(title: str, text: str, fallback_region: str) -> list:
    """
    Infers ALL host countries mentioned in the title or full content.
    Returns a deduplicated ordered list.
    Title matches are given priority (inserted first).
    Falls back to [fallback_region] if no countries are found.
    """
    title_lower = title.lower()
    text_lower  = text.lower()
    found, seen = [], set()

    # 1. Title matches first (highest confidence)
    for pattern, country in COUNTRY_KEYWORDS:
        if re.search(pattern, title_lower) and country not in seen:
            found.append(country)
            seen.add(country)

    # 2. Full content matches
    for pattern, country in COUNTRY_KEYWORDS:
        if re.search(pattern, text_lower) and country not in seen:
            found.append(country)
            seen.add(country)

    # 3. Fallback to WordPress region category if nothing found
    if not found and fallback_region:
        found.append(fallback_region)

    return found


def _extract_eligibility_text(paragraphs: list) -> str:
    """
    Scans the list of paragraph strings from the detail page and returns
    a block of text containing eligibility-related content.
    If no eligibility paragraph is found, returns an empty string.
    """
    ELIGIBILITY_KEYWORDS = [
        'eligible', 'eligibility', 'open to', 'requirements',
        'criteria', 'must be', 'applicants must', 'who can apply',
        'qualification', 'nationals of', 'citizens of',
    ]
    eligibility_paras = []
    capture = False
    for para in paragraphs:
        lower = para.lower()
        if any(kw in lower for kw in ELIGIBILITY_KEYWORDS):
            capture = True
        if capture:
            eligibility_paras.append(para)
            # Stop after collecting up to 5 paragraphs from first eligibility hit
            if len(eligibility_paras) >= 5:
                break
    return '\n\n'.join(eligibility_paras)


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

                # ── Published date ────────────────────────────────────────────
                date_tag = article.select_one('time')
                published = date_tag.get('datetime', '') if date_tag else ''

                # ── Category ──────────────────────────────────────────────────
                cat_tag = article.select_one('.cat-links a') or article.select_one('.entry-meta a')
                category = cat_tag.get_text(strip=True) if cat_tag else 'Scholarship'

                # ── Fallback Region ───────────────────────────────────────────
                fallback_region = _extract_fallback_region(article)

                # ── Fetch Full Article Detail Page ────────────────────────────
                full_text = ""
                description = ""
                paragraphs = []
                try:
                    detail_res = requests.get(url, headers=HEADERS, timeout=10)
                    detail_res.raise_for_status()
                    detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                    content_block = detail_soup.select_one('.entry-content')
                    if content_block:
                        # Extract clean text from all paragraphs in the article
                        paragraphs = [p.get_text(strip=True) for p in content_block.select('p') if p.get_text(strip=True)]
                        full_text = "\n\n".join(paragraphs)
                        # We use the full text as the description so the user sees the complete details!
                        description = full_text
                except Exception as e:
                    logger.warning(f"[{self.source_name}] Could not fetch single page for {title}: {e}")

                # Fallback to excerpt if fetching individual page fails
                if not description:
                    excerpt_tag = (
                        article.select_one('.entry-summary p') or
                        article.select_one('.entry-content p') or
                        article.select_one('p')
                    )
                    description = excerpt_tag.get_text(strip=True) if excerpt_tag else ''
                    full_text = description

                # ── Deadline (extracted from full text or description) ────────
                deadline = ''
                match = DEADLINE_RE.search(description)
                if match:
                    raw_deadline_text = match.group(1).strip()
                    date_match = DATE_RE.search(raw_deadline_text)
                    if date_match:
                        try:
                            from dateutil.parser import parse
                            deadline = parse(date_match.group(0)).strftime('%Y-%m-%d')
                        except Exception:
                            pass

                # ── Countries (multi) ─────────────────────────────────────────
                countries = _extract_host_countries(title, full_text, fallback_region)

                # ── Degree types ──────────────────────────────────────────────
                combined_text = f"{title} {full_text}"
                degree_types = _extract_degree_types(combined_text)

                # ── Fields of Study ───────────────────────────────────────────
                fields_of_study = _extract_fields_of_study(combined_text)

                # ── Eligibility text ──────────────────────────────────────────
                eligibility_text = _extract_eligibility_text(paragraphs) if paragraphs else ''

                grants.append({
                    'title':           title,
                    'url':             url,
                    'description':     description,
                    'deadline':        deadline,
                    'organization':    self.source_name,
                    'category':        category,
                    'country':         countries[0] if countries else '',  # backward compat
                    'countries':       countries,
                    'degree_types':    degree_types,
                    'fields_of_study': fields_of_study,
                    'eligibility_text': eligibility_text,
                    'published_at':    published,
                    'raw_html':        str(article),
                })

            except Exception as e:
                logger.warning(f"[{self.source_name}] Skipped one article due to: {e}")
                continue

        logger.info(f"[{self.source_name}] Parsed {len(grants)} grants from listing page.")
        return grants
