from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from unittest.mock import patch
from django.http import HttpResponse

from grants.models import GrantOpportunity, GrantFieldOfStudy, GrantDegreeLevel, GrantCountry
from grants.forms import GrantForm
from grants.views import grant_list, grant_search, is_admin, save_grant_tags


User = get_user_model()


# ============================================================
# Helper: Create admin user
# ============================================================
def create_admin():
    admin = User.objects.filter(username='admin').first()

    if not admin:
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        admin.role = 'admin'
        admin.save()

    return admin


# ============================================================
# Test: Save Tags Logic
# ============================================================
class SaveTagsTest(TestCase):

    def setUp(self):
        self.admin = create_admin()

        self.grant = GrantOpportunity.objects.create(
            title="Test Grant",
            organization="Test Org",
            description="Test",
            eligibility_text="Test",
            funding_type="fully_funded",
            deadline="2026-12-31",
            source_url="https://test.com",
            status="published",
            added_by=self.admin
        )

    def test_save_grant_tags(self):
        data = {
            'fields_of_study': 'Computer Science, Engineering',
            'degree_levels': ['master', 'phd'],
            'countries': 'Palestine, Germany',
        }

        save_grant_tags(self.grant, data)

        fields = list(self.grant.fields.values_list('field_name', flat=True))
        degrees = list(self.grant.degree_levels.values_list('degree', flat=True))
        countries = list(self.grant.countries.values_list('country_name', flat=True))

        self.assertCountEqual(fields, ['Computer Science', 'Engineering'])
        self.assertCountEqual(degrees, ['master', 'phd'])
        self.assertCountEqual(countries, ['Palestine', 'Germany'])


# ============================================================
# Test: Views (WITHOUT templates)
# ============================================================
class ViewsTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.admin = create_admin()

        GrantOpportunity.objects.create(
            title="Test Grant",
            organization="Test Org",
            description="Test",
            eligibility_text="Test",
            funding_type="fully_funded",
            deadline="2026-12-31",
            source_url="https://test.com",
            status="published",
            added_by=self.admin
        )

    # --------------------------------------------------------
    # Mock render so no template is needed
    # --------------------------------------------------------
    @patch('grants.views.render')
    def test_grant_list_view(self, mock_render):

        mock_render.return_value = HttpResponse("OK")

        request = self.factory.get('/grants/')
        response = grant_list(request)

        self.assertEqual(response.status_code, 200)


# ============================================================
# Test: Admin check
# ============================================================
class AdminCheckTest(TestCase):

    def setUp(self):
        self.admin = create_admin()

        self.student = User.objects.create_user(
            username='student',
            password='123456'
        )
        self.student.role = 'student'
        self.student.save()

    def test_is_admin(self):
        self.assertTrue(is_admin(self.admin))
        self.assertFalse(is_admin(self.student))