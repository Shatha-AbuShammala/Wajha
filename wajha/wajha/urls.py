from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.pages_views import landing_view, about_view
from applications.views import dashboard 

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("grants/", include("grants.urls", namespace="grants")),
    path("scrapers/", include("scrapers.urls", namespace="scrapers")),
    path("", landing_view, name="landing"),
    path("", landing_view, name="home"),
    path("about/", about_view, name="about"),
    path('applications/', include('applications.urls')),
    path('dashboard/', dashboard, name='dashboard_shortcut'),   


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
