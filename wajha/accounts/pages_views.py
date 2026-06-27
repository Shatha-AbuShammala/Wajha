from django.shortcuts import render

# بيانات مؤقتة لحد ما الـ grants app يخلص (نفس الداتا من الـ prototype الأصلي)
SAMPLE_GRANTS = [
    {"title": "Fulbright Foreign Student Program", "org": "U.S. Dept. of State", "level": "Masters", "days": 18, "tags": ["USA", "Open field"]},
    {"title": "DAAD Study Scholarship", "org": "DAAD · Germany", "level": "PhD", "days": 42, "tags": ["Germany", "Fully funded"]},
    {"title": "Chevening Scholarship", "org": "UK Government", "level": "Masters", "days": 90, "tags": ["UK"]},
    {"title": "Erasmus+ Mobility Grant", "org": "European Commission", "level": "Bachelor", "days": 30, "tags": ["EU"]},
    {"title": "Australia Awards", "org": "Govt. of Australia", "level": "PhD", "days": 120, "tags": ["Australia"]},
    {"title": "Türkiye Bursları", "org": "Govt. of Türkiye", "level": "Masters", "days": 9, "tags": ["Türkiye"]},
]


def landing_view(request):
    grants = []
    for g in SAMPLE_GRANTS:
        grants.append({**g, "urgent": g["days"] <= 21})
    return render(request, 'pages/landing.html', {"grants": grants})


def about_view(request):
    return render(request, 'pages/about.html')