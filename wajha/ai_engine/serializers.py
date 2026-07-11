from rest_framework import serializers
from .models import AIMatch

class AIMatchSerializer(serializers.ModelSerializer):
    grant_title = serializers.CharField(source='grant.title', read_only=True)
    # حقول إضافية للبطاقة بناءً على التصميم (الأيام المتبقية والمستوى الدراسي)
    deadline_days = serializers.IntegerField(source='grant.deadline_days', read_only=True) # تأكد من وجوده في موديل المنحة
    degree_level = serializers.CharField(source='grant.degree_level', read_only=True)
    
    # حقل ديناميكي لحالة التوافق النصية (strong fit / good fit)
    fit_status = serializers.SerializerMethodField()

    class Meta:
        model = AIMatch
        fields = [
            'id', 
            'grant', 
            'grant_title', 
            'degree_level',
            'deadline_days',
            'match_score', 
            'fit_status',
            'explanation', 
            'generated_at'
        ]

    def get_fit_status(self, obj):
        # تقسيم الفئات بناءً على النسب الظاهرة في واجهة image_11e7c8.png
        score = float(obj.match_score)
        if score >= 85.0:
            return "strong fit"
        elif score >= 70.0:
            return "good fit"
        else:
            return "fair fit"