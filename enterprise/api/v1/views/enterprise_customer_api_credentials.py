"""
Views for the Enterprise Customer API Credentials.
"""
from edx_rbac.decorators import permission_required
from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import get_application_model
from rest_framework import permissions, status
from rest_framework.response import Response

from enterprise.api.utils import (
    assign_feature_roles,
    get_enterprise_customer_from_user_id,
    has_api_credentials_enabled,
    set_application_name_from_user_id,
)
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)

# Application Model: https://github.com/jazzband/django-oauth-toolkit/blob/master/oauth2_provider/models.py
Application = get_application_model()


class APICredentialsViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer-api-credentials`` API endpoint.
    """

    # Verifies the requesting user has the appropriate API permissions
    permission_classes = (permissions.IsAuthenticated,)
    # Changes application's pk to be user's pk
    lookup_field = 'user'

    def get_queryset(self):
        return Application.objects.filter(user=self.request.user)  # only get current user's record

    def get_serializer_class(self):
        return serializers.EnterpriseCustomerApiCredentialSerializer

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id)
    )
    def create(self, request, *args, **kwargs):
        """
        Creates a new API application credentials and returns the created object.

        Method: POST

        URL: /enterprise/api/v1/enterprise_customer_api_credentials/{enterprise_uuid}

        Returns 201 if a new API application credentials was created.
        If an application already exists for the user, throw a 409.
        """

        # Verifies the requesting user is connected to an enterprise that has API credentialing bool set to True
        user = request.user
        enterprise_uuid = kwargs['enterprise_uuid']
        if not enterprise_uuid:
            return Response({'detail': "Invalid enterprise_uuid"}, status=status.HTTP_400_BAD_REQUEST)

        if not has_api_credentials_enabled(enterprise_uuid):
            return Response({'detail': 'Can not access API credential viewset.'}, status=status.HTTP_403_FORBIDDEN)

        # Fetches the application for the user
        # If an application already exists for the user, throw a 409.
        queryset = self.get_queryset().first()
        if queryset:
            return Response({'detail': 'Application exists.'}, status=status.HTTP_409_CONFLICT)

        # Adds the appropriate enterprise related feature roles if they do not already have them
        assign_feature_roles(user)

        application = Application.objects.create(
            name=set_application_name_from_user_id(request.user.id),
            user=request.user,
            authorization_grant_type="client-credentials",
            client_type="confidential",
            client_id=generate_client_id(),
            client_secret=generate_client_secret()
        )
        application.save()

        serializer = self.get_serializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id)
    )
    def destroy(self, request, *args, **kwargs):
        """
        Method: DELETE

        URL: /enterprise/api/v1/enterprise_customer_api_credentials/{enterprise_uuid}
        """
        enterprise_uuid = kwargs['enterprise_uuid']
        if not enterprise_uuid:
            return Response({'detail': "Invalid enterprise_uuid"}, status=status.HTTP_400_BAD_REQUEST)

        if not has_api_credentials_enabled(enterprise_uuid):
            return Response({'detail': 'Can not access API credential viewset.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(self, request, *args, **kwargs)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id)
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Method: GET

        URL: /enterprise/api/v1/enterprise_customer_api_credentials/{enterprise_uuid}
        """
        enterprise_uuid = kwargs['enterprise_uuid']
        if not enterprise_uuid:
            return Response({'detail': "Invalid enterprise_uuid"}, status=status.HTTP_400_BAD_REQUEST)

        if not has_api_credentials_enabled(enterprise_uuid):
            return Response({'detail': 'Can not access API credential viewset.'}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(self, request, *args, **kwargs)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id)
    )
    def update(self, request, *args, **kwargs):
        """
        Method: PUT

        URL: /enterprise/api/v1/enterprise_customer_api_credentials/{enterprise_uuid}
        """
        # Verifies the requesting user is connected to an enterprise that has API credentialing bool set to True
        user = request.user
        enterprise_uuid = kwargs['enterprise_uuid']
        if not enterprise_uuid:
            return Response({'detail': "Invalid enterprise_uuid"}, status=status.HTTP_400_BAD_REQUEST)

        if not has_api_credentials_enabled(enterprise_uuid):
            return Response({'detail': 'Can not access API credential viewset.'}, status=status.HTTP_403_FORBIDDEN)

        queryset = self.get_queryset().first()
        if not queryset:
            return Response({'detail': 'Could not find the Application.'}, status=status.HTTP_404_NOT_FOUND)

        instance = Application.objects.get(user=user)
        expected_fields = {'name', 'client_type', 'redirect_uris', 'authorization_grant_type'}
        # Throw a 400 if any field to update is not a part of the Application model.
        for field in request.data.keys():
            if field not in expected_fields:
                return Response({'detail': f"Invalid field for update: {field}"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class APICredentialsRegenerateViewSet(APICredentialsViewSet):
    """
    API views for the ``enterprise-customer-api-credentials`` API endpoint.
    """

    # Verifies the requesting user has the appropriate API permissions
    permission_classes = (permissions.IsAuthenticated,)
    # Changes application's pk to be user's pk
    lookup_field = 'user'

    def get_queryset(self):
        return Application.objects.filter(user=self.request.user)  # only get current user's record

    def get_serializer_class(self):
        return serializers.EnterpriseCustomerApiCredentialRegeneratePatchSerializer

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id)
    )
    def update(self, request, *args, **kwargs):
        """
        Method: PUT

        URL: /enterprise/api/v1/enterprise_customer_api_credentials/{enterprise_uuid}/regenerate_credentials
        """
        enterprise_uuid = kwargs['enterprise_uuid']

        # Verifies the requesting user is connected to an enterprise that has API credentialing bool set to True
        if not has_api_credentials_enabled(enterprise_uuid):
            return Response({'detail': 'Can not access API credential viewset.'}, status=status.HTTP_403_FORBIDDEN)

        # Fetches the application for the user
        # Throws a 404 if Application record not found
        application = self.get_queryset().first()
        if not application:
            return Response({'detail': 'Could not find the Application.'}, status=status.HTTP_404_NOT_FOUND)

        if 'redirect_uris' not in request.data:
            return Response({'detail': 'Could not update.'}, status=status.HTTP_400_BAD_REQUEST)

        redirect_uris = request.data.get('redirect_uris')
        application.redirect_uris = redirect_uris
        # Calls generate_client_secret and generate_client_id for the user
        application.client_id = generate_client_id()
        application.client_secret = generate_client_secret()
        application.save()

        serializer = self.get_serializer(application)
        return Response(serializer.data, status=status.HTTP_200_OK)
