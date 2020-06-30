"""
Test for heartbeat views.
"""
import json
import unittest

import ddt
import responses
from path import Path
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin

from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse

from enterprise.heartbeat.utils import Status
from enterprise.heartbeat.views import heartbeat
from test_utils.decorators import mock_api_response, mock_api_response_with_callback
from test_utils.fake_heartbeat_responses import fake_health, fake_lms_heartbeat


@ddt.ddt
class TestHeartbeatViews(unittest.TestCase):
    """
    Validate heartbeat views works as expected.
    """

    @mock_api_response(
        responses.GET,
        Path(settings.LMS_INTERNAL_ROOT_URL) / 'heartbeat',
        json=fake_lms_heartbeat(),
        additional_responses=[
            {
                'method': responses.GET,
                'url': Path(settings.ECOMMERCE_PUBLIC_URL_ROOT) / 'health',
                'json': fake_health(),
            },
            {
                'method': responses.GET,
                'url': Path(settings.COURSE_CATALOG_URL_ROOT) / 'health',
                'json': fake_health(),
            },
            {
                'method': responses.GET,
                'url': Path(settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL) / 'health',
                'json': fake_health(),
            },
        ]
    )
    def test_ok(self):
        """
        Test that a response with 200 status code is returned if all services are up and running.
        """
        request = RequestFactory().get(reverse('enterprise_heartbeat'))
        response = heartbeat(request)
        assert response.status_code == 200

        data = json.loads(response.content.decode('utf-8'))
        assert data['status'] == Status.OK
        assert data['message'] == 'Service is up and running.'
        assert all(service['status'] == Status.OK for service in data['services'])

    @ddt.unpack
    @ddt.data(
        (
            mock_api_response_with_callback(
                responses.GET,
                Path(settings.LMS_INTERNAL_ROOT_URL) / 'heartbeat',
                callback=lambda _: (200, {}, json.dumps(fake_health())),
                additional_responses=[
                    {
                        'method': responses.GET,
                        'url': Path(settings.ECOMMERCE_PUBLIC_URL_ROOT) / 'health',
                        'callback': lambda _: (503, {}, json.dumps(fake_health())),
                    },
                    {
                        'method': responses.GET,
                        'url': Path(settings.COURSE_CATALOG_URL_ROOT) / 'health',
                        'callback': lambda _: (400, {}, json.dumps(fake_health())),
                    },
                    {
                        'method': responses.GET,
                        'url': Path(settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL) / 'health',
                        'callback': Timeout,
                    },
                ]
            ),
            {'E-Commerce', 'Course Discovery', 'Enterprise Catalog'}
        ),
        (
            mock_api_response_with_callback(
                responses.GET,
                Path(settings.LMS_INTERNAL_ROOT_URL) / 'heartbeat',
                callback=ConnectionError,
                additional_responses=[
                    {
                        'method': responses.GET,
                        'url': Path(settings.ECOMMERCE_PUBLIC_URL_ROOT) / 'health',
                        'callback': lambda _: (500, {}, json.dumps(fake_health())),
                    },
                    {
                        'method': responses.GET,
                        'url': Path(settings.COURSE_CATALOG_URL_ROOT) / 'health',
                        'callback': lambda _: (403, {}, json.dumps(fake_health())),
                    },
                    {
                        'method': responses.GET,
                        'url': Path(settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL) / 'health',
                        'callback': Timeout,
                    },
                ]
            ),
            {'E-Commerce', 'Course Discovery', 'Enterprise Catalog', 'Learning Management System (LMS)'}
        ),
    )
    def test_run_checks_errors(self, responses_decorator, downed_services):
        """
        Validate that `run_checks` returns failure if some or all services are down.
        """
        @responses_decorator
        def _test_run_checks_errors():
            request = RequestFactory().get(reverse('enterprise_heartbeat'))
            response = heartbeat(request)
            assert response.status_code == 503

            data = json.loads(response.content.decode('utf-8'))
            assert data['status'] == Status.UNAVAILABLE
            assert data['message'] == 'Some or all of the dependant services are down.'
            assert all(
                service['status'] == Status.OK for service in data['services']
                if service['service'] not in downed_services
            )
            assert all(
                service['status'] == Status.UNAVAILABLE for service in data['services']
                if service['service'] in downed_services
            )

        # Run the tests
        _test_run_checks_errors()
