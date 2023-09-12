"""
Views for the ``enterprise-customer-sso-configuration`` API endpoint.
"""

from edx_rbac.decorators import permission_required
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from django.contrib import auth
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import transaction

from enterprise import models
from enterprise.api.utils import get_enterprise_customer_from_user_id
from enterprise.api.v1 import serializers
from enterprise.logging import getEnterpriseLogger
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerSsoConfiguration, EnterpriseCustomerUser
from enterprise.tasks import send_sso_configured_email
from enterprise.utils import localized_utcnow

User = auth.get_user_model()

LOGGER = getEnterpriseLogger(__name__)

BAD_CUSTOMER_ERROR = 'Must provide valid enterprise customer'
CONFIG_UPDATE_ERROR = 'Error updating SSO configuration record'
CONFIG_CREATE_ERROR = 'Error creating SSO configuration record'


class EnterpriseCustomerInactiveException(Exception):
    """
    Exception raised when an enterprise customer is inactive.
    """


def check_user_part_of_customer(user, enterprise_customer):
    """
    Checks if a user is in an enterprise customer.
    """
    ent_customer = enterprise_customer.enterprise_customer_users.filter(user_id=user.id)
    if ent_customer and not ent_customer.first().active:
        raise EnterpriseCustomerInactiveException
    return ent_customer.exists() or user.is_staff


def get_customer_from_request(request):
    """
    Gets the enterprise customer from the request or the user.
    """
    if customer_uuid := request.query_params.get('enterprise_customer'):
        return customer_uuid
    return get_enterprise_customer_from_user_id(request.user.id)


def fetch_configuration_record(kwargs):
    """
    Fetches the configuration record for the given uuid.
    """
    return EnterpriseCustomerSsoConfiguration.all_objects.filter(pk=kwargs.get('configuration_uuid'))


