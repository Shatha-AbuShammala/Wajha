from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import GrantOpportunity, GrantFieldOfStudy, GrantDegreeLevel, GrantCountry
from .forms import GrantForm, GrantSearchForm

def save_grant_tags(grant, cleaned_data):
    grant.fields.all().delete()

    for field in cleaned_data.get('fields_of_study', '').split(','):
        if field.strip():
            GrantFieldOfStudy.objects.create(grant=grant, field_name=field.strip())

    grant.degree_levels.all().delete()
    for degree in cleaned_data.get('degree_levels', []):
        GrantDegreeLevel.objects.create(grant=grant, degree=degree)

    grant.countries.all().delete()
    for country in cleaned_data.get('countries', '').split(','):
        if country.strip():
            GrantCountry.objects.create(grant=grant, country_name=country.strip()) 


# ============================================================
# Helper: Admin check
# ============================================================

def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


# ============================================================
# Public Views
# ============================================================

def grant_list(request):
    """Browse page: show all published grants as cards."""
    grants = GrantOpportunity.objects.filter(
        status='published',
        deadline__gte=timezone.now().date()
    ).prefetch_related('fields', 'degree_levels', 'countries')

    total = grants.count()
    paginator = Paginator(grants, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_count': total,
    }
    return render(request, 'grants/list.html', context)


def grant_detail(request, pk):
    """Grant detail page: full info + sidebar."""
    grant = get_object_or_404(
        GrantOpportunity.objects.prefetch_related(
            'fields', 'degree_levels', 'countries'
        ),
        pk=pk,
        status='published'
    )

    context = {
        'grant': grant,
        'days_left': grant.days_until_deadline(),
        'is_urgent': grant.is_urgent(),
    }
    return render(request, 'grants/detail.html', context)


def grant_search(request):
    """Search page with AJAX filtering."""
    form = GrantSearchForm(request.GET or None)

    grants = GrantOpportunity.objects.filter(
        status='published',
        deadline__gte=timezone.now().date()
    ).prefetch_related('fields', 'degree_levels', 'countries')

    if form.is_valid():
        # Filter by search query
        query = form.cleaned_data.get('query')
        if query:
            grants = grants.filter(
                Q(title__icontains=query) |
                Q(organization__icontains=query)
            )

        # Filter by degree level
        degree_levels = form.cleaned_data.get('degree_level')
        if degree_levels:
            grants = grants.filter(
                degree_levels__degree__in=degree_levels
            ).distinct()

        # Filter by country
        country = form.cleaned_data.get('country')
        if country:
            grants = grants.filter(
                countries__country_name__icontains=country
            ).distinct()

        # Filter by field of study
        field = form.cleaned_data.get('field_of_study')
        if field:
            grants = grants.filter(
                fields__field_name__icontains=field
            ).distinct()

        # Filter by deadline within x days
        deadline_within = form.cleaned_data.get('deadline_within')
        if deadline_within:
            max_date = timezone.now().date() + timedelta(days=deadline_within)
            grants = grants.filter(deadline__lte=max_date)

    # AJAX request → return JSON
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or request.GET.get('format') == 'json'
    )

    if is_ajax:
        data = []
        for grant in grants[:20]:
            data.append({
                'id': grant.pk,
                'title': grant.title,
                'organization': grant.organization,
                'deadline': grant.deadline.strftime('%d %b %Y'),
                'days_left': grant.days_until_deadline(),
                'is_urgent': grant.is_urgent(),
                'funding_type': grant.get_funding_type_display(),
                'degree_levels': list(
                    grant.degree_levels.values_list('degree', flat=True)
                ),
                'countries': list(
                    grant.countries.values_list('country_name', flat=True)
                ),
                'url': f'/grants/{grant.pk}/',
            })
        return JsonResponse({'grants': data, 'count': len(data)})

    # Normal request → render page
    total = grants.count()
    paginator = Paginator(grants, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_countries = GrantCountry.objects.values_list(
        'country_name', flat=True
    ).distinct().order_by('country_name')

    all_fields = GrantFieldOfStudy.objects.values_list(
        'field_name', flat=True
    ).distinct().order_by('field_name')

    context = {
        'form': form,
        'page_obj': page_obj,
        'total_count': total,
        'all_countries': all_countries,
        'all_fields': all_fields,
    }
    return render(request, 'grants/search.html', context)


# ============================================================
# Admin Views
# ============================================================

@login_required
def admin_grants(request):
    """Admin: grants management table."""
    if not is_admin(request.user):
        return redirect('grants:list')

    query = request.GET.get('q', '')
    grants = GrantOpportunity.objects.prefetch_related(
        'fields', 'degree_levels', 'countries'
    )

    if query:
        grants = grants.filter(
            Q(title__icontains=query) |
            Q(organization__icontains=query)
        )

    total = GrantOpportunity.objects.count()
    paginator = Paginator(grants, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_count': total,
        'query': query,
    }
    return render(request, 'grants/admin/grants_table.html', context)


@login_required
def grant_create(request):
    """Admin: add new grant."""
    if not is_admin(request.user):
        return redirect('grants:list')

    if request.method == 'POST':
        form = GrantForm(request.POST)
        if form.is_valid():
            grant = form.save(commit=False)
            grant.added_by = request.user
            grant.save()
            save_grant_tags(grant, form.cleaned_data)
            #form.save_tags()
            return redirect('grants:admin_grants')
    else:
        form = GrantForm()

    context = {
        'form': form,
        'action': 'Add',
    }
    return render(request, 'grants/admin/grant_form.html', context)


@login_required
def grant_edit(request, pk):
    """Admin: edit existing grant."""
    if not is_admin(request.user):
        return redirect('grants:list')

    grant = get_object_or_404(GrantOpportunity, pk=pk)

    if request.method == 'POST':
        form = GrantForm(request.POST, instance=grant)
        if form.is_valid():
            grant = form.save(commit=False)
            grant.save()
            save_grant_tags(grant, form.cleaned_data)
            return redirect('grants:admin_grants')
            
    else:
        form = GrantForm(instance=grant)

    context = {
        'form': form,
        'action': 'Edit',
        'grant': grant,
    }
    return render(request, 'grants/admin/grant_form.html', context)


@login_required
def grant_delete(request, pk):
    """Admin: delete grant with confirmation."""
    if not is_admin(request.user):
        return redirect('grants:list')

    grant = get_object_or_404(GrantOpportunity, pk=pk)

    if request.method == 'POST':
        grant.delete()
        return redirect('grants:admin_grants')

    context = {
        'grant': grant,
    }
    return render(request, 'grants/admin/confirm_delete.html', context)