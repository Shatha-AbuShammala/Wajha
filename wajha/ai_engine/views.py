from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import AIMatch
from .services import AIService
from grants.models import GrantOpportunity
from applications.models import Application
from accounts.views import calculate_profile_strength

@login_required
def student_matches(request):
    """
    Displays AI Matches page and recalculates matches via AJAX.
    """
    # Fetch existing matches sorted by match score
    matches = AIMatch.objects.filter(student=request.user).select_related('grant').order_by('-match_score')
    
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            # Recalculate match scores and explanations using Gemini
            AIService.generate_matches_for_student(request.user)
            
            # Fetch updated matches
            updated_matches = AIMatch.objects.filter(student=request.user).select_related('grant').order_by('-match_score')
            saved_grant_ids = list(Application.objects.filter(student=request.user).values_list('grant_id', flat=True))
            
            
            data = []
            for match in updated_matches:
                score = float(match.match_score)
                fit_status = "strong fit" if score >= 85 else "good fit" if score >= 70 else "fair fit"
                
                # Check days left
                days_left = match.grant.days_until_deadline()
                
                data.append({
                    'id': match.grant.id,
                    'grant_title': match.grant.title,
                    'funding_type': match.grant.get_funding_type_display(),
                    'degree_level': ", ".join([d.get_degree_display() for d in match.grant.degree_levels.all()]) or "Masters",
                    'deadline_days': days_left,
                    'match_score': int(score),
                    'fit_status': fit_status,
                    'explanation': match.explanation,
                    'saved': match.grant.id in saved_grant_ids,
                })
            
            return JsonResponse({'success': True, 'total_count': len(data), 'matches': data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Initial load page rendering
    total_count = matches.count()
    saved_grant_ids = list(Application.objects.filter(student=request.user).values_list('grant_id', flat=True))
    context = {
        'matches': matches,
        'total_count': total_count,
        'saved_grant_ids': saved_grant_ids,
    }
    return render(request, 'engines/matches.html', context)


@login_required
def ai_assistant(request):
    """
    Renders the AI Onboarding and Application Assistant interface.
    """
    # Get all applications tracked by user to show in dropdown
    applications = Application.objects.filter(student=request.user).select_related('grant')
    
    # Determine the selected grant opportunity
    selected_grant = None
    grant_id = request.GET.get('grant')
    if grant_id:
        selected_grant = get_object_or_404(GrantOpportunity, id=grant_id)
    elif applications.exists():
        selected_grant = applications.first().grant
    else:
        selected_grant = GrantOpportunity.objects.filter(status='published').first()
        
    # Get existing motivation letter drafted (if application exists)
    motivation_letter_text = ""
    app_exists = False
    if selected_grant:
        app_obj = applications.filter(grant=selected_grant).first()
        if app_obj:
            motivation_letter_text = app_obj.motivation_letter_text or ""
            app_exists = True

    context = {
        'applications': applications,
        'selected_grant': selected_grant,
        'motivation_letter_text': motivation_letter_text,
        'app_exists': app_exists,
        'profile_strength': calculate_profile_strength(request.user),
        'has_cv': bool(request.user.cv_file),
        'student': request.user,
    }
    return render(request, 'engines/assistant.html', context)


@login_required
@require_POST
def draft_letter_api(request):
    """
    API endpoint to draft a motivation letter via Gemini.
    """
    grant_id = request.POST.get('grant_id')
    tone = request.POST.get('tone', 'formal')
    custom_focus = request.POST.get('custom_focus', '')
    
    if not grant_id:
        return JsonResponse({'success': False, 'error': 'Missing grant ID'}, status=400)
        
    grant = get_object_or_404(GrantOpportunity, id=grant_id)
    draft_text = AIService.draft_motivation_letter(request.user, grant, tone, custom_focus)
    
    return JsonResponse({'success': True, 'draft': draft_text})


@login_required
@require_POST
def review_cv_api(request):
    """
    API endpoint to check profile gaps and get CV recommendations relative to a grant.
    """
    grant_id = request.POST.get('grant_id')
    
    if not grant_id:
        return JsonResponse({'success': False, 'error': 'Missing grant ID'}, status=400)
        
    grant = get_object_or_404(GrantOpportunity, id=grant_id)
    gaps = AIService.review_cv(request.user, grant)
    
    return JsonResponse({'success': True, 'gaps': gaps})


@login_required
@require_POST
def save_letter_api(request):
    """
    API endpoint to save the drafted motivation letter to the user's application.
    """
    grant_id = request.POST.get('grant_id')
    letter_text = request.POST.get('letter_text', '')
    
    if not grant_id:
        return JsonResponse({'success': False, 'error': 'Missing grant ID'}, status=400)
        
    grant = get_object_or_404(GrantOpportunity, id=grant_id)
    
    # Save to application (create if it doesn't exist)
    application, created = Application.objects.get_or_create(
        student=request.user,
        grant=grant,
        defaults={'status': 'saved'}
    )
    application.motivation_letter_text = letter_text
    application.letter_drafted = True
    application.save(update_fields=['motivation_letter_text', 'letter_drafted', 'updated_at'])
    
    return JsonResponse({'success': True, 'created': created})


@login_required
@require_POST
def simplify_eligibility_api(request, grant_id):
    """
    API endpoint to trigger dynamic eligibility summary simplification.
    """
    grant = get_object_or_404(GrantOpportunity, id=grant_id)
    summary = AIService.generate_eligibility_summary(grant)
    return JsonResponse({'success': True, 'summary': summary})