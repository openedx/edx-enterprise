"""
Views for the ``sap-success-factors`` API endpoint.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError

from enterprise.api.v1.serializers import EnterpriseSapSfUserInfoRequestSerializer
from enterprise.logging import getEnterpriseLogger
from enterprise.models import EnterpriseCustomer
from enterprise.utils import get_user_details

LOGGER = getEnterpriseLogger(__name__)


class SAPSuccessFactorsViewSet(viewsets.ViewSet):
    """
    API views for SAP SuccessFactors SSO operations.
    
    Provides endpoints for retrieving SAP SuccessFactors SSO user details.
    """
    permission_classes = (IsAuthenticated,)
    
    @action(detail=False, methods=['get'])
    def user_details(self, request):
        """
        Retrieve SAP SuccessFactors SSO user details.
        
        Query Parameters:
            * org_id: ID of the organization to retrieve Enterprise Customer
            * logged_in_user_id: ID of the user to get details for
            
        Returns:
            Response with SAP SuccessFactors SSO user details
        """
        serializer = EnterpriseSapSfUserInfoRequestSerializer(data=request.query_params)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        org_id = serializer.validated_data['org_id']
        logged_in_user_id = serializer.validated_data['logged_in_user_id']
        
        try:
            # Get Enterprise Customer by org_id
            enterprise_customer = EnterpriseCustomer.active_customers.get(auth_org_id=org_id)
            
            user_details = get_user_details(enterprise_customer, logged_in_user_id)
            
            if not user_details:
                return Response(
                    {'error': 'SAP SuccessFactors SSO user details not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            return Response(user_details, status=status.HTTP_200_OK)
            
        except EnterpriseCustomer.DoesNotExist:
            return Response(
                {'error': f'Enterprise customer not found for org_id: {org_id}'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            ) 