from django.urls import path
from . import views

app_name = 'grants'

urlpatterns = [

    # --------------------------------------------------------
    # Public URLs
    # --------------------------------------------------------
    path('', views.grant_list, name='list'),
    path('search/', views.grant_search, name='search'),
    path('<int:pk>/', views.grant_detail, name='detail'),

    # --------------------------------------------------------
    # Admin URLs (manage/ to avoid conflict with Django admin)
    # --------------------------------------------------------
    path('manage/', views.admin_grants, name='admin_grants'),
    path('manage/add/', views.grant_create, name='create'),
    path('manage/<int:pk>/edit/', views.grant_edit, name='edit'),
    path('manage/<int:pk>/delete/', views.grant_delete, name='delete'),
]