from django.shortcuts import render
from django.utils import timezone
from grants.models import GrantOpportunity

def landing_view(request):
    grants = GrantOpportunity.objects.filter(
        status='published',
        deadline__gte=timezone.now().date()).prefetch_related('degree_levels', 'countries').order_by('-created_at')[:6]

    return render(request, 'pages/landing.html', {'grants': grants})

def about_view(request):
    return render(request, 'pages/about.html')