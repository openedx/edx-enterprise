"""
URL definitions for integrated_channels API endpoint.
"""

from django.urls import include, path

app_name = 'api'
urlpatterns = [
    path('v1/', include('integrated_channels.api.v1.urls'), name='api')
]
