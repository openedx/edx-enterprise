"""
Views containing APIs for cornerstone integrated channel
"""

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import generics, permissions, renderers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from enterprise.api.throttles import ServiceUserThrottle
from enterprise.utils import get_enterprise_customer, get_enterprise_worker_user, get_oauth2authentication_class
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration


class BaseViewSet(generics.ListAPIView):
    """
    Base class for all Cornerstone view sets.
    """
    permission_classes = (permissions.IsAuthenticated,)

    OAuth2Authentication = get_oauth2authentication_class()
    if OAuth2Authentication is not None:
        authentication_classes = (JwtAuthentication, OAuth2Authentication, SessionAuthentication,)
    else:
        authentication_classes = (JwtAuthentication, SessionAuthentication,)

    throttle_classes = (ServiceUserThrottle,)
    renderer_classes = [renderers.JSONRenderer]


class CornerstoneCoursesUpdates(BaseViewSet):
    """
        **Use Cases**

            Get a list of courses that need updated to share on cornerstone filtered by an enterprise customer.

        **Example Requests**

            GET /cornerstone/course-updates?ciid={customer_uuid}

        **Query Parameters for GET**

            * ciid: Filters the result to courses available in catalogs corresponding to the
              given ciid where value of ciid should be uuid of any enterprise customer.

        **Response Values**

            If the request for information about the course updates is successful, an HTTP 200 "OK" response
            is returned.

            The HTTP 200 response has the following values.

            * JSON response with a list of the course objects. Each course object has these fields

                * ID: Unique Course id.

                * Title: Title of course.

                * Description: Course overview.

                * URL: URL where user is redirected to.

                * Thumbnail: Url of the course thumbnail image.

                * IsActive: Boolean value indicating if course is active and available.

                * LastModifiedUTC: Time of the last modification made.

                * Duration: Course duration.

                * Partners: List of organizations that are course owners.

                * Languages: List of available languages for a course.

                * Subjects: List of subjects for course.

            If the user is not logged in, a 401 error is returned.

            If the user is not global staff, a 403 error is returned.

            If ciid parameter is not provided, a 400 error is returned.

            If the specified ciid is not valid or any of registered enterprise customers
            a 404 error is returned.

            If the specified enterprise does not have course catalog an HTTP 200 "OK" response is returned with an
            empty result.
    """

    def get(self, request, *args, **kwargs):
        enterprise_customer_uuid = request.GET.get('ciid')
        if not enterprise_customer_uuid:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": (
                        u"Cornerstone course list API expects ciid parameter."
                    )
                })

        enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
        if not enterprise_customer:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data={
                    "message": (
                        u"No enterprise data found for given ciid."
                    )
                })

        worker_user = get_enterprise_worker_user()
        enterprise_config = CornerstoneEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer=enterprise_customer
        )
        exporter = enterprise_config.get_content_metadata_exporter(worker_user)
        transmitter = enterprise_config.get_content_metadata_transmitter()
        data = transmitter.transmit(*exporter.export())
        return Response(data)


class CornerstoneCoursesListView(BaseViewSet):
    """
        **Use Cases**

            Get a list of all catalog courses to share on cornerstone filtered by an enterprise customer.

        **Example Requests**

            GET /cornerstone/course-list?ciid={customer_uuid}

        **Query Parameters for GET**

            * ciid: Filters the result to courses available in catalogs corresponding to the
              given ciid where value of ciid should be uuid of any enterprise customer.

        **Response Values**

            If the request for information about the course list is successful, an HTTP 200 "OK" response
            is returned.

            The HTTP 200 response has the following values.

            * JSON response with a list of the course objects. Each course object has these fields

                * ID: Unique Course id.

                * Title: Title of course.

                * Description: Course overview.

                * URL: URL where user is redirected to.

                * Thumbnail: Url of the course thumbnail image.

                * IsActive: Boolean value indicating if course is active and available.

                * LastModifiedUTC: Time of the last modification made.

                * Duration: Course duration.

                * Partners: List of organizations that are course owners.

                * Languages: List of available languages for a course.

                * Subjects: List of subjects for course.

            If the user is not logged in, a 401 error is returned.

            If the user is not global staff, a 403 error is returned.

            If ciid parameter is not provided, a 400 error is returned.

            If the specified ciid is not valid or any of registered enterprise customers
            a 404 error is returned.

            If the specified enterprise does not have course catalog an HTTP 200 "OK" response is returned with an
            empty result.

    """

    def get(self, request, *args, **kwargs):
        enterprise_customer_uuid = request.GET.get('ciid')
        if not enterprise_customer_uuid:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    "message": (
                        u"Cornerstone course list API expects ciid parameter."
                    )
                })

        enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
        if not enterprise_customer:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data={
                    "message": (
                        u"No enterprise data found for given ciid."
                    )
                })

        worker_user = get_enterprise_worker_user()
        enterprise_config = CornerstoneEnterpriseCustomerConfiguration.objects.get(
            enterprise_customer=enterprise_customer
        )
        exporter = enterprise_config.get_content_metadata_exporter(worker_user)
        transmitter = enterprise_config.get_content_metadata_transmitter()
        data = transmitter.transmit(*exporter.export_force_all_catalogs())
        return Response(data)
