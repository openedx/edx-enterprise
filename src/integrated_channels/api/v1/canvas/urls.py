"""
URL definitions for integrated_channels/canvas API version 1.
"""

from rest_framework import routers

from .views import CanvasConfigurationViewSet

app_name = 'canvas'
router = routers.DefaultRouter()
router.register(r'configuration', CanvasConfigurationViewSet, basename="configuration")
urlpatterns = router.urls
