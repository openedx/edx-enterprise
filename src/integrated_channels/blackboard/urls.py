"""
URL definitions for Blackboard API.
"""

from django.urls import path

from integrated_channels.blackboard.views import BlackboardCompleteOAuthView

urlpatterns = [
    path('oauth-complete', BlackboardCompleteOAuthView.as_view(),
         name='blackboard-oauth-complete'
         ),
]
