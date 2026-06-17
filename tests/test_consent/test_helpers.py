"""
Tests for helper functions in the Consent application.
"""

from unittest import mock
from urllib.parse import parse_qs, urlparse

import ddt
from pytest import mark

from django.contrib.sites.models import Site
from django.test import override_settings, testcases

from consent import helpers
from test_utils import TEST_UUID
from test_utils.factories import UserFactory


def _mock_active_enterprise_learner_details(
        enterprise_customer_uuid=TEST_UUID,
        enable_data_sharing_consent=True,
        slug='test-slug',
        site_domain='example.com',
):
    """Return a mock mirroring the shape returned by get_active_enterprise_customer_user."""
    mock_ecu = mock.MagicMock()
    mock_ecu.enterprise_customer.uuid = enterprise_customer_uuid
    mock_ecu.enterprise_customer.slug = slug
    mock_ecu.enterprise_customer.enable_data_sharing_consent = enable_data_sharing_consent
    mock_ecu.enterprise_customer.site.domain = site_domain
    return mock_ecu


@mark.django_db
@ddt.ddt
class ConsentHelpersTest(testcases.TestCase):
    """
    Test cases for helper functions for the Consent application.
    """
    def setUp(self):
        self.fake_course_id = 'fake-course'
        super().setUp()

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_data_sharing_consent_no_enterprise(self, mock_catalog_api_class):
        """
        Test that the returned consent record is None when no EnterpriseCustomer exists.
        """
        mock_catalog_api_class = mock_catalog_api_class.return_value
        mock_catalog_api_class.get_course_id.return_value = self.fake_course_id
        assert helpers.get_data_sharing_consent('bob', TEST_UUID, course_id=self.fake_course_id) is None


