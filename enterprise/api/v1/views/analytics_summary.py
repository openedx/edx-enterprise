"""
Views for the `ChatGPTResponse` API endpoint.
"""
from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.shortcuts import get_object_or_404

from enterprise.api.utils import (
    generate_prompt_for_learner_engagement_summary,
    generate_prompt_for_learner_progress_summary,
)
from enterprise.api.v1.serializers import AnalyticsSummarySerializer
from enterprise.models import ChatGPTResponse, EnterpriseCustomer


class AnalyticsSummaryView(generics.GenericAPIView):
    """
    API to generate a signed token for an enterprise admin to use Plotly analytics.
    """
    authentication_classes = [JwtAuthentication, SessionAuthentication]
    permission_classes = (IsAuthenticated,)

    http_method_names = ['post']

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, enterprise_uuid: enterprise_uuid
    )
    def post(self, request, enterprise_uuid):
        """
        Generate auth token for plotly.
        """
        role = 'system'
        enterprise_customer = get_object_or_404(EnterpriseCustomer, uuid=enterprise_uuid)

        # Validate payload data
        serializer = AnalyticsSummarySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                data={
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        prompt_data = serializer.data
        learner_engagement_prompt = generate_prompt_for_learner_engagement_summary(prompt_data['learner_engagement'])
        response_data = {
            'learner_engagement': ChatGPTResponse.get_or_create(
                learner_engagement_prompt, role, enterprise_customer, ChatGPTResponse.LEARNER_ENGAGEMENT,
            ),
        }

        if 'learner_progress' in prompt_data:
            learner_progress_prompt = generate_prompt_for_learner_progress_summary(prompt_data['learner_progress'])
            response_data['learner_progress'] = ChatGPTResponse.get_or_create(
                learner_progress_prompt, role, enterprise_customer, ChatGPTResponse.LEARNER_PROGRESS,
            )

        return Response(data=response_data)
