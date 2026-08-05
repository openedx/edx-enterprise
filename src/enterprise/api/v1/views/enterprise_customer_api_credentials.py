"""
Views for the Enterprise Customer API Credentials.
"""
from edx_rbac.decorators import permission_required
from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import get_application_model
from rest_framework import permissions, status
from rest_framework.response import Response

from enterprise.api.utils import assign_feature_roles, has_api_credentials_enabled, set_application_name_from_user_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)

# Application Model: https://github.com/jazzband/django-oauth-toolkit/blob/master/oauth2_provider/models.py
Application = get_application_model()


class APICredEnabledPermission(permissions.BasePermission):
    """
    Permission that checks to see if the request user matches the user indicated in the request body.
    """

    def has_permission(self, request, view):
        return has_api_credentials_enabled(request.parser_context.get('kwargs', {}).get('enterprise_uuid'))


class APICredentialsViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer-api-credentials`` API endpoint.
    """

    # Verifies the requesting user has the appropriate API permissions
    permission_classes = (permissions.IsAuthenticated, APICredEnabledPermission,)

    def get_queryset(self):
        return Application.objects.filter(user=self.request.user)  # only get current user's record

    def get_serializer_class(self):
        return serializers.EnterpriseCustomerApiCredentialSerializer

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_uuid')
    )
    def create(self, request, *args, **kwargs):
        """
        Creates and returns a new enterprise API credential application record.

        Method: POST

        URL:
            /enterprise/api/v1/enterprise-customer-api-credentials/{enterprise_uuid}

        Returns:
            201 if a new API application credentials was created. If an application already exists for the user, throw
            a 409.
        """
        # Verifies the requesting user is connected to an enterprise that has API credentialing bool set to True
        user = request.user
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
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_uuid')
    )
    def destroy(self, request, *args, **kwargs):
        """
        Removes the enterprise API application credentials for the requesting user.

        Method: DELETE

        URL: /enterprise/api/v1/enterprise-customer-api-credentials/{enterprise_uuid}
        """
        application = Application.objects.filter(user=request.user).first()
        if not application:
            return Response(
                {'detail': 'Application does not exist for requesting user.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        application.delete()
        return Response(status=status.HTTP_200_OK)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_uuid')
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Returns the enterprise API application credentials details for the requesting user.

        Method: GET

        URL: /enterprise/api/v1/enterprise-customer-api-credentials/{enterprise_uuid}
        """
        user_application = Application.objects.get(user=request.user)
        serializer = self.get_serializer(instance=user_application)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_uuid')
    )
    def update(self, request, *args, **kwargs):
        """
        Updates the enterprise API application credentials details for the requesting user.

        Method: PUT

        URL: /enterprise/api/v1/enterprise-customer-api-credentials/{enterprise_uuid}
        """
        # Verifies the requesting user is connected to an enterprise that has API credentialing bool set to True
        user = request.user
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
    permission_classes = (permissions.IsAuthenticated, APICredEnabledPermission,)

    def get_queryset(self):
        return Application.objects.filter(user=self.request.user)  # only get current user's record

    def get_serializer_class(self):
        return serializers.EnterpriseCustomerApiCredentialRegeneratePatchSerializer

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_uuid')
    )
    def update(self, request, *args, **kwargs):
        """
        Regenerates the API application credentials (client ID and secret) for the requesting user. Throws a 404 if the
        user does not yet have any credentials.

        Method: PUT

        URL: /enterprise/api/v1/enterprise-customer-api-credentials/{enterprise_uuid}/regenerate_credentials
        """
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
