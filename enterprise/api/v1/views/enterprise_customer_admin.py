"""
Views for `EnterpriseCustomerAdmin` model.
"""
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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


class EnterpriseCustomerAdminViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    API views for the ``enterprise-customer-admin`` API endpoint.
    Only allows GET, and PATCH requests.
    """
    queryset = models.EnterpriseCustomerAdmin.objects.all()
    serializer_class = EnterpriseCustomerAdminSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = EnterpriseCustomerAdminPagination

    def get_queryset(self):
        """
        Filter queryset to only show records for the admin user.
        """
        return models.EnterpriseCustomerAdmin.objects.filter(
            enterprise_customer_user__user_fk=self.request.user
        )

    @action(detail=True, methods=['post'])
    def complete_tour_flow(self, request, pk=None):  # pylint: disable=unused-argument
        """
        Add a completed tour flow to the admin's completed_tour_flows.
        POST /api/v1/enterprise-customer-admin/{pk}/complete_tour_flow/

        Request Arguments:
        - ``flow_uuid``: The request object containing the flow_uuid

        Returns: A response indicating success or failure
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

    @action(detail=False, methods=['patch'])
    def dismiss_tour(self, request):
        """
        Update the onboarding_tour_dismissed field for the current admin.
        PATCH /api/v1/enterprise-customer-admin/dismiss_tour/

        Request Arguments:
        - ``dismissed``: Boolean indicating whether the tour should be dismissed (optional, defaults to True)

        Returns: A response indicating success or failure
        """
        admin = self.get_queryset().first()
        if not admin:
            return Response(
                {'error': 'No admin record found for current user'},
                status=status.HTTP_404_NOT_FOUND
            )

        dismissed = request.data.get('dismissed', True)

        if not isinstance(dismissed, bool):
            return Response(
                {'error': 'dismissed must be a boolean value'},
                status=status.HTTP_400_BAD_REQUEST
            )

        admin.onboarding_tour_dismissed = dismissed
        admin.save()

        return Response({
            'status': 'success',
            'message': f'Successfully updated onboarding_tour_dismissed to {dismissed}',
            'onboarding_tour_dismissed': dismissed
        })
