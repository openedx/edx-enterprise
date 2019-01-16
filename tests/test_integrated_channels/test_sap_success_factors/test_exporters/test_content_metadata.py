# -*- coding: utf-8 -*-
"""
Tests for SAPSF content metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
import responses
from pytest import mark

from enterprise.api_client.lms import parse_lms_api_datetime
from integrated_channels.sap_success_factors.exporters.content_metadata import SapSuccessFactorsContentMetadataExporter
from test_utils import factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestSapSuccessFactorsContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``SapSuccessFactorsContentMetadataExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

        # Mocks
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=str(self.enterprise_customer.uuid),
            course_run_ids=['course-v1:edX+DemoX+Demo_Course_1']
        )
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestSapSuccessFactorsContentMetadataExporter, self).setUp()

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'self_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        }
    )
    @responses.activate
    def test_transform_courserun_title_includes_start(self, course_run):
        """
        Transforming a title gives back the title with start date for course
        run of type `instructor-paced` or `self-paced`.
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        expected_title = '{course_run_title} (Starts: {start_date})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y')
        )
        assert exporter.transform_courserun_title(course_run) == \
            [{
                'locale': 'English',
                'value': expected_title
            }]

    @responses.activate
    def test_transform_courserun_title_excludes_start(self):
        """
        Transforming a title gives back just the title if there is not start date.
        """
        course_run = {
            'start': None,
            'pacing_type': 'self_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'en'
        }
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_courserun_title(course_run) == \
            [{
                'locale': 'English',
                'value': course_run['title']
            }]

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': None,
            'pacing_type': 'instructor_paced',
            'availability': 'Archived',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': None,
            'availability': 'Archived',
            'pacing_type': 'self_paced',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': '2012-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': '2014-02-05T05:00:00Z',
            'enrollment_end': '2015-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': 'Upcoming',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
    )
    @responses.activate
    def test_transform_courserun_title_includes_enrollment_closed(self, course_run):
        """
        Transforming a title gives back the title with start date and
        `enrollment closed` message for course run with availability set to
        `Archived`.
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        expected_title = '{course_run_title} ({start_date} - {enrollment_closed})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y'),
            enrollment_closed='Enrollment Closed'
        )
        assert exporter.transform_courserun_title(course_run) == \
            [{
                'locale': 'English',
                'value': expected_title
            }]

    @ddt.data(
        (
            {
                'aggregation_key': 'course:edX+DemoX',
                'title': 'edX Demonstration Course',
                'key': 'edX+DemoX',
                'content_type': 'course',
                'card_image_url': 'https://edx.devstack.lms:18000/'
                                  'asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
            },
            'https://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg'
        ),
        (
            {
                'number': 'DemoX',
                'org': 'edX',
                'seat_types': ['verified', 'audit'],
                'key': 'course-v1:edX+DemoX+Demo_Course',
                'availability': 'Current',
                'title': 'edX Demonstration Course',
                'content_type': 'courserun',
                'image_url': 'https://edx.devstack.lms:18000/'
                             'asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
            },
            'https://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg'
        ),
        (
            {

                'uuid': '5742ec8d-25ce-43b7-a158-6dad82034ca2',
                'title': 'edX Demonstration program',
                'published': True,
                'language': [],
                'type': 'Verified Certificate',
                'status': 'active',
                'content_type': 'program',
                'card_image_url': 'https://edx.devstack.discovery/'
                                  'media/programs/banner_images/5742ec8d-25ce-43b7-a158-6dad82034ca2.jpg',
            },
            'https://edx.devstack.discovery/media/programs/banner_images/5742ec8d-25ce-43b7-a158-6dad82034ca2.jpg',
        ),
        (
            {
                'title': 'INVALID COURSE',
                'content_type': 'INVALID-CONTENT_TYPE',
            },
            '',
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_image(self, content_metadata_item, expected_thumbnail_url):
        """
        Transforming a image gives back the thumbnail URI by checking the
        content type of the provided `content_metadata_item`.
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_image(content_metadata_item) == expected_thumbnail_url

    @responses.activate
    def test_transform_launch_points(self):
        """
        Transforming launch points generates list containing a dict that we expect
        """
        content_metadata_item = {
            'enrollment_url': 'http://some/enrollment/url/',
            'aggregation_key': 'course:edX+DemoX',
            'title': 'edX Demonstration Course',
            'key': 'edX+DemoX',
            'content_type': 'course',
            'card_image_url': 'https://edx.devstack.lms:18000/'
                              'asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
            'short_description': 'Some short description.',
            'full_description': 'Detailed description of edx demo course.',
        }
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        launch_points = exporter.transform_launch_points(content_metadata_item)

        assert launch_points[0]['providerID'] == 'EDX'
        assert launch_points[0]['launchURL'] == content_metadata_item['enrollment_url']
        assert launch_points[0]['contentTitle'] == content_metadata_item['title']
        assert launch_points[0]['contentID'] == 'edX+DemoX'
        assert launch_points[0]['launchType'] == 3
        assert launch_points[0]['mobileEnabled'] is True
        assert launch_points[0]['mobileLaunchURL'] == content_metadata_item['enrollment_url']
