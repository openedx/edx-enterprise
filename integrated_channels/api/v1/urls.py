"""
URL definitions for v1 Integrated Channel API endpoints.
"""

from django.urls import include, path

from .views import IntegratedChannelHealthCheckView, IntegratedChannelsBaseViewSet

app_name = 'v1'
urlpatterns = [
    path('canvas/', include('integrated_channels.api.v1.canvas.urls')),
    path('moodle/', include('integrated_channels.api.v1.moodle.urls')),
    path('blackboard/', include('integrated_channels.api.v1.blackboard.urls')),
    path('sap_success_factors/', include('integrated_channels.api.v1.sap_success_factors.urls')),
    path('degreed/', include('integrated_channels.api.v1.degreed.urls')),
    path('degreed2/', include('integrated_channels.api.v1.degreed2.urls')),
    path('cornerstone/', include('integrated_channels.api.v1.cornerstone.urls')),
    path('configs/health-check', IntegratedChannelHealthCheckView.as_view(), name='health_check'),
    path('configs/', IntegratedChannelsBaseViewSet.as_view({'get': 'list'}), name='configs'),
    path('logs/', include('integrated_channels.api.v1.logs.urls')),
]
