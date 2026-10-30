"""
    url mappings for integrated_channels/api/v1/degreed2/
"""

from rest_framework import routers

from .views import Degreed2ConfigurationViewSet

app_name = 'degreed2'
router = routers.DefaultRouter()
router.register(r'configuration', Degreed2ConfigurationViewSet, basename="configuration")
urlpatterns = router.urls
