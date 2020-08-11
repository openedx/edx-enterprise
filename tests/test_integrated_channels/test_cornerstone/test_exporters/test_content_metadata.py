# -*- coding: utf-8 -*-
"""
Tests for Cornerstone content metadata exporters.
"""

import datetime
import unittest

import ddt
import mock
import pytz
import responses
from freezegun import freeze_time
from pytest import mark

from integrated_channels.cornerstone.exporters.content_metadata import CornerstoneContentMetadataExporter
from integrated_channels.integrated_channel.constants import ISO_8601_DATE_FORMAT
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import FAKE_SEARCH_ALL_COURSE_RESULT_3
from test_utils.fake_enterprise_api import EnterpriseMockMixin
from test_utils.integrated_channels_utils import merge_dicts

NOW = datetime.datetime.now(pytz.UTC)
DEFAULT_OWNER = {
    "Name": "edX: edX Inc"
}
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
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_description)
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
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_course_runs)
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
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_course_runs)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_estimated_hours(item_content_metadata) == expected_duration

    @ddt.data(
        (
            {
                'course_runs': 'undefined',
            },
            NOW.strftime(ISO_8601_DATE_FORMAT)
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
            NOW.strftime(ISO_8601_DATE_FORMAT)
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
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_course_runs)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_modified(item_content_metadata) == expected_modified_datetime

    @ddt.data(
        (
            {'languages': ['English']},
            ['en-US'],
        ),
        (
            {'languages': []},
            ['en-US'],
        ),
        (
            {'languages': 'undefined'},
            ['en-US'],
        ),
        (
            {'languages': None},
            ['en-US'],
        ),
        (
            {'languages': ['Spanish', 'English', 'Japanese']},
            ['es-ES', 'en-US', 'ja-JP'],
        ),
        (
            {'languages': ['Afrikaans', 'Catalan', 'Zulu']},
            ['en-US'],
        ),
        (
            {'languages': ['Spanish', 'English', 'Chinese - Simplified', 'Chinese - China']},
            ['es-ES', 'en-US', 'zh-CN'],
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_languages(self, item_languages, expected_languages):
        """
        Test transforming languages should return a list of languages for course.
        """
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_languages)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        transformed_languages = exporter.transform_languages(item_content_metadata)
        assert sorted(transformed_languages) == sorted(expected_languages)

    @ddt.data(
        (
            {'organizations': []},
            [DEFAULT_OWNER],
        ),
        (
            {'organizations': 'undefined'},
            [DEFAULT_OWNER],
        ),
        (
            {'organizations': None},
            [DEFAULT_OWNER],
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
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_organizations)
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
            ["Industry Specific"]
        ),
        (
            {
                'subjects': None
            },
            ["Industry Specific"]
        ),
        (
            {
                'subjects': [
                    {'name': 'Computer Science'},
                    {'name': 'Communication'},
                    {'name': 'Music'},
                    {'name': 'Design'},
                ],
            },
            ["Technology", "Business Skills", "Creative"],
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_subjects(self, item_subjects, expected_subjects):
        """
        Transforming subjects gives back the a list of cornerstone's subjects.
        """
        item_content_metadata = merge_dicts(FAKE_SEARCH_ALL_COURSE_RESULT_3, item_subjects)
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert sorted(exporter.transform_subjects(item_content_metadata)) == sorted(expected_subjects)

    @ddt.data(
        (
            {
                'aggregation_key': 'course:edX+DemoX',
                'title': 'edX Demonstration Course',
                'key': 'edX+DemoX',
                'content_type': 'course',
                'image_url': 'https://edx.devstack.lms:18000/'
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
        exporter = CornerstoneContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_image(content_metadata_item) == expected_thumbnail_url
