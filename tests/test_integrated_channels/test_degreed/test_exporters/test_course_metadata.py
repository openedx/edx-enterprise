# -*- coding: utf-8 -*-
"""
Tests for Degreed course metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import json
import unittest

import ddt
import mock
import responses
from integrated_channels.degreed.exporters.course_metadata import DegreedCourseExporter
from pytest import mark

from enterprise.api_client.lms import parse_lms_api_datetime
from test_utils import factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestDegreedCourseExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``DegreedCourseExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            degreed_company_id='orgCode'
        )

        # Mocks
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=str(self.enterprise_customer.uuid),
            course_run_ids=['course-v1:edX+DemoX+Demo_Course_1']
        )
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestDegreedCourseExporter, self).setUp()

    @responses.activate
    def test_export(self):
        """
        If a course is unenrollable, it should be returned with a JSON dump and the ``DELETE`` method.
        """
        exporter = DegreedCourseExporter('fake-user', self.config)
        # Add a course marked for deletion by giving it just the single key; the course run ID.
        exporter.courses.append({'contentId': 'course-id-for-deletion'})
        data = exporter.export()
        json_dump_deleted, delete_method = (
            # JSON Dump to be DELETE'd
            json.dumps({
                'courses': [{'contentId': 'course-id-for-deletion'}],
                'orgCode': self.config.degreed_company_id,
                'providerCode': 'EDX',
            }, sort_keys=True).encode('utf-8'),
            'DELETE'
        )

        # Note: this course is already added to the data returned by the Enterprise API endpoint through
        # `self.mock_ent_courses_api_with_pagination` in setup code.
        json_dump_posted, post_method = (
            # JSON Dump to be POST'd
            json.dumps({
                'courses': [{
                    'authors': [],
                    'categoryTags': [],
                    'contentId': 'course-v1:edX+DemoX+Demo_Course_1',
                    'costType': 'Paid',
                    'description': 'edX Demonstration Course',
                    'difficulty': '',
                    'duration': 0,
                    'format': 'Instructor',
                    'imageUrl': '',
                    'institution': '',
                    'language': 'en',
                    'publishDate': '2013-02-05',
                    'title': 'edX Demonstration Course (Starts: February 2013)',
                    'url': 'http://lms.example.com/enterprise/' + str(self.enterprise_customer.uuid) +
                           '/course/course-v1:edX+DemoX+Demo_Course_1/enroll/',
                    'videoUrl': '',
                }],
                'orgCode': self.config.degreed_company_id,
                'providerCode': 'EDX',
            }, sort_keys=True).encode('utf-8'),
            'POST'
        )

        assert next(data) == (json_dump_deleted, delete_method)
        assert next(data) == (json_dump_posted, post_method)

    @responses.activate
    def test_transform_unenrollable_course(self):
        """
        If a course is unenrollable, transforming it gives back just its course run ID for transmission.
        """
        unenrollable_course_run = {
            'key': 'course-key',
            "enrollment_start": "2999-10-13T13:11:03Z"
        }
        exporter = DegreedCourseExporter('fake-user', self.config)
        assert exporter.transform(unenrollable_course_run) == {'contentId': 'course-key'}

    @responses.activate
    def test_transform_description_returns_full_description(self):
        """
        When we transform the description, we get back the full description if it has appropriate length.
        """
        course_run = {'full_description': 'a' * (DegreedCourseExporter.LONG_STRING_LIMIT - 1)}
        exporter = DegreedCourseExporter('fake-user', self.config)
        assert exporter.transform_description(course_run) == course_run['full_description']

    @responses.activate
    def test_transform_description_returns_empty_str(self):
        """
        Transforming the description gives back an empty string if the full description doesn't have appropriate length.
        """
        course_run = {'full_description': 'a' * (DegreedCourseExporter.LONG_STRING_LIMIT + 1)}
        exporter = DegreedCourseExporter('fake-user', self.config)
        assert exporter.transform_description(course_run) == ''

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'title': 'edX Demonstration Course'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'self_paced',
            'title': 'edX Demonstration Course'
        }
    )
    @responses.activate
    def test_transform_title_includes_start(self, course_run):
        """
        Transforming a title gives back the title with start date for course
        run of type `instructor-paced` or `self-paced`.
        """
        exporter = DegreedCourseExporter('fake-user', self.config)
        expected_title = '{course_run_title} (Starts: {start_date})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y')
        )
        assert exporter.transform_title(course_run) == expected_title
