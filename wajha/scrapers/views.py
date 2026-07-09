from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField
from django.contrib import messages
from .models import ScrapedGrant, GrantSource
from .utils import is_admin, get_referer


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
    query         = request.GET.get('q', '')

    qs = ScrapedGrant.objects.select_related('source', 'reviewed_by')

    if status_filter == 'default':
        # Show pending and rejected, with pending ordered first
        qs = qs.exclude(status='approved').order_by(
            Case(
                When(status='pending',  then=Value(1)),
                When(status='rejected', then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            '-scraped_at',
        )
    elif status_filter in ('pending', 'approved', 'rejected'):
        qs = qs.filter(status=status_filter).order_by('-scraped_at')
    else:
        qs = qs.order_by('-scraped_at')

    if source_filter:
        qs = qs.filter(source_id=source_filter)

    if query:
        qs = qs.filter(raw_title__icontains=query)

    pending_count = ScrapedGrant.objects.filter(status='pending').count()
    sources       = GrantSource.objects.all()

    paginator = Paginator(qs, 15)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj':      page_obj,
        'total_count':   qs.count(),
        'status_filter': status_filter,
        'source_filter': source_filter,
        'query':         query,
        'pending_count': pending_count,
        'sources':       sources,
    }
    return render(request, 'scrapers/admin/scraped_list.html', context)


@login_required
def scraped_grant_detail(request, pk):
    """Admin: view full parsed data for a single scraped grant."""
    if not is_admin(request.user):
        return redirect('grants:list')

    scraped = get_object_or_404(ScrapedGrant, pk=pk)
    context = {
        'scraped':       scraped,
        'pending_count': ScrapedGrant.objects.filter(status='pending').count(),
    }
    return render(request, 'scrapers/admin/scraped_detail.html', context)


def _process_scraped_approval(request, pk, grant_status='published'):
    """Helper to handle approving a scraped grant either as published or draft."""
    if not is_admin(request.user):
        return redirect('grants:list')

    if request.method != 'POST':
        return redirect('scrapers:list')

    scraped = get_object_or_404(ScrapedGrant, pk=pk)

    if scraped.status == ScrapedGrant.Status.APPROVED:
        messages.warning(request, f'"{scraped.raw_title[:60]}" was already approved.')
        return redirect(get_referer(request))

    grant, created = scraped.approve_to_grant(request.user, grant_status=grant_status)

    if not created:
        messages.info(request, 'Grant already exists in live grants (duplicate). Marked approved.')
    elif grant_status == 'published':
        messages.success(request, f'"{scraped.raw_title[:60]}" approved and is now live for users.')
    else:
        messages.success(request, f'"{scraped.raw_title[:60]}" saved to Grants as draft.')

    return redirect(get_referer(request))


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
    scraped.reject()

    messages.success(request, f'"{scraped.raw_title[:60]}" has been rejected.')
    return redirect(get_referer(request))