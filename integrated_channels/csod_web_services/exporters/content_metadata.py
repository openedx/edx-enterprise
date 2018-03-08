# -*- coding: utf-8 -*-
"""
Content metadata exporter for Cornerstone.
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter


LOGGER = getLogger(__name__)


class CSODWebServicesContentMetadataExporter(ContentMetadataExporter):  # pylint: disable=abstract-method
    """
    Cornerstone implementation of ContentMetadataExporter.
    """

    DATA_TRANSFORM_MAPPING = {}
