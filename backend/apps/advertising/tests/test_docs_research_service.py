from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase

from apps.advertising.services.docs_research_service import fetch_official_documentation


class FetchOfficialDocumentationTests(SimpleTestCase):
    def test_rejects_non_google_domain_without_making_a_request(self):
        with patch('apps.advertising.services.docs_research_service.requests.get') as mock_get:
            result = fetch_official_documentation('https://example.com/malicious')
        mock_get.assert_not_called()
        self.assertIn('error', result)
        self.assertIn('example.com', result['error'])

    def test_rejects_lookalike_subdomain(self):
        result = fetch_official_documentation('https://developers.google.com.evil.com/page')
        self.assertIn('error', result)

    @patch('apps.advertising.services.docs_research_service.requests.get')
    def test_accepts_developers_google_com_and_strips_html(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            text='<html><head><style>.x{}</style></head><body><script>evil()</script>'
                 '<h1>Data Manager API</h1><p>Envie eventos via events:ingest.</p></body></html>',
        )
        result = fetch_official_documentation('https://developers.google.com/data-manager/api')
        self.assertNotIn('error', result)
        self.assertIn('Data Manager API', result['content'])
        self.assertIn('events:ingest', result['content'])
        self.assertNotIn('evil()', result['content'])

    @patch('apps.advertising.services.docs_research_service.requests.get')
    def test_accepts_support_google_com(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text='<p>Política de anúncios.</p>')
        result = fetch_official_documentation('https://support.google.com/adspolicy/answer/6008942')
        self.assertNotIn('error', result)

    @patch('apps.advertising.services.docs_research_service.requests.get')
    def test_non_200_status_returns_error(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404, text='')
        result = fetch_official_documentation('https://developers.google.com/nonexistent')
        self.assertIn('error', result)

    @patch('apps.advertising.services.docs_research_service.requests.get')
    def test_network_failure_returns_friendly_error_never_raises(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException('boom')
        result = fetch_official_documentation('https://developers.google.com/whatever')
        self.assertIn('error', result)

    @patch('apps.advertising.services.docs_research_service.requests.get')
    def test_content_is_truncated(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=f'<p>{"a" * 10000}</p>')
        result = fetch_official_documentation('https://developers.google.com/long-page')
        self.assertLessEqual(len(result['content']), 6000)
