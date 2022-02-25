"""
Tests for the `integrated_channels` base configuration api.
"""
from unittest import mock
from uuid import uuid4

import ddt
from pytest import mark

from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from test_utils import APITest, factories

ENTERPRISE_ID = str(uuid4())


@ddt.ddt
@mark.django_db
class BaseConfigurationsViewSetTests(APITest):
    """
    Tests for the base integrated channels api REST endpoints
    """

    def setUp(self):
        super().setUp()
        self.set_jwt_cookie(self.client, [(ENTERPRISE_ADMIN_ROLE, ENTERPRISE_ID)])
        self.client.force_authenticate(user=self.user)

        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=ENTERPRISE_ID)

        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        self.customer_configs = set()
        self.customer_configs.add(factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            refresh_token='foobar',
        ).channel_code())
        self.customer_configs.add(factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            refresh_token='foobar',
        ).channel_code())
        self.customer_configs.add(factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        ).channel_code())
        self.customer_configs.add(factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        ).channel_code())
        self.customer_configs.add(factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        ).channel_code())
        self.customer_configs.add(factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        ).channel_code())
        self.customer_configs.add(factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        ).channel_code())

    @mock.patch('enterprise.rules.crum.get_current_request')
    def test_list(self, mock_current_request):
        # Add an extra config to confirm the endpoint only returns configs relating to the customer provided
        extra_customer = factories.EnterpriseCustomerFactory()
        factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=extra_customer,
            refresh_token='foobar',
        )

        mock_current_request.return_value = self.get_request_with_jwt_cookie(
            system_wide_role=ENTERPRISE_ADMIN_ROLE,
            context=self.enterprise_customer.uuid,
        )

        url = reverse('api:v1:configs')
        resp = self.client.get(url + f'?enterprise_customer={str(self.enterprise_customer.uuid)}')

        # There should be 7 total existing configs
        assert len(resp.data) == 7

        remaining_configs = self.customer_configs.copy()
        for config in resp.data:
            remaining_configs -= {config.get('channel_code')}
        assert len(remaining_configs) == 0
