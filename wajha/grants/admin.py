from django.contrib import admin
from .models import (
    GrantOpportunity,
    GrantFieldOfStudy,
    GrantDegreeLevel,
    GrantCountry
)


class GrantFieldOfStudyInline(admin.TabularInline):
    model = GrantFieldOfStudy
    extra = 1


class GrantDegreeLevelInline(admin.TabularInline):
    model = GrantDegreeLevel
    extra = 1


class GrantCountryInline(admin.TabularInline):
    model = GrantCountry
    extra = 1


@admin.register(GrantOpportunity)
class GrantOpportunityAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'organization',
        'funding_type',
        'deadline',
        'status',
        'days_until_deadline',
    ]
    list_filter = ['status', 'funding_type']
    search_fields = ['title', 'organization']
    readonly_fields = ['created_at', 'updated_at'] 
    inlines = [
        GrantFieldOfStudyInline,
        GrantDegreeLevelInline,
        GrantCountryInline
    ]


@admin.register(GrantFieldOfStudy)
class GrantFieldOfStudyAdmin(admin.ModelAdmin):
    list_display = ['grant', 'field_name']
    search_fields = ['field_name']
    


@admin.register(GrantDegreeLevel)
class GrantDegreeLevelAdmin(admin.ModelAdmin):
    list_display = ['grant', 'degree']
    list_filter = ['degree']


@admin.register(GrantCountry)
class GrantCountryAdmin(admin.ModelAdmin):
    list_display = ['grant', 'country_name']
    search_fields = ['country_name']