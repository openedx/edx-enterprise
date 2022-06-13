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


# pylint: disable=dangerous-default-value
def build_fake_enterprise_catalog_detail(enterprise_catalog_uuid=FAKE_UUIDS[1], title='All Content',
                                         enterprise_customer_uuid=FAKE_UUIDS[0], previous_url=None, next_url=None,
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
