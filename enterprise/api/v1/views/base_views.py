"""
Base API views for the enterprise app.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import filters, permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.mixins import CreateModelMixin, UpdateModelMixin

from enterprise.api.filters import UserFilterBackend
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseViewSet:
    """
    Base class for all Enterprise view sets.
    """

    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    def ensure_data_exists(self, request, data, error_message=None):
        """
        Ensure that the wrapped API client's response brings us valid data. If not, raise an error and log it.
        """
        if not data:
            error_message = (
                error_message or "Unable to fetch API response from endpoint '{}'.".format(request.get_full_path())
            )
            LOGGER.error(error_message)
            raise NotFound(error_message)


class EnterpriseWrapperApiViewSet(EnterpriseViewSet, viewsets.ViewSet):
    """
    Base class for attribute and method definitions common to all view sets which wrap external APIs.
    """


class EnterpriseModelViewSet(EnterpriseViewSet):
    """
    Base class for attribute and method definitions common to all view sets.
    """

    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, UserFilterBackend,)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions,)
    USER_ID_FILTER = 'id'


class EnterpriseReadOnlyModelViewSet(EnterpriseModelViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Base class for all read only Enterprise model view sets.
    """


class EnterpriseReadWriteModelViewSet(EnterpriseModelViewSet, viewsets.ModelViewSet):
    """
    Base class for all read/write Enterprise model view sets.
    """

    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions,)


class EnterpriseWriteOnlyModelViewSet(
    EnterpriseModelViewSet,
    CreateModelMixin,
    UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Base class for all write only Enterprise model view sets.
    """

    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions)
