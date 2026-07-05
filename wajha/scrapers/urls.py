from django.urls import path
from . import views

app_name = 'scrapers'

urlpatterns = [
    # Scraped Grants Review Queue
    path('scraped/', views.scraped_grants_list, name='list'),
    path('scraped/<int:pk>/', views.scraped_grant_detail, name='detail'),
    path('scraped/<int:pk>/approve/', views.scraped_grant_approve, name='approve'),
    path('scraped/<int:pk>/draft/', views.scraped_grant_draft, name='draft'),
    path('scraped/<int:pk>/reject/', views.scraped_grant_reject, name='reject'),
]
