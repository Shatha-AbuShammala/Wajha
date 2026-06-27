from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile Info', {
            'fields': ('role', 'full_name', 'country', 'field_of_study',
                       'degree_level', 'gpa', 'languages', 'cv_file', 'bio')
        }),
    )
    list_display = ('username', 'email', 'role', 'full_name', 'is_staff')


admin.site.register(User, UserAdmin)