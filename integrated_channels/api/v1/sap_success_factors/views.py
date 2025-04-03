"""
Viewsets for integrated_channels/v1/sap_success_factors/
"""
from rest_framework import exceptions, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.exceptions import ClientError
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration

from .serializers import SAPSuccessFactorsConfigSerializer, SAPUserInfoRequestSerializer


class SAPSuccessFactorsConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = SAPSuccessFactorsConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = SAPSuccessFactorsEnterpriseCustomerConfiguration


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def retrieve_additional_userinfo(request):
    """
    Retrieve additional user information from SAP SuccessFactors.
    
    GET params:
        org_id: Organization ID in SAP
        loggedinuserid: ID of the logged-in user
    
    Returns:
        User information retrieved from SAP SuccessFactors.
    """
    serializer = SAPUserInfoRequestSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    org_id = serializer.validated_data['org_id']
    logged_in_user_id = serializer.validated_data['loggedinuserid']
    
    # Find the SAP configuration for this organization
    try:
        # Use the company ID (org_id) to find the right configuration
        enterprise_config = SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.get(
            sapsf_company_id=org_id,
            active=True
        )
    except SAPSuccessFactorsEnterpriseCustomerConfiguration.DoesNotExist:
        return Response(
            {"error": f"No active SAP configuration found for organization ID: {org_id}"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Create the client and retrieve user information
    from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
    client = SAPSuccessFactorsAPIClient(enterprise_config)
    
    try:
        user_data = client.get_user_details(logged_in_user_id)
        
        # Return specifically formatted data to match Auth0's expected structure
        response_data = {
            "email": user_data.get('d', {}).get('email'),
            "given_name": user_data.get('d', {}).get('firstName'),
            "surname": user_data.get('d', {}).get('lastName'),
            "full_data": user_data.get('d', {})
        }
        
        return Response(response_data)
    except ClientError as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
