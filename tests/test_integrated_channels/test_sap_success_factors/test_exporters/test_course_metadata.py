# -*- coding: utf-8 -*-
"""
Tests for SAPSF course metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
import responses
from integrated_channels.integrated_channel.exporters.course_metadata import CourseExporter
from integrated_channels.sap_success_factors.exporters.course_metadata import SapSuccessFactorsCourseExporter
from pytest import mark, raises

from enterprise.api_client.lms import parse_lms_api_datetime
from test_utils import factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestSapSuccessFactorsCourseExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``SapSuccessFactorsCourseExporter`` class.
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
        super(TestSapSuccessFactorsCourseExporter, self).setUp()

    @ddt.data(
        ('cy', 'Welsh'),
        ('en-us', 'English'),
        ('zh-hk', 'Chinese Hong Kong'),
        ('ru-faaaaaake', 'Russian'),
        ('not-real', 'English')
    )
    @ddt.unpack
    @responses.activate
    def test_transform_language_code_valid(self, code, expected):
        """
        Transforming the language code returns the appropriate full-length language name.
        """
        exporter = SapSuccessFactorsCourseExporter('fake-user', self.config)
        assert exporter.transform_language_code(code) == expected

    @responses.activate
    def test_unparsable_language_code(self):
        """
        An error is raised if the language code is unparsable.
        """
        exporter = SapSuccessFactorsCourseExporter('fake-user', self.config)
        with raises(ValueError) as exc_info:
            exporter.transform_language_code('this-is-incomprehensible')
        assert str(exc_info.value) == (
            'Language codes may only have up to two components. Could not parse: this-is-incomprehensible'
        )

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': CourseExporter.AVAILABILITY_CURRENT,
            'title': 'edX Demonstration Course'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'self_paced',
            'availability': CourseExporter.AVAILABILITY_CURRENT,
            'title': 'edX Demonstration Course'
        }
    )
    @responses.activate
    def test_transform_title_includes_start(self, course_run):
        """
        Transforming a title gives back the title with start date for course
        run of type `instructor-paced` or `self-paced`.
        """
        exporter = SapSuccessFactorsCourseExporter('fake-user', self.config)
        expected_title = '{course_run_title} (Starts: {start_date})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y')
        )
        assert exporter.transform_title(course_run) == \
            [{
                'locale': 'English',
                'value': expected_title
            }]

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': None,
            'pacing_type': 'instructor_paced',
            'availability': CourseExporter.AVAILABILITY_ARCHIVED,
            'title': 'edX Demonstration Course'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': None,
            'availability': CourseExporter.AVAILABILITY_ARCHIVED,
            'pacing_type': 'self_paced',
            'title': 'edX Demonstration Course'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': '2012-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': CourseExporter.AVAILABILITY_CURRENT,
            'title': 'edX Demonstration Course'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': '2014-02-05T05:00:00Z',
            'enrollment_end': '2015-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': CourseExporter.AVAILABILITY_UPCOMING,
            'title': 'edX Demonstration Course'
        },
    )
    @responses.activate
    def test_transform_title_includes_enrollment_closed(self, course_run):
        """
        Transforming a title gives back the title with start date and
        `enrollment closed` message for course run with availability set to
        `Archived`.
        """
        exporter = SapSuccessFactorsCourseExporter('fake-user', self.config)
        expected_title = '{course_run_title} ({start_date} - {enrollment_closed})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y'),
            enrollment_closed='Enrollment Closed'
        )
        assert exporter.transform_title(course_run) == \
            [{
                'locale': 'English',
                'value': expected_title
            }]
