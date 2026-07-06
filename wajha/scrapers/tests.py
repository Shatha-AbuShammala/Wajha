from django.test import TestCase
from unittest.mock import Mock, patch
from scrapers.models import GrantSource, ScrapedGrant
from scrapers.scraper_scripts.opportunity_desk_scraper import OpportunityDeskScraper



class ScraperTestCase(TestCase):
    def setUp(self):
        # Clear state
        ScrapedGrant.objects.all().delete()
        GrantSource.objects.all().delete()

    @patch('requests.get')
    def test_opportunity_desk_scraper(self, mock_get):
        # Mock HTML structure representing an article post
        mock_html = """
        <html>
            <body>
                <article>
                    <h2 class="entry-title"><a href="https://opportunitydesk.org/test-scholarship/">Test Scholarship 2026</a></h2>
                    <div class="entry-summary">
                        <p>This is a description of the test scholarship. Deadline: August 12, 2026.</p>
                    </div>
                    <time datetime="2026-06-25T12:00:00Z"></time>
                    <span class="cat-links"><a href="#">Fellowships</a></span>
                </article>
            </body>
        </html>
        """
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = mock_html

        scraper = OpportunityDeskScraper()
        grants = scraper.scrape()

        # Assert correct parser extraction
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]['title'], 'Test Scholarship 2026')
        self.assertEqual(grants[0]['url'], 'https://opportunitydesk.org/test-scholarship/')
        # Scraper converts deadline strings to ISO format (YYYY-MM-DD)
        self.assertEqual(grants[0]['deadline'], '2026-08-12')
        self.assertEqual(grants[0]['category'], 'Fellowships')

        # Assert correct database creation
        scraper.run()
        self.assertEqual(ScrapedGrant.objects.count(), 1)
        scraped_obj = ScrapedGrant.objects.first()
        self.assertEqual(scraped_obj.raw_title, 'Test Scholarship 2026')
        self.assertEqual(scraped_obj.status, 'pending')

    def test_approve_grants_action(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from grants.models import GrantOpportunity, GrantFieldOfStudy, GrantCountry

        User = get_user_model()
        user = User.objects.create_user(username='testadmin', password='password123', is_staff=True, role='admin')
        self.client.force_login(user)

        source = GrantSource.objects.create(name='Test Source', url='https://test.com')
        scraped = ScrapedGrant.objects.create(
            source=source,
            raw_title="Awesome Engineering Fellowship",
            parsed_data={
                "url": "https://test.com/awesome-fellowship",
                "description": "This is an awesome fellowship opportunity for engineering students.",
                "deadline": "August 12, 2026",
                "organization": "Test Org",
                "fields_of_study": ["Engineering", "Science & STEM"],
                "countries": ["Germany", "France"],
                "eligibility_text": "Eligible candidates must be enrolled in an engineering program.",
            }
        )

        # Call the draft approve view using a POST request
        response = self.client.post(reverse('scrapers:draft', kwargs={'pk': scraped.pk}))

        # Assert redirection/success status code (302 redirect)
        self.assertEqual(response.status_code, 302)

        # Assert ScrapedGrant status is updated to approved
        scraped.refresh_from_db()
        self.assertEqual(scraped.status, 'approved')

        # Assert GrantOpportunity is created with scraped eligibility text
        self.assertEqual(GrantOpportunity.objects.count(), 1)
        grant = GrantOpportunity.objects.first()
        self.assertEqual(grant.title, "Awesome Engineering Fellowship")
        self.assertEqual(grant.source_url, "https://test.com/awesome-fellowship")
        self.assertEqual(grant.status, 'draft')
        self.assertEqual(grant.added_by_id, user.pk)
        self.assertIn('Eligible candidates', grant.eligibility_text)

        # Assert GrantFieldOfStudy records are created
        self.assertEqual(GrantFieldOfStudy.objects.filter(grant=grant).count(), 2)
        field_names = list(GrantFieldOfStudy.objects.filter(grant=grant).values_list('field_name', flat=True))
        self.assertIn('Engineering', field_names)
        self.assertIn('Science & STEM', field_names)

        # Assert multiple GrantCountry records are created
        self.assertEqual(GrantCountry.objects.filter(grant=grant).count(), 2)
        country_names = list(GrantCountry.objects.filter(grant=grant).values_list('country_name', flat=True))
        self.assertIn('Germany', country_names)
        self.assertIn('France', country_names)




