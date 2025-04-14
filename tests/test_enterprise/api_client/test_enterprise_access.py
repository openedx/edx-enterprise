"""
Tests for enterprise.api_client.enterprise_access.py
"""

import unittest
from unittest import mock

import ddt
import responses
from pytest import mark

from django.conf import settings

from enterprise.api_client import enterprise_access
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseGroupFactory, UserFactory


@ddt.ddt
@mark.django_db
class TestEnterpriseAccessApiClient(unittest.TestCase):
    """
    Test enterprise-access API client methods.
    """

    def setUp(self):
        """
        DRY method for TestEnterpriseAccessApiClient.
        """
        self.user = UserFactory()
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Lumon',
        )
        self.test_group = EnterpriseGroupFactory(enterprise_customer=self.enterprise_customer)
        self.url_base = settings.ENTERPRISE_ACCESS_INTERNAL_ROOT_URL
        self.delete_associations_url = \
            "{base}/api/v1/{enterprise_uuid}/delete-group-association/{group_uuid}/".format(
                base=self.url_base,
                enterprise_uuid=self.enterprise_customer.uuid,
                group_uuid=self.test_group.uuid,
            )

        super().setUp()

    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    @responses.activate
    def test_delete_policy_group_association(self):
        """
        Verify that the client method `delete_policy_group_association` works as expected.
        """
        responses.add(
            responses.DELETE,
            url=self.delete_associations_url,
            status=204,
        )
        client = enterprise_access.EnterpriseAccessApiClient(self.user)
        response = client.delete_policy_group_association(self.enterprise_customer.uuid, self.test_group.uuid)
        assert response is True
