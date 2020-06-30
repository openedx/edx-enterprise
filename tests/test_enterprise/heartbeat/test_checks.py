"""
Validate the behavior of service checks functions.
"""
import unittest

import ddt
import responses
from path import Path
from pytest import raises
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin

from django.conf import settings

from enterprise.heartbeat.checks import check_discovery, check_ecommerce, check_enterprise_catalog, check_lms
from enterprise.heartbeat.exceptions import (
    DiscoveryNotAvailable,
    EcommerceNotAvailable,
    EnterpriseCatalogNotAvailable,
    LMSNotAvailable,
)
from test_utils.decorators import mock_api_response, mock_api_response_with_callback
from test_utils.fake_heartbeat_responses import fake_health, fake_lms_heartbeat


@ddt.ddt
class TestChecks(unittest.TestCase):
    """
    Validate the behavior of service checks functions.
    """

    @mock_api_response(
        responses.GET,
        Path(settings.LMS_INTERNAL_ROOT_URL) / 'heartbeat',
        json=fake_lms_heartbeat(),
    )
    def test_check_lms(self):
        """
        Validate that `check_lms` function works as expected.
        """
        service, message = check_lms()

        assert service == 'Learning Management System (LMS)'
        assert message == 'Service is up and running.'

    @ddt.unpack
    @ddt.data(
        (503, 'Service is down'),
        (400, 'An error occurred while checking service status.'),
    )
    def test_check_lms_error(self, status_code, expected_error_message):
        """
        Validate that `check_lms` function works as expected.
        """
        @mock_api_response(
            responses.GET,
            Path(settings.LMS_INTERNAL_ROOT_URL) / 'heartbeat',
            json=fake_lms_heartbeat(all_okay=False),
            status=status_code
        )
        def _test_check_lms_error():

            with raises(LMSNotAvailable) as error:
                check_lms()
                assert error.message == expected_error_message

        # Run the tests
        _test_check_lms_error()

    @ddt.data(Timeout, ConnectionError)
    def test_check_lms_connection_errors(self, exception):
        """
        Validate that `check_lms` function works as expected.
        """
        @mock_api_response_with_callback(
            responses.GET,
            Path(settings.LMS_INTERNAL_ROOT_URL) / 'heartbeat',
            callback=exception,
            content_type='application/json'
        )
        def _test_check_lms_connection_errors():

            with raises(LMSNotAvailable) as error:
                check_lms()
                assert error.message == 'Service is not accessible.'

        # Run the tests
        _test_check_lms_connection_errors()

    @mock_api_response(
        responses.GET,
        Path(settings.ECOMMERCE_PUBLIC_URL_ROOT) / 'health',
        json=fake_lms_heartbeat(),
    )
    def test_check_ecommerce(self):
        """
        Validate that `check_ecommerce` function works as expected.
        """
        service, message = check_ecommerce()

        assert service == 'E-Commerce'
        assert message == 'Service is up and running.'

    @ddt.unpack
    @ddt.data(
        (503, 'Service is down'),
        (400, 'An error occurred while checking service status.'),
    )
    def test_check_ecommerce_error(self, status_code, expected_error_message):
        """
        Validate that `check_ecommerce` function works as expected.
        """
        @mock_api_response(
            responses.GET,
            Path(settings.ECOMMERCE_PUBLIC_URL_ROOT) / 'health',
            json=fake_health(all_okay=False),
            status=status_code
        )
        def _test_check_ecommerce_error():

            with raises(EcommerceNotAvailable) as error:
                check_ecommerce()
                assert error.message == expected_error_message

        # Run the tests
        _test_check_ecommerce_error()

    @ddt.data(Timeout, ConnectionError)
    def test_check_ecommerce_connection_errors(self, exception):
        """
        Validate that `check_ecommerce` function works as expected.
        """
        @mock_api_response_with_callback(
            responses.GET,
            Path(settings.ECOMMERCE_PUBLIC_URL_ROOT) / 'health',
            callback=exception,
            content_type='application/json'
        )
        def _test_check_ecommerce_connection_errors():

            with raises(EcommerceNotAvailable) as error:
                check_ecommerce()
                assert error.message == 'Service is not accessible.'

        # Run the tests
        _test_check_ecommerce_connection_errors()

    @mock_api_response(
        responses.GET,
        Path(settings.COURSE_CATALOG_URL_ROOT) / 'health',
        json=fake_health(),
    )
    def test_check_discovery(self):
        """
        Validate that `check_discovery` function works as expected.
        """
        service, message = check_discovery()

        assert service == 'Course Discovery'
        assert message == 'Service is up and running.'

    @ddt.unpack
    @ddt.data(
        (503, 'Service is down'),
        (400, 'An error occurred while checking service status.'),
    )
    def test_check_discovery_error(self, status_code, expected_error_message):
        """
        Validate that `check_discovery` function works as expected.
        """
        @mock_api_response(
            responses.GET,
            Path(settings.COURSE_CATALOG_URL_ROOT) / 'health',
            json=fake_health(all_okay=False),
            status=status_code
        )
        def _test_check_discovery_error():

            with raises(DiscoveryNotAvailable) as error:
                check_discovery()
                assert error.message == expected_error_message

        # Run the tests
        _test_check_discovery_error()

    @ddt.data(Timeout, ConnectionError)
    def test_check_discovery_connection_errors(self, exception):
        """
        Validate that `check_discovery` function works as expected.
        """
        @mock_api_response_with_callback(
            responses.GET,
            Path(settings.COURSE_CATALOG_URL_ROOT) / 'health',
            callback=exception,
            content_type='application/json'
        )
        def _test_check_discovery_connection_errors():

            with raises(DiscoveryNotAvailable) as error:
                check_discovery()
                assert error.message == 'Service is not accessible.'

        # Run the tests
        _test_check_discovery_connection_errors()

    @mock_api_response(
        responses.GET,
        Path(settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL) / 'health',
        json=fake_health(),
    )
    def test_check_enterprise_catalog(self):
        """
        Validate that `check_enterprise_catalog` function works as expected.
        """
        service, message = check_enterprise_catalog()

        assert service == 'Enterprise Catalog'
        assert message == 'Service is up and running.'

    @ddt.unpack
    @ddt.data(
        (503, 'Service is down'),
        (400, 'An error occurred while checking service status.'),
    )
    def test_check_enterprise_catalog_error(self, status_code, expected_error_message):
        """
        Validate that `check_enterprise_catalog` function works as expected.
        """
        @mock_api_response(
            responses.GET,
            Path(settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL) / 'health',
            json=fake_health(all_okay=False),
            status=status_code
        )
        def _test_check_enterprise_catalog_error():

            with raises(EnterpriseCatalogNotAvailable) as error:
                check_enterprise_catalog()
                assert error.message == expected_error_message

        # Run the tests
        _test_check_enterprise_catalog_error()

    @ddt.data(Timeout, ConnectionError)
    def test_check_enterprise_catalog_connection_errors(self, exception):
        """
        Validate that `check_enterprise_catalog` function works as expected.
        """
        @mock_api_response_with_callback(
            responses.GET,
            Path(settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL) / 'health',
            callback=exception,
            content_type='application/json'
        )
        def _test_check_enterprise_catalog_errors():

            with raises(EnterpriseCatalogNotAvailable) as error:
                check_enterprise_catalog()
                assert error.message == 'Service is not accessible.'

        # Run the tests
        _test_check_enterprise_catalog_errors()
