from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('<int:application_id>/update-status/', views.update_status, name='update_status'),
    path('save/<int:grant_id>/', views.save_grant, name='save_grant'), 
]