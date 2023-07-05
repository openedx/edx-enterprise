"""
Views for Plotly auth.
"""

from time import time

import jwt
from edx_rbac.decorators import permission_required
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.http import JsonResponse


class PlotlyAuthView(generics.GenericAPIView):
    """
    API to generate a signed token for an enterprise admin to use Plotly analytics.
    """
    permission_classes = (IsAuthenticated,)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, enterprise_uuid: enterprise_uuid
    )
    def get(self, request, enterprise_uuid):
        """
        Generate auth token for plotly.
        """
        # This is a new secret key and will be only shared between LMS and our Plotly server.
        secret_key = settings.ENTERPRISE_PLOTLY_SECRET

        now = int(time())
        expires_in = 3600  # time in seconds after which token will be expired
        exp = now + expires_in

        CLAIMS = {
            "exp": exp,
            "iat": now
        }

        jwt_payload = dict({
            'enterprise_uuid': enterprise_uuid,
        }, **CLAIMS)

        token = jwt.encode(jwt_payload, secret_key, algorithm='HS512')
        json_payload = {'token': token}
        return JsonResponse(json_payload)
