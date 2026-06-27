from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import GrantSource, ScrapedGrant


# ─────────────────────────────────────────────────────────────────────────────
# GrantSource Admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(GrantSource)
class GrantSourceAdmin(admin.ModelAdmin):
    list_display  = ('name', 'url', 'frequency', 'is_active', 'failure_count', 'last_scraped_at')
    list_filter   = ('is_active', 'frequency')
    search_fields = ('name', 'url')
    list_editable = ('is_active',)
    readonly_fields = ('last_scraped_at', 'failure_count')

    fieldsets = (
        ('Source Info', {
            'fields': ('name', 'url', 'frequency', 'is_active')
        }),
        ('Scraper Config', {
            'fields': ('selector_map',),
            'classes': ('collapse',),
        }),
        ('Health Stats', {
            'fields': ('last_scraped_at', 'failure_count'),
            'classes': ('collapse',),
        }),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Custom Admin Actions
# ─────────────────────────────────────────────────────────────────────────────

import datetime
import re

def parse_deadline_date(deadline_str):
    if not deadline_str:
        return None
    deadline_str = deadline_str.strip()
    if deadline_str.lower() in ['unspecified', 'n/a', 'none', '—', '']:
        return None
    
    # Try ISO date first (YYYY-MM-DD)
    iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', deadline_str)
    if iso_match:
        try:
            return datetime.date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    normalized = re.sub(r'[^\w\s]', ' ', deadline_str.lower())
    parts = normalized.split()
    
    year = None
    month = None
    day = None
    
    for part in parts:
        if part.isdigit() and len(part) == 4 and part.startswith('20'):
            year = int(part)
            break
            
    for part in parts:
        if part in months:
            month = months[part]
            break
            
    for part in parts:
        if part.isdigit() and len(part) <= 2:
            val = int(part)
            if 1 <= val <= 31:
                day = val
                
    if year and month:
        try:
            return datetime.date(year, month, day or 1)
        except ValueError:
            pass
            
    return None


@admin.action(description='✅ Approve & Publish selected scraped grants')
def approve_grants(modeladmin, request, queryset):
    from grants.models import GrantOpportunity
    
    approved_count = 0
    skipped_count = 0
    
    for scraped in queryset:
        if scraped.status != 'approved':
            title = scraped.raw_title
            url = scraped.parsed_data.get('url', '')
            desc = scraped.parsed_data.get('description', '')
            
            if not desc:
                desc = scraped.raw_title
            
            if not url and scraped.source:
                url = scraped.source.url
            if not url:
                url = "https://opportunitydesk.org/"
            
            # Deduplicate checking
            if GrantOpportunity.objects.filter(source_url=url).exists():
                scraped.status = 'approved'
                scraped.reviewed_by = request.user
                scraped.save()
                skipped_count += 1
                continue
            
            org = scraped.parsed_data.get('organization', '')
            if not org and scraped.source:
                org = scraped.source.name
            if not org:
                org = "Opportunity Desk"
            
            deadline_str = scraped.parsed_data.get('deadline', '')
            deadline_date = parse_deadline_date(deadline_str)
            if not deadline_date:
                # 30-day fallback
                deadline_date = timezone.now().date() + datetime.timedelta(days=30)
            
            # Guess funding type
            funding_type = 'fully_funded'
            search_text = (title + ' ' + desc).lower()
            if 'partial' in search_text:
                funding_type = 'partial'
            elif 'tuition' in search_text:
                funding_type = 'tuition_only'
            elif 'stipend' in search_text:
                funding_type = 'stipend_only'
            elif 'travel' in search_text:
                funding_type = 'travel_grant'
            
            # Create as Draft
            GrantOpportunity.objects.create(
                title=title,
                organization=org,
                description=desc,
                eligibility_text="Please refer to the source website link for detailed eligibility criteria.",
                eligibility_summary="No AI summary generated yet.",
                funding_type=funding_type,
                deadline=deadline_date,
                source_url=url,
                status='draft',
                added_by=request.user
            )
            
            scraped.status = 'approved'
            scraped.reviewed_by = request.user
            scraped.save()
            approved_count += 1
            
    message = f"Successfully approved and published {approved_count} new grants as drafts."
    if skipped_count > 0:
        message += f" Skipped {skipped_count} duplicates."
    modeladmin.message_user(request, message)


@admin.action(description='❌ Reject selected scraped grants')
def reject_grants(modeladmin, request, queryset):
    queryset.update(status='rejected', reviewed_by=request.user)


# ─────────────────────────────────────────────────────────────────────────────
# ScrapedGrant Admin (The Review Queue Page)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ScrapedGrant)
class ScrapedGrantAdmin(admin.ModelAdmin):
    list_display   = (
        'short_title', 'source',        'status_badge', 'deadline_display', 'source_link', 'scraped_at', 'reviewed_by'
    )
    list_filter    = ('status', 'source', 'scraped_at')
    search_fields  = ('raw_title', 'parsed_data')
    actions        = [approve_grants, reject_grants]
    readonly_fields = (
        'source', 'raw_title', 'raw_html_snippet', 'preview_html',
        'parsed_data', 'scraped_at', 'reviewed_by'
    )
    list_per_page  = 25

    fieldsets = (
        ('Raw Scraped Data', {
            'fields': ('source', 'raw_title', 'raw_html_snippet', 'preview_html', 'scraped_at')
        }),
        ('Parsed Details', {
            'fields': ('parsed_data',),
        }),
        ('Review', {
            'fields': ('status', 'reviewed_by'),
        }),
    )

    # ── Custom display columns ────────────────────────────────────────────────

    @admin.display(description='Title')
    def short_title(self, obj):
        return obj.raw_title[:70] + '…' if len(obj.raw_title) > 70 else obj.raw_title

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending':  '#f59e0b',
            'approved': '#10b981',
            'rejected': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )

    @admin.display(description='Deadline')
    def deadline_display(self, obj):
        return obj.parsed_data.get('deadline', '—')

    @admin.display(description='Source URL')
    def source_link(self, obj):
        url = obj.parsed_data.get('url', '')
        if url:
            return format_html('<a href="{}" target="_blank">🔗 Open</a>', url)
        return '—'

    @admin.display(description='HTML Preview')
    def preview_html(self, obj):
        if obj.raw_html_snippet:
            return format_html(
                '<iframe srcdoc="{}" style="width:100%; height:300px; border:1px solid #ccc; border-radius:4px; background:#fff;" sandbox=""></iframe>',
                obj.raw_html_snippet
            )
        return 'No snippet available'
