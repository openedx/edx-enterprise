# -*- coding: utf-8 -*-
"""
Tests for SAPSF course metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
import responses
from integrated_channels.sap_success_factors.exporters.course_metadata import SapSuccessFactorsCourseExporter
from pytest import mark, raises

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

    @responses.activate
    def test_transform_title_includes_start(self):
        """
        Transforming a title gives back the title and start date if the course is instructor-paced.
        """
        course_run = {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'title': 'edX Demonstration Course'
        }
        exporter = SapSuccessFactorsCourseExporter('fake-user', self.config)
        assert exporter.transform_title(course_run) == \
            [{
                'locale': 'English',
                'value': 'edX Demonstration Course (Starts: February 2013)'
            }]

    @responses.activate
    def test_transform_title_excludes_start(self):
        """
        Transforming a title gives only returns the title (not start date) if the course isn't instructor-paced.
        """
        course_run = {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'self_paced',
            'title': 'edX Demonstration Course'
        }
        exporter = SapSuccessFactorsCourseExporter('fake-user', self.config)
        assert exporter.transform_title(course_run) == \
            [{
                'locale': 'English',
                'value': 'edX Demonstration Course'
            }]
