from django.urls import path
from . import views

urlpatterns = [
    path('matches/', views.student_matches, name='matches'),
    path('assistant/', views.ai_assistant, name='assistant'),
    path('assistant/draft-letter/', views.draft_letter_api, name='draft_letter_api'),
    path('assistant/review-cv/', views.review_cv_api, name='review_cv_api'),
    path('assistant/save-letter/', views.save_letter_api, name='save_letter_api'),
    path('assistant/personalized-eligibility/', views.personalized_eligibility_api, name='personalized_eligibility_api'),
    path('grants/<int:grant_id>/simplify-eligibility/', views.simplify_eligibility_api, name='simplify_eligibility_api'),
]