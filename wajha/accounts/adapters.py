from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
import re


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        full_name = data.get('name') or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        if not full_name:
            full_name = data.get('login', 'User')

        user.full_name = full_name
        user.email = data.get('email', '')

        if user.email in getattr(settings, 'ADMIN_EMAILS', []):
            user.role = 'admin'
            user.is_staff = True
        else:
            user.role = 'student'

        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        from .models import User

        base = re.sub(r'\s+', '_', user.full_name.strip().lower())
        base = re.sub(r'[^a-z_\u0600-\u06FF]', '', base) or 'user'
        username = base
        counter = 1
        while User.objects.filter(username=username).exclude(id=user.id).exists():
            counter += 1
            username = f"{base}{counter}"

        user.username = username
        user.save(update_fields=['username'])
        return user