class EnterpriseCustomerSsoConfigurationViewSet(viewsets.ModelViewSet):
    """
    API views for the ``EnterpriseCustomerSsoConfiguration`` model.
    """
    permission_classes = (permissions.IsAuthenticated,)
    queryset = models.EnterpriseCustomerSsoConfiguration.all_objects.all()

    serializer_class = serializers.EnterpriseCustomerSsoConfiguration

    # ``can_manage_enterprise_orchestration_configs`` maps to the edx operator system wide role. Meaning only operators
    # can complete orchestration record configuration process. The only intended caller for this endpoint is the SSO
    # orchestration api.
    @permission_required(
        'enterprise.can_manage_enterprise_orchestration_configs',
    )
    @action(methods=['post'], detail=True)
    def oauth_orchestration_complete(self, request, configuration_uuid, *args, **kwargs):
        """
        SSO orchestration completion callback. This endpoint is called by the SSO orchestrator when it has completed
        the configuration process.
        """
        # Make sure the config record exists
        sso_configuration_record = self.queryset.filter(pk=configuration_uuid).first()
        if not sso_configuration_record:
            return Response(status=HTTP_404_NOT_FOUND)

        if not sso_configuration_record.submitted_at:
            LOGGER.warning(
                f'SSO configuration record {sso_configuration_record.pk} has received a completion callback but has'
                ' not been marked as submitted.'
            )

        # Send a notification email to the enterprise associated with the configuration record
        send_sso_configured_email.delay(sso_configuration_record.enterprise_customer.uuid)

        # Completing the orchestration process means the configuration record is now configured and can be considered
        # active
        sso_configuration_record.configured_at = localized_utcnow()
        sso_configuration_record.active = True
        sso_configuration_record.save()
        return Response(status=HTTP_200_OK)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_customer_from_request(request)
    )
    def retrieve(self, request, *args, **kwargs):
        sso_configuration_record = fetch_configuration_record(kwargs)
        if not sso_configuration_record:
            return Response(status=HTTP_404_NOT_FOUND)
        # Make sure the requesting user is part of the enterprise customer associated with the configuration record
        # or are a staff member
        config_customer = sso_configuration_record.first().enterprise_customer
        try:
            if not check_user_part_of_customer(request.user, config_customer):
                return Response(status=HTTP_404_NOT_FOUND)
        except EnterpriseCustomerInactiveException:
            return Response(status=HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(sso_configuration_record.first())
        return Response(serializer.data)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_customer_from_request(request)
    )
    def list(self, request, *args, **kwargs):
        list_queryset = self.queryset

        # If the request includes a customer uuid, we require through permissioning that the requesting user is an
        # admin of that customer
        if provided_customer := request.query_params.get('enterprise_customer'):
            enterprise_customer = EnterpriseCustomer.objects.filter(pk=provided_customer)
            list_queryset = list_queryset.filter(enterprise_customer__in=enterprise_customer)

        # For non-staff users, only show the configurations that are connected to enterprise customers
        # that they are associated with
        if not request.user.is_staff:
            ent_customers = EnterpriseCustomer.objects.filter(
                enterprise_customer_users__in=EnterpriseCustomerUser.objects.filter(user_id=request.user.id)
            )
            list_queryset = list_queryset.filter(enterprise_customer__in=ent_customers)

        serializer = self.serializer_class(list_queryset, many=True)
        return Response(serializer.data, status=HTTP_200_OK)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_customer_from_request(request)
    )
    def create(self, request, *args, **kwargs):
        # Force the enterprise customer to be the one associated with the user
        request_data = request.data.dict().copy()
        requesting_user_customer = request_data.get('enterprise_customer')
        if requesting_user_customer:
            try:
                enterprise_customer = EnterpriseCustomer.objects.get(uuid=requesting_user_customer)
            except EnterpriseCustomer.DoesNotExist:
                return Response(status=HTTP_403_FORBIDDEN)
            try:
                if not check_user_part_of_customer(request.user, enterprise_customer):
                    return Response(status=HTTP_403_FORBIDDEN)
            except EnterpriseCustomerInactiveException:
                return Response(status=HTTP_403_FORBIDDEN)
            request_data['enterprise_customer'] = enterprise_customer
        else:
            return Response({'error': BAD_CUSTOMER_ERROR}, status=HTTP_400_BAD_REQUEST)
        try:
            new_record = EnterpriseCustomerSsoConfiguration.objects.create(**request_data)
        except TypeError as e:
            LOGGER.error(f'{CONFIG_CREATE_ERROR}{e}')
            return Response({'error': f'{CONFIG_CREATE_ERROR}{e}'}, status=HTTP_400_BAD_REQUEST)
        return Response({'data': new_record.pk}, status=HTTP_201_CREATED)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_customer_from_request(request)
    )
    def update(self, request, *args, **kwargs):
        sso_configuration_record = fetch_configuration_record(kwargs)
        if not sso_configuration_record:
            return Response(status=HTTP_404_NOT_FOUND)
        # Make sure the requesting user is part of the enterprise customer associated with the configuration record
        # or are a staff member
        config_customer = sso_configuration_record.first().enterprise_customer
        try:
            if not check_user_part_of_customer(request.user, config_customer):
                return Response(status=HTTP_404_NOT_FOUND)
        except EnterpriseCustomerInactiveException:
            return Response(status=HTTP_403_FORBIDDEN)

        # If the request includes a customer uuid, ensure the new customer is valid
        if new_customer := request.data.dict().get('enterprise_customer'):
            try:
                enterprise_customer = EnterpriseCustomer.objects.get(uuid=new_customer)
            except EnterpriseCustomer.DoesNotExist:
                return Response(status=HTTP_403_FORBIDDEN)
            try:
                if not check_user_part_of_customer(request.user, enterprise_customer):
                    return Response(status=HTTP_403_FORBIDDEN)
            except EnterpriseCustomerInactiveException:
                return Response(status=HTTP_403_FORBIDDEN)
        try:
            with transaction.atomic():
                sso_configuration_record.update(**request.data.dict())
        except (TypeError, FieldDoesNotExist, ValidationError) as e:
            LOGGER.error(f'{CONFIG_UPDATE_ERROR}{e}')
            return Response({'error': f'{CONFIG_UPDATE_ERROR}{e}'}, status=HTTP_400_BAD_REQUEST)
        serializer = self.serializer_class(sso_configuration_record.first())
        return Response(serializer.data, status=HTTP_200_OK)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_customer_from_request(request)
    )
    def destroy(self, request, *args, **kwargs):
        sso_configuration_record = fetch_configuration_record(kwargs)
        if not sso_configuration_record:
            return Response(status=HTTP_404_NOT_FOUND)
        try:
            if not check_user_part_of_customer(request.user, sso_configuration_record.first().enterprise_customer):
                return Response(status=HTTP_404_NOT_FOUND)
        except EnterpriseCustomerInactiveException:
            return Response(status=HTTP_403_FORBIDDEN)
        sso_configuration_record.update(is_removed=True)
        return Response(status=HTTP_200_OK)
