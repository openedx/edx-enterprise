from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import generics, permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK

from django.utils.decorators import method_decorator

from enterprise.api.v1.decorators import require_at_least_one_query_parameter
from enterprise.utils import get_enterprise_customer_or_404
from integrated_channels.api.v1.blackboard.serializers import BlackboardConfigSerializer
from integrated_channels.api.v1.canvas.serializers import CanvasEnterpriseCustomerConfigurationSerializer
from integrated_channels.api.v1.cornerstone.serializers import CornerstoneConfigSerializer
from integrated_channels.api.v1.degreed2.serializers import Degreed2ConfigSerializer
from integrated_channels.api.v1.degreed.serializers import DegreedConfigSerializer
from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.api.v1.moodle.serializers import MoodleConfigSerializer
from integrated_channels.api.v1.sap_success_factors.serializers import SAPSuccessFactorsConfigSerializer
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.client import IntegratedChannelHealthStatus
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from integrated_channels.utils import get_enterprise_client_by_channel_code


class IntegratedChannelsBaseViewSet(viewsets.ViewSet):
    """
    API views for the ``integrated_channels`` base configurations endpoint.
    """
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)

    permission_required = 'enterprise.can_access_admin_dashboard'

    @method_decorator(require_at_least_one_query_parameter('enterprise_customer'))
    # pylint: disable=unused-argument
    def list(self, request, *arg, **kwargs):
        """
        Enterprise Customer's Integrated Channels config list without pagination
        """
        enterprise_customer = get_enterprise_customer_or_404(self.request.query_params.get('enterprise_customer'))
        blackboard_configs = BlackboardEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        blackboard_serializer = BlackboardConfigSerializer(blackboard_configs, many=True)

        canvas_configs = CanvasEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        canvas_serializer = CanvasEnterpriseCustomerConfigurationSerializer(canvas_configs, many=True)

        cornerstone_configs = CornerstoneEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        cornerstone_serializer = CornerstoneConfigSerializer(cornerstone_configs, many=True)

        degreed_configs = DegreedEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        degreed_serializer = DegreedConfigSerializer(degreed_configs, many=True)

        degreed2_configs = Degreed2EnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        degreed2_serializer = Degreed2ConfigSerializer(degreed2_configs, many=True)

        moodle_configs = MoodleEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        moodle_serializer = MoodleConfigSerializer(moodle_configs, many=True)

        sap_configs = SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.filter(
            enterprise_customer=enterprise_customer
        )
        sap_serializer = SAPSuccessFactorsConfigSerializer(sap_configs, many=True)

        response = blackboard_serializer.data + canvas_serializer.data + cornerstone_serializer.data + \
            degreed_serializer.data + degreed2_serializer.data + moodle_serializer.data + sap_serializer.data
        return Response(response)


class IntegratedChannelHealthCheckView(generics.ListAPIView):
    """
        **Use Cases**

            Perform Health Check on user's connection

        **Example Requests**

            GET /config/health-check

        **Query Parameters for GET**

            * channel_code: The channel code of the CanvasEnterpriseCustomerConfiguration
            * uuid: The uuid of the CanvasEnterpriseCustomerConfiguration

        **Supported Channels**
        canvas

        **Response Values**

            * is_healthy: Whether the Canvas connection is healthy
            * health_status: Status code for health status


    """
    renderer_classes = [JSONRenderer, ]

    @method_decorator(require_at_least_one_query_parameter('channel_code'))
    @method_decorator(require_at_least_one_query_parameter('uuid'))
    def get(self, request, *args, **kwargs):
        """
        Enterprise Customer's Integrated Channel health check
        """
        channel_code = request.query_params.get('channel_code').lower()
        uuid = request.query_params.get('uuid')

        # Get enterprise configuration
        config_type = EnterpriseCustomerPluginConfiguration.get_class_by_channel_code(channel_code)
        config = config_type.objects.get(uuid=uuid)
        client_type = get_enterprise_client_by_channel_code(channel_code)
        client = client_type(config)

        health_status = client.health_check()
        is_healthy = health_status == IntegratedChannelHealthStatus.HEALTHY
        payload = {'is_healthy': is_healthy, 'health_status': health_status.value}
        return Response(payload, status=HTTP_200_OK)
