"""
    url mappings for integrated_channels/v1/sap_success_factors/
"""

from django.urls import path
from rest_framework import routers

from .views import SAPSuccessFactorsConfigurationViewSet, retrieve_additional_userinfo

app_name = 'sap_success_factors'
router = routers.DefaultRouter()
router.register(r'configuration', SAPSuccessFactorsConfigurationViewSet, basename="configuration")
urlpatterns = router.urls + [
    path('retrieve-additional-userinfo/', retrieve_additional_userinfo, name='retrieve-additional-userinfo'),
]
