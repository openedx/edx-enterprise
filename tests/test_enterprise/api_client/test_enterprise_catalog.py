"""
Tests for enterprise.api_client.enterprise_catalog.py
"""
import json
import logging
from unittest import mock

import requests
import responses
from pytest import mark, raises
from requests.exceptions import ConnectionError, RequestException, Timeout  # pylint: disable=redefined-builtin

from enterprise.api_client import enterprise_catalog
from enterprise.models import EnterpriseCustomerCatalog
from test_utils import MockLoggingHandler
from test_utils.factories import EnterpriseCustomerCatalogFactory

TEST_ENTERPRISE_ID = '1840e1dc-59cf-4a78-82c5-c5bbc0b5df0f'
TEST_ENTERPRISE_CATALOG_UUID = 'cde8287a-1001-457c-b9d5-f9f5bd535427'
TEST_ENTERPRISE_CATALOG_NAME = 'Test Catalog'
TEST_ENTERPRISE_NAME = 'Test Enterprise'


def _url(path):
    """
    Build a URL for the relevant API named by base_name.

    Args:
        base_name (str): A name to identify the root URL by
        path (str): The URL suffix to append to the base path
    """
    return requests.compat.urljoin(enterprise_catalog.EnterpriseCatalogApiClient.API_BASE_URL, path)


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_create_enterprise_catalog():
    expected_response = {
        'catalog_uuid': TEST_ENTERPRISE_CATALOG_UUID,
        'enterprise_customer': TEST_ENTERPRISE_ID,
        'enterprise_customer_name': TEST_ENTERPRISE_NAME,
        'title': 'Test Catalog',
        'content_filter': {"content_type": "course"},
        'enabled_course_modes': ["verified"],
        'publish_audit_enrollment_urls': False,
    }
    expected_request = {
        'uuid': TEST_ENTERPRISE_CATALOG_UUID,
        'enterprise_customer': TEST_ENTERPRISE_ID,
        'enterprise_customer_name': TEST_ENTERPRISE_NAME,
        'title': 'Test Catalog',
        'content_filter': {"content_type": "course"},
        'enabled_course_modes': ["verified"],
        'publish_audit_enrollment_urls': 'false',
        'catalog_query_uuid': None,
        'query_title': None,
        'include_exec_ed_2u_courses': False,
    }
    responses.add(
        responses.POST,
        _url("enterprise-catalogs/"),
        json=expected_response
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.create_enterprise_catalog(
        expected_response['catalog_uuid'],
        expected_response['enterprise_customer'],
        expected_response['enterprise_customer_name'],
        expected_response['title'],
        expected_response['content_filter'],
        expected_response['enabled_course_modes'],
        expected_response['publish_audit_enrollment_urls'],
        expected_request['catalog_query_uuid'],
        expected_request['query_title'],
        expected_request['include_exec_ed_2u_courses'],
    )
    assert actual_response == expected_response
    request = responses.calls[0][0]
    assert json.loads(request.body) == expected_request


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_enterprise_catalog():
    expected_response = {
        'catalog_uuid': TEST_ENTERPRISE_CATALOG_UUID,
        'enterprise_customer': TEST_ENTERPRISE_ID,
        'enterprise_customer_name': TEST_ENTERPRISE_NAME,
        'title': 'Test Catalog',
        'content_filter': {"content_type": "course"},
        'enabled_course_modes': ["verified"],
        'publish_audit_enrollment_urls': False,
    }
    responses.add(
        responses.GET,
        _url("enterprise-catalogs/{catalog_uuid}/".format(catalog_uuid=TEST_ENTERPRISE_CATALOG_UUID)),
        json=expected_response,
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.get_enterprise_catalog(TEST_ENTERPRISE_CATALOG_UUID)
    assert actual_response == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_enterprise_catalog_by_hash():
    TEST_CONTENT_FILTER_HASH = 'abcd1234'
    expected_response = {
        'uuid': TEST_ENTERPRISE_CATALOG_UUID,
        'title': TEST_ENTERPRISE_CATALOG_NAME,
        'content_filter': {"content_type": "course"},
        'content_filter_hash': TEST_CONTENT_FILTER_HASH,
    }
    responses.add(
        responses.GET,
        _url(f"catalog-queries/get_query_by_hash?hash={TEST_CONTENT_FILTER_HASH}"),
        json=expected_response,
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.get_enterprise_catalog_by_hash(TEST_CONTENT_FILTER_HASH)
    assert actual_response == expected_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mark.parametrize('exception', (RequestException, ConnectionError, Timeout))
def test_get_enterprise_catalog_by_hash_error(exception):
    TEST_CONTENT_FILTER_HASH = 'abcd1234'
    responses.add_callback(
        responses.GET,
        _url(f"catalog-queries/get_query_by_hash?hash={TEST_CONTENT_FILTER_HASH}"),
        callback=exception,
        content_type='application/json'
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    logger = logging.getLogger('enterprise.api_client.enterprise_catalog')
    handler = MockLoggingHandler(level="ERROR")
    logger.addHandler(handler)
    expected_message = (
        f"Failed to get EnterpriseCustomer Catalog by hash [{TEST_CONTENT_FILTER_HASH}]"
        " in enterprise-catalog due to: ["
    )

    with raises(exception):
        client.get_enterprise_catalog_by_hash(TEST_CONTENT_FILTER_HASH)
    assert expected_message in handler.messages['error'][0]


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_catalog_query_hash():
    TEST_CONTENT_FILTER_HASH = 'abcd1234'
    responses.add(
        responses.GET,
        _url("catalog-queries/get_content_filter_hash"),
        json=TEST_CONTENT_FILTER_HASH,
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.get_catalog_query_hash({"content_type": "course"})
    assert actual_response == TEST_CONTENT_FILTER_HASH


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mark.parametrize('exception', (RequestException, ConnectionError, Timeout))
def test_get_catalog_query_hash_error(exception):
    TEST_QUERY_HASH = {"content_type": "course"}
    responses.add_callback(
        responses.GET,
        _url("catalog-queries/get_content_filter_hash"),
        callback=exception,
        content_type='application/json'
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    logger = logging.getLogger('enterprise.api_client.enterprise_catalog')
    handler = MockLoggingHandler(level="ERROR")
    logger.addHandler(handler)
    expected_message = (
        f"Failed to get catalog query hash for \"[{TEST_QUERY_HASH}]\" due to: ["
    )

    with raises(exception):
        client.get_catalog_query_hash(TEST_QUERY_HASH)
    assert expected_message in handler.messages['error'][0]


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_catalog_diff():
    items_to_create, items_to_delete, items_found = (['create me'], ['delete me'], ['look at me'])
    content_keys = items_to_create + items_to_delete + items_found
    enterprise_customer_catalog_mock = mock.Mock()
    enterprise_customer_catalog_mock.uuid = TEST_ENTERPRISE_CATALOG_UUID
    expected_response = {
        'items_not_found': items_to_delete,
        'items_not_included': items_to_create,
        'items_found': items_found,
    }
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')

    responses.add(
        responses.POST,
        _url(f"enterprise-catalogs/{TEST_ENTERPRISE_CATALOG_UUID}/generate_diff/"),
        json=expected_response,
    )
    actual_items_to_create, actual_items_to_delete, actual_items_found = client.get_catalog_diff(
        enterprise_customer_catalog_mock, content_keys
    )
    assert actual_items_to_create == items_to_create
    assert actual_items_to_delete == items_to_delete
    assert actual_items_found == items_found


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mark.parametrize(
    'exception, should_raise',
    [
        (RequestException, True),
        (ConnectionError, True),
        (Timeout, True),
        (RequestException, False),
        (ConnectionError, False),
        (Timeout, False)
    ]
)
def test_get_catalog_diff_error(exception, should_raise):
    """
    Check error handling for the EnterpriseCatalogApiClient.get_catalog_diff.
    """
    enterprise_customer_catalog_mock = mock.Mock()
    enterprise_customer_catalog_mock.uuid = TEST_ENTERPRISE_CATALOG_UUID

    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')

    responses.add_callback(
        responses.POST,
        _url(f"enterprise-catalogs/{TEST_ENTERPRISE_CATALOG_UUID}/generate_diff/"),
        callback=exception,
        content_type='application/json'
    )
    logger = logging.getLogger('enterprise.api_client.enterprise_catalog')
    handler = MockLoggingHandler(level="ERROR")
    logger.addHandler(handler)
    expected_message = (
        f"Failed to get EnterpriseCustomer Catalog [{TEST_ENTERPRISE_CATALOG_UUID}] in "
        f"enterprise-catalog due to: ["
    )
    if should_raise:
        with raises(exception):
            client.get_catalog_diff(enterprise_customer_catalog_mock, ['content_keys'], should_raise)
    else:
        client.get_catalog_diff(enterprise_customer_catalog_mock, ['content_keys'], should_raise)

    assert expected_message in handler.messages['error'][0]


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_update_enterprise_catalog():
    expected_response = {
        'catalog_uuid': TEST_ENTERPRISE_CATALOG_UUID,
        'enterprise_customer': TEST_ENTERPRISE_ID,
        'enterprise_customer_name': TEST_ENTERPRISE_NAME,
        'title': 'Test Catalog',
        'content_filter': {"content_type": "course"},
        'enabled_course_modes': ["verified"],
        'publish_audit_enrollment_urls': False,
    }
    responses.add(
        responses.PUT,
        _url("enterprise-catalogs/{catalog_uuid}/".format(catalog_uuid=TEST_ENTERPRISE_CATALOG_UUID)),
        json=expected_response,
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.update_enterprise_catalog(
        TEST_ENTERPRISE_CATALOG_UUID,
        content_filter={"content_type": "course"}
    )
    assert actual_response == expected_response
    request = responses.calls[0][0]
    assert json.loads(request.body) == {'content_filter': {"content_type": "course"}}


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mark.parametrize('exception', (RequestException, ConnectionError, Timeout))
def test_update_enterprise_catalog_error(exception):
    """
    Check error handling for the EnterpriseCatalogApiClient.update_enterprise_catalog.
    """
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')

    responses.add_callback(
        responses.PUT,
        _url(f"enterprise-catalogs/{TEST_ENTERPRISE_CATALOG_UUID}/"),
        callback=exception,
        content_type='application/json'
    )
    logger = logging.getLogger('enterprise.api_client.enterprise_catalog')
    handler = MockLoggingHandler(level="ERROR")
    logger.addHandler(handler)
    expected_message = (
        f"Failed to update EnterpriseCustomer Catalog [{TEST_ENTERPRISE_CATALOG_UUID}] in "
        f"enterprise-catalog due to: ["
    )
    result = client.update_enterprise_catalog(TEST_ENTERPRISE_CATALOG_UUID, content_filter={'fake': 'filter'})

    assert expected_message in handler.messages['error'][0]
    assert result == {}


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_delete_enterprise_catalog():
    responses.add(
        responses.DELETE,
        _url("enterprise-catalogs/{catalog_uuid}/".format(catalog_uuid=TEST_ENTERPRISE_CATALOG_UUID)),
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.delete_enterprise_catalog(TEST_ENTERPRISE_CATALOG_UUID)
    assert actual_response


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mark.parametrize('exception', (RequestException, ConnectionError, Timeout))
def test_delete_enterprise_catalog_error(exception):
    """
    Check error handling for the EnterpriseCatalogApiClient.delete_enterprise_catalog.
    """
    responses.add_callback(
        responses.DELETE,
        _url(f"enterprise-catalogs/{TEST_ENTERPRISE_CATALOG_UUID}/"),
        callback=exception
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.delete_enterprise_catalog(TEST_ENTERPRISE_CATALOG_UUID)
    assert not actual_response
    assert isinstance(actual_response, dict)


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_delete_enterprise_catalog_404():
    """
    Check 404 error handling for the EnterpriseCatalogApiClient.delete_enterprise_catalog.
    """
    responses.add(
        responses.DELETE,
        _url(f"enterprise-catalogs/{TEST_ENTERPRISE_CATALOG_UUID}/"),
        status=404
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')

    logger = logging.getLogger('enterprise.api_client.enterprise_catalog')
    handler = MockLoggingHandler(level="WARNING")
    logger.addHandler(handler)

    expected_message = (
        f"Deleted EnterpriseCustomerCatalog [{TEST_ENTERPRISE_CATALOG_UUID}] that was not in enterprise-catalog"
    )

    actual_response = client.delete_enterprise_catalog(TEST_ENTERPRISE_CATALOG_UUID)

    assert not actual_response
    assert isinstance(actual_response, dict)

    assert handler.messages['warning'][0] == expected_message


@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
@mark.parametrize('exception', (RequestException, ConnectionError, Timeout))
def test_traverse_get_content_metadata_error(exception):
    """
    Check error handling for the EnterpriseCatalogApiClient.traverse_get_content_metadata.
    """
    mock_client = mock.Mock()
    mock_client.get.side_effect = exception
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    client.client = mock_client

    logger = logging.getLogger('enterprise.api_client.enterprise_catalog')
    handler = MockLoggingHandler(level="ERROR")
    logger.addHandler(handler)

    expected_message = (
        f"Failed to get content metadata for Catalog {TEST_ENTERPRISE_CATALOG_UUID} in enterprise-catalog"
    )

    with raises(exception):
        client.traverse_get_content_metadata('/fake/url/', {'fake': 'query'}, TEST_ENTERPRISE_CATALOG_UUID)

    assert handler.messages['error'][0] == expected_message


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_contains_content_items():
    url = _url("enterprise-catalogs/{catalog_uuid}/contains_content_items/?course_run_ids=demoX".format(
        catalog_uuid=TEST_ENTERPRISE_CATALOG_UUID
    ))
    expected_response = {
        'contains_content_items': True,
    }
    responses.add(
        responses.GET,
        url,
        json=expected_response,
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.contains_content_items(TEST_ENTERPRISE_CATALOG_UUID, ['demoX'])
    assert actual_response == expected_response['contains_content_items']


@responses.activate
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_enterprise_contains_content_items():
    query_params = '?course_run_ids=demoX&get_catalogs_containing_specified_content_ids=True'
    url = _url(f"enterprise-customer/{TEST_ENTERPRISE_ID}/contains_content_items/{query_params}")
    expected_response = {
        'contains_content_items': True,
        'catalog_list': [],
    }
    responses.add(
        responses.GET,
        url,
        json=expected_response,
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.enterprise_contains_content_items(TEST_ENTERPRISE_ID, ['demoX'])
    actual_contains_content_items = actual_response['contains_content_items']
    actual_catalog_list = actual_response['catalog_list']
    assert actual_contains_content_items == expected_response['contains_content_items']
    assert actual_catalog_list == expected_response['catalog_list']


@responses.activate
@mark.django_db
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_successful_refresh_catalog():
    catalog = EnterpriseCustomerCatalogFactory()
    task_id = '17812314511'
    responses.add(
        responses.POST,
        _url("enterprise-catalogs/{catalog_uuid}/refresh_metadata/".format(catalog_uuid=catalog.uuid)),
        json={'async_task_id': task_id},
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    refreshed_catalogs, failed_to_refresh_catalogs = client.refresh_catalogs(EnterpriseCustomerCatalog.objects.all())
    assert refreshed_catalogs.get(catalog.uuid) == task_id
    assert len(failed_to_refresh_catalogs) == 0


@responses.activate
@mark.django_db
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_failing_refresh_catalog():
    catalog = EnterpriseCustomerCatalogFactory()
    responses.add(
        responses.POST,
        _url("enterprise-catalogs/{catalog_uuid}/refresh_metadata/".format(catalog_uuid=catalog.uuid)),
        body=ConnectionError(),
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    refreshed_catalogs, failed_to_refresh_catalogs = client.refresh_catalogs(EnterpriseCustomerCatalog.objects.all())
    assert failed_to_refresh_catalogs[0] == catalog.uuid
    assert len(refreshed_catalogs) == 0


@responses.activate
@mark.django_db
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_partial_successful_refresh_catalog():
    catalog1 = EnterpriseCustomerCatalogFactory()
    catalog2 = EnterpriseCustomerCatalogFactory()
    task_id = '17812314511'
    responses.add(
        responses.POST,
        _url("enterprise-catalogs/{catalog_uuid}/refresh_metadata/".format(catalog_uuid=catalog1.uuid)),
        json={'async_task_id': task_id},
    )
    responses.add(
        responses.POST,
        _url("enterprise-catalogs/{catalog_uuid}/refresh_metadata/".format(catalog_uuid=catalog2.uuid)),
        body=ConnectionError(),
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    refreshed_catalogs, failed_to_refresh_catalogs = client.refresh_catalogs(EnterpriseCustomerCatalog.objects.all())
    assert failed_to_refresh_catalogs[0] == catalog2.uuid
    assert len(refreshed_catalogs) == 1
    assert refreshed_catalogs.get(catalog1.uuid) == task_id


@responses.activate
@mark.django_db
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_content_metadata_with_content_key_filters():
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    client.GET_CONTENT_METADATA_PAGE_SIZE = 1
    page_size = client.GET_CONTENT_METADATA_PAGE_SIZE
    catalog = EnterpriseCustomerCatalogFactory()
    key_1 = 'key-1'
    key_2 = 'key-2'
    data = 'foo'
    content_type = 'course'
    url = _url(f'enterprise-catalogs/{catalog.uuid}/get_content_metadata/?page_size={page_size}')
    first_url = url + f'&content_keys={key_1}'
    second_url = url + f'&content_keys={key_2}'
    responses.reset()

    first_expected_response = {
        'count': 1,
        'next': None,
        'previous': None,
        'results': [{
            'content_type': content_type,
            'key': key_1,
            'data': data,
        }]
    }
    second_expected_response = {
        'count': 1,
        'next': None,
        'previous': None,
        'results': [{
            'content_type': content_type,
            'key': key_2,
            'data': data,
        }]
    }
    responses.add(responses.GET, first_url, json=first_expected_response)
    responses.add(responses.GET, second_url, json=second_expected_response)
    results = client.get_content_metadata(catalog.enterprise_customer, [catalog], ['key-1', 'key-2'])

    assert results == [{
        'content_type': content_type,
        'key': key_1,
        'data': data
    }, {
        'content_type': content_type,
        'key': key_2,
        'data': data
    }]
    first_request_url = responses.calls[0][0].url
    assert first_url == first_request_url
    second_request_url = responses.calls[1][0].url
    assert second_url == second_request_url


@responses.activate
@mark.django_db
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_content_metadata_with_enterprise_catalogs():
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    page_size = client.GET_CONTENT_METADATA_PAGE_SIZE
    catalog = EnterpriseCustomerCatalogFactory()
    first_url = _url('enterprise-catalogs/{catalog_uuid}/get_content_metadata/?page_size={page_size}'.format(
        catalog_uuid=catalog.uuid,
        page_size=page_size,
    ))
    second_url = _url('enterprise-catalogs/{catalog_uuid}/get_content_metadata/?page_size={page_size}&page=2'.format(
        catalog_uuid=catalog.uuid,
        page_size=page_size,
    ))

    responses.reset()

    first_expected_response = {
        'count': 100,
        'next': second_url,
        'previous': None,
        'results': [
            {
                'content_type': 'course',
                'key': 'key-{}'.format(index),
                'data': 'foo',
            } for index in range(page_size)
        ]
    }
    responses.add(responses.GET, first_url, json=first_expected_response)

    second_expected_response = {
        'count': 100,
        'next': None,
        'previous': first_url,
        'results': [
            {
                'content_type': 'course',
                'key': 'key-{}'.format(index),
                'data': 'foo',
            } for index in range(page_size, page_size * 2)
        ]
    }
    responses.add(responses.GET, second_url, json=second_expected_response)

    results = client.get_content_metadata(catalog.enterprise_customer, [catalog])

    expected_results = [
        {
            'content_type': 'course',
            'key': 'key-{}'.format(index),
            'data': 'foo',
        } for index in range(page_size * 2)
    ]
    assert results == expected_results

    first_request_url = responses.calls[0][0].url
    assert first_url == first_request_url
    second_request_url = responses.calls[1][0].url
    assert second_url == second_request_url


@responses.activate
@mark.django_db
@mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
def test_get_content_metadata_without_enterprise_catalogs():
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    page_size = client.GET_CONTENT_METADATA_PAGE_SIZE
    catalog = EnterpriseCustomerCatalogFactory()
    url = _url('enterprise-catalogs/{catalog_uuid}/get_content_metadata/?page_size={page_size}'.format(
        catalog_uuid=catalog.uuid,
        page_size=page_size,
    ))

    responses.reset()

    expected_response = {
        'count': 100,
        'next': None,
        'previous': None,
        'results': [
            {
                'content_type': 'course',
                'key': 'key-{}'.format(index),
                'data': 'foo',
            } for index in range(page_size)
        ]
    }
    responses.add(responses.GET, url, json=expected_response)
    results = client.get_content_metadata(enterprise_customer=catalog.enterprise_customer)

    expected_results = [
        {
            'content_type': 'course',
            'key': 'key-{}'.format(index),
            'data': 'foo',
        } for index in range(page_size)
    ]

    assert results == expected_results

    request_url = responses.calls[0][0].url
    assert url == request_url
