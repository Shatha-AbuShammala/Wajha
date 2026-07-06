from django.contrib import admin
from .models import GrantSource, ScrapedGrant

admin.site.register(GrantSource)
admin.site.register(ScrapedGrant)
