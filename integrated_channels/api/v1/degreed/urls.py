"""
    url mappings for integrated_channels/api/v1/degreed/
"""

from rest_framework import routers

from .views import DegreedConfigurationViewSet

app_name = 'degreed'
router = routers.DefaultRouter()  # pylint: disable=invalid-name
router.register(r'configuration', DegreedConfigurationViewSet, basename="configuration")
urlpatterns = router.urls
