"""
Tests for the ``integrated_channels`` app.
"""

from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from django.test import Client, TestCase


class TestPushLearnerDataToIntegratedChannel(TestCase):
    """
    Test PushLearnerDataToIntegratedChannel.
    """

    url = reverse('push_learner_data')

    def test_post(self):
        client = Client()
        try:
            client.post(self.url)
            self.fail("Should have raised NotImplementedError")
        except NotImplementedError:
            pass


class TestPushCatalogDataToIntegratedChannel(TestCase):
    """
    Test PushCatalogDataToIntegratedChannel.
    """

    url = reverse('push_catalog_data')

    def test_post(self):
        client = Client()
        try:
            client.post(self.url)
            self.fail("Should have raised NotImplementedError")
        except NotImplementedError:
            pass
