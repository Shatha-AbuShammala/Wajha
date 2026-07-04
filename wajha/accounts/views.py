from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, ProfileSetupForm, EmailAuthenticationForm
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.urls import reverse
from urllib.parse import urlencode
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives


# ===================== EMAIL FUNCTIONS =====================

def send_welcome_email(user, request):
    subject = "Welcome to Wajha — Your account is ready"
    site_url = request.build_absolute_uri('/')

    context = {
        'full_name': user.full_name,
        'username': user.username,
        'email': user.email,
        'site_url': site_url,
    }

    html_content = render_to_string('accounts/emails/welcome_email.html', context)
    text_content = render_to_string('accounts/emails/welcome_email.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=True)


def send_login_email(user, request):
    subject = "New sign-in to your Wajha account"
    password_reset_url = request.build_absolute_uri('/accounts/password-reset/')
    login_time = timezone.now().strftime("%B %d, %Y at %I:%M %p UTC")

    context = {
        'full_name': user.full_name,
        'username': user.username,
        'email': user.email,
        'login_time': login_time,
        'password_reset_url': password_reset_url,
    }

    html_content = render_to_string('accounts/emails/login_email.html', context)
    text_content = render_to_string('accounts/emails/login_email.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=True)  # لو فشل الإيميل، ما يكسر تسجيل الدخول


# ===================== PROFILE HELPERS =====================

def calculate_profile_strength(user):
    """Weighted profile completeness score out of 100."""
    fields_weight = {
        'field_of_study': 15,
        'degree_level': 15,
        'country': 10,
        'gpa': 15,
        'languages': 15,
        'cv_file': 20,
        'bio': 10,
    }
    score = 0
    for field, weight in fields_weight.items():
        if getattr(user, field, None):
            score += weight
    return min(score, 100)


def get_profile_gaps(user):
    """
    Rule-based placeholder for AI gap analysis.
    Developer D (ai_engine) can later replace this with a real Claude API call.
    """
    gaps = []
    if not user.bio:
        gaps.append("Add a short bio to help AI personalize your matches.")
    if not user.languages:
        gaps.append("Add at least one language you're fluent in.")
    if not user.cv_file:
        gaps.append("Upload your CV (PDF) to unlock application drafting.")
    if not user.country:
        gaps.append("Add your country to filter eligible grants correctly.")
    return gaps


# ===================== AUTH VIEW (unified signin/register) =====================
def auth_view(request):
    if request.method == 'POST':
        submitted = request.POST.get('form_type', 'signin')

        if submitted == 'register':
            register_form = SignUpForm(request.POST)
            login_form = EmailAuthenticationForm()
            if register_form.is_valid():
                user = register_form.save(commit=False)
                if user.email in getattr(settings, 'ADMIN_EMAILS', []):
                    user.role = 'admin'
                    user.is_staff = True
                else:
                    user.role = 'student'
                user.save()
                login(request, user, backend='accounts.backends.EmailBackend')
                send_welcome_email(user, request)
                return redirect('profile_setup')
            mode = 'register'
        else:
            login_form = EmailAuthenticationForm(request, data=request.POST)
            register_form = SignUpForm()
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)

                if not request.POST.get('remember_me'):
                    request.session.set_expiry(0)

                if user.email in getattr(settings, 'ADMIN_EMAILS', []) and user.role != 'admin':
                    user.role = 'admin'
                    user.is_staff = True
                    user.save(update_fields=['role', 'is_staff'])

                send_login_email(user, request)

                if user.role == 'admin':
                    return redirect('/admin/')
                return redirect('/')
            mode = 'signin'
    else:
        login_form = EmailAuthenticationForm()
        register_form = SignUpForm()
        mode = 'signin'

    return render(request, 'accounts/auth.html', {
        'login_form': login_form,
        'register_form': register_form,
        'mode': mode,
    })

def logout_view(request):
    logout(request)
    return redirect('login')


# ===================== PROFILE VIEWS =====================

@login_required
def profile_setup_view(request):
    if request.method == 'POST':
        form = ProfileSetupForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            changed = form.has_changed()
            form.save()
            if changed:
                return redirect('/accounts/profile/?saved=1')
            return redirect('profile')
    else:
        form = ProfileSetupForm(instance=request.user)

    context = {
        'form': form,
        'profile_strength': calculate_profile_strength(request.user),
        'profile_gaps': get_profile_gaps(request.user),
    }
    return render(request, 'accounts/profile_setup.html', context)


@login_required
def profile_view(request):
    context = {
        'profile_user': request.user,
        'profile_strength': calculate_profile_strength(request.user),
        'profile_gaps': get_profile_gaps(request.user),
    }
    return render(request, 'accounts/profile.html', context)


# ===================== ADMIN VIEWS =====================

def is_admin_user(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_staff)

def _admin_users_redirect(request):
    """Maintains the same search and page after any modification."""
    base = reverse('admin_users')
    params = {}
    if request.POST.get('q'):
        params['q'] = request.POST.get('q')
    if request.POST.get('page'):
        params['page'] = request.POST.get('page')
    return f"{base}?{urlencode(params)}" if params else base


@login_required
@user_passes_test(is_admin_user, login_url='landing')
def admin_users_view(request):
    from .models import User

    query = request.GET.get('q', '').strip()
    users_qs = User.objects.all().order_by('-created_at')

    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(full_name__icontains=query)
        )

    total_users = User.objects.count()
    now = timezone.now()
    new_this_month = User.objects.filter(
        created_at__year=now.year, created_at__month=now.month
    ).count()
    active_profiles = User.objects.filter(is_active=True).count()

    all_users = User.objects.all()
    if all_users.exists():
        avg_strength = sum(calculate_profile_strength(u) for u in all_users) / all_users.count()
    else:
        avg_strength = 0

    paginator = Paginator(users_qs, 6)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'query': query,
        'total_users': total_users,
        'new_this_month': new_this_month,
        'active_profiles': active_profiles,
        'avg_strength': round(avg_strength),
    }
    return render(request, 'accounts/admin_users.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='landing')
@require_POST
def toggle_admin_view(request, user_id):
    from .models import User
    target = get_object_or_404(User, id=user_id)

    if target.role == 'admin':
        target.role = 'student'
        target.is_staff = False
        msg = f"{target.username} is no longer an admin."
    else:
        target.role = 'admin'
        target.is_staff = True
        msg = f"{target.username} is now an admin."

    target.save(update_fields=['role', 'is_staff'])
    messages.success(request, msg)
    return redirect(_admin_users_redirect(request))


@login_required
@user_passes_test(is_admin_user, login_url='landing')
@require_POST
def toggle_active_view(request, user_id):
    from .models import User
    target = get_object_or_404(User, id=user_id)

    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    status = "suspended" if not target.is_active else "restored"
    messages.success(request, f"{target.username} has been {status}.")
    return redirect(_admin_users_redirect(request))


@login_required
@user_passes_test(is_admin_user, login_url='landing')
@require_POST
def delete_user_view(request, user_id):
    from .models import User
    target = get_object_or_404(User, id=user_id)

    if target.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect(_admin_users_redirect(request))

    username = target.username
    target.delete()
    messages.success(request, f"User '{username}' and all associated data have been deleted.")
    return redirect('admin_users')