@mark.django_db
@override_settings(ENABLE_ENTERPRISE_INTEGRATION=True, DATA_CONSENT_SHARE_CACHE_TIMEOUT=60)
class ConsentNeededForCourseTest(testcases.TestCase):
    """Tests for ``consent.helpers.consent_needed_for_course``."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory(username='janedoe')
        self.course_id = 'fake-course'
        self.site = Site.objects.get_or_create(domain='example.com', defaults={'name': 'example.com'})[0]
        self.request = mock.MagicMock(user=self.user, site=self.site)

    def _patch_platform_deps(self, **overrides):
        """Patch the lazy-imported platform symbols on consent.helpers with sensible defaults."""
        defaults = {
            'ConsentApiClient': mock.MagicMock(),
            'enterprise_customer_uuid_for_request': mock.MagicMock(return_value=TEST_UUID),
            'get_data_consent_share_cache_key': mock.MagicMock(return_value='cache-key'),
        }
        defaults.update(overrides)
        return mock.patch.multiple('consent.helpers', **defaults)

    @mock.patch('consent.helpers.get_active_enterprise_customer_user', return_value=None)
    def test_returns_false_when_user_has_no_active_enterprise(self, _mock_active):
        with self._patch_platform_deps():
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False

    @mock.patch('consent.helpers.TieredCache')
    @mock.patch('consent.helpers.get_active_enterprise_customer_user')
    def test_returns_false_when_dsc_cache_indicates_not_needed(self, mock_active, mock_cache):
        mock_active.return_value = _mock_active_enterprise_learner_details()
        cached = mock.MagicMock(is_found=True, value=0)
        mock_cache.get_cached_response.return_value = cached
        with self._patch_platform_deps():
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False

    @mock.patch('consent.helpers.TieredCache')
    @mock.patch('consent.helpers.get_active_enterprise_customer_user')
    def test_returns_false_when_dsc_disabled_for_customer(self, mock_active, mock_cache):
        mock_active.return_value = _mock_active_enterprise_learner_details(enable_data_sharing_consent=False)
        mock_cache.get_cached_response.return_value = mock.MagicMock(is_found=False)
        with self._patch_platform_deps():
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False
        mock_cache.set_all_tiers.assert_called_once()

    @mock.patch('consent.helpers.TieredCache')
    @mock.patch('consent.helpers.get_active_enterprise_customer_user')
    def test_returns_false_when_request_enterprise_does_not_match_learner(self, mock_active, mock_cache):
        mock_active.return_value = _mock_active_enterprise_learner_details(enterprise_customer_uuid=TEST_UUID)
        mock_cache.get_cached_response.return_value = mock.MagicMock(is_found=False)
        with self._patch_platform_deps(
            enterprise_customer_uuid_for_request=mock.MagicMock(return_value='other-uuid'),
        ):
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False

    @mock.patch('consent.helpers.TieredCache')
    @mock.patch('consent.helpers.get_active_enterprise_customer_user')
    def test_returns_false_when_site_does_not_match_learner(self, mock_active, mock_cache):
        Site.objects.get_or_create(domain='other.example.com', defaults={'name': 'other'})
        mock_active.return_value = _mock_active_enterprise_learner_details(site_domain='other.example.com')
        mock_cache.get_cached_response.return_value = mock.MagicMock(is_found=False)
        with self._patch_platform_deps():
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False

    @mock.patch('consent.helpers.TieredCache')
    @mock.patch('consent.helpers.get_active_enterprise_customer_user')
    def test_returns_false_when_consent_api_says_no_consent_required(self, mock_active, mock_cache):
        mock_active.return_value = _mock_active_enterprise_learner_details()
        mock_cache.get_cached_response.return_value = mock.MagicMock(is_found=False)
        consent_client = mock.MagicMock()
        consent_client.return_value.consent_required.return_value = False
        with self._patch_platform_deps(ConsentApiClient=consent_client):
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False

    @mock.patch('consent.helpers.TieredCache')
    @mock.patch('consent.helpers.get_active_enterprise_customer_user')
    def test_returns_true_when_consent_api_says_consent_required(self, mock_active, mock_cache):
        mock_active.return_value = _mock_active_enterprise_learner_details()
        mock_cache.get_cached_response.return_value = mock.MagicMock(is_found=False)
        consent_client = mock.MagicMock()
        consent_client.return_value.consent_required.return_value = True
        with self._patch_platform_deps(ConsentApiClient=consent_client):
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is True

    @override_settings(ENABLE_ENTERPRISE_INTEGRATION=False)
    def test_returns_false_when_integration_disabled(self):
        assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False

    def test_returns_false_when_platform_imports_unavailable(self):
        with mock.patch.multiple(
            'consent.helpers',
            ConsentApiClient=None,
            enterprise_customer_uuid_for_request=None,
            get_data_consent_share_cache_key=None,
        ):
            assert helpers.consent_needed_for_course(self.request, self.user, self.course_id) is False


@mark.django_db
@override_settings(ENABLE_ENTERPRISE_INTEGRATION=True, DATA_CONSENT_SHARE_CACHE_TIMEOUT=60)
@mock.patch('consent.helpers.reverse', side_effect=lambda name, *args, **kwargs: f'/reversed/{name}/')
@mock.patch('consent.helpers.enterprise_customer_uuid_for_request', return_value=TEST_UUID)
class GetEnterpriseConsentUrlTest(testcases.TestCase):
    """Tests for ``consent.helpers.get_enterprise_consent_url``."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory(username='janedoe')
        self.course_id = 'course-v1:edX+DemoX+T1'
        self.site = Site.objects.get_or_create(domain='example.com', defaults={'name': 'example.com'})[0]
        self.request = mock.MagicMock(
            user=self.user,
            site=self.site,
            path='/courses/course-v1:edX+DemoX+T1/courseware',
        )
        self.request.build_absolute_uri = lambda path: f'http://example.com{path}'

    def _parse_consent_url(self, url):
        """Parse a consent URL into (path, query_params_dict)."""
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        return parsed.path, params

    @mock.patch('consent.helpers.consent_needed_for_course', return_value=False)
    def test_returns_none_when_consent_not_needed(self, _mock_consent, _mock_uuid_fn, _mock_reverse):
        """Returns None when consent_needed_for_course says no."""
        result = helpers.get_enterprise_consent_url(self.request, self.course_id)
        assert result is None

    @mock.patch('consent.helpers.consent_needed_for_course', return_value=True)
    def test_returns_url_using_request_path_when_return_to_is_none(self, _mock_consent, _mock_uuid_fn, _mock_reverse):
        """Uses request.path as the return path when return_to is not specified."""
        result = helpers.get_enterprise_consent_url(self.request, self.course_id)
        path, params = self._parse_consent_url(result)
        assert path == '/reversed/grant_data_sharing_permissions/'
        assert params['next'] == 'http://example.com/courses/course-v1:edX+DemoX+T1/courseware'

    @mock.patch('consent.helpers.consent_needed_for_course', return_value=True)
    def test_returns_url_using_reverse_when_return_to_specified(self, _mock_consent, _mock_uuid_fn, _mock_reverse):
        """Uses reverse(return_to, args=(course_id,)) when return_to is given."""
        result = helpers.get_enterprise_consent_url(
            self.request, self.course_id, return_to='course_root',
        )
        path, params = self._parse_consent_url(result)
        assert path == '/reversed/grant_data_sharing_permissions/'
        assert params['next'] == 'http://example.com/reversed/course_root/'

    @mock.patch('consent.helpers.consent_needed_for_course', return_value=True)
    def test_uses_explicit_user_when_provided(self, mock_consent, _mock_uuid_fn, _mock_reverse):
        """Passes the explicit user arg to consent_needed_for_course."""
        other_user = UserFactory(username='other_user')
        result = helpers.get_enterprise_consent_url(self.request, self.course_id, user=other_user)
        path, _ = self._parse_consent_url(result)
        assert path == '/reversed/grant_data_sharing_permissions/'
        mock_consent.assert_called_once_with(
            self.request, other_user, self.course_id, enrollment_exists=False,
        )

    @mock.patch('consent.helpers.CONSENT_FAILED_PARAMETER', 'consent_failed')
    @mock.patch('consent.helpers.consent_needed_for_course', return_value=True)
    def test_includes_failure_url_with_consent_failed_param(self, _mock_consent, _mock_uuid_fn, _mock_reverse):
        """The returned URL includes a failure_url pointing to the dashboard."""
        result = helpers.get_enterprise_consent_url(self.request, self.course_id)
        path, params = self._parse_consent_url(result)
        assert path == '/reversed/grant_data_sharing_permissions/'
        assert params['failure_url'] == (
            'http://example.com/reversed/dashboard/?consent_failed=course-v1%3AedX%2BDemoX%2BT1'
        )
