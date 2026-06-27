from django.test import TestCase
from unittest.mock import Mock, patch
from scrapers.models import GrantSource, ScrapedGrant
from scrapers.scraper_scripts.opportunity_desk_scraper import OpportunityDeskScraper
from scrapers.scraper_scripts.grab_scholarship_scraper import GrabScholarshipScraper


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
        self.assertEqual(grants[0]['deadline'], 'August 12, 2026')
        self.assertEqual(grants[0]['category'], 'Fellowships')

        # Assert correct database creation
        scraper.run()
        self.assertEqual(ScrapedGrant.objects.count(), 1)
        scraped_obj = ScrapedGrant.objects.first()
        self.assertEqual(scraped_obj.raw_title, 'Test Scholarship 2026')
        self.assertEqual(scraped_obj.status, 'pending')

    def test_approve_grants_action(self):
        from django.contrib.auth import get_user_model
        from scrapers.admin import approve_grants
        from grants.models import GrantOpportunity
        from unittest.mock import Mock

        User = get_user_model()
        user = User.objects.create_user(username='testadmin', password='password123', is_staff=True)

        source = GrantSource.objects.create(name='Test Source', url='https://test.com')
        scraped = ScrapedGrant.objects.create(
            source=source,
            raw_title="Awesome Fellowship",
            parsed_data={
                "url": "https://test.com/awesome-fellowship",
                "description": "This is an awesome fellowship opportunity.",
                "deadline": "August 12, 2026",
                "organization": "Test Org"
            }
        )

        mock_request = Mock()
        mock_request.user = user

        mock_modeladmin = Mock()

        # Call the action
        approve_grants(mock_modeladmin, mock_request, ScrapedGrant.objects.all())

        # Assert ScrapedGrant status is updated to approved
        scraped.refresh_from_db()
        self.assertEqual(scraped.status, 'approved')
        self.assertEqual(scraped.reviewed_by, user)

        # Assert GrantOpportunity is created
        self.assertEqual(GrantOpportunity.objects.count(), 1)
        grant = GrantOpportunity.objects.first()
        self.assertEqual(grant.title, "Awesome Fellowship")
        self.assertEqual(grant.source_url, "https://test.com/awesome-fellowship")
        self.assertEqual(grant.status, 'draft')
        self.assertEqual(grant.added_by, user)

    @patch('requests.get')
    def test_grab_scholarship_scraper(self, mock_get):
        # Mock HTML structure representing an article post of Grab Scholarship
        mock_html = """
        <html>
            <body>
                <article class="elementor-post">
                    <h3 class="elementor-post__title">
                        <a href="https://grabscholarship.com/test-ar/">منحة دراسية تجريبية 2026</a>
                    </h3>
                    <div class="elementor-post__badge">بكالوريوس</div>
                    <div class="elementor-post-date">26 يونيو، 2026</div>
                </article>
                <article class="elementor-post">
                    <h3 class="elementor-post__title">
                        <a href="https://grabscholarship.com/test-job/">فرصة عمل تجريبية 2026</a>
                    </h3>
                    <div class="elementor-post__badge">عمل</div>
                </article>
            </body>
        </html>
        """
        detail_html = """
        <html>
            <body>
                <p>آخر موعد للتقديم: 1 نوفمبر 2026.</p>
            </body>
        </html>
        """

        def mock_response(html):
            response = Mock()
            response.status_code = 200
            response.text = html
            response.raise_for_status.return_value = None
            return response

        mock_get.side_effect = [
            mock_response(mock_html),
            mock_response(detail_html),
            mock_response(mock_html),
            mock_response(detail_html),
        ]

        scraper = GrabScholarshipScraper()
        grants = scraper.scrape()

        # Assert correct parser extraction
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]['title'], 'منحة دراسية تجريبية 2026')
        self.assertEqual(grants[0]['url'], 'https://grabscholarship.com/test-ar/')
        self.assertEqual(grants[0]['category'], 'بكالوريوس')
        self.assertEqual(grants[0]['deadline'], '2026-11-01')

        # Assert correct database creation
        scraper.run()
        self.assertEqual(ScrapedGrant.objects.count(), 1)
        scraped_obj = ScrapedGrant.objects.first()
        self.assertEqual(scraped_obj.raw_title, 'منحة دراسية تجريبية 2026')
        self.assertEqual(scraped_obj.status, 'pending')
        self.assertEqual(scraped_obj.parsed_data['deadline'], '2026-11-01')


