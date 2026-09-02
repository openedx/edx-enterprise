"""
    url mappings for integrated_channels/v1/moodle/
"""

from rest_framework import routers

from .views import MoodleConfigurationViewSet

app_name = 'moodle'
router = routers.DefaultRouter()
router.register(r'configuration', MoodleConfigurationViewSet, basename="configuration")
urlpatterns = router.urls
