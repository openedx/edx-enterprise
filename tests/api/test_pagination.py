# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api pagination.
"""
from __future__ import absolute_import, unicode_literals

import ddt
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory

from enterprise.api.pagination import get_paginated_response
from test_utils import APITest

DISCOVERY_URI = 'http://testserver.catalogs/api/v1/catalogs'
ENTERPRISE_URI = 'http://testserver.enterprise/enterprise/api/v1/catalogs/'


@ddt.ddt
class TestEnterpriseAPIPagination(APITest):
    """
    Tests for enterprise api pagination.
    """

    def setUp(self):
        """
        Common setup functions.
        """
        super(TestEnterpriseAPIPagination, self).setUp()

        # Create and authenticate a request
        self.request = APIRequestFactory().get(
            reverse('catalogs-list'),
            SERVER_NAME="testserver.enterprise",
        )

        self.data = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "owners": [
                        {
                            "description": None,
                            "tags": [],
                            "name": "",
                            "homepage_url": None,
                            "key": "edX",
                            "certificate_logo_image_url": None,
                            "marketing_url": None,
                            "logo_image_url": None,
                            "uuid": "aa4aaad0-2ff0-44ce-95e5-1121d02f3b27"
                        }
                    ],
                    "uuid": "d2fb4cb0-b538-4934-ba60-684d48ff5865",
                    "title": "edX Demonstration Course",
                    "prerequisites": [],
                    "image": None,
                    "expected_learning_items": [],
                    "sponsors": [],
                    "modified": "2017-03-03T07:34:19.322916Z",
                    "full_description": None,
                    "subjects": [],
                    "video": None,
                    "key": "edX+DemoX",
                    "short_description": None,
                    "marketing_url": None,
                    "level_type": None,
                    "course_runs": []
                }
            ]
        }

    @ddt.data(
        (None, None, None, None),
        (
            None,
            '{discovery_uri}?page=2'.format(discovery_uri=DISCOVERY_URI),
            None,
            '{enterprise_uri}?page=2'.format(enterprise_uri=ENTERPRISE_URI),
        ),
        (
            '{discovery_uri}?page=3'.format(discovery_uri=DISCOVERY_URI),
            None,
            '{enterprise_uri}?page=3'.format(enterprise_uri=ENTERPRISE_URI),
            None,
        ),
        (
            '{discovery_uri}?page=3'.format(discovery_uri=DISCOVERY_URI),
            '{discovery_uri}?page=1'.format(discovery_uri=DISCOVERY_URI),
            '{enterprise_uri}?page=3'.format(enterprise_uri=ENTERPRISE_URI),
            '{enterprise_uri}?page=1'.format(enterprise_uri=ENTERPRISE_URI),
        ),
        (
            '{discovery_uri}'.format(discovery_uri=DISCOVERY_URI),
            '{discovery_uri}?page=1'.format(discovery_uri=DISCOVERY_URI),
            '{enterprise_uri}'.format(enterprise_uri=ENTERPRISE_URI),
            '{enterprise_uri}?page=1'.format(enterprise_uri=ENTERPRISE_URI),
        ),
        (
            '{discovery_uri}?page=3'.format(discovery_uri=DISCOVERY_URI),
            '{discovery_uri}'.format(discovery_uri=DISCOVERY_URI),
            '{enterprise_uri}?page=3'.format(enterprise_uri=ENTERPRISE_URI),
            '{enterprise_uri}'.format(enterprise_uri=ENTERPRISE_URI),
        ),
        (
            '{discovery_uri}'.format(discovery_uri=DISCOVERY_URI),
            '{discovery_uri}'.format(discovery_uri=DISCOVERY_URI),
            '{enterprise_uri}'.format(enterprise_uri=ENTERPRISE_URI),
            '{enterprise_uri}'.format(enterprise_uri=ENTERPRISE_URI),
        ),
    )
    @ddt.unpack
    def test_get_paginated_response(self, previous_page, next_page, expected_previous, expected_next):
        """
        Verify get_paginated_response returns correct response.
        """
        self.data['next'] = next_page
        self.data['previous'] = previous_page

        # Update authentication parameters based in ddt data.
        response = get_paginated_response(self.data, self.request)

        assert response.data.get('next') == expected_next
        assert response.data.get('previous') == expected_previous

    def test_get_paginated_response_correct_query_parameters(self):
        """
        Verify get_paginated_response returns correct response.
        """
        self.data['next'] = '{discovery_uri}?page=3'.format(discovery_uri=DISCOVERY_URI)
        self.data['previous'] = '{discovery_uri}?page=1'.format(discovery_uri=DISCOVERY_URI)
        expected_next = '{enterprise_uri}?page=3'.format(enterprise_uri=ENTERPRISE_URI)
        expected_previous = '{enterprise_uri}?page=1'.format(enterprise_uri=ENTERPRISE_URI)
        request = APIRequestFactory().get(
            reverse('catalogs-list') + "?page=2",
            SERVER_NAME="testserver.enterprise",
        )

        # Update authentication parameters based in ddt data.
        response = get_paginated_response(self.data, request)

        assert response.data.get('next') == expected_next
        assert response.data.get('previous') == expected_previous
