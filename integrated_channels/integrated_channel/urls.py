# -*- coding: utf-8 -*-
"""
URLs for integrated_channel.
"""
from __future__ import absolute_import, unicode_literals

from integrated_channels.integrated_channel.views import (
    PushCatalogDataToIntegratedChannel,
    PushLearnerDataToIntegratedChannel,
)

from django.conf.urls import url

urlpatterns = [
    url(
        r'^integrated_channel/push_catalog_data',
        PushCatalogDataToIntegratedChannel.as_view(),
        name='push_catalog_data'
    ),
    url(
        r'^integrated_channel/push_learner_data',
        PushLearnerDataToIntegratedChannel.as_view(),
        name='push_learner_data'
    ),
]
