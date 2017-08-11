# -*- coding: utf-8 -*-
"""
Mock Enterprise API for testing.
"""
from __future__ import absolute_import, unicode_literals

from hashlib import md5

import responses
from faker import Factory as FakerFactory
from opaque_keys.edx.keys import CourseKey
from rest_framework.reverse import reverse

from django.conf import settings
from django.core.cache import cache

from six.moves.urllib.parse import urljoin  # pylint: disable=import-error,ungrouped-imports


class EnterpriseMockMixin(object):
    """
    Mocks for the Enterprise service response.
    """

    def setUp(self):
        """
        DRY method for EnterpriseMockMixin.
        """
        super(EnterpriseMockMixin, self).setUp()
        cache.clear()

    def build_enterprise_customer_courses_url(self, enterprise_uuid, limit=None, offset=None):
        """
        DRY method to make enterprise customer courses url.

        Example URL: 'enterprise/api/v1/enterprise-customer/{enterprise_uuid}/courses'
        """
        if limit and offset:
            enterprise_customer_courses_url = '{lms_root_url}{enterprise_api_uri}?limit={limit}&offset={offset}'.format(
                lms_root_url=settings.LMS_ROOT_URL,
                enterprise_api_uri=reverse('enterprise-customer-courses', args=[enterprise_uuid]),
                limit=limit,
                offset=offset,
            )
        else:
            enterprise_customer_courses_url = settings.LMS_ROOT_URL + reverse(
                'enterprise-customer-courses', args=[enterprise_uuid]
            )

        return enterprise_customer_courses_url

    def build_fake_enterprise_course_detail(self, enterprise_uuid, course_run_key):
        """
        DRY method to create course detail json.
        """
        course_detail = {
            'uuid': FakerFactory.create().uuid4(),  # pylint: disable=no-member
            'key': course_run_key.to_deprecated_string(),
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
                    'enterprise_course_enrollment_page',
                    args=[enterprise_uuid, course_run_key.to_deprecated_string()],
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
        }
        return course_detail

    def generate_dummy_sku(self, course_run_key):
        """
        DRY method to generate dummy course product SKU.
        """
        md5_hash = md5(course_run_key.to_deprecated_string().encode('utf-8'))
        digest = md5_hash.hexdigest()[-7:]
        sku = digest.upper()
        return sku

    def mock_ent_courses_api_with_pagination(self, enterprise_uuid, course_run_ids):
        """
        DRY function to register enterprise courses API with pagination.
        """
        for course_index, course_run_id in enumerate(course_run_ids):
            offset = course_index + 1
            course_run_key = CourseKey.from_string(course_run_id)
            mocked_course_data = {
                'enterprise_id': enterprise_uuid,
                'catalog_id': 1,
                'uuid': FakerFactory.create().uuid4(),  # pylint: disable=no-member
                'tpa_hint': 'testshib',
                'key': '{org}+{course}'.format(org=course_run_key.org, course=course_run_key.course),
                'title': 'edX Demonstration Course',
                'short_description': None,
                'full_description': None,
                'image': None,
                'video': None,
                'marketing_url': None,
                'subjects': [],
                'prerequisites': [],
                'expected_learning_items': [],
                'sponsors': [],
                'level_type': None,
                'owners': [
                    {
                        'uuid': FakerFactory.create().uuid4(),  # pylint: disable=no-member
                        'description': None,
                        'tags': [],
                        'name': '',
                        'homepage_url': None,
                        'key': 'edX',
                        'certificate_logo_image_url': None,
                        'marketing_url': None,
                        'logo_image_url': None,
                    }
                ],
                'course_runs': [
                    self.build_fake_enterprise_course_detail(enterprise_uuid, course_run_key)
                ],
            }

            next_page_url = None
            if offset < len(course_run_ids):
                # Not a last page so there will be more courses for another page
                next_page_url = self.build_enterprise_customer_courses_url(
                    enterprise_uuid, limit=1, offset=offset
                )

            previous_page_url = None
            if course_index != 0:
                # Not a first page so there will always be courses on previous page
                previous_page_url = self.build_enterprise_customer_courses_url(
                    enterprise_uuid, limit=1, offset=course_index
                )

            paginated_api_response = {
                'count': len(course_run_ids),
                'next': next_page_url,
                'previous': previous_page_url,
                'results': [mocked_course_data]
            }
            responses.add(
                responses.GET,
                url=self.build_enterprise_customer_courses_url(enterprise_uuid),
                json=paginated_api_response,
                status=200,
                content_type='application/json',
            )
