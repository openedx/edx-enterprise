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
