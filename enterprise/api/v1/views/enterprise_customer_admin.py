"""
Views for EnterpriseCustomerAdmin model.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404

from enterprise import models
from enterprise.api.v1.serializers import EnterpriseCustomerAdminSerializer


class EnterpriseCustomerAdminPagination(PageNumberPagination):
    """
    Pagination class for EnterpriseCustomerAdmin viewset.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class EnterpriseCustomerAdminViewSet(viewsets.ModelViewSet):
    """
    ViewSet for EnterpriseCustomerAdmin model.
    """
    queryset = models.EnterpriseCustomerAdmin.objects.all()
    serializer_class = EnterpriseCustomerAdminSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = EnterpriseCustomerAdminPagination

    def get_queryset(self):
        """
        Filter queryset to only show records for the user's enterprise customer.
        """
        return models.EnterpriseCustomerAdmin.objects.filter(
            enterprise_customer_user__user_fk=self.request.user
        )

    @action(detail=True, methods=['post'])
    def complete_tour_flow(self, request):
        """
        Add a completed tour flow to the admin's completed_tour_flows.

        Args:
            request: The request object containing the flow_uuid

        Returns:
            Response: A response indicating success or failure

        Example request:
            POST /api/v1/enterprise-customer-admin/{pk}/complete_tour_flow/
            {
                "flow_uuid": "uuid-of-onboarding-flow"
            }
        """
        admin = self.get_object()
        flow_uuid = request.data.get('flow_uuid')

        if not flow_uuid:
            return Response(
                {'error': 'flow_uuid is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            flow = get_object_or_404(models.OnboardingFlow, uuid=flow_uuid)
            admin.completed_tour_flows.add(flow)

            return Response({
                'status': 'success',
                'message': f'Successfully added tour flow {flow.title} to completed flows'
            })

        except models.OnboardingFlow.DoesNotExist:
            return Response(
                {'error': f'OnboardingFlow with uuid {flow_uuid} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
