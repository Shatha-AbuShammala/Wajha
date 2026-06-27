from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from .forms import SignUpForm, ProfileSetupForm, EmailAuthenticationForm


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # لو الإيميل بقائمة الأدمن المعرّفة بـ settings.py، نعطيه صلاحية أدمن تلقائياً
            if user.email in getattr(settings, 'ADMIN_EMAILS', []):
                user.role = 'admin'
                user.is_staff = True
            else:
                user.role = 'student'
            user.save()
            login(request, user, backend='accounts.backends.EmailBackend')
            return redirect('profile_setup')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = EmailAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        # احتياطي: لو الإيميل بقائمة الأدمن بس الدور لسا مش متزامن
        if user.email in getattr(settings, 'ADMIN_EMAILS', []) and user.role != 'admin':
            user.role = 'admin'
            user.is_staff = True
            user.save(update_fields=['role', 'is_staff'])
        return response

    def get_success_url(self):
        user = self.request.user
        if user.role == 'admin':
            return '/admin/'
        return '/'


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile_setup_view(request):
    if request.method == 'POST':
        form = ProfileSetupForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been successfully saved.")
            return redirect('profile')
    else:
        form = ProfileSetupForm(instance=request.user)
    return render(request, 'accounts/profile_setup.html', {'form': form})


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileSetupForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated')
            return redirect('profile')
    else:
        form = ProfileSetupForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form, 'profile_user': request.user})