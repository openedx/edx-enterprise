# -*- coding: utf-8 -*-
"""
Tests for enterprise.api_client.enterprise_catalog.py
"""
from __future__ import absolute_import, unicode_literals, with_statement

import json

import mock
import requests
import responses

from enterprise.api_client import enterprise_catalog

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
@mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
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
        expected_response['publish_audit_enrollment_urls']
    )
    assert actual_response == expected_response
    request = responses.calls[0][0]
    assert json.loads(request.body) == expected_request


@responses.activate
@mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
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
@mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
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
@mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
def test_delete_enterprise_catalog():
    responses.add(
        responses.DELETE,
        _url("enterprise-catalogs/{catalog_uuid}/".format(catalog_uuid=TEST_ENTERPRISE_CATALOG_UUID)),
    )
    client = enterprise_catalog.EnterpriseCatalogApiClient('staff-user-goes-here')
    actual_response = client.delete_enterprise_catalog(TEST_ENTERPRISE_CATALOG_UUID)
    assert actual_response


@responses.activate
@mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
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
@mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
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
