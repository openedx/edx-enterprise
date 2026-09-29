"""
    url mappings for integrated_channels/v1/blackboard/
"""

from rest_framework import routers

from .views import BlackboardConfigurationViewSet, BlackboardGlobalConfigurationViewSet

app_name = 'blackboard'
router = routers.DefaultRouter()
router.register(r'configuration', BlackboardConfigurationViewSet, basename="configuration")
router.register(r'global-configuration', BlackboardGlobalConfigurationViewSet, basename="global-configuration")
urlpatterns = router.urls
