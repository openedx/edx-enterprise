"""
URL definitions for integrated_channels log api version 1 endpoint.
"""

from django.urls import re_path

from . import views

app_name = 'logs'

urlpatterns = [
    re_path(
        r'content_sync_status/(?P<enterprise_customer_uuid>[A-Za-z0-9-]+)/(?P<integrated_channel_code>[\w]+)/(?P<plugin_configuration_id>[\d]+)/?$',
        views.ContentSyncStatusViewSet.as_view({'get': 'list'}),
        name='content_sync_status_logs'
    ),
    re_path(
        r'learner_sync_status/(?P<enterprise_customer_uuid>[A-Za-z0-9-]+)/(?P<integrated_channel_code>[\w]+)/(?P<plugin_configuration_id>[\d]+)/?$',
        views.LearnerSyncStatusViewSet.as_view({'get': 'list'}),
        name='learner_sync_status_logs'
    ),
]
