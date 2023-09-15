"""
Mock Enterprise API for testing.
"""

from hashlib import md5
from urllib.parse import urlencode, urljoin

import responses
from faker import Factory as FakerFactory
from rest_framework.reverse import reverse

from django.conf import settings
from django.core.cache import cache

from enterprise.constants import DefaultColors
from test_utils import FAKE_UUIDS, fake_catalog_api, update_search_with_enterprise_context


class EnterpriseMockMixin:
    """
    Mocks for the Enterprise service response.
    """

    def setUp(self):
        """
        DRY method for EnterpriseMockMixin.
        """
        super().setUp()
        cache.clear()

    def build_enterprise_api_url(self, resource, *args, **kwargs):
        """
        DRY method to make Enterprise API URLs.

        Example URL: 'enterprise/api/v1/enterprise-customer/{enterprise_uuid}/courses'
        """
        return '{lms_root_url}{enterprise_api_uri}{params}'.format(
            lms_root_url=settings.LMS_INTERNAL_ROOT_URL,
            enterprise_api_uri=reverse(resource, args=args),
            params=('?' + urlencode(kwargs)) if kwargs else '',
        )

    def build_fake_enterprise_course_detail(self, enterprise_uuid, course_run_key):
        """
        DRY method to create course detail json.
        """
        course_detail = {
            'uuid': FakerFactory.create().uuid4(),  # pylint: disable=no-member
            'key': str(course_run_key),
            'aggregation_key': 'courserun:{org}+{course}'.format(
                org=course_run_key.org, course=course_run_key.course
            ),
            'title': 'edX Demonstration Course',
            'short_description': None,
            'full_description': None,
            'start': '2013-02-05T05:00:00Z',
            'end': None,
            'enrollment_start': None,
            'enrollment_end': None,
            'image': None,
            'video': None,
            'min_effort': 5,
            'max_effort': 3,
            'course': '{org}+{course}'.format(org=course_run_key.org, course=course_run_key.course),
            'seats': [
                {
                    'sku': self.generate_dummy_sku(course_run_key),
                    'credit_hours': None,
                    'price': '100.00',
                    'currency': 'USD',
                    'upgrade_deadline': None,
                    'credit_provider': None,
                    'type': 'verified'
                }
            ],
            'enrollment_url': urljoin(
                settings.LMS_ROOT_URL,
                reverse(
                    'enterprise_course_run_enrollment_page',
                    args=[enterprise_uuid, str(course_run_key)],
                )
            ),
            'content_language': None,
            'eligible_for_financial_aid': True,
            'availability': 'Upcoming',
            'transcript_languages': [],
            'staff': [],
            'announcement': None,
            'track_selection_url': None,
            'hidden': False,
            'level_type': None,
            'type': 'verified',
            'marketing_url': None,
            'status': 'published',
            'instructors': [],
            'reporting_type': 'mooc',
            'mobile_available': False,
            'pacing_type': 'instructor_paced',
            'content_type': 'courserun',
        }
        return course_detail

    def generate_dummy_sku(self, course_run_key):
        """
        DRY method to generate dummy course product SKU.
        """
        md5_hash = md5(str(course_run_key).encode('utf-8'))
        digest = md5_hash.hexdigest()[-7:]
        sku = digest.upper()
        return sku

    def mock_enterprise_customer_catalogs(self, enterprise_catalog_uuid):
        """
        DRY function to register enterprise customer catalog API.
        """
        responses.add(
            responses.GET,
            url=self.build_enterprise_api_url('enterprise-catalogs-detail', enterprise_catalog_uuid),
            json=build_fake_enterprise_catalog_detail(
                enterprise_catalog_uuid=enterprise_catalog_uuid,
                include_enterprise_context=True,
            ),
            status=200,
            content_type='application/json',
        )

    def mock_enterprise_catalogs_with_error(self, enterprise_uuid):
        """
        DRY function to register enterprise catalogs API to return error response.
        """
        responses.add(
            responses.GET,
            url=self.build_enterprise_api_url('enterprise-catalogs-detail', enterprise_uuid),
            json={},
            status=500,
            content_type='application/json',
        )

    def mock_empty_response(self, resource, *args, **kwargs):
        """
        DRY function to register an empty response from some Enterprise API endpoint.
        """
        responses.add(
            responses.GET,
            url=self.build_enterprise_api_url(resource, *args, **kwargs),
            json={},
            status=200,
            content_type='application/json',
        )


# pylint: disable=dangerous-default-value
def build_fake_enterprise_catalog_detail(enterprise_catalog_uuid=FAKE_UUIDS[1], title='All Content',
                                         enterprise_customer_uuid=FAKE_UUIDS[0], enterprise_catalog_query=1,
                                         previous_url=None, next_url=None,
                                         paginated_content=fake_catalog_api.FAKE_SEARCH_ALL_RESULTS,
                                         include_enterprise_context=False, add_utm_info=True,
                                         count=None):
    """
    Return fake EnterpriseCustomerCatalog detail API result.
    """
    if include_enterprise_context:
        paginated_content = update_search_with_enterprise_context(paginated_content, add_utm_info)

    return {
        'count': count,
        'previous': previous_url,
        'next': next_url,
        'uuid': enterprise_catalog_uuid,
        'title': title,
        'enterprise_customer': enterprise_customer_uuid,
        'results': paginated_content['results'],
        'enterprise_catalog_query': enterprise_catalog_query,
    }


def get_default_branding_object(customer_uuid, customer_slug):
    """
    Return a fake EnterpriseCustomerBrandingConfiguration object
    """
    return {
        'enterprise_customer': customer_uuid,
        'enterprise_slug': customer_slug,
        'logo': 'http://fake.url',
        'primary_color': DefaultColors.PRIMARY,
        'secondary_color': DefaultColors.SECONDARY,
        'tertiary_color': DefaultColors.TERTIARY,
    }
