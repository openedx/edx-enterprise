# -*- coding: utf-8 -*-
"""
Tests for Cornerstone content metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import copy
import datetime
import unittest

import ddt
import mock
import pytz
import responses
from freezegun import freeze_time
from pytest import mark

from integrated_channels.cornerstone.exporters.content_metadata import CornerstoneContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import FAKE_SEARCH_ALL_COURSE_RESULT_3
from test_utils.fake_enterprise_api import EnterpriseMockMixin

NOW = datetime.datetime.now(pytz.UTC)
LONG_ORG_NAME = "Very long org name, Very long org name, Very long org name, Very long org name, " \
                "Very long org name, Very long org name, Very long org name, Very long org name, " \
                "Very long org name, Very long org name, Very long org name, Very long org name, " \
                "Very long org name, Very long org name, Very long org name, Very long org name, " \
                "Very long org name, Very long org name, Very long org name, Very long org name, " \
                "Very long org name, Very long org name, Very long org name, Very long org name, " \
                "Very long org name, Very long org name"


@mark.django_db
@ddt.ddt
class TestCornerstoneContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``CornerstoneContentMetadataExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        self.global_config = factories.CornerstoneGlobalConfigurationFactory()

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestCornerstoneContentMetadataExporter, self).setUp()

    def _merge_dicts(self, dict1, dict2):
        """
        Merges dict1 and dict2 and returns merged dict.
        If dict2 has a key with value set to `undefined`
        it removes that key from dict1
        """
        merged_dict = copy.deepcopy(dict1)
        if dict2:
            for key, val in dict2.items():
                if val == 'undefined' and key in merged_dict:
                    del merged_dict[key]
                else:
                    merged_dict.update(dict2)
        return merged_dict

    @responses.activate
    def test_content_exporter_export(self):
        """
        ``CornerstoneContentMetadataExporter``'s ``export`` produces the expected export.
        """
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])

    @ddt.data(
        (

            {
                'full_description': u'Test case - is the smallest unit of the testing plan - which includes a '
                                    u'description of necessary actions and parameters to achieve and verify the '
                                    u'expected behaviour of a particular function.',
                'short_description': u'This is short description of course',
            },
            u'This is short description of course',
        ),
        (
            {
                'full_description': u'This is full description of course',
                'short_description': u'This is short description of course',
            },
            u'This is full description of course',
        ),
        (
            {
                'full_description': u'',
                'short_description': u'',
            },
            u'edX Demonstration Course',
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_description(self, item_description, expected_description):
        """
        Transforming a description gives back the full description of course if it is
        small than or equal to LONG_STRING_LIMIT. If it is greater than LONG_STRING_LIMIT
        course short description or course title should be returned
        content type of the provided `content_metadata_item`.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_description)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        exporter.LONG_STRING_LIMIT = 100
        assert exporter.transform_description(item_content_metadata) == expected_description

    @ddt.data(
        (
            {'course_runs': []},
            False,
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Archived"
                    },
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "verified",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": None,
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Current"
                    },
                ]
            },
            True,
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Archived"
                    },
                ]
            },
            False,
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Starting Soon"
                    },
                ]
            },
            True,
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Upcoming"
                    },
                ]
            },
            True,
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_is_active(self, item_course_runs, expected_is_active):
        """
        Test transforms for is_active status of course.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_course_runs)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_is_active(item_content_metadata) == expected_is_active

    @ddt.data(
        (
            {'course_runs': []},
            None,
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "availability": "Current"
                    }
                ]
            },
            None,
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "estimated_hours": 5.5,
                        "availability": "Archived"
                    },
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "verified",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": None,
                        "start": "2019-02-05T05:00:00Z",
                        "go_live_date": None,
                        "estimated_hours": 6.5,
                        "availability": "Current"
                    },
                ]
            },
            "06:30:00",
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "go_live_date": None,
                        "estimated_hours": 100,
                        "availability": "Archived"
                    },
                ]
            },
            "100:00:00",
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_estimated_hours(self, item_course_runs, expected_duration):
        """
        Test transformation of estimated_hours into course duration.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_course_runs)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_estimated_hours(item_content_metadata) == expected_duration

    @ddt.data(
        (
            {
                'course_runs': 'undefined',
            },
            str(NOW)
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2023-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Archived"
                    },
                ]
            },
            str(NOW)
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-02-05T05:00:00Z",
                        "start": "2023-02-05T05:00:00Z",
                        "modified": "2019-02-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Archived"
                    },
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "verified",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": None,
                        "start": "2019-02-05T05:00:00Z",
                        "modified": "2019-03-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Current"
                    },
                ]
            },
            "2019-03-05T05:00:00Z",
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-06-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "modified": "2019-04-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Archived"
                    },
                ]
            },
            "2019-04-05T05:00:00Z",
        ),
        (
            {
                'course_runs': [
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2013-06-05T05:00:00Z",
                        "start": "2013-02-05T05:00:00Z",
                        "modified": "2013-04-05T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Archived"
                    },
                    {
                        "enrollment_end": None,
                        "enrollment_mode": "audit",
                        "key": "course-v1:edX+DemoX+Demo_Course",
                        "enrollment_start": None,
                        "pacing_type": "instructor_paced",
                        "end": "2019-09-05T05:00:00Z",
                        "start": "2019-06-05T05:00:00Z",
                        "modified": "2019-06-20T05:00:00Z",
                        "go_live_date": None,
                        "availability": "Starting Soon"
                    },
                ]
            },
            "2019-06-20T05:00:00Z",
        ),
    )
    @responses.activate
    @freeze_time(NOW)
    @ddt.unpack
    def test_transform_modified(self, item_course_runs, expected_modified_datetime):
        """
        Test transformation for LastModifiedUTC field.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_course_runs)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_modified(item_content_metadata) == expected_modified_datetime

    @ddt.data(
        (
            {'languages': ['English']},
            ['en-US'],
        ),
        (
            {'languages': 'undefined'},
            ['en-US'],
        ),
        (
            {'languages': ['Spanish', 'English', 'Japanese']},
            ['es-ES', 'en-US', 'ja'],
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_languages(self, item_languages, expected_languages):
        """
        Test transforming languages should return a list of languages for course.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_languages)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_languages(item_content_metadata) == expected_languages

    @ddt.data(
        (
            {'organizations': []},
            [],
        ),
        (
            {'organizations': 'undefined'},
            [],
        ),
        (
            None,
            [{"Name": "edX: "}],
        ),
        (
            {'organizations': ["edX: edX Inc", "MITx: Massachusetts Institute of Technology"]},
            [{"Name": "edX: edX Inc"}, {"Name": "MITx: Massachusetts Institute of Technology"}],
        ),
        (
            {'organizations': ["edX: edX Inc", LONG_ORG_NAME]},
            [{"Name": "edX: edX Inc"}, {"Name": LONG_ORG_NAME[:500]}],
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_organizations(self, item_organizations, expected_organizations):
        """
        Transforming organizations gives back the a list of dict {"Name": "Org Name"}.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_organizations)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_organizations(item_content_metadata) == expected_organizations

    @ddt.data(
        (
            {
                'subjects': ["Computer Science", "Communication", "Music", "Design"]
            },
            ["Technology", "Business Skills", "Creative"]
        ),
        (
            {
                'subjects': ["Some New Subject"]
            },
            ["Industry Specific"]
        ),
        (
            {
                'subjects': []
            },
            []
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_subjects(self, item_subjects, expected_subjects):
        """
        Transforming subjects gives back the a list of cornerstone's subjects.
        """
        item_content_metadata = self._merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_subjects)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert sorted(exporter.transform_subjects(item_content_metadata)) == sorted(expected_subjects)
