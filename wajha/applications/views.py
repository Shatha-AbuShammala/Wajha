from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from .models import Application
from grants.models import GrantOpportunity


STATUS_CSS_MAP = {
    'saved': 'c-saved',
    'in_progress': 'c-progress',
    'submitted': 'c-submitted',
    'under_review': 'c-review',
    'accepted': 'c-accepted',
    'rejected': 'c-rejected',
}


@login_required
def dashboard(request):
    applications = Application.objects.filter(
        student=request.user
    ).select_related('grant')

    columns = {key: [] for key, _ in Application.STATUS_CHOICES}
    for app in applications:
        columns[app.status].append(app)

    status_columns = [
        (key, label, STATUS_CSS_MAP[key])
        for key, label in Application.STATUS_CHOICES
    ]

    upcoming_cutoff = timezone.now().date() + timedelta(days=7)
    deadlines_this_week = applications.filter(
        grant__deadline__lte=upcoming_cutoff,
        grant__deadline__gte=timezone.now().date(),
    ).exclude(status__in=['accepted', 'rejected']).count()

    context = {
        'columns': columns,
        'status_columns': status_columns,
        'total_tracked': applications.count(),
        'deadlines_this_week': deadlines_this_week,
    }
    return render(request, 'applications/dashboard.html', context)


@require_POST
@login_required
def update_status(request, application_id):
    application = get_object_or_404(
        Application, id=application_id, student=request.user
    )
    new_status = request.POST.get('status')

    valid_statuses = dict(Application.STATUS_CHOICES)
    if new_status not in valid_statuses:
        return JsonResponse({'ok': False, 'error': 'Invalid status'}, status=400)

    application.status = new_status
    application.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'ok': True, 'status': new_status})


@require_POST
@login_required
def save_grant(request, grant_id):
    grant = get_object_or_404(GrantOpportunity, id=grant_id)
    application, created = Application.objects.get_or_create(
        student=request.user,
        grant=grant,
        defaults={'status': 'saved'}
    )
    if not created and application.status == 'saved':
        
        application.delete()
        return JsonResponse({'ok': True, 'saved': False})

    return JsonResponse({'ok': True, 'saved': True, 'status': application.status})