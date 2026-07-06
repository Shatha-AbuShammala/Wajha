import datetime
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from .models import ScrapedGrant, GrantSource


# ============================================================
# Helper
# ============================================================

def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


def parse_deadline_date(deadline_str):
    """Parse a loose deadline string into a date object, or return None."""
    if not deadline_str:
        return None
    deadline_str = deadline_str.strip()
    if deadline_str.lower() in ['unspecified', 'n/a', 'none', '—', '']:
        return None

    iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', deadline_str)
    if iso_match:
        try:
            return datetime.date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3))
            )
        except ValueError:
            pass

    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    normalized = re.sub(r'[^\w\s]', ' ', deadline_str.lower())
    parts = normalized.split()
    year = month = day = None

    for part in parts:
        if part.isdigit() and len(part) == 4 and part.startswith('20'):
            year = int(part)
            break
    for part in parts:
        if part in months:
            month = months[part]
            break
    for part in parts:
        if part.isdigit() and len(part) <= 2:
            val = int(part)
            if 1 <= val <= 31:
                day = val

    if year and month:
        try:
            return datetime.date(year, month, day or 1)
        except ValueError:
            pass
    return None


# ============================================================
# Admin: Scraped Grant Queue
# ============================================================

@login_required
def scraped_grants_list(request):
    """Admin: review queue for scraped grants."""
    if not is_admin(request.user):
        return redirect('grants:list')

    status_filter = request.GET.get('status', 'default')
    source_filter = request.GET.get('source', '')
    query = request.GET.get('q', '')

    qs = ScrapedGrant.objects.select_related('source', 'reviewed_by')

    if status_filter == 'default':
        # Default view: show pending and rejected, order by status (pending first)
        from django.db.models import Case, When, Value, IntegerField
        qs = qs.exclude(status='approved').order_by(
            Case(
                When(status='pending', then=Value(1)),
                When(status='rejected', then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            '-scraped_at'
        )
    elif status_filter in ('pending', 'approved', 'rejected'):
        qs = qs.filter(status=status_filter).order_by('-scraped_at')
    else:
        qs = qs.order_by('-scraped_at')

    if source_filter:
        qs = qs.filter(source_id=source_filter)

    if query:
        qs = qs.filter(raw_title__icontains=query)

    # Note: deadline is in JSON field parsed_data, filtering directly can be complex
    # but we will allow sorting via template or basic search

    pending_count = ScrapedGrant.objects.filter(status='pending').count()
    sources = GrantSource.objects.all()

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'total_count': qs.count(),
        'status_filter': status_filter,
        'source_filter': source_filter,
        'query': query,
        'pending_count': pending_count,
        'sources': sources,
    }
    return render(request, 'scrapers/admin/scraped_list.html', context)


@login_required
def scraped_grant_detail(request, pk):
    """Admin: view full parsed data for a single scraped grant."""
    if not is_admin(request.user):
        return redirect('grants:list')

    scraped = get_object_or_404(ScrapedGrant, pk=pk)
    context = {
        'scraped': scraped,
        'pending_count': ScrapedGrant.objects.filter(status='pending').count(),
    }
    return render(request, 'scrapers/admin/scraped_detail.html', context)


def _process_scraped_approval(request, pk, grant_status='published'):
    """Helper to handle approving a scraped grant either as published or draft."""
    if not is_admin(request.user):
        return redirect('grants:list')

    if request.method != 'POST':
        return redirect('scrapers:list')

    from grants.models import GrantOpportunity

    scraped = get_object_or_404(ScrapedGrant, pk=pk)

    if scraped.status == 'approved':
        messages.warning(request, f'"{scraped.raw_title[:60]}" was already approved.')
        return redirect(request.META.get('HTTP_REFERER', 'scrapers:list'))

    title = scraped.raw_title
    url = scraped.parsed_data.get('url', '')
    desc = scraped.parsed_data.get('description', '') or title

    if not url and scraped.source:
        url = scraped.source.url
    if not url:
        url = 'https://opportunitydesk.org/'

    # Deduplication check
    if GrantOpportunity.objects.filter(source_url=url).exists():
        # Only update status — do NOT touch reviewed_by because the MySQL FK
        # constraint on that column points to a legacy 'user' table that no
        # longer matches the accounts_user table Django uses.
        ScrapedGrant.objects.filter(pk=scraped.pk).update(status='approved')
        messages.info(request, 'Grant already exists in live grants (duplicate). Marked approved.')
        return redirect(request.META.get('HTTP_REFERER', 'scrapers:list'))

    org = scraped.parsed_data.get('organization', '')
    if not org and scraped.source:
        org = scraped.source.name
    if not org:
        org = 'Opportunity Desk'

    deadline_str = scraped.parsed_data.get('deadline', '')
    deadline_date = parse_deadline_date(deadline_str)
    if not deadline_date:
        deadline_date = timezone.now().date() + datetime.timedelta(days=30)

    # Guess funding type
    funding_type = 'fully_funded'
    search_text = (title + ' ' + desc).lower()
    if 'partial' in search_text:
        funding_type = 'partial'
    elif 'tuition' in search_text:
        funding_type = 'tuition_only'
    elif 'stipend' in search_text:
        funding_type = 'stipend_only'
    elif 'travel' in search_text:
        funding_type = 'travel_grant'

    eligibility = scraped.parsed_data.get('eligibility_text', '').strip()
    if not eligibility:
        eligibility = 'Please refer to the source website link for detailed eligibility criteria.'

    from grants.models import GrantOpportunity, GrantCountry, GrantDegreeLevel, GrantFieldOfStudy

    grant = GrantOpportunity.objects.create(
        title=title,
        organization=org,
        description=desc,
        eligibility_text=eligibility,
        eligibility_summary='No AI summary generated yet.',
        funding_type=funding_type,
        deadline=deadline_date,
        source_url=url,
        status=grant_status,  # 'published' or 'draft'
        added_by_id=request.user.pk,
    )

    # ── Save countries (multi-country support) ───────────────────────────────
    # Prefer the 'countries' list; fall back to single 'country' for backward compat.
    countries = scraped.parsed_data.get('countries', [])
    if not countries:
        single_country = scraped.parsed_data.get('country', '').strip()
        if single_country:
            countries = [single_country]
    for country_name in countries:
        country_name = country_name.strip()
        if country_name:
            GrantCountry.objects.get_or_create(grant=grant, country_name=country_name)

    # ── Save degree types ─────────────────────────────────────────────────────────
    DEGREE_MAP = {
        'bachelor': 'bachelor',
        'master':   'master',
        'phd':      'phd',
        'diploma':  'diploma',
    }
    degree_types = scraped.parsed_data.get('degree_types', [])
    for label in degree_types:
        key = DEGREE_MAP.get(label.lower())
        if key:
            GrantDegreeLevel.objects.get_or_create(grant=grant, degree=key)

    # ── Save fields of study ───────────────────────────────────────────
    fields_of_study = scraped.parsed_data.get('fields_of_study', [])
    for field_name in fields_of_study:
        field_name = field_name.strip()
        if field_name:
            GrantFieldOfStudy.objects.get_or_create(grant=grant, field_name=field_name)

    # Only update status — reviewed_by is intentionally skipped because the
    # raw DB FK constraint references a stale 'user' table causing IntegrityError.
    ScrapedGrant.objects.filter(pk=scraped.pk).update(status='approved')

    if grant_status == 'published':
        messages.success(request, f'"{title[:60]}" approved and is now live for users.')
    else:
        messages.success(request, f'"{title[:60]}" saved to Grants as draft.')
    return redirect(request.META.get('HTTP_REFERER', 'scrapers:list'))


@login_required
def scraped_grant_approve(request, pk):
    """Admin: approve a scraped grant → creates a published GrantOpportunity."""
    return _process_scraped_approval(request, pk, grant_status='published')


@login_required
def scraped_grant_draft(request, pk):
    """Admin: approve a scraped grant as a draft."""
    return _process_scraped_approval(request, pk, grant_status='draft')


@login_required
def scraped_grant_reject(request, pk):
    """Admin: reject a scraped grant."""
    if not is_admin(request.user):
        return redirect('grants:list')

    if request.method != 'POST':
        return redirect('scrapers:list')

    scraped = get_object_or_404(ScrapedGrant, pk=pk)

    if scraped.status == 'approved':
        # If it was already approved, it means there is a live grant. We need to delete it.
        from grants.models import GrantOpportunity
        url = scraped.parsed_data.get('url', '')
        if not url and scraped.source:
            url = scraped.source.url
            
        if url:
            # Delete the live grant(s) created from this URL
            GrantOpportunity.objects.filter(source_url=url).delete()

    # Only update status — reviewed_by skipped (stale MySQL FK constraint).
    ScrapedGrant.objects.filter(pk=scraped.pk).update(status='rejected')

    messages.success(request, f'"{scraped.raw_title[:60]}" has been rejected.')
    return redirect(request.META.get('HTTP_REFERER', 'scrapers:list'))
