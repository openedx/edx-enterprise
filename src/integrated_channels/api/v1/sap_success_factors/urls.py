"""
    url mappings for integrated_channels/v1/sap_success_factors/
"""

from rest_framework import routers

from .views import SAPSuccessFactorsConfigurationViewSet

app_name = 'sap_success_factors'
router = routers.DefaultRouter()
router.register(r'configuration', SAPSuccessFactorsConfigurationViewSet, basename="configuration")
urlpatterns = router.urls
