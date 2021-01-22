"""
    url mappings for integrated_channels/api/v1/cornerstone/
"""

from rest_framework import routers

from .views import CornerstoneConfigurationViewSet

app_name = 'cornerstone'
router = routers.DefaultRouter()  # pylint: disable=invalid-name
router.register(r'configuration', CornerstoneConfigurationViewSet, basename="configuration")
urlpatterns = router.urls
