"""
Tests for enterprise.api_client.enterprise_catalog.py
"""

import json
from unittest import mock

import requests
import responses
from pytest import mark
from requests.exceptions import ConnectionError  # pylint: disable=redefined-builtin

from enterprise.api_client import enterprise_catalog
from enterprise.models import EnterpriseCustomerCatalog
from test_utils.factories import EnterpriseCustomerCatalogFactory

TEST_ENTERPRISE_ID = '1840e1dc-59cf-4a78-82c5-c5bbc0b5df0f'
TEST_ENTERPRISE_CATALOG_UUID = 'cde8287a-1001-457c-b9d5-f9f5bd535427'
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
        expected_request['query_title']
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
    url = _url("enterprise-customer/{enterprise_uuid}/contains_content_items/?course_run_ids=demoX".format(
        enterprise_uuid=TEST_ENTERPRISE_ID
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
    actual_response = client.enterprise_contains_content_items(TEST_ENTERPRISE_ID, ['demoX'])
    assert actual_response == expected_response['contains_content_items']


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
